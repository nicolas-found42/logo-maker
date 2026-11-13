# Cached test scheduling experiment — 2026-11-12

Scope: [issue #20](https://github.com/nicolas-found42/logo-maker/issues/20), optimizing the full
offline suite while preserving defect detection. Baseline
`475406228d575a77bb6da2582ce9dcef4f372eba`, clean detached checkout; implementation branch
`codex/test-duration-balancing`. Only the test harness changes. `measurements.json` binds the
measured final harness by SHA-256; the accompanying identities and source make the comparison
inspectable.

## Commands and environment

- macOS arm64, Darwin 27.0.0, M5 Pro, 18 logical CPUs, 48 GiB RAM; Python 3.13.16, uv 0.13.6, pytest
  9.2.0, pytest-xdist 3.8.0. `-n auto` starts 18 workers. No explicit CPU, memory, test retry or
  sharding limit. Shell limits: unlimited CPU/data/virtual memory; 8,176 KiB stack, 8,000 processes,
  1,048,575 file descriptors. Shared workstation, no exclusive-machine claim.
- `uv sync --locked`: 1.37 s with warm shared package cache (new worktree environment, 137
  packages). `npm ci --prefix js`: 12.48 s with existing npm cache. The CI browser provisioning
  command found cached Chrome headless 156.0.8078.47 and launched it successfully. These are setup
  measurements, not clean-download timings.
- Authoritative offline command: `PAG_USE_LOCAL_REV=1 just test`, expanding to `uv run --locked
  python -m pytest -q -m "not render and not live" -n auto --dist worksteal`.
- Timed runs add `--durations=20 -p perf_probe`, `PYTHONPATH=/tmp/logo-test-perf`,
  `PERF_OUTPUT=/tmp/logo-test-perf/<label>.json`, and `/usr/bin/time -p`. The initial run used
  `--durations=25`. Cache-cold runs add `--cache-clear`; warm runs retain pytest duration history.
  Baseline cold repetitions temporarily restored the exact baseline conftest and removed only the
  newly authored scheduling test file, then restored both in `finally`; the 524 baseline identities
  were checked in every run.
- Reproduce the probe from this checkout with `PYTHONPATH="$PWD/benchmarks/test-speed/20261112"
  PERF_OUTPUT=/tmp/logo-test-measurement.json PAG_USE_LOCAL_REV=1 /usr/bin/time -p just test -p
  perf_probe --durations=20`.

`pyproject.toml` discovers all `tests/` and excludes `live` by default. `just test`, CI and the
pre-push hook exclude `render` and `live`. `just render-example` runs the two GPU checks. Four
`live` tests require external provider access (one also explicitly requires GPU validation opt-in);
they were collected but not called for this test-harness change. No discovery, exclusions,
assertions, test budgets, service boundaries, coverage configuration, retries or dependencies
change. No coverage or mutation framework/results are configured in the repository.

CI (`.github/workflows/ci.yml`) runs lint on Ubuntu with dev-only dependencies, static hooks on
Ubuntu, and types, retained-evidence verification and the full offline suite on `macos-latest`. It
provisions native canvas libraries, npm dependencies, a PWA browser and the locked Python
environment. It caches uv packages, not pytest duration history. There is no configured test
timeout, retry plugin, coverage collection, shard or external service dependency for the offline
suite; provider tests use local HTTP servers. `just check` also includes hooks and the local GPU
regression.

## Bottlenecks and iterations

1. Baseline profiling: two export/browser lifecycle cases take 18.07 and 17.40 s. Their 20 s job
   budgets include real rendering-format setup and process cleanup. The previous hosted failure from
   shrinking that allowance is documented in `docs/research/check-telemetry-and-bottlenecks.md`;
   this task preserves it. The first worktree run also spent 16.70 s in the combined geometry test.
   Warm geometry drops to about 6.7 s. Blocked-QA fixture setup costs about 4–5.6 s and exercises
   real owned workers with a 4000 px synthetic image. No integration setup was mocked or shared
   across bound filesystem paths.
2. Measured cached worker blocks carried about 26–29 s on the workers owning the long deadline
   cases, versus roughly 13–18 s elsewhere. Expected benefit: remove several seconds of tail work by
   assigning each descending-duration item to the least-loaded block. Risk: omission, duplication,
   divergent worker collections, wrong block boundaries, order dependence or swallowed failures. The
   implementation keeps all item objects, follows xdist's floor-sized initial allocation, and sorts
   only after deselection when timing history exists.
3. Initial scheduler-option check accidentally saw `dist=no` inside xdist workers and only sorted
   tests, giving 37.69 s. Corrected by explicitly propagating the controller's scheduler choice. The
   corrected cached runs took 21.13 and 21.28 s with all 524 original tests passing. This failed
   implementation is not retained.
4. Deferred the render-only `skimage.metrics.structural_similarity` import. Five serial collection
   runs: before median 0.7298 s (0.6981–0.8995), after 0.7289 s (0.6868–0.8440). Reverted: no
   measurable benefit. The 0.001 s difference does not justify a change.
5. The first exact-block implementation regressed cache-cold performance: median 22.73 s
   (22.64–23.10), versus 21.59 s (21.32–21.65). Report timing isolated the extra 1.4 s to execution,
   not collection/teardown: without estimates, a long deadline case started later. Revised the hook
   into a wrapper: retain the original pre-deselection round-robin deal when the timing cache is
   empty; balance measured loads after selection when it is populated. Disabling the cache leaves
   discovery order intact.
6. No static timing seed or new shared resource cache was added. A cold run has no history to
   justify workload estimates, and a checked-in seed would need ongoing maintenance across different
   machines. Remaining repeated host starts and geometry/image setup preserve meaningful integration
   boundaries. The unchanged 18 s deadline case is now the main local lower bound; further
   full-suite gains need stronger evidence or a more invasive test-clock design.

## Effectiveness and verification

`identities.json` lists every baseline offline identity and the ten added scheduler checks; none are
removed. Every timed successful run independently checked identical worker collections, one call
report per selected identity, no duplicates, no skipped/failed calls and exit status zero. All 524
original tests continue to execute; the ten new tests cover deterministic ordering, identity
preservation, unknown/stale estimates, more workers than tests, disabled caches and scheduler
propagation. Assertions and the rendering/provider/process boundaries in the original tests are
untouched.

`uv run --locked python benchmarks/test-speed/20261112/check_harness.py` runs the actual
pytest/xdist machinery in a temporary suite. Each test creates an exclusive per-identity file,
detecting duplicate execution. The script verifies marker deselection, cold/warm/disabled caches,
`worksteal`, `load`, serial execution and a collection smaller than the worker count. A deliberate
test failure must execute all ten selected identities and return exit status 1; a masked failure,
omitted case or duplicate execution fails the verifier. Results are retained in
`harness-results.json`.

The probe records controller startup/collection events, first test and last report, session finish
and per-test setup/call/teardown durations. Worker phase sums are aggregate CPU/wait time, not
additive wall time under parallelism. `last_report` to `session_finish` measures worker/session
shutdown; the outer `time` includes interpreter and command-wrapper teardown. It is not valid to add
these overlapping values or call aggregate setup time the suite's setup wall time.

A fresh worktree's first run took 32.98 s with warm shared dependency/browser/GPU caches; time to
first test was 6.87 s. Subsequent cache-cold runs do not erase bytecode, OS pages or shared tool
caches and are reported separately. Fully empty package/browser/GPU caches were not measured. No
cold or local speedup is extrapolated to hosted CI.

## Final local measurements

All rows are full offline-suite measurements, including startup and teardown. Each repeated row has
three runs; ranges show minimum–maximum. The final rows include ten additional tests.

| Cache state | Baseline wall (s) | Final wall (s) | Interpretation |
| --- | --- | --- | --- |
| pytest duration history present | median 27.35; 23.48–30.11 | median 20.90; 20.85–20.93 | 23.6% less wall time, 1.31× throughput |
| pytest cache cleared, other caches warm | median 21.59; 21.32–21.65 | median 21.66; 20.65–22.84 | No supported cold-cache improvement; median difference 0.07 s |
| first test run in this worktree | 32.98 | Not repeated | Includes initially cold import/bytecode state; shared tool caches already warm |

Approximate median controller phases from the probe (seconds; excludes interpreter/CLI startup
before plugin import):

| Runs | To first test, including worker boot/collection | First test to last report | Last report to session finish |
| --- | --- | --- | --- |
| Baseline warm | 2.10 | 22.78 | 0.90 |
| Final warm | 1.38 | 18.08 | 0.73 |
| Baseline pytest-cache cold | 1.38 | 18.48 | 0.72 |
| Final pytest-cache cold | 1.32 | 19.53 | 0.70 |

The much smaller final warm range is observed across these three runs, not a promised flake-rate or
variance bound. Collection acceleration is not claimed: the unchanged suite and fluctuating worker
boot/import state can affect that component. The principal retained improvement removes the
overloaded cached-worker tail.

Final commands and observed results:

| Check | Result |
| --- | --- |
| `PAG_USE_LOCAL_REV=1 just test` with the probe/duration arguments above | All repeated final runs: 534 passed, 0 skipped, 49 existing warnings; no retries |
| `uv run --locked python -m pytest --collect-only -q -m ''` | 540 collected: 534 offline, 2 render, 4 live; baseline 530 = 524 + 2 + 4 |
| `uv run --locked python benchmarks/test-speed/20261112/check_harness.py` | Seven real harness scenarios pass verification; deliberate failure returns 1 and executes all selected identities |
| `just lint` | Pass: Ruff, formatting and skill check |
| `just type` | Pass |
| `just hooks` | Pass, including retained-evidence verification |
| `just render-example` | 2 passed; baseline 15.15 s wall, final 7.04 s with GPU cache variation; no render speedup claim |
| `logo-maker doctor` | Not required: no dependency or adapter change; locked environment setup only |
| `-m live` | Not run: no provider, Jev-question or product-code change; collected identities retained |

## Hosted CI

Baseline: [main run
43132681631](https://github.com/nicolas-found42/logo-maker/actions/runs/43132681631), revision
`475406228d575a77bb6da2582ce9dcef4f372eba`. All required checks passed. The offline step lasted 219
s by job-step timestamps; pytest reported 522 passed, 2 skipped, 49 warnings in 217.11 s. Test-job
elapsed time was 362 s. The hosted environment uses Python 3.13.17; local measurements use 3.13.16.
The baseline log does not publish individual skipped identities, so it cannot establish a
per-identity skip comparison on its own.

Final hosted result will be recorded in the saved PR after its exact head runs. CI does not retain
pytest history, so the local warm speedup is not a CI improvement claim. No workflow, cache policy,
setup step or test-selection rule changes.
