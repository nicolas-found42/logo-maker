"""Submission validation: real bodies, Markdown bypasses and GitHub write boundaries."""

from __future__ import annotations

import copy
import subprocess
import sys

import pytest

from scripts import template_check as check

REPO = "nicolas-found42/logo-maker"
SHA = "a" * 40
BEFORE = "https://github.com/user-attachments/assets/before-capture"
AFTER = "https://github.com/user-attachments/assets/after-capture"
PR = f"""## Summary
Fix exports clipping when a motif reaches its contour bounds.

## Evidence
**Visible app change:** Yes: the rendered export contour changes.
### Before
![Before export]({BEFORE})
**Revision:** 1111111
**Scenario:** Export the same minimal motif with logo-maker export sample.
**Observed result:** The right edge is clipped.
### After
![After export]({AFTER})
**Revision:** 2222222
**Scenario:** Same logo-maker export sample command and motif.
**Observed result:** The complete contour is visible.
### Verification
| Check | Result and evidence, or reason not run |
| --- | --- |
| Offline tests: `just test` | Pass: export boundary regression. |
| Lint and formatting: `just lint` | Pass. |
| Types: `just type` | Pass. |
| Repository hooks: `just hooks` | Pass. |
| Render changes: `just render-example` | Not run: flat exports only. |
| Dependency changes: `logo-maker doctor` | N/A: dependencies unchanged. |
| Jev/provider changes: relevant live tests with `-m live` | N/A: judging unchanged. |
### Gaps
None
### Applicable project rules
| Rule | Response or reason unaffected |
| --- | --- |
| Stage contracts in `docs/architecture.md` | Existing output contract preserved. |
| Jev definitions in `logo_maker/jev/questions.py` and regenerated `docs/jev-questions.md` | Unaffected: no judging changes. |
| New external-tool adapters and license documentation | Unaffected: existing tools only. |
| Brand-neutral catalog/defaults; examples used only for regression | No catalog or example-brand changes. |
| Images from geometry/fonts/materials/renderers; models only judge | Captures show actual geometry exports. |
## Merge Danger
**Door:** Two-way; revert the export fix.
**Blast Radius:** Flat SVG consumers may see changed bounds.
**Recovery:** Revert the commit and re-export affected assets.
"""
FEATURE = """### User problem
Need an SVG export with explicit dimensions for a print tool.
### Desired behavior and success example
Export an SVG that opens at 20 mm wide in the print tool.
"""
BUG = """### Summary
The export command drops the last contour.
### Steps and minimal inputs
Run logo-maker export sample using the attached motif.
### Expected behavior
Every contour is exported.
### Actual behavior
The last contour is missing.
### Version or commit
logo-maker 0.1.0
### Environment and installation method
macOS on Apple silicon, installed with uv.
"""


@pytest.mark.parametrize(("kind", "body"), [("pr", PR), ("feature", FEATURE), ("bug", BUG)])
def test_complete_submissions(kind, body):
    assert check.validate(body, kind) == []


def test_unfilled_pr_template_fails():
    errors = check.validate((check.ROOT / ".github/pull_request_template.md").read_text(), "pr")
    assert any("Summary" in error for error in errors)
    assert any("Before: embed" in error for error in errors)
    assert any("Offline tests" in error for error in errors)
    assert any("Stage contracts" in error for error in errors)
    assert any("Recovery" in error for error in errors)


@pytest.mark.parametrize(
    "value", ["", "<!-- answered -->", "_No response_", "TODO", "TBD later", "N/A", "..."]
)
def test_required_issue_answer_cannot_be_placeholder(value):
    body = FEATURE.replace("Need an SVG export with explicit dimensions for a print tool.", value)
    assert any("User problem" in error for error in check.validate(body, "feature"))


def test_extra_spec_sections_and_code_answers_are_allowed():
    body = (
        FEATURE.replace(
            "Export an SVG that opens at 20 mm wide in the print tool.",
            "```shell\nlogo-maker export sample\n```",
        )
        + "\n## Agent brief\nUse the existing exporter.\n"
    )
    assert check.validate(body, "feature") == []


@pytest.mark.parametrize("wrapper", ["```markdown\n{}\n```", "<!-- {} -->", "    {}"])
def test_fake_required_headings_do_not_count(wrapper):
    fake = wrapper.format("### User problem\nThis only looks like a section.")
    body = fake + "\n### Desired behavior and success example\nA working SVG export.\n"
    assert check.validate(body, "feature")


def test_duplicate_required_sections_fail():
    assert check.validate(FEATURE + "\n### User problem\nAnother answer.\n", "feature")


def test_issue_field_cannot_borrow_nested_field_answer():
    body = (
        "### User problem\n#### Desired behavior and success example\nExport a print-ready SVG.\n"
    )
    assert check.validate(body, "feature")


def test_wrong_pr_heading_parent_fails():
    moved = PR.replace("## Evidence\n", "").replace(
        "### Verification", "## Evidence\n### Verification"
    )
    assert any("Before: use" in error for error in check.validate(moved, "pr"))


@pytest.mark.parametrize(
    "replacement",
    [
        "",
        f"[Before export]({BEFORE})",
        f"`![Before]({BEFORE})`",
        f"```markdown\n![Before]({BEFORE})\n```",
        f"<!-- ![Before]({BEFORE}) -->",
        f"\\![Before]({BEFORE})",
        "![Before](/tmp/before.png)",
        "![Before](data:image/png;base64,abc)",
        "![Before](https://example.com/before.png)",
        "![Before](https://[broken/before.png)",
    ],
)
def test_missing_or_nonrendering_before_image_fails(replacement):
    body = PR.replace(f"![Before export]({BEFORE})", replacement)
    assert any("Before: embed" in error for error in check.validate(body, "pr"))


def test_after_image_is_independently_required():
    body = PR.replace(f"![After export]({AFTER})", "")
    assert any("After: embed" in error for error in check.validate(body, "pr"))


def test_same_image_with_different_query_is_not_separate_capture():
    body = PR.replace(AFTER, BEFORE + "?different-token=1")
    assert any("separate captures" in error for error in check.validate(body, "pr"))


def test_reference_images_and_github_html_images_are_supported():
    body = PR.replace(f"![Before export]({BEFORE})", "![Before export][baseline]")
    body = body.replace(f"![After export]({AFTER})", f'<img alt="After export" src="{AFTER}">')
    assert check.validate(body + f"\n[baseline]: {BEFORE}\n", "pr") == []


def test_local_inline_image_cannot_borrow_unused_reference_definition():
    body = PR.replace(f"![Before export]({BEFORE})", "![Before export](/tmp/before.png)")
    body += f"\n[Before export]: {BEFORE}\n"
    assert any("Before: embed" in error for error in check.validate(body, "pr"))


def test_image_without_observed_result_fails():
    body = PR.replace("**Observed result:** The right edge is clipped.", "")
    assert any("Before / Observed result" in error for error in check.validate(body, "pr"))


def nonvisual_pr():
    return (
        PR.replace(
            "Yes: the rendered export contour changes.",
            "No: CLI validation only; app and rendered output are unchanged.",
        )
        .replace(f"![Before export]({BEFORE})", "")
        .replace(f"![After export]({AFTER})", "")
        .replace("The right edge is clipped.", "Invalid input exits 0.\n\n```text\nexit=0\n```")
        .replace(
            "The complete contour is visible.", "Invalid input exits 2.\n\n```text\nexit=2\n```"
        )
    )


def test_nonvisual_before_after_text_passes_without_images():
    assert check.validate(nonvisual_pr(), "pr") == []


@pytest.mark.parametrize("side", ["Before", "After"])
@pytest.mark.parametrize("field", ["Revision", "Scenario", "Observed result"])
def test_nonvisual_proof_requires_each_detail(side, field):
    body = nonvisual_pr()
    section = next(section for section in check.sections(body) if section.title == side)
    changed = section.body.replace(f"**{field}:**", f"{field} omitted:")
    body = body.replace(section.body, changed)
    assert any(f"{side} / {field}" in error for error in check.validate(body, "pr"))


@pytest.mark.parametrize("declaration", ["", "No", "No: TODO", "Maybe: CLI", "<!-- No: CLI -->"])
def test_screenshot_opt_out_requires_explicit_classification_and_reason(declaration):
    body = PR.replace("Yes: the rendered export contour changes.", declaration)
    assert any("Visible app change" in error for error in check.validate(body, "pr"))


def test_declaration_inside_code_cannot_disable_screenshot_requirement():
    body = PR.replace(
        "**Visible app change:** Yes: the rendered export contour changes.",
        "```text\n**Visible app change:** No: backend only.\n```",
    ).replace(f"![Before export]({BEFORE})", "")
    errors = check.validate(body, "pr")
    assert any("Visible app change" in error for error in errors)
    assert any("Before: embed" in error for error in errors)


def test_empty_or_missing_verification_row_fails():
    for row in ["| Offline tests: `just test` | |", ""]:
        body = PR.replace("| Offline tests: `just test` | Pass: export boundary regression. |", row)
        assert any("Offline tests" in error for error in check.validate(body, "pr"))


def test_bare_na_is_not_a_reason_not_run():
    body = PR.replace("N/A: judging unchanged.", "N/A")
    assert any("Jev/provider" in error for error in check.validate(body, "pr"))


def test_duplicate_verification_row_fails_without_crashing():
    body = PR.replace("### Gaps", "| Offline tests: `just test` | Pass. |\n### Gaps")
    assert any("duplicate table row" in error for error in check.validate(body, "pr"))


def test_merge_fields_cannot_borrow_neighbor_answer():
    body = PR.replace("**Door:** Two-way; revert the export fix.", "**Door:** <!-- fill later -->")
    assert any("Merge Danger / Door" in error for error in check.validate(body, "pr"))


def test_required_issue_fields_come_from_current_form():
    template = (check.ROOT / ".github/ISSUE_TEMPLATE/feature-request.yml").read_text()
    changed = template.replace("label: User problem", "label: User constraint")
    assert "User constraint" in check.required_issue_fields(changed)
    with pytest.raises(ValueError, match="layout"):
        check.required_issue_fields(
            template.replace("validations:\n      required: true", "validations: {required: true}")
        )


@pytest.fixture
def github_env(monkeypatch):
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)


def event(kind):
    return {"repository": {"full_name": REPO}, kind: {"number": 7, "head": {"sha": SHA}}}


def fake_api(monkeypatch, snapshots):
    writes = []
    pending = iter(snapshots)

    def invoke(path, *, method="GET", payload=None):
        if method == "GET":
            return copy.deepcopy(next(pending))
        writes.append((path, method, payload))
        return {}

    monkeypatch.setattr(check, "api", invoke)
    return writes


def test_pr_reports_status_on_current_head_not_event_head(monkeypatch, github_env):
    current_sha = "b" * 40
    current = {"body": PR, "state": "open", "head": {"sha": current_sha}}
    writes = fake_api(monkeypatch, [current, current])
    assert check.github_check(event("pull_request"), "pull_request_target", REPO) == 0
    assert writes[-1][0].endswith(current_sha)
    assert writes[-1][2]["state"] == "success"
    assert writes[-1][2]["context"] == "template/pr"
    assert all(write[1] == "POST" for write in writes)


def test_body_edit_on_same_sha_invalidates_old_success(monkeypatch, github_env):
    current = {"body": "", "state": "open", "head": {"sha": SHA}}
    writes = fake_api(monkeypatch, [current, current])
    assert check.github_check(event("pull_request"), "pull_request_target", REPO) == 1
    assert writes[0][2]["state"] == "pending"
    assert writes[-1][2]["state"] == "failure"


def test_changed_body_is_revalidated_before_success(monkeypatch, github_env):
    valid = {"body": PR, "state": "open", "head": {"sha": SHA}}
    invalid = {**valid, "body": ""}
    writes = fake_api(monkeypatch, [valid, invalid, invalid, invalid])
    assert check.github_check(event("pull_request"), "pull_request_target", REPO) == 1
    assert not any(write[2]["state"] == "success" for write in writes)


def test_invalid_issue_gets_needs_info_preserving_category_and_area(monkeypatch, github_env):
    issue = {
        "body": "",
        "state": "open",
        "labels": [{"name": name} for name in ["bug", "area:exports", "ready-for-agent"]],
    }
    writes = fake_api(monkeypatch, [issue])
    assert check.github_check(event("issue"), "issues", REPO) == 1
    assert writes == [
        (f"repos/{REPO}/issues/7/labels", "POST", {"labels": ["needs-info"]}),
        (f"repos/{REPO}/issues/7/labels/ready-for-agent", "DELETE", None),
    ]


def test_valid_issue_has_no_status_or_label_writes(monkeypatch, github_env):
    issue = {"body": FEATURE, "state": "open", "labels": [{"name": "enhancement"}]}
    writes = fake_api(monkeypatch, [issue])
    assert check.github_check(event("issue"), "issues", REPO) == 0
    assert writes == []


def test_already_flagged_issue_does_not_write_labels_again(monkeypatch, github_env):
    issue = {
        "body": "",
        "state": "open",
        "labels": [
            {"name": "bug"},
            {"name": "needs-info"},
        ],
    }
    writes = fake_api(monkeypatch, [issue])
    assert check.github_check(event("issue"), "issues", REPO) == 1
    assert writes == []


def test_unknown_issue_category_fails_and_requests_info(monkeypatch, github_env):
    writes = fake_api(monkeypatch, [{"body": FEATURE, "state": "open", "labels": []}])
    assert check.github_check(event("issue"), "issues", REPO) == 1
    assert writes[-1][2] == {"labels": ["needs-info"]}


def test_cross_repository_payload_rejected_before_any_api_call(monkeypatch, github_env):
    writes = fake_api(monkeypatch, [])
    with pytest.raises(ValueError, match="repository"):
        check.github_check(event("issue"), "issues", "other/repo")
    assert not writes


def test_local_cli_exit_code(tmp_path):
    body = tmp_path / "body.md"
    body.write_text(FEATURE)
    command = [
        sys.executable,
        str(check.ROOT / "scripts/template_check.py"),
        "--kind",
        "feature",
        "--body-file",
        str(body),
    ]
    assert subprocess.run(command, capture_output=True).returncode == 0
    body.write_text("<!-- empty -->")
    assert subprocess.run(command, capture_output=True).returncode == 1


def test_body_is_data_not_shell_code(tmp_path):
    body = tmp_path / "body.md"
    marker = tmp_path / "unexpected-file"
    body.write_text(FEATURE.replace("Need an SVG", f"$(touch {marker}) Need an SVG"))
    command = [
        sys.executable,
        str(check.ROOT / "scripts/template_check.py"),
        "--kind",
        "feature",
        "--body-file",
        str(body),
    ]
    assert subprocess.run(command, capture_output=True).returncode == 0
    assert not marker.exists()
