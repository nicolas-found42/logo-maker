"""Real worker stalls must stop, including after the first published rename."""

import json
import os
import time

import pytest

from logo_maker.publication import publish
from logo_maker.sampling import Budget, SamplingLimit


def inject_stall(tmp_path, monkeypatch, operation, selector, *, after=False):
    """Inject an IO stall into fresh interpreters, with no product test hook."""
    hooks = tmp_path / "hooks"
    hooks.mkdir()
    marker = tmp_path / "fault-started"
    (hooks / "sitecustomize.py").write_text(
        "import pathlib,shutil,time\n"
        f"marker=pathlib.Path({str(marker)!r})\n"
        f"operation={operation!r}; selector={selector!r}; after={after!r}\n"
        "owner=shutil if operation=='copyfile' else pathlib.Path\n"
        "original=getattr(owner,operation)\n"
        "def injected(*args,**kwargs):\n"
        " hit=selector in str(args[0])\n"
        " if hit and not after:\n"
        "  marker.touch(); time.sleep(30)\n"
        " result=original(*args,**kwargs)\n"
        " if hit and after:\n"
        "  marker.touch(); time.sleep(30)\n"
        " return result\n"
        "setattr(owner,operation,injected)\n"
    )
    monkeypatch.setenv("PYTHONPATH", str(hooks) + os.pathsep + os.environ.get("PYTHONPATH", ""))
    return marker


@pytest.mark.parametrize("failure", ["copy", "after_rename"])
def test_publication_stall_terminates_and_restores_whole_prior_set(tmp_path, monkeypatch, failure):
    prior = tmp_path / "final.png"
    sidecar = tmp_path / "final.sampling.json"
    prior.write_bytes(b"approved prior pixels")
    sidecar.write_text('{"prior":true}')
    source = tmp_path / "next.bin"
    source.write_bytes(b"next pixels")
    marker = inject_stall(
        tmp_path,
        monkeypatch,
        "copyfile" if failure == "copy" else "rename",
        "next.bin" if failure == "copy" else ".publishing-",
        after=failure == "after_rename",
    )
    started = time.monotonic()
    with pytest.raises(SamplingLimit, match="time_limit"):
        publish(
            [
                {"source": str(source), "target": str(prior)},
                {"text": '{"next":true}', "target": str(sidecar)},
            ],
            tmp_path / "journal.json",
            Budget(wall_seconds=8),
            [],
        )
    assert marker.exists(), "fault was not reached"
    assert time.monotonic() - started < 10
    assert prior.read_bytes() == b"approved prior pixels"
    assert json.loads(sidecar.read_text()) == {"prior": True}
    assert source.read_bytes() == b"next pixels"


def test_committed_cleanup_stall_is_bounded_and_keeps_recovery_evidence(tmp_path, monkeypatch):
    prior = tmp_path / "final.png"
    prior.write_bytes(b"prior")
    marker = inject_stall(tmp_path, monkeypatch, "unlink", ".prior-")
    started = time.monotonic()
    result = publish(
        [{"text": "next", "target": str(prior)}],
        tmp_path / "journal.json",
        Budget(wall_seconds=8),
        [],
    )
    assert marker.exists()
    assert result["published"]
    assert result["cleanup"] == "pending"
    assert time.monotonic() - started < 10
    assert prior.read_bytes() == b"next"
    assert next(tmp_path.glob(".prior-*")).read_bytes() == b"prior"
    assert json.loads((tmp_path / "journal.json").read_text())["state"] == "committed"


def test_finalize_interrupted_winner_publication_restores_winner_and_run_state(
    tmp_path, monkeypatch
):
    from test_eligibility import EligibilityClient, finalize_logo

    from logo_maker import pipeline, publication, render

    logo, cid = finalize_logo(tmp_path / "logo")
    monkeypatch.setattr(render, "machine_context", lambda *a: {})
    prior = logo.ideation / "winner.json"
    prior.write_text('{"winner":"approved-prior"}')
    result = pipeline.qa_concept(logo, cid, EligibilityClient(), pipeline.brand(logo))
    previous_state = json.loads(logo.run_json.read_text())
    monkeypatch.setattr(pipeline, "qa_concept", lambda *a, **kw: result)
    marker = inject_stall(tmp_path, monkeypatch, "rename", ".publishing-", after=True)
    phase_started = []
    original = publication.publish

    def bounded_publication(entries, journal, budget, stages, **kwargs):
        # Allow cold preparation on hosted Macs, then shorten the same job budget
        # at the publication boundary whose rollback this test exercises.
        phase_started.append(time.monotonic())
        budget.deadline = min(budget.deadline, phase_started[-1] + 12)
        return original(entries, journal, budget, stages, **kwargs)

    monkeypatch.setattr(publication, "publish", bounded_publication)
    with pytest.raises(SamplingLimit, match="time_limit"):
        pipeline.finalize(logo, EligibilityClient(), budget=Budget(wall_seconds=60))
    assert marker.exists()
    assert len(phase_started) == 1
    assert time.monotonic() - phase_started[0] < 14
    assert json.loads(prior.read_text()) == {"winner": "approved-prior"}
    assert json.loads(logo.run_json.read_text()) == previous_state
