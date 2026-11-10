# Triage labels

## Canonical role mapping

| Canonical role | GitHub label | Meaning |
| --- | --- | --- |
| `needs-triage` | `needs-triage` | Maintainer evaluation is pending. |
| `needs-info` | `needs-info` | Waiting on specific information requested from the reporter. |
| `ready-for-agent` | `ready-for-agent` | Scope, acceptance criteria, and verification are specified for an agent. |
| `ready-for-human` | `ready-for-human` | Requires human implementation, judgment, access, or manual verification. |
| `wontfix` | `wontfix` | Will not be actioned; explain why and close. |

Use these tracker strings whenever a skill names a canonical role. Each triaged
issue carries exactly one role and one category: `bug` or `enhancement`.
`documentation`, `question`, and contributor labels may add context. Preserve
existing labels; treat conflicting role labels as a maintainer decision.

An untriaged issue normally enters `needs-triage`, then moves to the appropriate
role. When a reporter answers a `needs-info` request, re-evaluate under
`needs-triage`. The maintainer may override transitions.

For `ready-for-agent`, attach an agent brief with reproduction or desired behavior,
acceptance criteria, relevant code pointers, and verification steps. A GPU or live
Jev check alone does not imply human-only work; record the required environment
and whether the assigned agent can access it.

Use native issue dependencies for blockers, as described in `issue-tracker.md`.

## Component areas

| Label | Use for |
| --- | --- |
| `area:installation` | Setup, doctor checks, tool discovery and dependency compatibility. |
| `area:exports` | Export formats, transparency, dimensions and packaging. |
| `area:motifs` | SVG masters, contours and geometry conversion. |
| `area:rendering` | Scenes, materials, lighting and GPU rendering defects. |
| `area:judging` | Jev questions, scoring, ranking and QA decisions. |
| `area:workflow` | Stage orchestration, resumability, CLI and MCP contracts. |

Choose the component responsible for the issue, rather than every downstream
symptom. Use multiple areas when the work actually spans those components; leave
the area unset while ownership is unknown. For example, malformed SVG contours
belong to `area:motifs`, an incorrect camera belongs to `area:rendering`, and a
wrong export size belongs to `area:exports`.

## Outstanding validation

| Label | Use for |
| --- | --- |
| `needs:gpu-validation` | An actual GPU render or visual regression check remains outstanding. |
| `needs:live-jev` | A provider-backed Jev check remains outstanding. |

These labels supplement the canonical role and component area. They can coexist
and do not imply human-only work. Record the required check and environment in
the issue; remove the corresponding label after recording the result. Apply
`needs-info` when waiting on the reporter, rather than using a validation flag as
a substitute for that role.

See `../research/github-issue-triage.md` for the research and Jev-assisted shortlist
behind these labels.
