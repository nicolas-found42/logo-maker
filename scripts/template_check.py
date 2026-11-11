#!/usr/bin/env python3
"""Validate submitted Markdown against trusted repo templates; no image URLs are fetched."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import subprocess
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
PR_CONTEXT = "template/pr"
ROLES = {"needs-triage", "needs-info", "ready-for-agent", "ready-for-human", "wontfix"}
COMMENT = re.compile(r"<!--.*?(?:-->|\Z)", re.DOTALL)
HEADING = re.compile(r"^ {0,3}(#{1,6})\s+(.+?)(?:\s+#+)?\s*$")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
IMAGE = re.compile(r"(?<!\\)!\[[^\]\n]*\]\(\s*<?(https://[^\s)>]+)>?(?:\s+[^)]*)?\)")
REFERENCE_IMAGE = re.compile(r"(?<!\\)!\[([^\]\n]*)\](?:\[([^\]\n]*)\])?(?!\()")
REFERENCE = re.compile(r"^ {0,3}\[([^\]]+)\]:\s*<?(https://[^\s>]+)>?", re.MULTILINE)


@dataclass
class Section:
    level: int
    title: str
    parent: str | None
    body: str


def outside_code(text: str) -> str:
    """Blank fenced/indented code while keeping line positions for heading parsing."""
    lines = COMMENT.sub("", text).split("\n")
    fence = ""
    output = []
    for line in lines:
        match = FENCE.match(line)
        if fence:
            if re.fullmatch(
                r" {0,3}" + re.escape(fence[0]) + "{" + str(len(fence)) + r",}\s*", line
            ):
                fence = ""
            output.append("")
        elif match:
            fence = match[1]
            output.append("")
        elif line.startswith(("    ", "\t")):
            output.append("")
        else:
            output.append(line)
    return "\n".join(output)


def sections(text: str) -> list[Section]:
    clean = COMMENT.sub("", text)
    lines = clean.split("\n")
    headings = []
    stack: list[tuple[int, str]] = []
    for index, line in enumerate(noncode_prose(clean).split("\n")):
        match = HEADING.match(line)
        if not match:
            continue
        level, title = len(match[1]), match[2].strip()
        while stack and stack[-1][0] >= level:
            stack.pop()
        parent = stack[-1][1] if stack else None
        headings.append((index, level, title, parent))
        stack.append((level, title))
    result = []
    for position, (start, level, title, parent) in enumerate(headings):
        end = next((row[0] for row in headings[position + 1 :] if row[1] <= level), len(lines))
        result.append(Section(level, title, parent, "\n".join(lines[start + 1 : end])))
    return result


def own_body(text: str) -> str:
    """Return a section's content before child headings, ignoring headings in code."""
    clean = COMMENT.sub("", text)
    lines = clean.split("\n")
    for index, line in enumerate(noncode_prose(clean).split("\n")):
        if HEADING.match(line):
            return "\n".join(lines[:index])
    return clean


def noncode_prose(text: str, *, marker: str = "") -> str:
    """Replace fenced/indented code, HTML pre/code blocks and inline code while keeping lines."""

    def replace_span(match: re.Match[str]) -> str:
        return "\n".join(marker for _ in range(match.group(0).count("\n") + 1))

    clean = outside_code(text)
    clean = re.sub(r"(?s)(`+).*?\1", replace_span, clean)
    clean = re.sub(r"(?is)<pre\b[^>]*>.*?(?:</pre\s*>|\Z)", replace_span, clean)
    return re.sub(r"(?is)<code\b[^>]*>.*?(?:</code\s*>|\Z)", replace_span, clean)


def field_values(text: str, field: str) -> list[str]:
    """Extract bold-labeled field values declared outside code while preserving code answers."""
    lines = COMMENT.sub("", text).split("\n")
    masked = noncode_prose(text, marker="\x00").split("\n")
    label = re.compile(r"^\*\*([^*\n\x00]+):\*\*\s*(.*)$")
    starts: list[tuple[int, str, str]] = []
    for index, line in enumerate(masked):
        if HEADING.match(line):
            break
        if match := label.match(line):
            starts.append((index, match[1], lines[index].split(":**", 1)[1].lstrip()))
    values = []
    for position, (start, name, first_line) in enumerate(starts):
        if name != field:
            continue
        end = starts[position + 1][0] if position + 1 < len(starts) else len(lines)
        values.append("\n".join([first_line, *lines[start + 1 : end]]))
    return values


def answer(text: str, *, allow_none: bool = False) -> bool:
    text = COMMENT.sub("", text)
    prose = noncode_prose(text)
    prose = re.sub(r"^\s*#{1,6}\s+.*$", "", prose, flags=re.MULTILINE)
    prose = re.sub(r"<[^>]*>", "", prose)
    code_chunks = [
        line
        for line, unmasked in zip(text.split("\n"), outside_code(text).split("\n"), strict=False)
        if not unmasked
    ]
    unmasked_text = outside_code(text)
    code_chunks.extend(match.group(2) for match in re.finditer(r"(?s)(`+)(.*?)\1", unmasked_text))
    without_inline = re.sub(r"(?s)(`+).*?\1", "", unmasked_text)
    for match in re.finditer(r"(?is)<pre\b[^>]*>(.*?)(?:</pre\s*>|\Z)", without_inline):
        code_chunks.append(re.sub(r"(?is)</?code\b[^>]*>", "", match.group(1)))
    without_pre = re.sub(r"(?is)<pre\b[^>]*>.*?(?:</pre\s*>|\Z)", "", without_inline)
    code_chunks.extend(
        match.group(1)
        for match in re.finditer(r"(?is)<code\b[^>]*>(.*?)(?:</code\s*>|\Z)", without_pre)
    )
    code = re.sub(r"^\s*(?:`{3,}|~{3,}).*$", "", "\n".join(code_chunks), flags=re.MULTILINE)
    text = prose + "\n" + code
    text = IMAGE.sub("", text)
    text = REFERENCE_IMAGE.sub("", text)
    text = REFERENCE.sub("", text)
    text = re.sub(r"[*_`>#\[\]()-]", " ", html.unescape(text))
    text = " ".join(text.split()).casefold().strip(" .:;!?")
    if not re.search(r"\w", text):
        return False
    if text == "none":
        return allow_none
    return not re.fullmatch(
        r"(?:n/?a|not applicable|no response|null|todo\b.*|tbd\b.*|placeholder|your .* here)", text
    )


def required_issue_fields(template: str) -> list[str]:
    """Read the repo's block-style field metadata, rejecting unsupported YAML layouts.

    This is intentionally not a general YAML parser: labels must be plain single-line
    scalars and validations must be the two-line block used in our GitHub forms.
    Unsupported layout changes fail the check instead of dropping requirements.
    """
    _, separator, body = template.partition("\nbody:\n")
    if not separator:
        raise ValueError("issue form needs block-style body metadata")
    blocks = re.split(r"(?m)^  - type: ", body)
    if blocks[0].strip() or len(blocks) < 2:
        raise ValueError("unsupported issue form field layout")
    required = []
    for block in blocks[1:]:
        if not re.match(r"(?:markdown|input|textarea|dropdown|checkboxes)\n", block):
            raise ValueError("unsupported issue form field type")
        if "validations:" not in block:
            continue
        validation = re.search(r"(?m)^    validations:\n      required: (true|false)\s*$", block)
        if not validation or len(re.findall(r"\brequired:", block)) != 1:
            raise ValueError("unsupported issue form validations layout")
        if validation[1] == "false":
            continue
        label = re.search(r"(?m)^      label: ([\w /:?().-]+)$", block)
        if not label:
            raise ValueError("required issue labels must be plain single-line scalars")
        required.append(label[1])
    if not required or len(set(required)) != len(required):
        raise ValueError("issue form must have unique required field labels")
    return required


def table_rows(text: str) -> dict[str, list[str]]:
    rows = {}
    for line in outside_code(text).splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [cell.strip() for cell in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
        if len(cells) < 2 or all(re.fullmatch(r":?-+:?", cell) for cell in cells):
            continue
        if cells[0] in rows:
            raise ValueError(f"duplicate table row: {cells[0]}")
        rows[cells[0]] = cells[1:]
    return rows


class Images(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.urls: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "img":
            self.urls.extend(value for key, value in attrs if key == "src" and value)


def image_urls(text: str, whole_body: str) -> set[str]:
    clean = noncode_prose(text)
    references = {
        key.casefold(): value for key, value in REFERENCE.findall(outside_code(whole_body))
    }
    urls = IMAGE.findall(clean)
    for alt, reference in REFERENCE_IMAGE.findall(clean):
        if (reference or alt).casefold() in references:
            urls.append(references[(reference or alt).casefold()])
    parser = Images()
    parser.feed(clean)
    urls.extend(parser.urls)
    result = set()
    for url in urls:
        try:
            parsed = urlsplit(html.unescape(url))
            host = parsed.hostname or ""
        except ValueError:
            continue
        if (
            parsed.scheme == "https"
            and host
            and parsed.path not in {"", "/"}
            and host not in {"example.com", "example.org", "example.net"}
            and not host.endswith((".invalid", ".test"))
        ):
            result.add(f"https://{parsed.netloc}{parsed.path}")
    return result


def validate(body: str, kind: str, root: Path = ROOT) -> list[str]:
    if kind == "pr":
        template = (root / ".github/pull_request_template.md").read_text()
        expected = sections(template)
    else:
        form = {"bug": "bug-report.yml", "feature": "feature-request.yml"}[kind]
        fields = required_issue_fields((root / ".github/ISSUE_TEMPLATE" / form).read_text())
        expected = [Section(3, title, None, "") for title in fields]
    actual = sections(body)
    errors = []
    for required in expected:
        matches = [
            section for section in actual if section.title.casefold() == required.title.casefold()
        ]
        if len(matches) != 1:
            errors.append(f"{required.title}: expected exactly one section (found {len(matches)})")
            continue
        found = matches[0]
        parent_matches = found.parent is None and required.parent is None
        if found.parent is not None and required.parent is not None:
            parent_matches = found.parent.casefold() == required.parent.casefold()
        if found.level != required.level or (kind == "pr" and not parent_matches):
            errors.append(f"{required.title}: use the template's heading level and parent")
        # Containers such as Evidence get their answers in their required child sections.
        container = any(section.parent == required.title for section in expected)
        if not container and not answer(found.body, allow_none=required.title == "Gaps"):
            errors.append(f"{required.title}: provide an answer, not comments or placeholders")
        if kind != "pr":
            continue
        required_own = own_body(required.body)
        found_own = own_body(found.body)
        for field in re.findall(r"(?m)^\*\*([^*\n]+):\*\*", outside_code(required_own)):
            values = field_values(found.body, field)
            if len(values) != 1 or not answer(values[0]):
                errors.append(f"{required.title} / {field}: provide a filled answer")
        expected_rows = table_rows(required_own)
        try:
            found_rows = table_rows(found_own)
        except ValueError as exc:
            errors.append(f"{required.title}: {exc}")
            continue
        for row, cells in list(expected_rows.items())[1:]:  # First row is the table header.
            values = found_rows.get(row, [])
            if len(values) != len(cells) or not all(answer(value) for value in values):
                errors.append(f"{required.title} / {row}: fill every answer cell")
    if kind == "pr":
        evidence_sections = [
            section for section in actual if section.title.casefold() == "evidence"
        ]
        declaration = ""
        if len(evidence_sections) == 1:
            # Only the container's own prose can declare screenshot applicability.
            introduction = own_body(evidence_sections[0].body)
            declarations = [
                line.split(":**", 1)[1].strip()
                for line, masked_line in zip(
                    COMMENT.sub("", introduction).split("\n"),
                    noncode_prose(introduction, marker="\x00").split("\n"),
                    strict=False,
                )
                if re.match(r"^\*\*Visible app change:\*\*\s*\S", masked_line)
            ]
            if len(declarations) == 1:
                declaration = declarations[0]
        applicability = re.fullmatch(r"(Yes|No):\s*(.+)", declaration, re.IGNORECASE)
        if not applicability or not answer(applicability[2]):
            errors.append("Evidence / Visible app change: use Yes: reason or No: reason")
        if applicability and applicability[1].casefold() == "no":
            return errors
        evidence = []
        for title in ["Before", "After"]:
            found = [section for section in actual if section.title.casefold() == title.casefold()]
            urls = image_urls(found[0].body, body) if len(found) == 1 else set()
            if not urls:
                errors.append(f"{title}: embed an HTTPS image, outside code/comments")
            evidence.append(urls)
        if evidence[0] and evidence[1] and evidence[0] == evidence[1]:
            errors.append("Before / After: use separate captures, not the same image URL")
    return errors


def api(path: str, *, method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any]:
    command = ["gh", "api", "--method", method, path]
    if payload is not None:
        command.extend(["--input", "-"])
    result = subprocess.run(
        command,
        input=json.dumps(payload) if payload is not None else None,
        text=True,
        capture_output=True,
        check=True,
    )
    if method != "GET":
        return {}
    value = json.loads(result.stdout)
    if not isinstance(value, dict):
        raise ValueError("GitHub returned a non-object response")
    return value


def report(errors: list[str]) -> int:
    lines = ["# Template validation", ""] + (
        [f"- {error}" for error in errors] if errors else ["All required fields are filled."]
    )
    text = "\n".join(lines) + "\n"
    print(text)
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(summary).open("a") as output:
            output.write(text)
    return int(bool(errors))


def github_check(event: dict[str, Any], event_name: str, repo: str) -> int:
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", repo) or event["repository"]["full_name"] != repo:
        raise ValueError("event repository does not match GITHUB_REPOSITORY")
    is_pr = event_name == "pull_request_target"
    if event_name not in {"issues", "pull_request_target"}:
        raise ValueError("unsupported event")
    number = event["pull_request" if is_pr else "issue"]["number"]
    if type(number) is not int or number < 1:
        raise ValueError("invalid issue/PR number")
    endpoint = f"repos/{repo}/{'pulls' if is_pr else 'issues'}/{number}"

    def status(sha: str, state: str) -> None:
        if not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise ValueError("invalid PR head SHA")
        api(
            f"repos/{repo}/statuses/{sha}",
            method="POST",
            payload={
                "state": state,
                "context": PR_CONTEXT,
                "description": "Required sections and before/after evidence",
                "target_url": f"{os.environ['GITHUB_SERVER_URL']}/{repo}/actions/runs/{os.environ['GITHUB_RUN_ID']}",
            },
        )

    if is_pr:
        status(event["pull_request"]["head"]["sha"], "pending")
        for _ in range(3):
            current = api(endpoint)
            if current["state"] != "open":
                return report(["PR is closed; no open submission to validate"])
            sha = current["head"]["sha"]
            status(sha, "pending")
            errors = validate(current.get("body") or "", "pr")
            latest = api(endpoint)
            if (latest.get("body"), latest["head"]["sha"], latest["state"]) != (
                current.get("body"),
                sha,
                current["state"],
            ):
                continue
            status(sha, "failure" if errors else "success")
            return report(errors)
        return report(["PR changed during validation; rerun the latest event"])
    current = api(endpoint)
    names = {label["name"] for label in current["labels"]}
    categories = names & {"bug", "enhancement"}
    errors = (
        validate(current.get("body") or "", "bug" if "bug" in categories else "feature")
        if len(categories) == 1
        else ["Issue needs exactly one category: bug or enhancement"]
    )
    if errors and current["state"] == "open":
        # Change only triage roles so concurrent category/area additions survive.
        if "needs-info" not in names:
            api(endpoint + "/labels", method="POST", payload={"labels": ["needs-info"]})
        for role in sorted((names & ROLES) - {"needs-info"}):
            api(endpoint + "/labels/" + role, method="DELETE")
    return report(errors)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--github", action="store_true")
    mode.add_argument("--kind", choices=["pr", "bug", "feature"])
    parser.add_argument("--body-file", type=Path)
    args = parser.parse_args()
    try:
        if args.github:
            event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
            return github_check(
                event, os.environ["GITHUB_EVENT_NAME"], os.environ["GITHUB_REPOSITORY"]
            )
        if args.body_file is None:
            parser.error("--kind requires --body-file")
        return report(validate(args.body_file.read_text(), args.kind))
    except (ValueError, KeyError, IndexError, OSError, subprocess.CalledProcessError) as exc:
        # Do not dump the untrusted body, API response or credentials into workflow commands.
        return report(
            [f"Validator could not complete ({type(exc).__name__}); check configuration/API access"]
        )


if __name__ == "__main__":
    raise SystemExit(main())
