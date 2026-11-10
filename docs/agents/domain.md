# Domain docs

This repo uses a single-context layout:

- `GLOSSARY.md` at the repository root for domain terms.
- `docs/adr/` for architecture decisions.

## Before exploring domain behavior

Read `GLOSSARY.md` when present and the ADRs relevant to the area being explored.
Read `docs/architecture.md` for stage contracts; change that document first when
changing a contract, as required by `AGENTS.md`.

If a glossary or ADR directory is absent, proceed silently. Domain-modeling work
creates them lazily when terms or decisions are resolved.

Use defined glossary terms in issues, proposals, hypotheses, and tests. When a
needed concept is missing, reconsider the terminology or record the gap for
domain-modeling work.

Surface conflicts with an accepted ADR explicitly, naming the ADR and explaining
why its decision should be reopened.
