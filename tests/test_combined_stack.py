"""Public selection with bounded real transport, synthetic provider and retained prior output."""

import hashlib
import json
import threading
import time
from contextlib import contextmanager, suppress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from logo_maker import pipeline, render
from logo_maker.jev.client import JevClient, JevError
from logo_maker.sampling import Budget, SamplingLimit


@contextmanager
def provider(monkeypatch, respond):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            status, response = respond(body)
            raw = json.dumps(response).encode()
            self.send_response(status)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            with suppress(BrokenPipeError):
                self.wfile.write(raw)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "synthetic-provider-secret")
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)


def prepared_run(tmp_path, monkeypatch):
    from test_eligibility import finalize_logo

    logo, cid = finalize_logo(tmp_path / "logo")
    monkeypatch.setattr(render, "machine_context", lambda *a: {})
    prior = {
        logo.ideation / "winner.json": b'{"winner":"approved prior"}',
        logo.exports / "hero-transparent.png": b"approved prior exports",
        logo.root / "floor/hero-transparent.png": b"approved improvement floor",
    }
    for path, data in prior.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return logo, cid, prior


@pytest.mark.parametrize(
    "failure", ["provider_error", "missing_usage", "stale_inputs", "overall_rejection"]
)
def test_combined_selection_keeps_errors_costs_and_eligibility_independent(
    tmp_path, monkeypatch, failure
):
    logo, cid, prior = prepared_run(tmp_path, monkeypatch)
    candidate = logo.concept(cid) / "final.png"
    if failure == "overall_rejection":
        (logo.qa / "owner-feedback.json").write_text(
            json.dumps(
                [
                    {
                        "concept": cid,
                        "candidate_sha256": hashlib.sha256(candidate.read_bytes()).hexdigest(),
                        "brief_sha256": hashlib.sha256(logo.brief.read_bytes()).hexdigest(),
                        "overall": "fail",
                        "statement": "Explicit synthetic overall rejection; dimensional labels unknown.",
                    }
                ]
            )
        )
    changed = False

    def respond(body):
        nonlocal changed
        craft = "form_finish" in body["questions"]
        if failure == "provider_error" and craft:
            return 400, {"error": "synthetic craft provider failure"}
        if failure == "stale_inputs" and craft and not changed:
            motif = logo.concept(cid) / "motif.svg"
            motif.write_text(motif.read_text() + "\n<!-- concurrent input edit -->\n")
            changed = True
        response = {"answers": {key: {"noul": 0.9} for key in body["questions"]}}
        if failure != "missing_usage":
            response["usage"] = {"input_tokens": 20, "output_tokens": 3, "cost": 0.001}
        return 200, response

    with provider(monkeypatch, respond) as url:
        client = JevClient(logo)
        client.url = url
        # Allow the complete isolated-worker transport chain to start on loaded CI hosts.
        budget = Budget(wall_seconds=120)
        if failure == "missing_usage":
            assert pipeline.finalize(logo, client, budget=budget) == cid
        else:
            expected = JevError if failure == "provider_error" else pipeline.AuthoringNeeded
            with pytest.raises(expected):
                pipeline.finalize(logo, client, budget=budget)
    records = [json.loads(path.read_text()) for path in (logo.qa / "jev/requests").glob("*.json")]
    usage = json.loads(logo.run_json.read_text())["jev"]
    assert usage["requests"] == len(records)
    assert all(record["status"] != "submission_pending" for record in records)
    if failure in {"provider_error", "missing_usage"}:
        assert usage["cost_usd"] is None
        assert usage["unpriced_requests"] > 0
    if failure == "provider_error":
        assert any(
            record["status"] == "api_error" and record["assets_status"] == "ready"
            for record in records
        )
    if failure == "overall_rejection":
        row = json.loads((logo.qa / "eligibility.jsonl").read_text().splitlines()[-1])
        assert row["decision_basis"] == "owner_rejection"
        assert row["fit"]["appearance"] == "pass"
        assert "craftsmanship" not in row["owner_feedback"][0]
    for path, data in prior.items():
        if failure == "missing_usage" and path.name == "winner.json":
            continue
        assert path.read_bytes() == data


def test_provider_timeout_keeps_pending_attempt_unknown_and_prior_output(tmp_path, monkeypatch):
    from logo_maker import owned_process

    logo, _, prior = prepared_run(tmp_path, monkeypatch)
    reached = threading.Event()
    release = threading.Event()
    phase_started = []
    original = owned_process.run

    def bounded_post(*args, **kwargs):
        if kwargs.get("label") == "Jev post":
            # Bound the actual transport phase, after source/brief/image preparation.
            # Only shorten the shared deadline; never replace it with a fresh budget.
            phase_started.append(time.monotonic())
            budget = kwargs["budget"]
            budget.deadline = min(budget.deadline, phase_started[-1] + 4)
        return original(*args, **kwargs)

    monkeypatch.setattr(owned_process, "run", bounded_post)

    def respond(body):
        reached.set()
        release.wait(12)
        return 200, {"answers": {key: {"noul": 0.9} for key in body["questions"]}}

    try:
        with provider(monkeypatch, respond) as url:
            client = JevClient(logo)
            client.url = url
            with pytest.raises(SamplingLimit, match="time_limit"):
                pipeline.finalize(logo, client, budget=Budget(wall_seconds=60))
    finally:
        release.set()
    assert reached.is_set(), "timeout must reach the actual owned provider worker"
    assert len(phase_started) == 1
    assert time.monotonic() - phase_started[0] < 8
    records = [json.loads(path.read_text()) for path in (logo.qa / "jev/requests").glob("*.json")]
    assert len(records) == 1
    assert records[0]["status"] == "submission_pending"
    assert records[0]["usage"]["cost"] is None
    assert records[0]["assets_status"] == "ready"
    for asset in records[0]["assets"].values():
        retained = logo.qa / f"jev/assets/{asset['sha256']}.{asset['format']}"
        assert hashlib.sha256(retained.read_bytes()).hexdigest() == asset["sha256"]
    usage = json.loads(logo.run_json.read_text())["jev"]
    assert usage["requests"] == 1
    assert usage["unpriced_requests"] == 1
    assert usage["cost_usd"] is None
    assert all(path.read_bytes() == data for path, data in prior.items())
