"""Deadline-owned staging, publication and recovery with retained prior bytes."""

from __future__ import annotations

import json
import os
import shutil
import time
import uuid
from pathlib import Path

from logo_maker import host
from logo_maker.sampling import Budget, SamplingLimit


def publish(entries: list[dict], journal: Path, budget: Budget, stages: list[dict]) -> dict:
    """Reserve recovery time before starting any mutation of published paths."""
    if budget.remaining <= 4:
        raise SamplingLimit("time_limit: insufficient publication and recovery budget")
    work = Budget(parent=budget, attempt_limit=budget.attempt_limit)
    work.deadline = budget.deadline - 3
    payload = {
        "operation": "publish",
        "entries": entries,
        "journal": str(journal),
        "deadline": time.monotonic() + work.remaining,
        "lock": str(Path(entries[0]["target"]).with_name(".publication.lock")),
    }
    try:
        result = host.run(payload, work, stages)
    except BaseException as original:
        # The journal is written before the first rename. Recovery is itself
        # killable and spends the original reserve, never a fresh deadline.
        try:
            host.run(
                {
                    "operation": "recover_publication",
                    "journal": str(journal),
                    "lock": payload["lock"],
                },
                budget,
                stages,
            )
        except Exception as recovery:
            raise SamplingLimit(
                f"cleanup unconfirmed: publication recovery failed; retain {journal}; {recovery}"
            ) from original
        raise
    try:
        host.run({"operation": "clean_publication", "journal": str(journal)}, budget, stages)
        result["cleanup"] = "completed"
    except Exception as exc:
        # Publication is complete. Keep the journal/prior paths for explicit
        # later maintenance; cleanup cannot turn a committed set into a partial one.
        result["cleanup"] = "pending"
        result["cleanup_error"] = str(exc)
    return result


def _remove(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink(missing_ok=True)


def _record(path: Path, data: dict) -> None:
    pending = path.with_suffix(".pending")
    pending.write_text(json.dumps(data))
    pending.replace(path)


def apply(payload: dict) -> dict:
    journal = Path(payload["journal"])
    journal.parent.mkdir(parents=True, exist_ok=True)
    lock = Path(payload["lock"])
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise RuntimeError(f"publication_conflict: retained transaction lock at {lock}") from exc
    with os.fdopen(descriptor, "w") as handle:
        handle.write(str(journal))
    _record(journal, {"state": "staging", "entries": [], "lock": str(lock)})
    token = uuid.uuid4().hex
    rows: list[dict] = []
    for entry in payload["entries"]:
        if entry.get("optional") and not Path(entry["source"]).exists():
            continue
        target = Path(entry["target"])
        target.parent.mkdir(parents=True, exist_ok=True)
        rows.append(
            {
                **entry,
                "pending": str(target.with_name(".publishing-" + token + "-" + target.name)),
                "backup": str(target.with_name(".prior-" + token + "-" + target.name)),
                "quarantine": str(target.with_name(".interrupted-" + token + "-" + target.name)),
                "existed": target.exists(),
            }
        )
    # Record every pending name even if copying blocks. No target changes before
    # staging all entries, including the provenance record.
    _record(journal, {"state": "staging", "entries": rows, "lock": str(lock)})
    for row in rows:
        pending = Path(row["pending"])
        if "text" in row:
            pending.write_text(row["text"])
        elif row.get("move"):
            Path(row["source"]).rename(pending)
        else:
            shutil.copyfile(row["source"], pending)
    _record(journal, {"state": "prepared", "entries": rows, "lock": str(lock)})
    for row in rows:
        if time.monotonic() >= payload["deadline"]:
            raise SamplingLimit("time_limit: publication deadline exhausted")
        target = Path(row["target"])
        if row["existed"]:
            target.rename(row["backup"])
        Path(row["pending"]).rename(target)
    _record(journal, {"state": "committed", "entries": rows, "lock": str(lock)})
    return {"published": True, "journal": str(journal)}


def recover(journal: Path, lock: Path | None = None) -> dict:
    if not journal.exists():
        if lock is not None and lock.exists() and lock.read_text() == str(journal):
            lock.unlink()
        return {"recovered": True}
    record = json.loads(journal.read_text())
    if record["state"] != "staging":
        for row in reversed(record["entries"]):
            target, backup, pending = map(Path, (row["target"], row["backup"], row["pending"]))
            if backup.exists():
                if target.exists():
                    target.rename(row["quarantine"])
                backup.rename(target)
            elif not row["existed"] and not pending.exists() and target.exists():
                target.rename(row["quarantine"])
    _record(journal, {**record, "state": "recovered"})
    if record.get("lock"):
        Path(record["lock"]).unlink(missing_ok=True)
    # Prior outputs have been restored before potentially slow staging cleanup.
    return {"recovered": True, "journal": str(journal)}


def clean(journal: Path) -> dict:
    if journal.exists():
        record = json.loads(journal.read_text())
        for row in record["entries"]:
            for key in ("pending", "backup", "quarantine"):
                _remove(Path(row[key]))
        if record.get("lock"):
            Path(record["lock"]).unlink(missing_ok=True)
        journal.unlink()
    return {"cleaned": True}
