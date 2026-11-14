# Peer README research: programmable rendering / vector / 3D tools (2026-11-14)

Scope: how six popular tools that overlap logo-maker's programmable
rendering / vector / 3D workflow open their official GitHub READMEs, and what
logo-maker's root `README.md` should borrow. Every factual claim cites the
official repository README (raw GitHub URL) or the official GitHub REST API
(`api.github.com/repos/...`, fetched 2026-11-14). Star/fork counts are
point-in-time API values, not timeless facts. Observations (§observation) are
kept separate from proposed design (§recommendation). No product files were
modified; the root README is owned by the main agent.

Local baseline (what logo-maker already does): `README.md:1-16` opens with a
one-line promise ("Give your next project a mark worth opening"), a
no-AI-image-generation differentiator, then a tracked hero image
(`docs/assets/readme/showcase.png`) with a provenance caption, then anchor
links. `README.md:47-111` gates the full 3D path on Apple-silicon Metal and
offers a flat/no-GPU alternative at `README.md:113-118`.

## Selection

All six assignment candidates were kept (no homogeneous bulk scan; six
repos total). Overlap rationale:

| Repo | Overlap with logo-maker | Stars / forks (GitHub API, 2026-11-14) |
| --- | --- | --- |
| ManimCommunity/manim | Programmable scene -> rendered video; code authors structure, engine renders | 42,330 / 3,300 |
| DLR-RM/BlenderProc | Procedural Blender/Cycles rendering pipeline | 3,703 / 519 |
| mikedh/trimesh | Python mesh load/manipulate/analyse library | 3,719 / 703 |
| fogleman/primitive | Image -> geometric-primitive vector reproduction (logo-adjacent) | 13,595 / 671 |
| visioncortex/vtracer | Raster -> SVG vector tracing (logo-adjacent) | 7,531 / 517 |
| fogleman/sdf | SDF/CSG -> 3D mesh in Python (geometry authoring) | 2,019 / 173 |

Sources: `https://api.github.com/repos/ManimCommunity/manim` (pushed
2026-11-05), `https://api.github.com/repos/DLR-RM/BlenderProc` (pushed
2026-01-20), `https://api.github.com/repos/mikedh/trimesh` (pushed
2026-11-09), `https://api.github.com/repos/fogleman/primitive` (pushed
2024-07-22 — most stale of the six),
`https://api.github.com/repos/visioncortex/vtracer` (pushed 2026-11-13),
`https://api.github.com/repos/fogleman/sdf` (pushed 2026-09-30). Default
branches: `main` except `primitive` and `vtracer` (`master`).

## Observations

### 1. ManimCommunity/manim — code-first, proof-by-example, badges as trust wall

- README: `https://raw.githubusercontent.com/ManimCommunity/manim/main/README.md`
- **Opening:** centered logo + 9-badge row (PyPI, Docker, Binder, MIT,
  Reddit, Twitter, Discord, docs, CI), then an italic one-liner:
  "An animation engine for explanatory math videos". First prose sentence
  names the proof: "used to create precise animations programmatically, as
  demonstrated in the videos of 3Blue1Brown". No screenshot in the top block;
  the first image is a CLI-args diagram deep in the README.
- **Installation / first result:** Installation section defers to external
  docs and offers a zero-install try path ("try it out first ... in our
  online Jupyter environment"); Usage then gives a complete minimal
  `SquareToCircle` scene plus the one render command
  (`manim -p -ql example.py SquareToCircle`) and the expected visible
  result ("you should see your native video player ... play").
- **Audience:** teachers / explainer-video creators who write Python scenes.
- **Transferable pattern:** proof-by-named-output (a famous artifact the
  tool produced) + a complete copy-paste sample + the exact command that
  shows it working, with a no-install trial before the install gate.

### 2. DLR-RM/BlenderProc — animated hero GIF, one-command quickstart

- README: `https://raw.githubusercontent.com/DLR-RM/BlenderProc/main/README.md`
- **Opening:** title + 3 badges (docs, Colab, GPL), then a full-width
  animated GIF immediately ("Front readme image"), then one sentence:
  "A procedural Blender pipeline for photorealistic rendering." Nav links and
  a Features bullet list follow before Installation.
- **Installation / first result:** `pip install blenderproc`, then a
  dedicated `blenderproc quickstart` command — the first-result path is a
  single command, not a script you must write.
- **Audience:** ML researchers needing synthetic photorealistic training
  data (papers, JOSS article linked in the nav row).
- **Transferable pattern:** motion hero above the fold (GIF proves the
  render pipeline in one glance) + a named one-command quickstart that
  removes blank-page fear.

### 3. mikedh/trimesh — library README: no hero, install + giant quickstart

- README: `https://raw.githubusercontent.com/mikedh/trimesh/main/README.md`
- **Opening:** logotype + 4 badges, then a definition sentence naming the
  data model ("loading and using triangular meshes with an emphasis on
  watertight surfaces") and an analogy to a known library (Shapely's
  Polygon). No hero image or screenshot anywhere.
- **Installation / first result:** `pip install trimesh`, then a long
  "Quick Start" that is a heavily commented end-to-end example (load,
  inspect `is_watertight`, transform, show). Features section follows.
- **Audience:** Python developers doing graphics/CAD/3D-printing mesh work.
- **Transferable pattern:** name the core object and the one property users
  care about (watertight) in the second sentence; the quickstart doubles as
  API documentation. [INFERENCE] This works for trimesh because it is a
  library; logo-maker is a workflow, so it should not copy the no-hero shape.

### 4. fogleman/primitive — result image as the argument

- README: `https://raw.githubusercontent.com/fogleman/primitive/master/README.md`
- **Opening:** title + one line ("Reproducing images with geometric
  primitives."), then immediately a large example output image, then a
  "How it Works" paragraph that quantifies the method ("Around 50 to 200
  shapes"). A native macOS app and a Twitter bot are promoted before
  command-line usage.
- **Installation / first result:** `go get -u github.com/fogleman/primitive`,
  then the one-liner `primitive -i input.png -o output.png -n 100`.
- **Audience:** creative hackers / generative-art users; the Twitter bot is
  the zero-install trial.
- **Transferable pattern:** the example output IS the pitch — no badges, no
  feature list before the proof. The bot/app give a no-install path that
  precedes the CLI. This is the closest logo-adjacent pattern for
  logo-maker's screenshot-led README.

### 5. visioncortex/vtracer — app-first, comparison as differentiation

- README: `https://raw.githubusercontent.com/visioncortex/vtracer/master/README.md`
- **Opening:** centered banner + title + bold one-liner ("Raster to Vector
  Graphics Converter"), then direct download links for Windows/macOS/Linux
  apps, then registry badges (crates/PyPI/npm). No prose pitch.
- **Installation / first result:** "Desktop App" screenshot section, then
  pre-built binaries from Releases, then `cargo install vtracer-cli` as the
  from-source fallback. The GUI screenshot appears before any install text.
- **Audience:** designers converting raster art/blueprints to SVG; also
  Rust/Python/Node library users.
- **Transferable pattern:** differentiate by explicit comparison ("Comparing
  to Potrace ... Comparing to Adobe Illustrator's Image Trace ...") and
  lead with the easiest artifact (desktop app) rather than the build.
  logo-maker's equivalent contrast is "no AI image generation", which its
  README already states at `README.md:7-8`.

### 6. fogleman/sdf — complete example in ~10 lines, minimalism as voice

- README: `https://raw.githubusercontent.com/fogleman/sdf/main/README.md`
- **Opening:** title + two lines ("Generate 3D meshes based on SDFs ...
  with a dirt simple Python API."). No badges, no hero. The Example section
  right after the opening shows a small rendered model image (floated
  right) and a complete program — "Yes, that's really the entire code!"
- **Installation / first result:** `git clone https://github.com/fogleman/sdf.git`
  (Installation section is *after* the Example); the example itself is the
  first result. One line: "You can 3D print that model or use it in a 3D
  application" names the payoff.
- **Audience:** Python users who want CSG geometry without a CAD GUI.
- **Transferable pattern:** brevity as credibility — the whole program fits
  on screen, and the README says so. The first thing a visitor can do is
  run the example they just read. logo-maker cannot match this (its
  workflow is agent-mediated), but it can narrow the gap by putting a
  complete, short, runnable flat-assets example in the first screenful.

## Proposed design (recommendations for logo-maker's README)

These are proposals, not observations; each cites the peer pattern it borrows.

1. **Keep the current shape; it already matches the two best logo-adjacent
   peers.** One-line promise + differentiator + tracked hero image with
   provenance caption (`README.md:1-16`) mirrors `primitive` (result image
   as the argument) and `vtracer` (one-liner + easiest artifact first).
   Do not add a badge wall: Manim's 9 badges fit a large community project;
   logo-maker is v0.1.0 and badges would imply maturity the release history
   does not yet support (local facts, see previous report §7).
2. **Add a motion or before/after proof point (from BlenderProc).** A short
   GIF or a flat-mark → 3D-study before/after pair near the top would prove
   the render pipeline the way BlenderProc's hero GIF does. Must be a real
   tracked output with the same provenance caption discipline as
   `README.md:10-13` — [INFERENCE] a static contact sheet may already
   carry this; the main agent judges the visuals.
3. **Name the proof artifact explicitly (from Manim).** Manim leans on
   "3Blue1Brown videos" as its existence proof. logo-maker's equivalent is
   a named shipped example: link the Found42/Field Kettle studies (already
   captioned at `README.md:29-34`) as "real studies produced by this
   pipeline" with study IDs/manifests per the previous report §8, so the
   claim is traceable rather than asserted.
4. **Put a complete, runnable first-result example in the first screenful
   (from sdf + Manim).** sdf's "that's really the entire code!" and Manim's
   `SquareToCircle` both let a reader run what they just read. logo-maker's
   flat-assets path (`README.md:113-118`) is the natural candidate: show
   the 3-5 commands that turn a brief into a favicon set, inline, before
   the gated 3D install. This also defers the Apple-silicon requirement
   below the first success, the way Manim defers local install behind a
   Binder trial.
5. **Contrast, don't just describe (from vtracer).** Add one explicit
   comparison sentence against the obvious alternative (AI image
   generators / stock logo tools): who wins on editable vectors, `.blend`
   scenes, and deterministic renders — each claim already substantiated in
   the previous report §§1, 6, 7. Avoid unsubstantiated competitor claims.
6. **Keep the "quickstart" command (from BlenderProc), but flag the gate
   honestly.** `blenderproc quickstart` exists so a reader never faces a
   blank page. logo-maker's `logo-maker study ... --preview` plus
   `logo-maker doctor` play this role (`README.md:96-111`); make sure the
   doctor step reads as "check before you start" (previous report §5),
   not as a second installation.
7. **Do not copy trimesh's no-hero, API-first shape.** It suits a library
   whose users import an object; logo-maker's users brief an agent. The
   hero image and the "From a mark to the whole set" outcome table
   (`README.md:18-45`) are the right inversion of trimesh's order.

## Method and limits

- Six repos only (the six named candidates); no bulk scan, no homogeneous
  top-N list. README text was fetched from `raw.githubusercontent.com`
  official repo files via Keenable `fetch_page_content`; popularity via
  official GitHub REST API (`api.github.com/repos/...`). No scripts from
  any page were fetched or run; no install commands were executed.
- Fetched README excerpts were summarized/extracted by the fetch prompt;
  verbatim quotes above are short and cross-checked against section
  headings. Star counts are as of 2026-11-14 and will drift.
- Local baseline claims cite `README.md` line numbers as read on
  2026-11-14; the main agent is editing that file concurrently, so line
  numbers may shift.
- No builds, lint, tests, or formatters were run. Machine-readable
  observations: `/tmp/logo-maker-peer-readmes.json` (6 records:
  `repo, url, source_excerpt, observation, recommendation`).

## Applied decisions and Jev check

Six comparison records were judged together with a frozen pattern-transfer rubric. No records
were excluded or truncated, and none failed. Results: five `adopt`, one `mixed` (trimesh).
All six were escalated and read: top probabilities ranged from 0.45 to 0.64, below the 0.70
automatic-confidence threshold. These are advisory suggestions, not proof of better conversion.

The source-backed presentation patterns retained in `README.md` are:

- **primitive / BlenderProc:** put real visual output before the setup instructions. The
  existing three-render showcase and Seedwell flat/3D contact sheet provide this evidence;
  no decorative animation or fabricated interface was added.
- **Manim / sdf:** give a complete runnable example with a visible result. The README now
  exports four PNG sizes from the bundled `docs/assets/readme/seedwell.svg`, before the
  Apple-silicon 3D setup. This is an artwork-export demo, not automatic logo design and not
  a zero-install hosted trial.
- **vtracer:** explain the concrete distinction early: no AI image generation, with editable
  vector artwork and scenes. No superiority or deterministic-render claim was added.
- **trimesh:** retain the clear definition, but do not adopt a library/API-first layout.
  This resolves the mixed recommendation: the outcome-led visual introduction remains.

The bundled SVG is copied from the same delivered Seedwell study as the contact-sheet image:
`logos/campaign-release-development/seedwell/studies/study-d243ae3556f1/sill-basin/mark-color.svg`.
The exact flat-demo shell block was executed locally and exited 0, producing nonempty RGBA
PNGs at 16, 32, 180, and 512 px. The 512 px result was opened and inspected.

## Final verification limits

The final README passed `uvx rumdl==0.2.78 check README.md CHANGELOG.md`. All 22 local
link/image references and Markdown fragment targets passed existence checks. A local
GitHub-style HTML preview was inspected at desktop and 390 px mobile widths; both images
loaded, the page had no horizontal overflow, and the Get started link reached its heading.
This is local preview evidence, not a claim about a published GitHub page.

The final Jev gate verified three claims (image provenance, runnable PNG demo, links/Markdown)
and marked the visual-inspection claim unsupported from its text-only evidence. Its patch
review also escalated on uncertain blast-radius/test-gap scores. It did **not** auto-approve
the change. The visual claim is supported instead by the main agent's observed screenshots
and browser checks (`bodyWidth = viewportWidth = 390`, both images loaded,
`hash = "#get-started"`, heading top approximately 0.44 px). No claim was contradicted.
No fresh-machine 3D installation, GPU render, hosted-page check, or provider review was run.
