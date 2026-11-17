# M5 Pro sampling and campaign release checks, November 16–17, 2026

The rerun used Apple M5 Pro and the working tree based on `f419196`. The campaign
install matched all 71 package file hashes and used the pinned Codex 0.167.1 runtime
and companion. The Blender execution-denial check and the native Seatbelt, Cycles Metal,
and GPU OIDN preflight passed.

## Sampling evidence

- Declarative scenes completed 20 native render and export jobs and verified 620 export
  inventory entries. Nine matched pairs compared 4096 and 8192 sample caps at 0.01.
  Two additional renders exercised 0.02. The median full-job times were 67.1 s at 4096
  and 96.2 s at 8192. The candidate 8192 / 0.01 profile awaits owner review.
- Packed scenes completed Breakwater's 0.01 positive and 0.02 degraded comparison and
  the independently authored tie-down eye at 0.01 and 0.005. The packet covers satin
  zinc-gray cast metal. The 95th-percentile maximum RGB channel difference between the
  positive and degraded images was 1 of 255 among opaque pixels. The packed profile
  awaits separate owner review.

The declarative approval ZIP has SHA-256
`d6e3e900abe10be6a3708996f88503dabe54f6fb99111263fceb0a7dc78b5551`.
The packed approval ZIP has SHA-256
`fb3067e12d2f80f474e1081bcbec9d0a2f1d376423779209af4b99e292a451e0`.

## Campaign checks

- The production Jev evaluator failed on the six-case frozen panel. It returned zero
  false acceptances and called the sole sound case unsettled. Experimental triage
  matched five labels and called one insufficient-evidence case a defect.
- Found42 retained the verified first view across an interrupted second render. The
  restart rendered the missing view. A subsequent scene edit invalidated the affected
  cached render.
- Breakwater Supply, Meridian FM, and Seedwell verified their heroes and four inspection
  views and reopened the Blender scenes from the verified handoff archives. The three
  visual reviews were unsettled. Breakwater passed the three measured geometry checks.
- The fresh trials exercised an original modeled object (Bench Index), adaptation of a
  supplied SVG (Ridge Datum), and a brief that left the medium open (Field Register).
  Bench Index and Ridge Datum each verified five renders, passed six geometry checks,
  and reopened the editable handoff scenes. The reference audit found 0 qualifying
  captures for Bench Index and 3 for Ridge Datum. Both used the inspection-only route.
  Ridge Datum's hero side margins were 3.6% against the 4% minimum. Field Register's
  verified flat preview and handoff await exact-artwork acceptance.
- The trial launchers reached their 90-minute limit during the modeled runs. The two
  underlying Codex sessions continued and finished packaging their studies.

| Artwork awaiting owner review | Exact approval SHA-256 |
| --- | --- |
| Bench Index, Axial Pull study `study-6bdfd4f2fcd6` | `84ebeaffdb777c2374ab3a4b1b739f67f29189a48051929847b0b692d13a6c42` |
| Ridge Datum, Service Plate study `study-6494c56e8b6b` | `7462cf23fa2e73191779aa1fcab4644c01a996109c194d8353b8a28952336266` |
| Field Register, Shared Datum flat preview | `eabc6561aa12780586f80fd6c5334ef4f6369efcec162508fb8da357fc72c768` |

Production qualification remains blocked by the evaluator, the fresh modeled trials'
reference and visual gates, and the relevant sampling and artwork approvals. The
local `logos/requalification-2026-11-16/APPROVALS.md` indexes the review artifacts,
hashes and receipts. It retains the reviewer links to the native artifacts and logs.
