# GitHub issue and PR templates for a graphics CLI

Research date: 2026-11-10. Inspected current upstream source for Manim, BlenderProc and CadQuery, plus official GitHub documentation. These are template snapshots, not measurements of submission quality or maintainer compliance. Links to upstream branches can change.

## Comparable projects

| Project | Intake evidence and enforcement | Useful PR practice |
| --- | --- | --- |
| BlenderProc | YAML **Bug or Question** requires description, minimal Python example, expected/actual behavior and version. Supporting files are explicitly optional; screenshots are suggested. It defaults to `question`. Its feature form requires the request, with a possible solution optional. | No repository-local PR template found in the inspected `.github` tree; this does not establish absence of inherited defaults. |
| Manim | Markdown bug intake asks for reproducing code, produced images/GIFs, terminal logs and environment. Separate installation intake asks for full installation output and installation-guide/FAQ checks. Markdown prompts request evidence without field validation. | Default PR template asks what changed, motivation, documentation links and reviewer checks for labels, applicable docstrings and tests. A separate bugfix template explicitly asks for regression tests. |
| CadQuery | Markdown crash intake explicitly calls itself a suggestion. It asks for a minimal example, Python traceback, native-debugger trace for crashes, installation method and environment; a pre-error model screenshot is helpful. Separate modelling intake emphasizes runnable examples. | No repository-local PR template found in the inspected `.github` tree; inherited defaults were not audited. |

Sources: BlenderProc [bug form](https://github.com/DLR-RM/BlenderProc/blob/main/.github/ISSUE_TEMPLATE/bug_report.yml), [feature form](https://github.com/DLR-RM/BlenderProc/blob/main/.github/ISSUE_TEMPLATE/feature_request.yml), [tree API](https://api.github.com/repos/DLR-RM/BlenderProc/git/trees/HEAD?recursive=1); Manim [bug](https://github.com/ManimCommunity/manim/blob/main/.github/ISSUE_TEMPLATE/bug_report.md), [installation](https://github.com/ManimCommunity/manim/blob/main/.github/ISSUE_TEMPLATE/installation_issue.md), [default PR](https://github.com/ManimCommunity/manim/blob/main/.github/PULL_REQUEST_TEMPLATE.md), [bugfix PR](https://github.com/ManimCommunity/manim/blob/main/.github/PULL_REQUEST_TEMPLATE/bugfix.md); CadQuery [crash](https://github.com/CadQuery/cadquery/blob/master/.github/ISSUE_TEMPLATE/exception_crash_report.md), [modelling](https://github.com/CadQuery/cadquery/blob/master/.github/ISSUE_TEMPLATE/modelling-question.md), [tree API](https://api.github.com/repos/CadQuery/cadquery/git/trees/HEAD?recursive=1).

## GitHub constraints

YAML issue forms support typed fields and required responses; submissions become editable Markdown. Forms are unavailable for PRs. Labels must already exist to be applied automatically. Use unique field IDs and replace corresponding Markdown templates when converting, avoiding duplicate chooser entries. [Issue-form syntax](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms).

An unrendered textarea supports attachments; setting `render` formats code but disables attachment/Markdown editing in that field. Required validation is documented for public repositories and establishes completion, not reproducibility or correctness. Current schema also documents upload fields; ordinary textareas suffice here. [Form schema](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-githubs-form-schema).

PR templates prefill the body and become available from the default branch; multiple templates require selecting one through a query parameter. A checklist is review guidance, not an executable merge gate. Keep one existing PR template. [PR-template behavior](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/creating-a-pull-request-template-for-your-repository).

## Recommended local field sets

These are recommendations grounded in the [stage contracts](../architecture.md), existing templates and [local label rules](../agents/triage-labels.md), not upstream requirements.

Replace the two existing Markdown issue templates with two YAML forms. Retain disabled blank intake; installation belongs within bug intake until volume justifies another form.

| Form | Required responses | Optional or conditional evidence |
| --- | --- | --- |
| Bug | Summary; version or commit; environment/install method; exact command and reproduction steps; expected and actual behavior | `logo-maker doctor` output or an explanation that the CLI cannot start; minimal shareable `brief.toml`, `motif.py`/`motif.svg` and `scene.toml` as applicable; terminal traceback, relevant `run.json` and `qa/rounds.jsonl`; images/contact sheet for visual failures; GPU/renderer details for rendering; install command and full output for setup failures. |
| Feature | User problem; desired observable result or acceptance example | Proposed command/field/export, alternatives and constraints, relevant stage, links or media. Implementation design remains optional. |

Use a plain textarea for attachments and a separate code-formatted textarea for logs. Ask reporters to explain unavailable evidence; do not require renders for installation failures or credentials for judging failures. Request a minimal shareable reproducer and redact secrets/private client material. An optional component hint should include an unknown choice and must not pretend to automatically apply area labels.

Default bug intake to `needs-triage` + `bug`, feature intake to `needs-triage` + `enhancement`. Maintainers determine responsible areas: `area:installation`, `area:exports`, `area:motifs`, `area:rendering`, `area:judging`, `area:workflow`. Preserve exactly one triage role among `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. Apply `needs:gpu-validation` or `needs:live-jev` only when that check remains outstanding; neither implies human-only work. Do not add routing automation for dropdown responses.

Retain the PR template's **Summary**, **Evidence**, and **Merge Danger** structure. Request linked issue, resulting behavior, actual commands/results and outstanding checks. For applicable changes, record `just test`, `just lint`, `just type`; dependency changes also need `logo-maker doctor`; render changes need before/after PNGs or a contact sheet and `just render-example`; provider-dependent changes need the relevant live check or an explicit pending result. Allow reasoned N/A for unaffected checks rather than a ceremonial all-checked list. Describe risk, affected stages and recovery in Merge Danger. Preserve geometry/font/material rendering, judge-only models and brand-neutral defaults; do not solicit AI-generated render evidence or use example brands as design references. [Repository rules](../../AGENTS.md).

## Verification and limits

Fetched sources passed Jev screening. Six source claims were verified; three lower-confidence judgments were checked directly against the quoted source fields and official documentation. In particular, Manim's reviewer checklist requests **docstrings**, while documentation-page links are a separate body section. No templates, labels, issues or automation were changed by this note; local implementation may follow separately.
