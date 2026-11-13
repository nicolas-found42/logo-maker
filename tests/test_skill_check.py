"""Skill validator contract: valid YAML frontmatter, matching folder name, and live relative links."""

from __future__ import annotations

from pathlib import Path

import scripts.skill_check as skill_check

BROKEN_MAIN_SKILL = """---
name: logo-maker
description: Logos and brand marks. Use when making, redesigning, or improving a logo, app icon,
favicon set, or social avatar for any project, business, product, or profile, from an idea, a
reference image, a repository, or a brainstorm.
---

# logo-maker

Body text.
"""


def _write_skill(tmp_path: Path, content: str, *, folder: str = "logo-maker") -> Path:
    skill = tmp_path / "skills" / folder / "SKILL.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text(content, encoding="utf-8")
    return skill


def test_repo_skills_pass_validation() -> None:
    assert skill_check.validate_all() == []
    assert skill_check.main([]) == 0


def test_unindented_multiline_frontmatter_scalar_fails_with_line_and_column(tmp_path: Path) -> None:
    skill = _write_skill(tmp_path, BROKEN_MAIN_SKILL)
    errors = skill_check.validate_skill(skill)
    assert len(errors) == 1
    assert "could not find expected ':'" in errors[0]
    assert "while scanning a simple key" in errors[0]
    assert "line 4 column 1" in errors[0]
    assert skill_check.main([str(skill)]) == 1


def test_missing_frontmatter_or_empty_body_is_rejected(tmp_path: Path) -> None:
    no_fm = _write_skill(tmp_path, "# logo-maker\n\nBody.\n", folder="no-fm")
    assert any("missing opening/closing '---'" in err for err in skill_check.validate_skill(no_fm))

    empty_body = _write_skill(
        tmp_path,
        "---\nname: empty-body\ndescription: Valid description.\n---\n   \n",
        folder="empty-body",
    )
    assert any("body after frontmatter" in err for err in skill_check.validate_skill(empty_body))


def test_duplicate_or_unknown_frontmatter_keys_and_mismatched_name_fail(tmp_path: Path) -> None:
    dup = _write_skill(
        tmp_path,
        "---\nname: dup\nname: dup\ndescription: Valid.\n---\n\n# dup\n",
        folder="dup",
    )
    assert any("duplicate key 'name'" in err for err in skill_check.validate_skill(dup))

    bad_meta = _write_skill(
        tmp_path,
        "---\nname: wrong-name\ndescription: Valid.\ndisable-model-invocation: 'yes'\nextra: 1\n---\n\n# x\n",
        folder="right-name",
    )
    errors = skill_check.validate_skill(bad_meta)
    assert any("unknown frontmatter keys: extra" in err for err in errors)
    assert any("does not match skill directory 'right-name'" in err for err in errors)
    assert any("'disable-model-invocation' must be a boolean" in err for err in errors)


def test_broken_relative_link_outside_code_fails_while_code_examples_pass(tmp_path: Path) -> None:
    skill = _write_skill(
        tmp_path,
        "---\nname: link-skill\ndescription: Valid.\n---\n\n"
        "See `[ignored](missing-inline.md)` and:\n\n"
        "```markdown\n[ignored](missing-fenced.md)\n```\n\n"
        "Read [real](references/real.md#section) and [broken](references/missing.md).\n",
        folder="link-skill",
    )
    ref = skill.parent / "references" / "real.md"
    ref.parent.mkdir(parents=True, exist_ok=True)
    ref.write_text("# Real\n", encoding="utf-8")

    errors = skill_check.validate_skill(skill)
    assert errors == [f"{skill}: broken relative link target 'references/missing.md'"]


def test_link_text_wrapped_across_lines_is_still_checked(tmp_path: Path) -> None:
    skill = _write_skill(
        tmp_path,
        "---\nname: wrapped\ndescription: Valid.\n---\n\nSee [the long\nlink text](../../docs/gone.md).\n",
        folder="wrapped",
    )
    assert any("broken relative link target" in err for err in skill_check.validate_skill(skill))


SKILL_HEAD = "---\nname: logo-maker\ndescription: Logos.\n---\n\n# logo-maker\n\n"


def test_malformed_skill_files_are_reported_not_raised(tmp_path: Path) -> None:
    long_link = _write_skill(
        tmp_path, SKILL_HEAD + "[x](" + "a" * 5000 + ".md) and [y]( ) and [z](a%00.md)\n"
    )
    errors = skill_check.validate_skill(long_link)
    assert len(errors) == 2
    assert all("unusable relative link target" in error for error in errors)
    binary = tmp_path / "skills" / "other" / "SKILL.md"
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"\xff\xfe---\n")
    assert "cannot read file" in skill_check.validate_skill(binary)[0]


def test_angle_bracket_and_percent_encoded_links_resolve(tmp_path: Path) -> None:
    skill = _write_skill(tmp_path, SKILL_HEAD + "[x](<a b.md>) [y](a%20b.md#part)\n")
    (skill.parent / "a b.md").write_text("target")
    assert skill_check.validate_skill(skill) == []
