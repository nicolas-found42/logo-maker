"""A bounded POSIX tool session, including launcher cleanup and process reaping."""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import time
from collections.abc import Mapping
from pathlib import Path

from logo_maker.proc import ToolError
from logo_maker.sampling import Budget, SamplingLimit


def run(
    command: list[str],
    *,
    budget: Budget,
    input_text: str = "",
    label: str = "tool",
    timeout: float | None = None,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Reserve cleanup inside the shared deadline; never leave owned work running."""
    if os.name != "posix":
        raise ToolError("bounded workers require macOS/Linux process-session cleanup")
    if budget.remaining <= 1:
        raise SamplingLimit(f"time_limit: insufficient {label} budget including process cleanup")
    worker = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        errors="replace",
        start_new_session=True,
        cwd=cwd,
        env=env,
    )
    try:
        try:
            stdout, stderr = worker.communicate(
                input_text, timeout=max(0.001, min(timeout or float("inf"), budget.remaining - 1))
            )
        except subprocess.TimeoutExpired as exc:
            raise SamplingLimit(
                f"time_limit: {label} deadline exhausted; prior artifacts retained"
            ) from exc
        return subprocess.CompletedProcess(command, worker.returncode, stdout, stderr)
    finally:
        try:
            stop_session(worker, budget)
        finally:
            for stream in (worker.stdin, worker.stdout, worker.stderr):
                if stream:
                    stream.close()


def stop_session(worker: subprocess.Popen, budget: Budget) -> None:
    """Give launcher hooks time even after the immediate worker has exited."""

    def active() -> bool:
        try:
            os.killpg(worker.pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return _group_has_live_members(worker.pid, budget)
        return True

    def send(sig: signal.Signals) -> bool:
        """Return false only when the group is already known to have no live members."""
        try:
            os.killpg(worker.pid, sig)
        except ProcessLookupError:
            return False
        except PermissionError as exc:
            if _group_has_live_members(worker.pid, budget):
                raise SamplingLimit("cleanup unconfirmed: live group signal denied") from exc
            return False
        return True

    failed = False
    try:
        alive = send(signal.SIGTERM) and active()
        grace_end = time.monotonic() + max(0, min(0.8, budget.remaining - 0.2))
        while alive and time.monotonic() < grace_end:
            time.sleep(min(0.01, max(0, grace_end - time.monotonic())))
            alive = active()
        if alive:
            send(signal.SIGKILL)
    except BaseException:
        failed = True
        # A failed proof remains a failure, but must not skip stopping our session.
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(worker.pid, signal.SIGKILL)
        raise
    finally:
        try:
            worker.wait(timeout=max(0.001, min(0.2, budget.remaining)))
        except subprocess.TimeoutExpired as exc:
            if not failed:
                raise SamplingLimit("time_limit: worker cleanup unconfirmed") from exc


def _group_has_live_members(group: int, budget: Budget) -> bool:
    """Darwin EPERM includes zombie-only groups; prove their state before accepting it."""
    try:
        proc = subprocess.run(
            ["/bin/ps", "-axo", "pgid=,stat="],
            capture_output=True,
            text=True,
            check=True,
            timeout=max(0.001, min(0.8, budget.remaining - 0.2)),
        )
        rows = [line.split() for line in proc.stdout.splitlines() if line.strip()]
        if not rows or any(len(row) != 2 or not row[0].isdigit() for row in rows):
            raise ValueError("invalid process-state inspection")
        return any(int(pgid) == group and not state.startswith("Z") for pgid, state in rows)
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        raise SamplingLimit("cleanup unconfirmed: process-state inspection failed") from exc
