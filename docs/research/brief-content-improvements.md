# Brief content that gives the designer something consequential to decide

Research date: 2026-11-10. Content recommendations and experiments; no implementation, question, threshold, fixture or owner-label changes.

## Recommendation

Improve the brief's **decision-bearing content**, then test actual designs. Capture one real activity and audience encounter, choose what matters most in that encounter, and separate what the owner requires from what the designer proposes. Develop distinct visual arguments before resolving their construction. Additional fields, stronger provenance, longer prose and more elaborate detail do not establish better design.

This extends, rather than replaces, [brief-creation-design.md](brief-creation-design.md), [brief-creation-pipeline.md](brief-creation-pipeline.md) and [rootshare-brief-and-craft.md](rootshare-brief-and-craft.md). Those notes already recommend evidence separation, a communication priority, concept alternatives and a detail ledger. The new contribution here is a tighter content test: **what decision changes because this information is present?** New primary-source examples also show why an initial-led identity can be purposeful and why the mark need not explain the whole organization.

In the current working tree, `briefing.py` implements source-linked facts and requirements, communication priority, design latitude, evidence review and frozen requirements. Its source-excerpt checks establish traceability to the supplied record, not independent truth about an audience. Concept-plan/detail review is described in the architecture contract but is not implemented by this module; the concept-plan content recommended below remains an authoring proposal rather than a verified runtime mechanism. The recommendation is to author useful content within the existing evidence structure before adding schema, and to pilot the concept/detail plan separately. [Architecture: brief contract](../architecture.md#brief-evidence-review-and-frozen-requirements-2), [briefing.py](../../logo_maker/briefing.py), [brief.py](../../logo_maker/brief.py). Existing research documents describe earlier snapshots; their statements about absent provenance or overall owner-rejection handling must not be read as a fresh implementation audit.

## New primary-source evidence and its limits

### Actual audience evidence is different from an owner hypothesis

GOV.UK's service manual recommends learning what people are trying to do, how they currently do it and what obstructs them. It distinguishes evidence from assumptions, recommends reviewing existing records and speaking with actual users, and frames needs around problems rather than predetermined solutions. This is service-design guidance, not a controlled logo study. Its transferable lesson is to avoid converting the designer's imagined audience into an established fact. [GOV.UK: Learning about users and their needs](https://www.gov.uk/service-manual/user-research/start-by-learning-user-needs).

**Recommendation:** “Local gardeners” is a useful start, but the next valuable information is an encounter: who sees this identity, while trying to do what, beside which alternatives? An owner statement about audience intent is valid evidence of the owner's intent; it does not independently prove how gardeners perceive the brand. Source type and claim type should stay distinct. Use the available project record first; an informal project need not commission research before sketching.

### A strong monogram can solve an actual identity-system problem

Pentagram describes MIT Media Lab's challenge as combining a stable identity with flexibility. Its solution used a shared seven-by-seven grid for an ML monogram and the identities of 23 research groups. The client's brand portal separately explains that its wordmark is essential in external communications and that the glyph's M is larger than its L for legibility. These are studio/client accounts of one identity; they do not prove that grids or monograms generally outperform other approaches. [Pentagram: MIT Media Lab](https://www.pentagram.com/news/mit-media-lab), [MIT Media Lab: Brand Portal](https://www-prod.media.mit.edu/posts/MLBrandPortal/).

**Recommendation:** Avoid the default “initial plus category icon,” but do not ban initials or insist that a new business invent a unique service mechanic. Ask what an initial-led construction accomplishes: a recognizable abbreviation, a coherent family, distinctive custom lettering, a useful compact silhouette? A nonliteral identity may be appropriate. Its purpose must be evaluated through the mark and its real lockup/context rather than a decorative explanation pasted onto a standard letter.

The MIT example also argues against testing every symbol as though its standalone form must communicate the full institution. State when the full name accompanies the symbol and when it does not. Distinguish recognition, category association and comprehension of the service; they are different tasks.

### A communication priority can generate coherent detail without encoding everything

Mozilla's 2017 first-party account identifies better understanding of its purpose as the central task. It connects the URL-language wordmark, typography and surrounding identity to its Internet mission. The same account explicitly places diverse imagery in the wider system rather than expecting one icon to represent all of Mozilla and the Internet. This is historical author/client rationale, not evidence of present audience comprehension or a style to copy. [Mozilla Open Design: Arrival](https://blog.mozilla.org/opendesign/arrival/).

**Recommendation:** Separate the message the mark should lead with from information that can be carried by the name, supporting copy or applications. Specificity can reside in a carefully developed relationship, lettering or systematic construction. Requiring a seed, exchange, neighborhood, library, care and reciprocity all to be readable from a small mark risks competing visual demands. Choose a lead and test it; let supporting identity carry the rest.

## A compact authoring conversation

These are proposed authoring prompts, not new production Jev questions. Ask only unresolved questions that change the next decision; reuse evidence already supplied.

| Content to resolve | Question | What its answer changes |
| --- | --- | --- |
| Real activity | “Tell me what one person actually does here, and what changes for them.” | Whether a proposed visual relationship reflects the service or an invented transaction |
| Audience encounter | “Who first sees this, where, and what are they trying to recognize?” | Name/mark balance, required context, small-size tests |
| Priority | “What should they take away first? Which misunderstanding would cause the most trouble?” | Hierarchy and criteria for comparing territories |
| Difference with evidence | “What do people choose instead? Is there something specific here we can substantiate?” | Useful distinctions and confusion controls; an honest ‘nothing established yet’ remains valid |
| Owner constraint | “Which of these choices must stay, which do you prefer, and which were only early ideas?” | Preservation of genuine mandates; room for exploration |
| Reference ambition | “Which visible qualities demonstrate the care you want? Which features belong only to that reference?” | A craft target without importing another identity |

Read back a short decision brief: activity; primary encounter; one lead communication intention; essential constraints; open design choices; consequential assumptions. A rich evidence record can sit behind a short brief. Neither length nor completion of every row is a readiness criterion. Where the owner specifies a symbol or finish deliberately, preserve it with its provenance and test the tradeoff; “solution neutral” must not erase authorized direction.

## Content/schema recommendations: use existing records first

The existing `facts` status, `requirements` origin/priority/source IDs, `communication_priority` and `design_latitude` support the core distinction. First pilot a content convention within them, rather than adding mandatory metadata:

- Facts: activity and audience/encounter, with a source or an honest assumption/unknown status. Distinguish owner-reported belief from externally observed behavior in the claim's wording.
- Communication requirements: one lead intention and only the supporting intentions that affect design. Name an unwanted confusion where it is consequential; do not require a long competitor list.
- Constraints: exact name/text, actual uses, existing equity, owner mandates and avoidances. Keep designer suggestions visibly proposed.
- Concept plans: one hypothesis, one observable visual relationship, requirement IDs, likely confusion and a detail ledger. The plan describes intent; it does not certify the resulting image.

**Optional future schema hypothesis:** if pilot records become hard to compare, introduce typed `audience_encounter` and `confusion_risk` records, each linked to existing fact/requirement IDs. Do not require them universally until their value and authoring burden are observed. Any contract change starts in architecture; this note makes none.

A useful internal test is “Could I replace the brand name and leave this rationale unchanged?” Treat a yes as a prompt to inspect distinctiveness, not an automatic failure. Simple wordmarks and initials can acquire specificity through actual form, name and use. Conversely, a long origin story does not make a stock letter plus stock category symbol distinctive.

## Worked Rootshare example: explicit facts to alternative visual arguments

This is a proposal for owner review, not a fixture replacement. The archived record establishes a neighborhood seed library, gardeners borrowing/contributing seeds, and favicon/app-icon/social-avatar uses. Terracotta, pale detail, an R and the current tone are archived design intentions; their status as mandatory owner constraints is not established here. Seed return obligations, provenance tracking, local adaptation and physical packet/signage deliverables remain unknown. [Retained Rootshare case](rootshare-brief-and-craft.md).

**Proposed lead:** a welcoming resource held in common. **Supporting intention:** grounded care. **Proposed confusion to avoid:** a seed retailer or generic gardening product. These are positioning hypotheses for confirmation, not additional service facts.

| Territory | Distinct argument to sketch | Purposeful detail after selection | Main failure to inspect |
| --- | --- | --- | --- |
| Relationship-led | Complementary forms create one shared interior or collection | Refine the shared boundary, spacing and interdependence; clarify which contours carry the idea in flat form | Two generic shapes whose sharing meaning exists only in the caption |
| Name-led | Custom Rootshare lettering or an initial with a distinctive structural rhythm; surrounding name/context carries the service | Resolve custom terminals, counter proportions and junctions before adding material complexity | A stock R decorated with an interchangeable seed |
| Collection-led | Repeated elements form one coherent retained group, without implying an unverified return mechanism | Establish deliberate rhythm, count/spacing and controlled negative space | A literal container illustration or visually busy cluster that collapses at small size |

These are different concept hypotheses, not three material variants of the same R. The brief should not require all three ideas to be combined. For a selected ceramic treatment, explicitly choose flush inlay, recess or applied relief and resolve the contact, edge and thickness consistently. The material choice may support care and groundedness; it is not evidence that viewers perceive sharing. If the concept works without a pale accent, that accent may still serve hierarchy or credible fabrication; it need not encode an additional business metaphor.

## Translating Chief-level ambition without copying Chief

The owner's recorded overall response is: “rootshare fails. needs more specific brief and more detail. compare to both chief craft logos.” Both Chief treatments are craft references. This establishes overall rejection and the requested comparisons; it establishes neither independent craft/fit labels nor a preference for either finish. [Retained context and comparisons](rootshare-brief-and-craft.md#fresh-comparison-evidence-and-follow-up-gaps).

Translate the ambition into observable questions about contour resolution, proportion, junctions, material boundaries, edge hierarchy, purposeful detail and readable lighting. Do not translate it into “add gold,” “add a seal,” “make it glossy,” “copy the ribbons,” or a minimum element count. For each detail, record its purpose, intended scale, construction and removal consequence. Some details earn their place through proportion or material credibility rather than symbolic meaning.

Keep primary recognition contours and semantic divisions in the shared motif. Hero-only thickness, seating and finish may reveal how that same identity is made. This follows [accepted ADR 0001](../adr/0001-motif-plus-treatment.md); no reopening is proposed. Compare actual images independently with each Chief reference, using each reference's own intended finish. A prose detail ledger cannot establish matching execution quality.

## Failure examples and an outcome test

| Weak content or review move | Better experiment |
| --- | --- |
| “Innovative, premium, trustworthy” | Ask for the audience encounter and one priority; test concrete interpretations rather than adding adjectives |
| “An R protects a seed, therefore it communicates community” | Keep the service fact separate; show the image before its rationale and record what viewers actually perceive |
| “Borrowing means mandatory seed return” | Mark the rule unknown and avoid depicting it until confirmed |
| “More detail means more seams and grain” | Compare refined contours/joints with added ornament under the same time budget |
| “All ideas need a hidden business metaphor” | Include a strong name-led territory; test recognition, fit and owner response in context |
| “A source-backed brief passed, so the logo improved” | Judge resulting pixels and preserve rejection independently of intake success |

**Validation proposal, not demonstrated benefit:** use Rootshare for workflow development, then untouched brands for a paired trial. Compare current content with this short decision-brief approach under matched authoring time, concept count, render budget and review opportunity. Freeze business facts and owner requirements before authoring; keep actual owner corrections and version reasons. Include short sufficient briefs, owner-mandated initials, nonliteral identities, weak business differentiation, deliberately open materials and conflicting constraints.

Review first without rationales or workflow labels: whole flat/hero images, realistic required contexts, actual small sizes and relevant native-pixel details. Collect unprompted observations before asking targeted questions. Assess own-brief fit, intended appearance, craft against **both** Chief floors, preference and explicit overall owner acceptance separately. Unknown remains unknown. Any overall owner rejection remains a rejection. Report per-brand outcomes, unresolved cases, clarification burden and cost; source count, word count, ornament count and model confidence are diagnostic only.

No new renders or owner study were performed for this note. Primary pages were opened and read directly; source guidance and case-study rationales support the recommendations' plausibility, not causal proof that the workflow produces better logos. Focused reads used the named repository files; no new broad behavioral discovery was required.

One batched Jev screen of the relevant source excerpts ran **retrospectively**, after initial reading and drafting, rather than before interpretation. It returned `review` (injection 0.34, substance 0.99, relevance 0.93; 1,232 input and 57 output tokens). Direct inspection found human-facing service/brand guidance, with no request for credentials, redirection of agent tools or override of operating rules. These passages are retained only as source data. The ignored [source record](../../logos/issue-2-completion/research-content-sources.json) preserves normalized excerpts and the result for parent verification. This retrospective check does not repair the screen-first timing lapse. Cross-note claim verification and the final research-only completion review are handled by the parent task.

Parent review checked eleven bounded primary-source claims across the two new notes with Jev: all were supported, with no contradicted, unsupported or review results (minimum confidence 0.89). Direct inspection corrected a draft that conflated implemented evidence/freeze behavior with the architecture's planned concept review. Source agreement supports the cited descriptions; it does not validate any proposed logo outcome. Verification records remain under `logos/issue-2-completion/`.
