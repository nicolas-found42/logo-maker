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
IMAGE = re.compile(r"(?<!\\)!\[[^\]\n\x00]*\]\(\s*<?(https://[^\s)>\x00]+)>?(?:\s+[^)\x00]*)?\)")
REFERENCE_IMAGE = re.compile(r"(?<!\\)!\[([^\]\n\x00]*)\](?:\[([^\]\n\x00]*)\])?(?!\()")
REFERENCE = re.compile(r"^ {0,3}\[([^\]]+)\]:\s*<?(https://[^\s>]+)>?", re.MULTILINE)


@dataclass
class Section:
    level: int
    title: str
    parent: str | None
    body: str


def _uncomment(text: str) -> str:
    return COMMENT.sub("", text).replace("\r\n", "\n").replace("\r", "\n")


def outside_code(text: str) -> str:
    """Blank fenced/indented code while keeping line positions for heading parsing."""
    lines = _uncomment(text).split("\n")
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
    clean = _uncomment(text)
    lines = clean.split("\n")
    headings = []
    stack: list[tuple[int, str]] = []
    for index, masked_line in enumerate(noncode_prose(clean).split("\n")):
        if not HEADING.match(masked_line):
            continue
        match = HEADING.match(lines[index])
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
    clean = _uncomment(text)
    lines = clean.split("\n")
    for index, masked_line in enumerate(noncode_prose(clean).split("\n")):
        if HEADING.match(masked_line) and HEADING.match(lines[index]):
            return "\n".join(lines[:index])
    return clean


def _find_tag_end(text: str, start: int) -> int:
    """Find closing '>' of an HTML tag starting at `start`, respecting quoted attributes."""
    quote = ""
    index = start
    while index < len(text):
        char = text[index]
        if quote:
            if char == quote:
                quote = ""
        elif char in {'"', "'"}:
            quote = char
        elif char == ">":
            return index
        index += 1
    return -1


def _strip_tags(text: str, names: tuple[str, ...]) -> str:
    """Strip opening/closing HTML tags in `names`, respecting quoted '>' in attributes."""
    pattern = re.compile(r"(?is)<(/?)(" + "|".join(names) + r")(?=[\s/>]|\Z)")
    parts: list[str] = []
    cursor = 0
    while match := pattern.search(text, cursor):
        gt_pos = _find_tag_end(text, match.end())
        if gt_pos == -1:
            break
        parts.append(text[cursor : match.start()])
        cursor = gt_pos + 1
    parts.append(text[cursor:])
    return "".join(parts)


def _is_unescaped_backtick_run(text: str, start: int) -> bool:
    backslashes = 0
    pos = start - 1
    while pos >= 0 and text[pos] == "\\":
        backslashes += 1
        pos -= 1
    return backslashes % 2 == 0


def _scan_inline_and_html_code(text: str, *, marker: str = "") -> tuple[str, list[str]]:
    """Mask backtick spans and <pre>/<code> blocks in linear time, returning (prose, code_chunks)."""
    paragraph_breaks = [match.start() for match in re.finditer(r"\n[ \t]*\n", text)]
    backtick_runs: list[tuple[int, int, int]] = []
    para_id = 0
    for match in re.finditer(r"`+", text):
        start, end = match.start(), match.end()
        if not _is_unescaped_backtick_run(text, start):
            continue
        while para_id < len(paragraph_breaks) and paragraph_breaks[para_id] < start:
            para_id += 1
        backtick_runs.append((start, end, para_id))
    runs_by_key: dict[tuple[int, int], list[int]] = {}
    for run_idx, (run_start, run_end, run_para) in enumerate(backtick_runs):
        runs_by_key.setdefault((run_end - run_start, run_para), []).append(run_idx)
    key_cursor: dict[tuple[int, int], int] = dict.fromkeys(runs_by_key, 0)
    tag_pattern = re.compile(r"(?is)<(/?)(pre|code)(?=[\s/>]|\Z)")
    raw_tags: list[tuple[int, bool, str, int]] = []
    tag_cursor = 0
    while match := tag_pattern.search(text, tag_cursor):
        is_close = match.group(1) == "/"
        name = match.group(2).casefold()
        gt_pos = _find_tag_end(text, match.end())
        if gt_pos == -1:
            break
        raw_tags.append((match.start(), is_close, name, gt_pos))
        tag_cursor = gt_pos + 1
    prose_parts: list[str] = []
    code_chunks: list[str] = []
    cursor = 0
    bt_index = 0
    tag_index = 0
    while cursor < len(text):
        while bt_index < len(backtick_runs) and backtick_runs[bt_index][0] < cursor:
            bt_index += 1
        while tag_index < len(raw_tags) and raw_tags[tag_index][0] < cursor:
            tag_index += 1
        next_inline: tuple[int, int, str] | None = None
        scan_bt = bt_index
        while scan_bt < len(backtick_runs):
            open_start, open_end, open_para = backtick_runs[scan_bt]
            key = (open_end - open_start, open_para)
            positions = runs_by_key[key]
            pos_cursor = key_cursor[key]
            while pos_cursor < len(positions) and positions[pos_cursor] <= scan_bt:
                pos_cursor += 1
            key_cursor[key] = pos_cursor
            if pos_cursor < len(positions):
                close_idx = positions[pos_cursor]
                close_start, close_end, _ = backtick_runs[close_idx]
                next_inline = (open_start, close_end, text[open_end:close_start])
                bt_index = scan_bt
                break
            scan_bt += 1
        else:
            bt_index = len(backtick_runs)
        next_tag = raw_tags[tag_index] if tag_index < len(raw_tags) else None
        if next_inline and (next_tag is None or next_inline[0] < next_tag[0]):
            start, end, inner = next_inline
            prose_parts.append(text[cursor:start])
            prose_parts.append("\n".join(marker for _ in range(text[start:end].count("\n") + 1)))
            code_chunks.append(inner)
            cursor = end
            continue
        if next_tag is None:
            prose_parts.append(text[cursor:])
            break
        tag_start, is_close, tag_name, tag_gt = next_tag
        if is_close:
            end_pos = tag_gt + 1
            prose_parts.append(text[cursor:end_pos])
            cursor = end_pos
            tag_index += 1
            continue
        prose_parts.append(text[cursor:tag_start])
        inner_start = tag_gt + 1
        depth = 1
        sub_index = tag_index + 1
        inner_end = len(text)
        block_end = len(text)
        while sub_index < len(raw_tags):
            sub_start, sub_is_close, sub_name, sub_gt = raw_tags[sub_index]
            if sub_name == tag_name:
                if not sub_is_close:
                    depth += 1
                else:
                    depth -= 1
                    if depth == 0:
                        inner_end = sub_start
                        block_end = sub_gt + 1
                        break
            sub_index += 1
        prose_parts.append(
            "\n".join(marker for _ in range(text[tag_start:block_end].count("\n") + 1))
        )
        code_chunks.append(_strip_tags(text[inner_start:inner_end], ("pre", "code")))
        cursor = block_end
        tag_index = sub_index + 1
    return "".join(prose_parts), code_chunks


def noncode_prose(text: str, *, marker: str = "\x00") -> str:
    """Replace fenced/indented code, HTML pre/code blocks and inline code while keeping lines."""
    prose, _ = _scan_inline_and_html_code(outside_code(text), marker=marker)
    return prose


def field_values(text: str, field: str) -> list[str]:
    """Extract bold-labeled field values declared outside code while preserving code answers."""
    lines = _uncomment(text).split("\n")
    masked = noncode_prose(text, marker="\x00").split("\n")
    label = re.compile(r"^\*\*([^*\n\x00]+):\*\*\s*(.*)$")
    starts: list[tuple[int, str, str]] = []
    for index, line in enumerate(masked):
        if HEADING.match(line) and HEADING.match(lines[index]):
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
    text = _uncomment(text)
    unmasked_text = outside_code(text)
    prose, html_and_inline_chunks = _scan_inline_and_html_code(unmasked_text, marker="")
    prose = re.sub(r"^\s*#{1,6}\s+.*$", "", prose, flags=re.MULTILINE)
    prose = re.sub(r"<[^>]*>", "", prose)
    code_chunks = [
        line
        for line, unmasked in zip(text.split("\n"), unmasked_text.split("\n"), strict=False)
        if not unmasked
    ]
    code_chunks.extend(html_and_inline_chunks)
    code = re.sub(r"^\s*(?:`{3,}|~{3,}).*$", "", "\n".join(code_chunks), flags=re.MULTILINE)
    code = _strip_tags(code, ("img",))
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
    for line in noncode_prose(text, marker="").split("\n"):
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
    clean = noncode_prose(text, marker="\x00")
    references = {
        key.casefold(): value
        for key, value in REFERENCE.findall(noncode_prose(whole_body, marker="\x00"))
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
                masked_line.split(":**", 1)[1].replace("\x00", "").strip()
                for masked_line in noncode_prose(introduction, marker="\x00").split("\n")
                if re.match(r"^\*\*Visible app change:\*\*\s*[^\s\x00]", masked_line)
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
