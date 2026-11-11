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
            # Charge probe latency to its timeout, without a cold interpreter proxy.
            limit = float(kwargs["timeout"])
            started = time.monotonic()
            time.sleep(min(0.25, limit))
            remaining = limit - (time.monotonic() - started)
            if remaining <= 0:
                raise subprocess.TimeoutExpired(command, limit)
            kwargs["timeout"] = remaining
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


def test_inactive_group_proof_is_not_repeated_after_signal_denial(tmp_path, monkeypatch):
    original_killpg = os.killpg
    original_run = subprocess.run
    probes = []
    marker = tmp_path / "completed-worker"

    def denied_signals(group, sig):
        if sig in (0, signal.SIGTERM):
            raise PermissionError("controlled inactive group denial")
        return original_killpg(group, sig)

    def inspect(command, **kwargs):
        if command[0] == "/bin/ps":
            probes.append(command)
        return original_run(command, **kwargs)

    monkeypatch.setattr(os, "killpg", denied_signals)
    monkeypatch.setattr(subprocess, "run", inspect)
    result = owned_process.run(
        [sys.executable, "-c", f"from pathlib import Path;Path({str(marker)!r}).touch()"],
        budget=Budget(wall_seconds=2),
    )
    assert result.returncode == 0
    assert marker.exists()
    assert len(probes) == 1
