"""Provenance and qualification are independent of aesthetic preference."""

import hashlib
import json

import pytest


def test_changed_asset_is_rejected_without_rewriting_owner_labels(tmp_path):
    from logo_maker.benchmark import verify_bundle

    image = tmp_path / "reference.png"
    image.write_bytes(b"approved original bytes")
    manifest = {
        "schema": 1,
        "assets": [
            {
                "path": "reference.png",
                "sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
                "origin": "owner supplied",
                "permitted_use": "benchmark evidence",
            }
        ],
        "cases": [
            {
                "id": "original",
                "asset": "reference.png",
                "owner_labels": {
                    "craftsmanship": "approved",
                    "fidelity": "not-applicable",
                    "brief_fit": "unknown",
                    "preference": "unranked",
                },
            }
        ],
        "remaining_gaps": ["held-out owner review"],
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    report = verify_bundle(tmp_path)
    assert report["qualification"] == "incomplete"
    assert report["cases"][0]["owner_labels"]["preference"] == "unranked"
    image.write_bytes(b"new render must not replace original")
    with pytest.raises(ValueError, match="hash"):
        verify_bundle(tmp_path)


def test_bundle_rejects_missing_dimensions_and_escaping_assets(tmp_path):
    from logo_maker.benchmark import verify_bundle

    manifest = {
        "schema": 1,
        "assets": [
            {
                "path": "../outside.png",
                "sha256": "0" * 64,
                "origin": "owner",
                "permitted_use": "evidence",
            }
        ],
        "cases": [],
        "remaining_gaps": [],
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="inside bundle"):
        verify_bundle(tmp_path)
    image = tmp_path / "pinned.png"
    image.write_bytes(b"pinned")
    manifest["assets"] = [
        {
            "path": "pinned.png",
            "sha256": hashlib.sha256(b"pinned").hexdigest(),
            "origin": "owner",
            "permitted_use": "evidence",
        }
    ]
    manifest["cases"] = [
        {"id": "missing", "asset": "unknown.png", "owner_labels": {"craftsmanship": "approved"}}
    ]
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="four independent"):
        verify_bundle(tmp_path)
    labels = ["craftsmanship", "fidelity", "brief_fit", "preference"]
    for case in (
        {"asset": ["pinned.png"], "owner_labels": labels},
        {"asset": "pinned.png", "owner_labels": [labels]},
    ):
        manifest["cases"] = [case]
        path.write_text(json.dumps(manifest))
        with pytest.raises(ValueError, match="four independent"):
            verify_bundle(tmp_path)


@pytest.mark.parametrize(
    ("text", "match"),
    [
        ('{"schema": 1, "assets": [', "not valid JSON"),
        ("[]", "integer schema"),
        ('{"schema": true, "assets": [], "cases": [], "remaining_gaps": []}', "integer schema"),
        ('{"schema": 1, "assets": [], "cases": [], "remaining_gaps": []}', "pins no assets"),
        ('{"schema": 1, "assets": [{"path": "a"}], "cases": [], "remaining_gaps": []}', "string"),
        ("[" * 100_000, "not readable JSON"),
    ],
)
def test_malformed_manifests_are_named_errors(tmp_path, text, match):
    from logo_maker.benchmark import verify_bundle

    (tmp_path / "manifest.json").write_text(text)
    with pytest.raises(ValueError, match=match):
        verify_bundle(tmp_path)
    with pytest.raises(ValueError, match="cannot read"):
        verify_bundle(tmp_path / "missing")
