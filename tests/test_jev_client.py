"""Jev client: transport selection, retry, request splitting, and log stripping.

Offline: HTTP is stubbed at the httpx boundary; only `JevError` paths,
backoff classification, and on-disk redaction are exercised.
"""

from __future__ import annotations

import base64
import io
import json
import os

import pytest
from PIL import Image as _PILImage

from logo_maker.jev.client import Image, JevClient, JevError, _load_image, is_retryable
from logo_maker.paths import LogoDir


class FakeResponse:
    def __init__(self, status: int, payload: dict, headers: dict | None = None):
        self.status_code = status
        self._payload = payload
        self.headers = headers or {}
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


def ok_response(questions):
    answers = {}
    for qid, q in questions.items():
        t = q["type"]
        if t == "noul":
            answers[qid] = {"type": "noul", "noul": 0.9}
        elif t == "choice":
            first = next(iter(q["criteria"]))
            answers[qid] = {
                "type": "choice",
                "choice": first,
                "confidence": 0.8,
                "probabilities": {first: 1.0},
            }
        else:
            answers[qid] = {
                "type": "score",
                "score": 2.0,
                "confidence": 0.6,
                "legend": {"0": "a", "1": "b"},
                "probabilities": {"0": 0.5, "1": 0.5},
            }
    return {"model": "x", "answers": answers, "usage": {"input_tokens": 10, "output_tokens": 2}}


def make_client(tmp_path, monkeypatch, script: list):
    monkeypatch.setenv("OPENROUTER_API_KEY", "dummy")
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    logo = LogoDir(tmp_path / "logo")
    client = JevClient(logo, concurrency=2)
    calls: list[dict] = []

    def fake_post(url, json=None, headers=None):
        calls.append({"url": url, "json": json, "headers": headers})
        item = script[min(len(calls) - 1, len(script) - 1)]
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(client._http, "post", fake_post)
    monkeypatch.setattr("logo_maker.jev.client.time.sleep", lambda s: None)
    return client, calls


def test_missing_keys_names_both_vars(tmp_path, monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(JevError, match=r"TYPESAFE_API_KEY.*OPENROUTER_API_KEY"):
        JevClient(LogoDir(tmp_path / "logo"))


def test_mixed_image_dimensions_preserve_translucent_source_pixels(tmp_path, monkeypatch):
    from logo_maker.jev.questions import fit_questions

    client, calls = make_client(
        tmp_path,
        monkeypatch,
        [FakeResponse(200, ok_response({"symbol": fit_questions()["symbol"]}))],
    )
    small, large = tmp_path / "small.png", tmp_path / "large.png"
    _PILImage.new("RGBA", (280, 280), (20, 40, 60, 128)).save(small)
    _PILImage.new("RGBA", (400, 400), (0, 0, 0, 0)).save(large)
    client.ask(
        {"candidate": Image(small), "context": Image(large)},
        {"symbol": fit_questions()["symbol"]},
        label="pixel-preservation",
    )
    request = calls[0]["json"]
    encoded = request["assets"][request["state"]["candidate"]]
    actual = _PILImage.open(io.BytesIO(base64.b64decode(encoded["data_base64"])))
    assert actual.getpixel((200, 200)) == (20, 40, 60, 128)


def test_is_retryable():
    for status in (429, 502, 503, 504, 529):
        assert is_retryable(status)
    for status in (400, 401, 404, 422):
        assert not is_retryable(status)


def test_retry_then_success(tmp_path, monkeypatch):
    script = [
        FakeResponse(429, {"error": "slow"}),
        FakeResponse(503, {"error": "busy"}),
        FakeResponse(200, ok_response({"q": {"type": "noul"}})),
    ]
    client, calls = make_client(tmp_path, monkeypatch, script)
    answers = client.ask({"t": "x"}, {"q": {"type": "noul"}}, label="probe")
    assert answers["q"]["noul"] == 0.9
    assert len(calls) == 3


def test_retry_exhausted_raises(tmp_path, monkeypatch):
    script = [FakeResponse(503, {"error": "busy"})] * 6
    client, _ = make_client(tmp_path, monkeypatch, script)
    with pytest.raises(JevError, match="6 tries"):
        client.ask({"t": "x"}, {"q": {"type": "noul"}}, label="probe")


def test_bad_request_raises_with_body(tmp_path, monkeypatch):
    script = [FakeResponse(400, {"detail": "assets: image too large"})]
    client, _ = make_client(tmp_path, monkeypatch, script)
    with pytest.raises(JevError, match="image too large"):
        client.ask({"t": "x"}, {"q": {"type": "noul"}}, label="probe")


def test_network_error_retries_then_raises(tmp_path, monkeypatch):
    import httpx

    script = [httpx.ConnectError("down")]
    client, _ = make_client(tmp_path, monkeypatch, script)
    with pytest.raises(JevError, match="6 tries"):
        client.ask({"t": "x"}, {"q": {"type": "noul"}}, label="probe")


def test_splitting_caps_request_size(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch, [FakeResponse(200, {"pending": True})])
    seen: list[int] = []

    def counting_post(url, json=None, headers=None):
        assert json is not None
        seen.append(len(json["questions"]))
        return FakeResponse(200, ok_response(json["questions"]))

    monkeypatch.setattr(client._http, "post", counting_post)
    questions = {f"q{i}": {"type": "noul"} for i in range(130)}
    answers = client.ask({"t": "x"}, questions, label="big")
    assert sorted(answers) == sorted(questions)
    assert seen == [60, 60, 10]


def test_logging_strips_base64_and_records_usage(tmp_path, monkeypatch):
    img = tmp_path / "mark.png"
    _PILImage.new("RGB", (600, 400), (30, 74, 122)).save(img, "PNG")
    script = [
        FakeResponse(
            200,
            ok_response({"readable": {"type": "noul", "criteria": {"true": "x", "false": "y"}}}),
        )
    ]
    client, _ = make_client(tmp_path, monkeypatch, script)
    answers = client.ask(
        {"logo": Image(img)},
        {
            "readable": {
                "type": "noul",
                "instructions": "Readable?",
                "criteria": {"true": "x", "false": "y"},
            }
        },
        label="preview mark",
    )
    assert answers["readable"]["noul"] == 0.9
    logo = client.logo
    assert logo is not None
    req_files = sorted((logo.qa / "jev" / "requests").glob("*.json"))
    assert len(req_files) == 1
    record = json.loads(req_files[0].read_text())
    blob = json.dumps(record)
    assert "base64" not in blob.lower()
    assert record["assets"]
    for ref, meta in record["assets"].items():
        assert meta["sha256"]
        assert meta["bytes"] > 0
        stored = logo.qa / "jev" / "assets" / f"{meta['sha256']}.{meta['format']}"
        assert stored.is_file()
        assert stored.stat().st_size == meta["bytes"]
        assert ref in json.dumps(record["state"])
    lines = (logo.qa / "jev" / "answers.jsonl").read_text().strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["label"] == "preview mark"
    run = json.loads((logo.root / "run.json").read_text())
    assert run["jev"]["requests"] == 1
    assert run["jev"]["input_tokens"] == 10


def test_multi_image_request_shares_dimensions(tmp_path, monkeypatch):
    big = tmp_path / "big.png"
    small = tmp_path / "small.png"
    _PILImage.new("RGB", (640, 480), (10, 20, 30)).save(big, "PNG")
    _PILImage.new("RGB", (64, 64), (200, 30, 30)).save(small, "PNG")
    sent: dict = {}

    def capture_post(url, json=None, headers=None):
        assert json is not None
        sent.update(json["assets"])
        return FakeResponse(200, ok_response({"q": {"type": "noul"}}))

    client, _ = make_client(tmp_path, monkeypatch, [FakeResponse(200, {})])
    monkeypatch.setattr(client._http, "post", capture_post)
    client.ask({"a": Image(big), "b": Image(small)}, {"q": {"type": "noul"}}, label="two")
    sizes = set()
    for asset in sent.values():
        raw = base64.b64decode(asset["data_base64"])
        sizes.add(_PILImage.open(io.BytesIO(raw)).size)
        assert asset["format"] == "png"
    assert len(sizes) == 1


def test_ask_many_collects_failures(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch, [])
    monkeypatch.setattr(
        client,
        "_send_one",
        lambda s, q, label: (
            (_ for _ in ()).throw(JevError("nope")) if "bad" in label else {"q": {"type": "noul"}}
        ),
    )
    with pytest.raises(JevError) as exc:
        client.ask_many(
            [
                ({"t": 1}, {"q": {"type": "noul"}}, "good"),
                ({"t": 2}, {"q": {"type": "noul"}}, "bad-one"),
                ({"t": 3}, {"q": {"type": "noul"}}, "bad-two"),
            ]
        )
    assert "bad-one" in str(exc.value)
    assert "bad-two" in str(exc.value)


def test_direct_typesafe_transport(tmp_path, monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "ts-key")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    client = JevClient(LogoDir(tmp_path / "logo"))
    assert "api.typesafe.ai" in client.url
    assert client.model == "jev-1.14"

    def fake_post(url, json=None, headers=None):
        assert headers is not None
        assert "TypeSafe-Danger-Zone-Images" not in headers
        return FakeResponse(
            200,
            {
                "model": "jev-1.14",
                "answers": {"q": {"type": "noul", "noul": 0.2}},
                "usage": {"input_tokens": 100, "output_tokens": 5},
            },
        )

    monkeypatch.setattr(client._http, "post", fake_post)
    answers = client.ask({"t": "x"}, {"q": {"type": "noul"}}, label="direct")
    assert answers["q"]["noul"] == 0.2
    assert client.logo is not None
    run = json.loads((client.logo.root / "run.json").read_text())
    assert run["jev"]["cost_usd"] == round(100 * 42e-9, 6)


def test_openrouter_prefers_typesafe_key(tmp_path, monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "ts")
    monkeypatch.setenv("OPENROUTER_API_KEY", "or")
    assert JevClient(LogoDir(tmp_path)).url == "https://api.typesafe.ai/v1/systemone"
    assert os.environ["OPENROUTER_API_KEY"] == "or"


def test_small_image_upscaled_to_api_floor(tmp_path):
    tiny = tmp_path / "tiny.png"
    _PILImage.new("RGB", (100, 60), (10, 20, 30)).save(tiny, "PNG")
    im, fmt = _load_image(tiny)
    assert min(im.size) >= 280
    assert fmt == "png"
