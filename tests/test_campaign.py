"""Campaign gates that must survive a new process or a changed input."""

from __future__ import annotations

import json

import pytest

from logo_maker import campaign, campaign_runtime, pipeline
from logo_maker.paths import LogoDir
from logo_maker.sampling import SamplingLimit


@pytest.fixture
def logo(tmp_path, monkeypatch):
    monkeypatch.setattr(campaign.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(campaign.platform, "machine", lambda: "arm64")
    logo = LogoDir(tmp_path)
    logo.brief.write_text('name = "Pilot"\nsummary = "Dock fittings."\ntone = ["precise"]\n')
    return logo


def test_campaign_reopens_changed_research_and_preserves_request_reservations(logo):
    campaign.execute(logo, "init", record={"requests": 6})
    with pytest.raises(pipeline.AuthoringNeeded, match="Research the brand"):
        campaign.execute(logo, "approve-brief", note="Owner delegated the brief.")
    research = logo.root / "research.md"
    research.write_text("Original research.\n")
    campaign.execute(logo, "approve-brief", note="Owner delegated the brief.")
    path = logo.root / "campaign.json"
    budget = campaign.CampaignBudget(path, json.loads(path.read_text()))
    budget.reserve_request(6)
    # Leave the lease unclosed to model an interrupted network worker.
    state = campaign.execute(logo, "status")
    assert "active_lease" not in state
    assert state["usage"]["requests_reserved"] == 6
    assert state["usage"]["unpriced_requests"] == 1
    resumed = campaign.CampaignBudget(path, json.loads(path.read_text()))
    try:
        with pytest.raises(SamplingLimit, match="request limit"):
            resumed.reserve_request(1)
    finally:
        resumed.close()
    research.write_text("Revised source evidence.\n")
    with pytest.raises(pipeline.AuthoringNeeded, match="Approve the current researched brief"):
        campaign.execute(logo, "preview", concepts=["fitting"])


def test_campaign_cash_limit_stops_unknown_price_before_request(logo):
    campaign.execute(logo, "init", record={"max_usd": 2.0})
    path = logo.root / "campaign.json"
    budget = campaign.CampaignBudget(path, json.loads(path.read_text()))
    try:
        with pytest.raises(SamplingLimit, match="per-attempt price bound"):
            budget.reserve_request(1)
    finally:
        budget.close()
    assert campaign.execute(logo, "status")["usage"]["requests_reserved"] == 0


def test_campaign_direction_approval_is_required_and_bound_to_brief(logo):
    campaign.execute(logo, "init")
    (logo.root / "research.md").write_text("Dock cleat casting evidence.\n")
    campaign.execute(logo, "approve-brief", note="Owner approved.")
    folder = logo.concept("cleat")
    concept = folder / "concept.json"
    concept.write_text(json.dumps({"label": "Cleat", "description": "Cast dock cleat."}))
    state = campaign.execute(logo, "status")
    with pytest.raises(pipeline.AuthoringNeeded, match="Approve the researched directions"):
        campaign._directions_current(logo, state, ["cleat"])
    campaign.execute(logo, "approve-directions", concepts=["cleat"], note="Owner approved pitch.")
    state = campaign.execute(logo, "status")
    campaign._directions_current(logo, state, ["cleat"])
    concept.write_text(json.dumps({"label": "Fairlead", "description": "Cast rope guide."}))
    with pytest.raises(pipeline.AuthoringNeeded, match="Approve the researched directions"):
        campaign._directions_current(logo, state, ["cleat"])


def test_campaign_cli_native_dispatch_fails_before_work_without_pinned_runtime(logo, monkeypatch):
    monkeypatch.delenv("CODEX_SANDBOX", raising=False)
    with pytest.raises(RuntimeError, match="project-local Codex Metal runtime"):
        campaign_runtime.dispatch(logo, "preflight")
    assert not (logo.root / "campaign.json").exists()


def test_campaign_profiles_keep_network_and_metal_separate(tmp_path):
    binary = tmp_path / "codex"
    gpu = campaign_runtime._arguments(binary, tmp_path, "render", {})
    photo = campaign_runtime._arguments(
        binary, tmp_path, "fetch-photo", {"url": "https://upload.wikimedia.org/image.jpg"}
    )
    judge = campaign_runtime._arguments(binary, tmp_path, "diagnose", {})
    assert "--allow-metal" in gpu
    assert "permissions.logo-maker.network.enabled=false" in gpu
    assert "--allow-metal" not in photo
    assert "--allow-metal" not in judge
    author = campaign_runtime._arguments(binary, tmp_path, "author", {})
    assert "--allow-metal" in author
    assert "permissions.logo-maker.network.enabled=false" in author
    assert any('"/Applications/Blender.app"="deny"' in arg for arg in author)
    assert 'permissions.logo-maker.network.domains={"upload.wikimedia.org"="allow"}' in photo
    assert 'permissions.logo-maker.network.domains={"openrouter.ai"="allow"}' in judge
    with pytest.raises(ValueError, match="direct public HTTPS URL"):
        campaign_runtime._arguments(binary, tmp_path, "fetch-photo", {"url": "http://localhost/a"})


def test_author_refuses_to_execute_generator_without_visible_metal(tmp_path, monkeypatch):
    from logo_maker.blender import metal

    monkeypatch.setattr(campaign_runtime, "_policy", lambda: None)

    def unavailable():
        raise RuntimeError("Metal device unavailable")

    monkeypatch.setattr(metal, "require_metal_device", unavailable)
    generator = tmp_path / "generator.py"
    touched = tmp_path / "executed"
    generator.write_text(f"from pathlib import Path\nPath({str(touched)!r}).touch()\n")
    with pytest.raises(RuntimeError, match="Metal device unavailable"):
        campaign_runtime._run_author(generator, [])
    assert not touched.exists()


def test_flat_campaign_binds_selection_and_owner_approval_to_rendered_artwork(logo, monkeypatch):
    from zipfile import ZipFile

    monkeypatch.setattr(campaign_runtime, "_policy", lambda: None)
    campaign.execute(logo, "init")
    (logo.root / "research.md").write_text("The dock mark will be engraved on a small plate.\n")
    campaign.execute(logo, "approve-brief", note="Flat mark approved.", record={"medium": "flat"})
    for cid, color in (("cleat", "#183B51"), ("pier", "#783B2C")):
        folder = logo.concept(cid)
        (folder / "concept.json").write_text(json.dumps({"label": cid, "description": cid}))
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="1000" '
            'viewBox="0 0 1000 1000">'
            f'<path id="mark" fill="{color}" d="M 180 180 L 820 180 L 500 820 Z"/></svg>'
        )
        (folder / "motif.svg").write_text(svg)
        if cid == "cleat":
            for name, fill in (
                ("mono.svg", "#111111"),
                ("compact.svg", "#222222"),
                ("compact-dark.svg", "#eeeeee"),
            ):
                (folder / name).write_text(svg.replace(color, fill))
    concepts = ["cleat", "pier"]
    campaign.execute(logo, "approve-directions", concepts=concepts, note="Both pitches approved.")
    with pytest.raises(pipeline.AuthoringNeeded, match="Render previews"):
        campaign.execute(logo, "select", concepts=["cleat"], note="Owner selected cleat.")
    preview = campaign.execute(logo, "flat-preview", concepts=concepts)
    campaign.execute(logo, "select", concepts=["cleat"], note="Owner selected cleat.")
    with pytest.raises(pipeline.AuthoringNeeded, match="Accept the exact verified"):
        campaign.execute(logo, "flat-accept", note="Approved.", record={"archive_sha256": "stale"})
    campaign.execute(
        logo,
        "flat-accept",
        note="Owner approved the cleat artwork.",
        record={"archive_sha256": preview["archive_sha256"]},
    )
    report = campaign.execute(logo, "flat-deliver")
    assert report["status"] == "qualified"
    with ZipFile(report["shareable"]) as package:
        assert "cleat/mark-color.svg" in package.namelist()
        assert "cleat/mark-mono.svg" in package.namelist()
        assert "cleat/mark-compact.svg" in package.namelist()
        assert "cleat/mark-compact-dark.svg" in package.namelist()
        assert "cleat/favicon-dark-16.png" in package.namelist()
        assert "pier/mark-color.svg" not in package.namelist()
    campaign.execute(logo, "select", concepts=["pier"], note="Owner selected the pier.")
    assert campaign.execute(logo, "flat-deliver")["status"] == "review_needed"
