"""Real session cleanup under slow or failed process-state inspection."""

import os
import signal
import subprocess
import sys
import time

import pytest

from logo_maker import owned_process
from logo_maker.sampling import Budget, SamplingLimit


@pytest.mark.parametrize(
    "inspection", ["slow_valid", "failed", "invalid", "invalid_stubborn", "wait_failure"]
)
def test_owned_timeout_inspection_is_bounded_and_reaps_worker(tmp_path, monkeypatch, inspection):
    original_killpg = os.killpg
    original_run = subprocess.run
    original_popen = subprocess.Popen
    workers = []
    marker = tmp_path / "worker-started"

    def popen(*args, **kwargs):
        worker = original_popen(*args, **kwargs)
        if kwargs.get("start_new_session"):
            workers.append(worker)
            if inspection == "wait_failure":

                def failed_wait(timeout=None):
                    raise subprocess.TimeoutExpired("controlled worker wait", timeout or 0.0)

                monkeypatch.setattr(worker, "wait", failed_wait)
        return worker

    def denied_probe(group, sig):
        if sig == 0:
            raise PermissionError("controlled Darwin EPERM process-group probe")
        return original_killpg(group, sig)

    def delayed_ps(command, **kwargs):
        if command[0] == "/bin/ps":
            if inspection == "failed":
                raise subprocess.CalledProcessError(1, command)
            if inspection.startswith("invalid"):
                return subprocess.CompletedProcess(command, 0, "invalid state row\n", "")
            command = [
                sys.executable,
                "-c",
                "import os,time;time.sleep(.25);os.execv('/bin/ps',['/bin/ps','-axo','pgid=,stat='])",
            ]
        return original_run(command, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", popen)
    monkeypatch.setattr(subprocess, "run", delayed_ps)
    monkeypatch.setattr(os, "killpg", denied_probe)
    started = time.monotonic()
    ignore_term = (
        "import signal;signal.signal(signal.SIGTERM,signal.SIG_IGN);"
        if inspection == "invalid_stubborn"
        else ""
    )
    try:
        with pytest.raises(
            SamplingLimit,
            match="time_limit" if inspection == "slow_valid" else "cleanup unconfirmed",
        ):
            owned_process.run(
                [
                    sys.executable,
                    "-c",
                    f"from pathlib import Path;import time;{ignore_term}Path({str(marker)!r}).touch();time.sleep(30)",
                ],
                budget=Budget(wall_seconds=2),
            )
        assert marker.exists()
        assert time.monotonic() - started < 2.5
        assert all(worker.poll() is not None for worker in workers)
    finally:
        for worker in workers:
            if worker.poll() is None:
                original_killpg(worker.pid, signal.SIGKILL)
            original_popen.wait(worker, timeout=1)
