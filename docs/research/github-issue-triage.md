# GitHub issue triage in graphics projects

Research date: 2026-11-10. Primary sources inspected: official repository issue templates, contribution guidance and GitHub label APIs for BlenderProc, CadQuery and Manim. These are configuration snapshots, not an audit of actual maintainer behavior. Triage cadence, response times, and consistent label application were not assessed.

## Observed practice

### BlenderProc: distinguish an incoming report from a confirmed bug

The **Bug or Question** form declares `question`, requires a minimal code example, expected versus actual behavior and BlenderProc version, and makes supporting input files optional. The feature form declares `enhancement`; blank issues are disabled. This is explicit intake configuration, not evidence that maintainers subsequently validate every report. Sources: [bug form](https://github.com/DLR-RM/BlenderProc/blob/main/.github/ISSUE_TEMPLATE/bug_report.yml), [feature form](https://github.com/DLR-RM/BlenderProc/blob/main/.github/ISSUE_TEMPLATE/feature_request.yml), [chooser configuration](https://github.com/DLR-RM/BlenderProc/blob/main/.github/ISSUE_TEMPLATE/config.yml).

The catalog includes `bug`, `bug?`, `no_script_provided`, `no_data_provided`, `third party bug`, `Apple M1 Problem`, and `good first issue`. These names expose useful distinctions: uncertainty, missing evidence, dependency ownership and platform. Most have empty descriptions, so names alone cannot establish precise maintainer rules. Source: [label API](https://api.github.com/repos/DLR-RM/BlenderProc/labels?per_page=100).

### CadQuery: request evidence appropriate to geometry failures

The exception/crash template declares `bug` and requests a minimal reproducer, Python/native backtraces and environment details. It explicitly describes the template as a suggestion. The modelling-question template declares `question` and asks for small, runnable examples. The chooser links documentation, GitHub Discussions and a mailing list. Sources: [crash template](https://github.com/CadQuery/cadquery/blob/master/.github/ISSUE_TEMPLATE/exception_crash_report.md), [modelling question](https://github.com/CadQuery/cadquery/blob/master/.github/ISSUE_TEMPLATE/modelling-question.md), [chooser configuration](https://github.com/CadQuery/cadquery/blob/master/.github/ISSUE_TEMPLATE/config.yml).

The catalog includes `no_MRE`, `cannot reproduce`, `OCC kernel issue`, `Priority:high`, and `good first issue`. It also contains both `help wanted` and `helpwanted`, illustrating why copying a mature catalog wholesale can import overlapping names. Source: [label API](https://api.github.com/repos/CadQuery/cadquery/labels?per_page=100).

### Manim: collect visual evidence and separate installation intake

Manim has distinct bug, installation and feature templates. The bug template asks for reproduction code, rendered media, logs and system details; the installation template asks for full installation output and checks against installation guidance. Sources: [bug template](https://github.com/ManimCommunity/manim/blob/main/.github/ISSUE_TEMPLATE/bug_report.md), [installation template](https://github.com/ManimCommunity/manim/blob/main/.github/ISSUE_TEMPLATE/installation_issue.md), [feature template](https://github.com/ManimCommunity/manim/blob/main/.github/ISSUE_TEMPLATE/feature_request.md).

The catalog defines `issue:bug` for issues and `pr:bugfix` for fixes in PRs; it also has `installation`, `performance`, `opengl`, `cairo`, and `needs discussion`. The bug template literally declares `bug`, whereas the fetched catalog lists `issue:bug`: verify template references against existing labels before adopting this pattern. This observation does not establish how GitHub handles that declaration at submission time. Source: [label API](https://api.github.com/repos/ManimCommunity/manim/labels?per_page=100) and the bug template above.

Manim's contribution guide points contributors to a development project board and warns that a major refactor limits feature acceptance. This is a reminder to make current acceptance policy explicit; it is not a policy recommendation for logo-maker. Source: [contribution guide](https://github.com/ManimCommunity/manim/blob/main/docs/source/contributing.rst).

## Recommendations for logo-maker

These are proposed local rules, not claims about the three projects' actual workflows.

Follow the explicitly invoked setup skill's canonical workflow rather than importing another project's taxonomy. Map its five triage roles to `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, and `wontfix`; assign exactly one role per triaged issue. `needs-info` means progress is waiting on a specific answer from the reporter. `ready-for-human` means design choices or human judgment are pending, even when the report already contains sufficient evidence.

Use `bug` or `enhancement` as the canonical category required by that workflow. Existing `documentation` and `question` labels can remain optional descriptors; they do not replace the canonical category or triage role. Native open/closed state records lifecycle and milestones record release scope.

| Concern | Local recommendation | Boundary |
| --- | --- | --- |
| Triage role | Exactly one of the five roles above | Do not combine waiting for reporter information with pending human design decisions. |
| Category | `bug` or `enhancement` | A bug violates intended behavior; an enhancement changes it. Optional descriptors add context. |
| External dependency | Native dependency links where applicable; otherwise a linked upstream issue | A possible optional `external-blocker` descriptor is a brainstorm, not another triage role. |
| Contributor readiness | Existing `good first issue`, `help wanted` descriptors | Newcomer suitability requires a bounded task and a starting point; help wanted need not be easy. Neither replaces the triage role. |

The initial recommendation was to defer area and validation labels until useful filtering needs emerged. On 2026-11-10, the maintainer requested adoption of the eight-label shortlist below. These labels supplement the canonical triage roles; current usage rules live in [the triage configuration](../agents/triage-labels.md).

For bug intake, request the exact command, version/commit, a minimal shareable brief or motif, expected and actual output, logs and relevant environment details. Rendering reports should include an image and GPU/renderer details; install failures should include doctor output and installation logs. Avoid making every reporter provide every rendering field.

Triage should first decide scope and reproducibility, then the canonical category and single triage role; request missing evidence with a concrete question. Link duplicates to the canonical issue. Attach an upstream link before declaring an external blocker. Close with a reason and reopen when new evidence changes the decision. Avoid severity or priority labels until their owner and decision rules are defined.

Validate every template's declared label against the repository catalog. Keep label descriptions explicit enough to distinguish symptom, ownership and readiness. Research itself changed no GitHub issues; the subsequent label adoption is recorded above.

## Jev-assisted label brainstorm

Jev ranked 15 proposed additions against this repo's pipeline, existing labels,
actionability, overlap and maintenance burden. These are model judgments of
usefulness, not measured workflow outcomes; the ranking does not decide what to
create. The shortlist keeps routing and verification separate.

| Candidate | Relevance judgment | Intended use |
| --- | --- | --- |
| `area:installation` | 0.96 | Setup, doctor, tool discovery and dependency compatibility. |
| `area:exports` | 0.94 | Export formats, transparency, dimensions and packaging. |
| `area:motifs` | 0.92 | SVG masters, contours and geometry conversion. |
| `area:rendering` | 0.91 | Scenes, materials, lighting and GPU rendering defects. |
| `area:judging` | 0.87 | Jev questions, scores, rankings and QA decisions. |
| `area:workflow` | 0.82 | Stage orchestration, resumability, CLI and MCP contracts. |
| `needs:gpu-validation` | 0.88 | An actual GPU render or visual regression check remains. |
| `needs:live-jev` | 0.85 | A provider-backed Jev check remains. |

Use the component responsible for a defect, rather than every downstream symptom,
when choosing an area. Verification requirements can coexist with an area and a
canonical role; they do not imply a task requires a human. All eight shortlisted
labels have now been added to the repository's GitHub label catalog.

## Verification and limits

External text passed Jev screening before interpretation. Jev verified six batched source claims; two required manual review. The template/catalog naming observation was checked directly against the literal strings. The other review concerned the limitation statement: no response-time or cadence claim is made here. Recommendations are author judgment. Source links target moving branches/APIs and should be rechecked before implementation.
