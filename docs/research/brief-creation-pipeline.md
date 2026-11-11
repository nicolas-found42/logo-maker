# Brief creation: evidence, clarification and qualification

Research date: 2026-11-10. This note proposes a workflow; it changes no code, schemas, Jev wording, thresholds, fixtures or owner labels. The question is how to improve the information and authoring decisions upstream of a logo, without declaring a longer brief or more ornament to be quality.

## Finding

The strongest low-impact experiment is an evidence-backed brief review before ideation, followed by a separate concept and detail plan. Business facts should remain distinguishable from the designer's hypothesis and the owner's actual visual constraints. Freeze the requirements before authoring, then assess the resulting pixels against those requirements. This targets a demonstrated workflow gap; better logo outcomes remain a hypothesis requiring held-out evaluation.

Rootshare is the motivating development case. Its retained summary specifies a neighborhood seed library, then prescribes an R sheltering a seed-shaped counter. Its appearance description further specifies terracotta, softened edges and pale inlay. Fresh comparison evidence records four unsettled craft comparisons against both Chief images in both orders. Several fit judgments pass despite the owner's explicit overall rejection: “rootshare fails. needs more specific brief and more detail. compare to both chief craft logos.” Separate owner craft and fit labels remain unknown. These facts do not establish that the R is intrinsically wrong, that matte clay cannot qualify, or that the owner meant “add decoration.” [Retained calibration](../../benchmarks/omp/validation/issue-2/follow-up/rootshare-both-chief-research/calibration.json), [prior research](rootshare-brief-and-craft.md#fresh-comparison-evidence-and-follow-up-gaps).

## Current behavior and precise gaps

The loader requires nonempty name/summary and one to five tone entries, validates palette/font roles, and validates reference use/path rules. Audience is optional. It does not judge whether the business proposition is evidenced, distinctive, contradictory or sufficiently specified. `Brief.as_state()` removes empty optional fields, which is useful for compact state but does not preserve *why* information is absent: unknown, deliberately open, or irrelevant. No evidence provenance or claim-status field exists in this dataclass. [brief.py:59–134](../../logo_maker/brief.py#L59).

The authoring skill asks one form only for what cannot be inferred, naming name and audience, and calls the brief complete when intake passes. It subsequently requires intended appearance and an owner-supplied craft reference before selection. This minimizes interruption but gives no explicit checkpoint for an ambiguous brand action, an inferred visual mandate, or unsupported source claims. [SKILL.md:22–50](../../skills/logo-maker/SKILL.md#L22).

Actual intake judges style references and extracted colors, selects palettes/fonts from proposals, and records supplied settings. It is not a semantic brief review. The public pipeline requests new proposals when needed, then records intake done. This is a narrower, source-supported claim than saying the whole application has no brand-fit checks. [intake.py:34–59, 131–151](../../logo_maker/intake.py#L34), [pipeline.py:122–171](../../logo_maker/pipeline.py#L122).

Concept authoring receives metaphor/treatment/material descriptions. Metaphors currently have an id and free text; loader checks count, slug uniqueness and nonempty descriptions. The skill requests twenty distinct ideas, while the loader permits eight to forty. Neither validates a traceable relationship between an idea and a separately evidenced business requirement. Text-stage questions do assess fit, buildability and predicted small-size legibility; uncertain buildability/legibility may advance with flags. This exploration policy should not be confused with final eligibility. [ideate.py:39–82](../../logo_maker/ideate.py#L39), [questions.py:81–100, 291–341](../../logo_maker/jev/questions.py#L291), [SKILL.md:52–90](../../skills/logo-maker/SKILL.md#L52).

Final fit already asks symbol, appearance, brand specificity, meaningful synthesis, constraint fidelity, communicative clarity and small-size questions. Thus the proposal is stronger state and authoring discipline upstream, not inventing an absent final-fit concern. Craft and technical assessment are separate. The existing owner veto tests explicit craft/fit rejection; an overall-only rejection needs a future explicit representation without fabricating dimensional labels. [questions.py:483–549](../../logo_maker/jev/questions.py#L483), [eligibility.py:229–363](../../logo_maker/eligibility.py#L229).

## Primary-source implications

TypeSafe's current architecture guidance keeps workflow and effects in code, decomposes semantic work into narrow questions, supplies relevant structured state, and routes uncertainty. Its state documentation distinguishes supporting facts from questions and recommends descriptive object fields. These mechanisms support a typed brief review but do not establish what counts as a good logo. [How to build](https://docs.typesafe.ai/concepts/how-to-build-with-system-one.md), [State](https://docs.typesafe.ai/concepts/state.md).

The model's documented weaknesses include literal reading, indirection, distracting state, adversarial framing and generation. Therefore a fit request containing the already-chosen solution can plausibly reward matching that solution. This is a diagnostic hypothesis, not proof of why Rootshare received its answers. More prose can worsen the state. Keep the business proposition, visible construction and rationale separable; do not ask Jev to write the missing brief. [Model jaggedness](https://docs.typesafe.ai/model-jaggedness.md).

A Choice always picks among supplied options. A companion Noul establishes whether any option fits before code consumes that pick. Apply this to candidate follow-up questions or proposed directions, rather than forcing a winner when none addresses the missing information. TypeSafe's extraction cascade similarly separates generated structured data from field-level checks and escalation. Neither pattern makes unsupported source claims true. [Companion Noul](https://docs.typesafe.ai/patterns/companion-noul.md), [SDE cascade](https://docs.typesafe.ai/cookbooks/sde_cascade.md).

For the complementary intake conversation and design exercises, see [brief-creation-design.md](brief-creation-design.md). The technical proposal here supports that conversation rather than replacing it with a long questionnaire.

## Proposed contract outline

This is an API/data sketch, **not the current schema**. Keep the established brief as the downstream projection initially; store the experiment alongside it. Any adoption must change `docs/architecture.md` first and keep question wording/options/thresholds centralized in `questions.py`.

```text
BriefEvidence
  sources[]: id, origin, revision, exact excerpt
  facts[]: id, claim, source_ids, status
      status = owner_stated | source_supported | assumption | unknown | conflict
  requirements[]: id, claim, priority, source_ids, constraint_kind
      constraint_kind = business | communication | visual_mandate | usage
  open_questions[]: id, affected_requirement_ids, candidate_question
  references[]: existing use, path/hash, note, demonstrated_property

BriefReview
  input_revision, question_revision, exact_request, raw_answers
  structural_problems[], unsupported_claim_ids[], conflict_ids[]
  semantic_sufficiency_by_dimension, unresolved_ids[], route

ConceptPlan
  requirement_revision, concept_id, hypothesis, visible_relationship
  supported_requirement_ids[], assumptions[], expected_confusions[]
  detail_ledger[]: feature, purpose, scale, construction, deletion_test
```

Preserve known absence explicitly in the evidence record. Do not send every unknown to every question: construct task-specific state projections. A missing font may remain deliberately open; an unknown actual business model is consequential if the proposed logo depicts a transaction that may not exist. Exact source spans and source revisions let reviewers distinguish extraction errors from ambiguous owner intent. Deterministic parsers should validate enums, source links, hashes and required presence before semantic calls.

“Neutral” must mean free of *unapproved designer solutions*, not free of owner direction. If the owner explicitly mandates an R, retain it as a visual requirement with provenance. If the agent proposed it, keep it in the concept plan. Likewise a real product's distinctive shape may be factual source material, whereas “this curve communicates community” is a design hypothesis. No automatic rewriting should erase intentional constraints.

## Proposed routing truth table

The following symbolic states avoid proposing new numeric thresholds. Existing final eligibility remains unchanged; a future intake experiment needs its own predeclared bands and validation.

| Evidence / judgment | Proposed action |
| --- | --- |
| Structural input invalid | Report exact field problem; no semantic call or ideation |
| Conflicting mandatory requirements | Ask one targeted resolution question; retain both claims |
| Required brand fact absent | Ask for that fact; do not infer it from selected geometry |
| Agent assertion unsupported | Remove from factual brief or mark assumption; do not present as owner mandate |
| Adequacy unsettled | Review the named gap; no automatic conversion to yes |
| Adequacy no, useful follow-up exists | Ask highest-impact unresolved question with answerable examples |
| Adequacy no, no useful question found | Explain missing evidence; request owner description rather than forced Choice |
| Adequacy yes, all required conflicts resolved | Freeze requirement revision; permit ideation |
| Optional detail unknown, adequacy otherwise yes | Proceed with explicit design latitude |
| Provider error / malformed result | Operational error; no semantic fail/pass label |
| Owner explicitly rejects current artifact overall | Stop delivery/advancement; retain dimensional unknowns and seek targeted diagnosis |

A generic-brand substitution is a useful diagnostic: would the same rationale fit a materially different business unchanged? It is not a hard failure rule; wordmarks and nonliteral identities can succeed without pictorially explaining a service. Annotate references by transferable dimension and contrast desired impressions with specific unwanted confusions.

A practical form asks at most the questions that change the next authoring decision: “What do people do here that the identity should emphasize?”, “What should viewers confuse it with least?”, “Which visual choices are mandatory versus suggestions?” Source-backed repository facts can answer these without another user interruption. Examples should demonstrate answer shape without suggesting invented features. For Rootshare, return obligations, provenance tracking or local adaptation remain unknown unless confirmed.

## Detail as an authoring plan

After freezing business requirements, the agent proposes several visibly different relationships before committing to material polish. Each detail has a purpose, intended scale and deletion test. Primary semantic relationships belong in the shared flat motif; hero-only depth and material refinements may support the same identity. This preserves the accepted motif-plus-treatment ADR rather than requiring microscopic detail in a favicon. [ADR 0001](../adr/0001-motif-plus-treatment.md).

For example, distinguish the requirement “express a neighborhood resource held in common” from the proposed mechanism “two parts create one protected chamber.” Then specify whether a pale ceramic element is flush inlay, recessed slip or applied relief; identify the joint, contact, edge profile and material boundary needed to make that construction convincing. These are candidate decisions, not newly established Rootshare facts. A controlled counter and bowl/leg junction may be more valuable detail than additional grain or lettering. Test deletion: if removing the feature changes neither meaning, hierarchy nor material credibility, its necessity is doubtful.

Keep separate review views: owner/business facts for requirement sufficiency; flat shapes for visual proposition; motif plus intended treatment for construction; actual rendered pixels and both Chief floors for craft. Candidate explanation can establish authoring intent but cannot prove viewers perceive the relationship. A useful experiment elicits an unprompted description before showing the rationale, while avoiding an impossible demand that a logo communicate an entire service without context.

## Phased experiments and evaluation

**Phase A: no-runtime-change pilot.** Manually author evidence and concept-plan sidecars for several development brands. Review current briefs using a checklist; record questions asked, assumptions removed and whether requirements changed before authoring. This reveals workflow burden without shipping a new gate. Rootshare is explicitly development data after repeated owner feedback and probes; it cannot now supply an untouched holdout.

**Phase B: shadow judgments.** On a separately authorized bounded live budget, judge frozen intake records without controlling advancement. Compare structural-only, evidence-backed, and evidence-plus-targeted-follow-up workflows. Retain exact payloads and error/uncertainty states. Test whether model answers track independently labeled sufficiency, not whether they agree with the author. Generate question text with an authoring model or templates; Jev judges bounded candidates. Never repeatedly reword a failed case until it returns the desired probability.

**Phase C: paired authoring trial.** Split by *brand*, not image, material variant or rewritten brief. Reserve entire owner-approved briefs and brands unseen during workflow development. Freeze business requirements and evaluation rubrics before any candidate authoring. Compare existing and proposed intake with equal authoring time, concept opportunities, render budget, hardware policy and review opportunities. Randomize paired presentation order and blind reviewers to workflow, author narrative and model scores where practical. Keep both Chief craft references as independent floors; their identities must not become design defaults.

Collect independent owner craft, business/communication fit, intended-appearance fit and preference labels, allowing unknown and no preference. Preserve explicit overall rejection too. Do not infer craft fail from dislike or preference success from fit. Report per-brand results and missing cases, then paired differences and uncertainty appropriate to the small sample. Primary outcomes: owner acceptance under declared requirements, false advancement of rejected artifacts, independently labeled fit improvement, and whether *both* craft floors qualify. Secondary outcomes: clarification burden, unsupported-claim rate, contradiction detection, authoring/render cost, unresolved/error rate and time to a reviewable candidate. Word count, number of details, polygon count and Jev confidence are diagnostic measurements, never success metrics.

Required counterexamples include: eloquent but generic business prose; very short yet sufficient briefs; owner-mandated monograms; deliberately open material choices; contradictory requirements; invented service features; a polished category icon; a strong fit with weak craft; excellent craft with wrong identity; matte and glossy successes; copied reference styling; a narrative that changes while pixels stay fixed; and a brief rewritten after seeing its result. Include absent-source and provider-error cases. A pixel-identical candidate should not become evidentially better because its rationale becomes more flattering. Transfer remains unproven until held-out owners judge actual outputs.

Keep GPU tracing and effective GPU denoising evidence mandatory for production-eligible renders. CPU scene construction, submission, analysis and file I/O remain allowed. Hardware provenance, technical image acceptance, craft, fit and preference remain independent. No positive owner override, threshold tuning, or fixture relabeling is proposed. [Architecture contracts](../architecture.md#render).

## Source handling and limits

Behavioral discovery began with `jg` at the explicit repository root, using the required 8000-request cap and concurrency 20; it completed with `End context.` Focused source reads established the claims above. External pages were screened before interpretation. Companion-Noul and jaggedness pages returned `review` (injection 0.38); inspection found documentation instructions, examples and navigation, with no unresolved credential request or tool redirection used as authority. Web retrieval failures for several Markdown pages were recovered with bounded direct HTTP GETs. Source claims support architectural mechanisms, not guaranteed improvements in logo acceptance. This research makes no implementation or calibration claim.

A six-claim Jev source verification returned six `verified`, zero contradicted/unsupported, with three requiring review (confidence 0.73–0.77). Direct inspection resolves their scope: the skill's “done” statement applies to the brief check, not final selection; owner veto is the explicit craft/fit conditional, not an overall-feedback override; Rootshare's owner dimensional labels remain unknown. These review results are retained rather than promoted to automatic acceptance. [Local verification record](../../benchmarks/omp/validation/issue-2/follow-up/rootshare-both-chief-research/brief-pipeline-verification.json).
