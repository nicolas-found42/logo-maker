"""Slow image persistence must not serialize independent budgeted requests."""

import base64
import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image as PillowImage

from logo_maker import owned_process
from logo_maker.jev import client as client_module
from logo_maker.jev.client import Image, JevClient
from logo_maker.paths import LogoDir
from logo_maker.sampling import Budget


def test_budgeted_image_requests_enter_slow_asset_storage_concurrently(tmp_path, monkeypatch):
    from test_combined_stack import provider

    entered = tmp_path / "entered"
    entered.mkdir()
    release = tmp_path / "release"
    worker = tmp_path / "slow_asset_worker.py"
    # Inject only the IO stall; transport, persistence, ownership and cleanup remain real.
    worker.write_text(
        "import json, runpy, sys, time\n"
        "from pathlib import Path\n"
        f"sys.path.insert(0, {str(Path(client_module.__file__).resolve().parents[2])!r})\n"
        "from logo_maker.jev import client\n"
        f"entered = Path({str(entered)!r})\n"
        f"release = Path({str(release)!r})\n"
        "original = client._finish_asset_storage\n"
        "def store(logo, assets, request_path):\n"
        "    record = json.loads(request_path.read_text())\n"
        "    if record['status'] == 'submission_pending':\n"
        "        (entered / request_path.name).touch()\n"
        "        while not release.exists():\n"
        "            time.sleep(0.01)\n"
        "    return original(logo, assets, request_path)\n"
        "client._finish_asset_storage = store\n"
        "runpy.run_module('logo_maker.jev.worker', run_name='__main__')\n"
    )
    original_run = owned_process.run

    def run(command, **kwargs):
        if command[1:] == ["-m", "logo_maker.jev.worker"]:
            command = [command[0], str(worker)]
        return original_run(command, **kwargs)

    monkeypatch.setattr(owned_process, "run", run)
    logo = LogoDir(tmp_path / "logo")
    image = tmp_path / "image.png"
    PillowImage.new("RGBA", (320, 320), (36, 88, 70, 255)).save(image)
    dispatched = []

    def respond(body):
        records = [json.loads(p.read_text()) for p in (logo.qa / "jev/requests").glob("*.json")]
        record = next(r for r in records if r["state"]["job"] == body["state"]["job"])
        assert record["assets_status"] == "ready"
        for ref, asset in body["assets"].items():
            data = base64.b64decode(asset["data_base64"])
            digest = hashlib.sha256(data).hexdigest()
            assert record["assets"][ref]["sha256"] == digest
            assert (logo.qa / f"jev/assets/{digest}.{asset['format']}").read_bytes() == data
        dispatched.append(body["state"]["job"])
        return 200, {
            "answers": {"ready": {"type": "noul", "noul": 0.9}},
            "usage": {"input_tokens": 10, "output_tokens": 2, "cost": 0.001},
        }

    with provider(monkeypatch, respond) as url:
        client = JevClient(logo, concurrency=4)
        client.url = url
        budgeted = client.with_budget(Budget(wall_seconds=30))
        jobs = [
            ({"job": i, "image": Image(image)}, {"ready": {"type": "noul"}}, f"parallel-{i}")
            for i in range(4)
        ]
        with ThreadPoolExecutor(max_workers=1) as coordinator:
            result = coordinator.submit(budgeted.ask_many, jobs)
            try:
                deadline = time.monotonic() + 10
                while len(list(entered.iterdir())) < len(jobs) and time.monotonic() < deadline:
                    time.sleep(0.01)
                assert len(list(entered.iterdir())) == len(jobs), (
                    "one slow asset store prevented independent requests from starting persistence"
                )
                assert not dispatched, "provider dispatched before its exact assets were retained"
            finally:
                release.touch()
            answers = result.result(timeout=20)
    assert answers == [{"ready": {"type": "noul", "noul": 0.9}}] * len(jobs)
    assert sorted(dispatched) == list(range(len(jobs)))
    records = [json.loads(p.read_text()) for p in (logo.qa / "jev/requests").glob("*.json")]
    assert {r["seq"] for r in records} == {1, 2, 3, 4}
    assert all(r["assets_status"] == "ready" for r in records)
    lines = [json.loads(line) for line in (logo.qa / "jev/answers.jsonl").read_text().splitlines()]
    assert len(lines) == 8
    assert all(sum(row["seq"] == seq for row in lines) == 2 for seq in range(1, 5))
    usage = json.loads(logo.run_json.read_text())["jev"]
    assert usage["requests"] == 4
    assert usage["input_tokens"] == 40
    assert usage["output_tokens"] == 8
    assert abs(usage["cost_usd"] - 0.004) < 0.000001
