# Concurrent bounded persistence — 11 November 2026

Refs #3. This follow-up retains the correction to Sourcery's finding on PR #15:
slow image asset storage held the shared client lock and serialized independent requests.
The prior `deadline-persistence-20261111` bundle remains immutable historical evidence.

A public `ask_many` regression uses real owned workers and local HTTP. Its injected asset
storage barrier admits only one of four requests before this fix, and all four after it.
The provider checks that exact submitted image bytes are already retained and marked ready
before dispatch. Four request IDs, eight parseable journal lines and exact aggregate usage
are verified after release. No provider response or worker result is mocked.

Runtime `28adfd5` releases the client lock before bounded persistence. Sequence allocation
and received-usage accounting stay in the parent. A POSIX file lock protects journal append
through close-time flushing, and closes before asset storage. The same append helper serves
budgeted and unbudgeted writes. Workers waiting on file IO or a file lock remain bounded by
the original owned-process deadline and cleanup. Request ordering and pending-until-verified
asset state remain intact. No production default or dedicated deadline test changes.

Validation: 456 offline tests passed from the extracted committed source; 46 targeted tests
passed. The original 0.6-second startup reproduction still passes with four Jev workers.
GPU regression: 2 passed. Final GPU/live: 1 passed. Live controls: 3 passed. Doctor, lint,
formatting, types and isolated wheel/sdist builds passed. The native final retains Metal
tracing, GPU OIDN, 31 low-level export hashes and actual QA, then preserves the prior winner
at the unqualified sampling stop. Canned brief/plan answers qualify only that runtime fixture.

Hosted checks and fresh post-merge main CI remain separate obligations. This transport bundle
adds no artwork case or production sampling approval; issues #1, #3 and #4 remain open.
Run `uv run --locked python scripts/verify_reconciled_refinement.py`. Preserve raw captured bytes.
