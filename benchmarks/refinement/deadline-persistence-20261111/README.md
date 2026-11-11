# Bounded request persistence — 11 November 2026

Refs #3. Post-merge main `64bcb70` failed one dedicated six-second regression because
normal startup/persistence work exhausted the deadline before its injected QA image read.
The retained hosted log reports 1 failed, 452 passed and 2 optional skips.

With 0.6 seconds of controlled startup latency per Jev worker, the unchanged regression
reproduces that exact symptom with six workers. Runtime `5fa7050` batches each request-log
publication and exact asset verification into one owned worker. Two saved confirmations
pass with four workers. No dedicated deadline test or production budget is changed.
The diagnostic plugin is retained as text, not installed in the test suite.

Sequence allocation, locks and received-usage accounting remain in the parent. Initial
submission context and unknown cost persist before dispatch. Received answers and usage
replace the same request record before asset IO; assets remain pending until their exact
bytes are verified. Provider errors, corrupt-asset recovery and prior-winner retention use
the same bounded path. `validation/source-binding.json` pins the committed source tested
from an extracted checkout, excluding concurrent uncommitted template work.

Validation: 455 offline tests passed; targeted client/selection/sampling tests 45 passed;
GPU regression 2 passed; explicit final GPU/live check 1 passed; owner-labeled live controls
3 passed. Doctor, lint/format, types and wheel/sdist builds passed. The final synthetic
runtime retains native Metal/GPU-OIDN evidence, 31 low-level export hashes and live QA.
Its canned brief/plan, unqualified sampling profile and preserved prior winner do not
qualify artwork or a production sampling profile. Hosted PR and post-merge checks remain
separate obligations. Issues #1, #3 and #4 remain open.

Run `uv run --locked python scripts/verify_reconciled_refinement.py`. Raw logs and snapshots
are immutable and retain their captured whitespace. This bundle adds no artwork cases.
