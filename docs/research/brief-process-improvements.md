# Brief creation: test the decisions between intake and pixels

Research date: 2026-11-10. Process research and proposed experiments, not implementation or logo qualification. External sources below were checked live; local observations describe this working tree, including uncommitted work. No renders were made for this note. One compact Jev source-screening call is disclosed below.

## Finding and current baseline

The next useful intervention is a small **decision-to-image pilot**: demonstrate that a clarification changes a consequential design choice, that exploration produces different visual arguments, and that a selected argument survives construction and actual-size applications. Another longer questionnaire or another pass on the same explanatory prose would not establish this.

The repository already has substantial prior research on conversation, evidence separation, frozen requirements and detail ledgers: [brief-creation-design](brief-creation-design.md), [brief-creation-pipeline](brief-creation-pipeline.md), and [Rootshare brief/craft](rootshare-brief-and-craft.md). Some of their implementation-gap statements are historical. Current [briefing.py](../../logo_maker/briefing.py) validates source excerpts, claim statuses and requirement origins, separates business from design direction, rejects essential unresolved facts, records review outcomes and binds a freeze to input hashes. Its follow-up routing selects one failed dimension using a fixed priority; it does not itself demonstrate the value of the resulting owner question. Current [eligibility.py](../../logo_maker/eligibility.py) also vetoes explicit overall rejection. These are directly inspected code observations, not claims that all public behavior has been verified.

The [architecture](../architecture.md#brief-evidence-review-and-frozen-requirements-2) now specifies concept plans and detail review. Treat those as an adopted contract; this note does not claim the entire plan workflow is implemented. The [authoring skill](../../skills/logo-maker/SKILL.md) still describes a short infer-and-intake flow and twenty text metaphors. This makes the handoff from reviewed requirements to visibly different authored alternatives the practical place to test next. The accepted [motif/treatment ADR](../adr/0001-motif-plus-treatment.md) remains the identity constraint: one flat master supplies the hero contours. No ADR reversal is proposed.

## What primary sources support—and what they do not

1. GOV.UK distinguishes the questions a team needs answered from the questions it actually asks participants, then prioritizes the former. Its interview guidance recommends open, neutral prompts, concrete stories and clarifying follow-ups. This supports translating a failed review dimension into a useful conversation rather than presenting an internal rubric question verbatim. It is service-research practice guidance, not an experiment on logo briefs. [Capturing research questions](https://www.gov.uk/service-manual/user-research/capturing-research-questions), [Using in-depth interviews](https://www.gov.uk/service-manual/user-research/using-in-depth-interviews).
2. Design Council describes discovery with affected people, definition of the challenge, development of different answers and testing. This supports returning to a mistaken problem definition; it does not imply that all unknowns must be resolved before any visual exploration. [Double Diamond](https://www.designcouncil.org.uk/resources/the-double-diamond/).
3. Pentagram reports exploring materially different Slack directions before retaining the octothorpe and addressing reproduction/context problems. This illustrates a useful distinction between exploring a new proposition and refining existing equity. It is a first-party project account, without a controlled baseline or general acceptance effect. [Slack](https://www.pentagram.com/work/slack).
4. IBM distinguishes midfidelity agreement on a proposed experience from delivery reviews using the actual working solution. It also distinguishes users from buyers and stakeholders. The corresponding logo-process inference is to review representative actual applications separately from attractive presentations, and to avoid treating an owner interview as audience research. IBM's software practice is not direct evidence that this logo workflow works. [Enterprise Design Thinking framework](https://www.ibm.com/training/enterprise-design-thinking/framework).

No retrieved primary source establishes an optimal number of questions, metaphors, details, or logos; a universal advantage of literal symbolism; or that adding a provenance record improves accepted logo quality. The proposed counts below are bounded pilot choices.

## Proposed workflow: use the existing freeze, improve what surrounds it

### 1. Translate gaps into questions with visible consequences

Before interrupting the owner, write a small internal table: unresolved issue; existing evidence; two plausible answers; what each answer would change; urgency. If both answers lead to the same next authoring action, defer the question. This is a proposed practical test, not a semantic quality gate or numeric information-gain estimate.

| Internal uncertainty | Owner-facing prompt | Different consequences to record |
| --- | --- | --- |
| Category confusion | “Describe a recent person using this service. What did they do, and what might someone mistake the service for?” | If mistaken for a retailer, explore a shared-resource relationship; if mistaken for a technical catalog, emphasize approachable participation. Both are hypothetical until answered. |
| Initial is mandate or proposal | “Where did the R direction come from, and what about it must survive?” | An explicit mandate constrains exploration; an agent proposal leaves non-initial concepts open. Do not erase a confirmed mandate. |
| Meaning of “more detail” | Show the rejected image beside two targeted crops: “Which relationship feels unresolved here?” | An unresolved proportion calls for contour studies; an implausible insert calls for construction work. If the owner cannot diagnose it, preserve the overall rejection and let the designer investigate. |

Ask the open prompt before presenting suggested interpretations. Read back the answer, the interpretation, and the affected requirement separately. Owner statements establish owner intent; they do not automatically prove customer behavior. Reuse sourced facts and allow “unknown” or “designer to explore.” This operationalizes the neutral-question guidance without turning intake into a design exam for the owner.

### 2. Freeze the brief, then make a portfolio of arguments

Use the existing review/freeze mechanism. Keep a short human readback: activity, priority, primary encounter, mandates, latitude and unresolved optional choices. Do not add a new mandatory artifact just to repeat hashes already retained by code.

For the pilot, author three distinct flat arguments before expanding treatments. For each, retain a one-sentence hypothesis, one visible mechanism, one likely confusion and the evidence that could reject it. Require a visual difference in topology, silhouette, typographic construction or relationship—not merely a different material or a more persuasive metaphor description. A wordmark or nonliteral solution is legitimate where the approved brief permits it.

The new diagnostic is **portfolio coverage**: inspect the actual flat sheets together and name which different decisions they test. Ten finish variants of one R are one semantic direction for this purpose. Do not impose artificial novelty if an owner mandate narrows the space; record that restriction. The twenty-metaphor text step can remain useful raw exploration, but its count is not evidence of visual breadth. This recommendation is a process hypothesis derived from the repo's combinatorial pool and the Slack case, not a new pool algorithm.

### 3. Review identity before finish; examine craft risks before polishing everything

Show matched flat masters and real-size required applications first, without author rationales or model scores. Ask for an unprompted description and relevant confusions, then reveal the brief and assess fit. A logo need not independently explain a complete service. Record what the image carries, what the name/context carries, and what only its rationale supplies. Preserve all three responses rather than replacing the initial response after explanation.

For a selected direction, use the architecture's plan/detail ledger. Add one proposed field to the manual pilot, **highest-risk visual claim**: for example, “these two forms read as one deliberately assembled chamber” or “this accent reads as flush ceramic rather than a floating outline.” Identify the image region and scale where that claim can be inspected.

Run one bounded probe addressing that risk before a full polish pass: change only the seating construction while holding motif, camera, framing, finish and lighting constant where feasible. Retain the unchanged control. A diagnostic clay view can distinguish contour/construction work from material work, but cannot itself qualify the final appearance. This is a cheaper diagnosis proposal, not authorization to weaken GPU execution policy or to accept lower-resolution substitutes as finals.

### 4. Make critiques predict the next visible change

For each actionable critique record: dimension; exact image/region; observation; suspected cause; planned change; expected visible effect; unchanged factors; result. Keep observation separate from diagnosis: “edge transition appears uneven” does not establish insufficient samples. If the change does not produce the expected effect, revise the diagnosis instead of adding unrelated details.

Example: a pale boundary appears detached; hypothesis is raised geometry without convincing contact; proposed change is a seated joint; expected effect is an intentional material transition at the delivered hero size. None of those sentences asserts owner agreement or successful craft. The actual before/after images decide whether this experiment helped.

### 5. Validate actual outputs on independent dimensions

Use exact retained image hashes and corresponding frozen inputs. For craft, compare each candidate independently with **both Chief original and Chief reconstruction, in both presentation orders**. Include appropriate whole-image and native-pixel detail evidence under existing rules. Keep both finishes' own intended treatments explicit; neither becomes Rootshare's design vocabulary or a preferred finish.

Collect separate records for craft, business/communication fit, intended-appearance fit, aesthetic preference, technical image acceptance and rendering-policy failures. Preserve overall owner approval/rejection separately. Missing dimensional labels stay unknown. A failed GPU execution check is an operational error, not “bad craft”; strong brief fit cannot compensate for weak craft; preference cannot qualify an ineligible image. A pleasing rationale or a relative tournament win is insufficient.

Present owner review blind to workflow, author rationale and model scores where practicable. Obtain fresh judgments on the exact submitted images; Chief's owner craft approval never transfers to a candidate. Rootshare's overall rejection never creates a separate owner fit or craft label. Rewriting a description cannot turn unchanged rejected pixels into an improved artifact.

## Prioritized minimal changes to try

| Priority | Pilot change | Why this is additional to prior research | Immediate measure |
| --- | --- | --- | --- |
| P0 | Question consequence table for only the next unresolved decision | Tests whether a follow-up helps authoring, beyond identifying a missing field | Questions that changed a recorded decision; owner correction/burden; questions answered by existing evidence |
| P0 | Three actual flat arguments and portfolio review before finish expansion | Distinguishes visual exploration from metaphor count and material combinations | Number of distinct decisions tested; observed confusions; rejected directions retained |
| P1 | One predeclared high-risk construction probe with unchanged control | Turns “more detail” into a falsifiable visible intervention | Predicted vs observed effect; region/scale; authoring and render cost |
| P1 | Delayed rationale review and matched application sheet | Measures dependence on explanation and presentation | Initial vs post-rationale responses, separately retained; fit at declared encounters |
| P2 | Critique-to-change record | Makes iterative craft work traceable rather than additive | Resolved vs unresolved observations and failed diagnoses |

Start manually; do not ship new questions, thresholds or schemas until the pilot shows which records help. Any adopted contract change goes through architecture first. Update the authoring skill only once its actual workflow is settled; that is outside this note's editing scope.

## Concrete experiments and stop rules

**A. Development pilot.** Use Rootshare, preserving rejected bytes, feedback and original brief. Measure what targeted clarification actually changes, then produce three flat studies and one bounded construction probe. This can establish feasibility and reveal another failure; Rootshare is repeatedly tuned development data and cannot be a holdout. Report zero qualifying outputs plainly if all fail. A more detailed plan without better actual images is a process artifact, not success.

**B. Economical paired development run.** After the manual pilot, use three development briefs to compare current evidence/freeze workflow against evidence/freeze plus decision-consequence questions and portfolio review. Pair by brand; hold authoring time, number of authored directions, render opportunities, craft floors and review opportunity equal. Blind reviewers to process and scores, randomize presentation order, and collect reactions before revealing rationale. Predeclare failure: no improvement in independently reviewed actual outputs, more false advancement of rejected images, failure against either craft floor, unresolved essential fit/appearance, exceeded budget, or a gain that exists only after explanation. Keep ambiguous and no-qualifying-candidate outcomes. Structural/evidence completeness is a process measure; it cannot create an automatic pixel-quality pass. Changing every stage simultaneously would make attribution impossible. Record clarification cost and failed hypotheses, not just the chosen winner.

**C. Reserve an untouched brand before tuning.** Freeze an entire previously unused brand/brief and its owner requirements; do not hold out only a finish or another image of Rootshare. Use a different intended material where the qualification contract requires transfer. Predeclare outcomes, preserve exact images, blind review, counterbalance order, and require both independent Chief comparisons and fresh owner judgments. Report per-brand outcomes and uncertainty; a tiny pilot supports operational learning rather than a general causal claim.

**D. Negative controls.** Retain one identical image under a plain and a flattering rationale as a diagnostic only. If judgments change, investigate framing sensitivity; do not qualify the image by selecting favorable wording. Also retain: short sufficient brief; verbose generic brief; contradictory mandates; optional unknown; confirmed initial mandate; polished wrong identity; good fit/weak craft; wrong intended finish; renderer-policy failure; missing owner feedback; and no qualifying candidate. Do not train or tune on holdout responses. No positive owner override or fixture relabeling is proposed.

Primary result: accepted actual artifacts under the predeclared independent gates, with false advancement of rejected images explicitly counted. Process measures—fewer unsupported claims, useful questions, broader exploration, and cheaper diagnosis—are secondary and may improve while logo acceptance does not. No live qualification outcome, transfer success, or solved calibration is claimed here.

## Uncertainty and conflicting pressures

Freezing protects against rationalizing a result, but must allow an explicit evidence-driven reopening when an early study exposes a mistaken requirement. Preserve the old revision and reason; do not retroactively make the old image pass. Wider exploration can waste effort when mandates are narrow; question tables can become bureaucracy; matched flat sheets can understate the value of a treatment central to a particular brief. Those are reasons to compare process cost and actual outcomes, not to turn this proposal into universal mandatory gates.

Audience first impressions, owner taste and studio craft are different evidence. A small unprompted-description exercise does not establish market distinctiveness or comprehension rates. The cited sources offer practice guidance and one studio case, not controlled evidence that these interventions improve this system. Current implementation and prior research coexist in a changing working tree; all adoption and completion claims require fresh code and image verification.

## Source-screening record

Compact cited primary excerpts and the raw screen result are retained in [research-process-sources.json](../../logos/issue-2-completion/research-process-sources.json). Screening was retrospective: the sources had already been read and interpreted, so this was not a screen-first execution. The batched screen returned `pass` with injection 0.20, substance 0.98 and relevance 0.81; usage was 980 input / 57 output tokens. It returned no price, so cost is unknown rather than zero. This is a screening signal, not claim verification or evidence of improved logos. Parent research review owns cross-note claim verification and the final research-only completion judgment.

Parent review separately screened the supplemental IBM and Design Council excerpts before reading them (`pass`, injection 0.03), then verified eleven bounded source claims across both new notes. All were supported, with no contradicted, unsupported or review results (minimum confidence 0.89). This checks source relationships, not whether the proposed process improves logos. No rendering, owner study or eligibility result is claimed.
