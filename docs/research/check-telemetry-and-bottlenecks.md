# Check telemetry and bottlenecks

Primary sources: this repository at the time of writing (line numbers are from the working tree and will drift while
tests are edited), `pytest --durations` output from one `-n auto` run, and the repository's own CI workflow.
Not read: external `pytest-xdist`, `prek`, `ruff` and `ty` documentation. Statements about their behaviour are marked
`[INFERENCE]`.

## 1. Measured baseline

| Run | Command | Result |
| --- | --- | --- |
| Parallel | `uv run --locked python -m pytest -q -m "not render and not live" -n auto --durations=30` | 524 passed in 37.68 s wall, 3m33s user, 1m00s sys |
| Serial | the same command without `-n` | Only 62 of 524 dots appeared before a 280 s cutoff; it was killed, so there is no total |

- The `just test` recipe (`justfile:40-41`) has no `-n`. CI does (`.github/workflows/ci.yml:95`, `-n auto`).
  Local `just check` is therefore much slower than CI for the same tests.
- `pytest-xdist>=3.8.0` is already in the dev group (`pyproject.toml:48`; `uv.lock:1320`).
  `[tool.pytest.ini_options]` (`pyproject.toml:66-72`) has `addopts = "-m 'not live'"` only. No `-n`, no `--dist`.
- With `-n auto` the wall time (37.7 s) is bounded by the slowest single test, not by the total CPU time.
  The slowest durations from that run:

| Duration | Test |
| --- | --- |
| 17.08 s | `test_sampling_render.py::test_stalled_image_hash_stops_at_wall_budget_and_keeps_prior_result` |
| 13.01 s | `test_publication.py::test_finalize_interrupted_winner_publication_restores_winner_and_run_state` |
| 12.08 s | `test_combined_stack.py::test_combined_selection_keeps_errors_costs_and_eligibility_independent[missing_usage]` |
| 6-10 s | `test_publication_guards.py::test_export_publication_input_edit_restores_prior_exports_and_run[*]` (six params) |
| 7-8 s | `test_export.py::test_pipeline_export_rejects_concurrent_qualification_replacement[unqualified, missing]` |
| 7.05 s | `test_publication.py::test_committed_cleanup_stall_is_bounded_and_keeps_recovery_evidence` |
| 6.16 s | `test_combined_stack.py::test_provider_timeout_keeps_pending_attempt_unknown_and_prior_output` |
| 5.05 s | `test_sampling_render.py::test_finalize_blocked_qa_cannot_overrun_budget_or_replace_prior_winner[*]` (5 params) |
| 5.05 s | `test_sampling_render.py::test_stalled_cached_image_check_stops_at_its_shared_budget` |
| 5.07 s | `test_export.py::test_export_set_sizes_and_manifest` |
| 4-4.4 s | `test_refinement.py::test_final_tournament_cannot_approve_in_flight_edits[*]`; `test_publication.py::test_publication_stall_terminates_and_restores_whole_prior_set[*]`; `test_publication_guards.py::test_publication_guard_read_uses_same_deadline_and_recovers`; `test_export.py::test_export_deadline_stops_tool_and_its_detached_browser[deadline]` |

The 5.05 s parameters are consistent with `Budget(wall_seconds=6)` minus the 1 s reservation (section 2.1).
That is inference from the numbers, not a measured breakdown.
Total CPU time is about 5.7x wall time, so xdist is saturating cores. Wall time is dominated by the stall tail.

## 2. Wall-clock deadlines and fixed sleeps in `tests/`

### 2.1 The production floor that sets the minimum deadline

- `Budget.__init__` (`logo_maker/sampling.py:207-231`) accepts any positive finite float. Only `wall_seconds <= 0`
  or a non-finite value raises (`sampling.py:218`).
- `owned_process.run` (`logo_maker/owned_process.py:29`) raises `SamplingLimit` immediately if `budget.remaining <= 1`.
  Its worker timeout is `max(0.001, min(timeout or inf, budget.remaining - 1))` (`owned_process.py:42`).
  So the effective stall wait is `wall_seconds - 1 - time already spent`.
- `stop_session` (`owned_process.py:59-107`) reserves cleanup: SIGTERM grace up to
  `min(0.8, remaining-0.2)` (`:86`, polling every 0.01 s at `:87`), then `worker.wait(min(0.2, remaining))` (`:99`).
- `render.py:199` and `:221` read `config["wall_seconds"]`, defaulting to 1800. `scene.py:206` allows
  `lo=0.001`. A scene `[sampling] wall_seconds=6` is therefore a data knob, not a code change.
- **Consequence:** a stall test can never use `wall_seconds <= 1`. It can use roughly `1 + (cold child interpreter start
  + path to the stall marker) + 0.8 s grace + 0.2 s wait`. The current 6 to 8 s values leave about 4 s of margin over
  that floor. The 2 s in `test_owned_process.py` is below that and is the tightest in the suite.
- Shortening these budgets without a ready-signal can make the test fail at the wrong place. A deadline that expires
  before the child reaches the stall marker raises `time_limit` from startup, not from the stall.
  The `assert marker.exists()` guards, e.g. `tests/test_refinement_owned.py:~57`, exist to catch that.

### 2.2 Inventory

| Location | Value | Why it waits | Safe minimum / lever |
| --- | --- | --- | --- |
| `tests/test_export.py:95` | `Budget(1, clock=lambda)` | Fake clock; no real wait | none needed |
| `tests/test_export.py:162-163` | releaser polls FIFO open every 0.01 s; holds writer `stop.wait(10)` | The child must block reading the provenance FIFO until the deadline | The 10 s hold is only a safety valve; `finally` sets `stop` (`:186`). Does not extend runtime |
| `tests/test_export.py:181` | `Budget(wall_seconds=6)`; asserts `< 9` s (`:184`) | The FIFO stall runs to `6 - 1` s | See "Lever A" below |
| `tests/test_export.py:219-241` | child heartbeat every 0.03 s for 60 s; launcher `sleep(0.3)` in its SIGTERM handler; driver polls 0.01 s for up to 2 s | Simulates a launcher that is slow to clean up its browser child | The 0.3 s handler sleep must stay under the 0.8 s grace (`owned_process.py:86`). The 60 s heartbeat is a ceiling; the process is killed |
| `tests/test_export.py:265` | `Budget(wall_seconds=20)` | The comment says it covers cold imports on a slow hosted Mac, before the external-tool lifecycle | Deadline fires at about 19 s of wall time only if the child never exits, but the stub exits earlier on SIGTERM. Cost is the real elapsed time to the deadline |
| `tests/test_export.py:270` | `time.sleep(0.2)` | Proves the heartbeat file is no longer being written after the deadline | Could poll `stat().st_mtime_ns` for 2 intervals of 0.03 s (about 0.1 s). Saves about 0.1 s only |
| `tests/test_sampling_render.py:85` | scene `wall_seconds=6` | Scene-driven deadline for the host-timeout test | Config knob, can be lowered with the rest of Lever A |
| `tests/test_sampling_render.py:103-104, 167-178, 262-263, 442-456, 756-757` | FIFO releaser polls 0.01 s; holds `stop.wait(10)` (`:263` uses `35`) | Same FIFO-stall pattern | The 10 s and 35 s holds are only upper bounds |
| `tests/test_sampling_render.py:122, 187, 770` | `Budget(wall_seconds=6)` | FIFO stall until `deadline - 1` | Lever A |
| `tests/test_sampling_render.py:278` | `Budget(wall_seconds=20)`; releaser holds 35 s (`:263`); the 17.08 s slowest test in the suite is `test_stalled_image_hash_stops_at_wall_budget_and_keeps_prior_result` | A 20 s budget means roughly 19 s of stall by design | The largest single lever; this one sets the whole `-n auto` wall time |
| `tests/test_sampling_render.py:559, 590, 976` | `Budget(wall_seconds=6/30/5)` | Mostly stall (`:559`), upper bounds (`:590`) or error paths (`:976`) | `:559` is the 5.05 s parametrised group |
| `tests/test_sampling_render.py:63, 627` | `Budget(1, clock=lambda)` | Fake clock | none needed |
| `tests/test_sampling_render.py:503` | `serve_forever(poll_interval=0.05)` | In-process fake provider (`socketserver` default is 0.5 s) | already tuned |
| `tests/test_publication.py:27-30, 61, 79` | injected child `time.sleep(30)` after `marker.touch()`; `Budget(wall_seconds=8)` | The sleep is a stall; the deadline kills it at `8 - 1` s | Lever A; the 30 s sleep is never reached |
| `tests/test_publication.py:91-118` | `Budget(wall_seconds=60)`, but `bounded_publication` sets `budget.deadline = min(deadline, phase_started + 12)` | The 13.01 s test is a 12 s stall window at the publication boundary, by design, after cold preparation | Lever B: lower `+ 12` to about `+ 4`; the 60 s outer budget already covers cold start |
| `tests/test_publication_guards.py:217` | `Budget(wall_seconds=8)` | Guard-read stall | Lever A |
| `tests/test_publication_guards.py:61, 147, 165, 191, 281` | `Budget(wall_seconds=30)` | Success or fast-fail; upper bound only | none needed |
| `tests/test_refinement_owned.py:35` | `owned_scope(Budget(wall_seconds=4))`; asserts `< 6` s | Stall until `4 - 1` s inside the scope | Already minimal; the floor is about 2-3 s |
| `tests/test_refinement_owned.py:66` | `Budget(wall_seconds=8)` | Success path; real subprocess work | not a deadline issue |
| `tests/test_owned_process.py:51` | `time.sleep(min(0.25, limit))` in the `ps` stub | Charges probe latency to the timeout | tiny |
| `tests/test_owned_process.py:76, 78, 110` | child `time.sleep(30)`; `Budget(wall_seconds=2)` | Stall until the `2 - 1` s deadline | Already the lowest in the suite; do not lower |
| `tests/test_combined_stack.py:156, 164` | provider holds `release.wait(12)`; `Budget(wall_seconds=60)`; the test shortens the shared deadline with `+ 6` (`:~145`) | The injected `phase_started + 6` deadline is the real timeout | Lever B below |
| `tests/test_combined_stack.py:104` | `Budget(wall_seconds=120)` | Upper bound | none needed |
| `tests/test_jev_concurrency.py:40, 86` | child poll `sleep(0.01)` | Polls for a concurrent storage handshake | already fine |
| `tests/test_jev_concurrency.py:76, 93` | `Budget(wall_seconds=30)`, `result(timeout=20)` | Upper bounds | none needed |

### 2.3 Levers

**Lever A: the one-second reservation plus cold child start dominate.** Most stall tests wait for
`wall_seconds - 1` s although the assertion only needs the child to be provably blocked and then terminated.
The stall tests need `wall_seconds` to cover three things:

1. Python cold start in the child.
2. Reaching the stall marker or FIFO.
3. The 1 s production reservation (`owned_process.py:29, 42`).

`[INFERENCE]` Dropping 6 to about 3 and 8 to about 4 would keep the production path identical and save about 3-4 s per
stall test. The `marker.exists()` / `reached.is_set()` assertions already detect a budget that is too short.
Do this per test and measure; the `-n auto` wall time is set by the slowest test.

**Lever B: end the deadline from a ready signal, not a fixed duration.** `tests/test_combined_stack.py` already
does this: `bounded_post` (`:136-147`) shortens the shared `budget.deadline` to `phase_started + 6` once the transport
phase starts. This leaves cold start outside the timer. The same pattern in `test_sampling_render.py` and
`test_export.py` would let the outer budget stay large (for cold start) while the stall window is a small constant.
Keep the monkeypatch `min`-only so the shared deadline is never extended; that comment is already in
`test_combined_stack.py:~141-143`.

**Lever C: the releaser threads.** Five copies of the same releaser (`test_export.py:155-187`, and
`test_sampling_render.py:97-132, 160-196, 255-290, 435-460, 750-776`) are structurally identical. A shared fixture
would make a single change possible, but it saves no time on its own.

## 3. Subprocess spawning

- `host.run` (`logo_maker/host.py:15-41`) spawns `sys.executable -m logo_maker.host` through `owned_process.run`
  (`:19-24`) once per operation. Operations dispatched in `host.main` (`host.py:46-332`) include `selection_guard`,
  `export_guard`, `concept_states`, `refinement`, `export_eligibility`, `eligibility`, `write_json`, `read_json`,
  `append_jsonl`, `runlog_load`, `pipeline_inputs`, `apply_fixes`, `remove_path`, `publish`, `recover_publication`,
  `render_setup`, `render_attempt`, `render_execution`, `render_record`, `load_config`, `compile`,
  `sampling_controls`, `process_image`, `artifact_current`, `qa_checks` and `tiny_image`.
- `render.py` calls `_host_work` (an alias of `host.run`, `render.py:19`) at `:183, 193, 208, 251, 295, 307, 335, 450,
  680`. Each is a cold interpreter start with `import logo_maker...`; `judging.py:166` does the same.
- **Already inlined in synthetic tests:** `tests/test_refinement.py:11-25` (`inline_refinement_workers`) replaces
  `host.run` only for `refinement`, `concept_states` and `pipeline_inputs`, running `host.main` in process under
  `refinement.owned_scope(None)`. It is applied autouse in `test_refinement.py:27-29` and
  `test_eligibility.py:11-17`, where `render.machine_context` is also patched to `{}`.
  Every other operation still goes through `original(...)`.
- **Not inlined, so still real subprocesses:** `selection_guard`, `export_guard`, `eligibility`,
  `export_eligibility`, `publish`, `recover_publication`, `write_json`/`read_json`/`append_jsonl`, `remove_path`,
  `render_*`, `compile`, `load_config`, `process_image`, `artifact_current`, `qa_checks`, `tiny_image`.
  `test_combined_stack.py`, `test_publication.py`, `test_publication_guards.py`, `test_export.py`, `test_refinement_owned.py`
  and `test_sampling_render.py` call pipeline functions that issue many of these. This is the likely source of the 8-13 s
  non-stall tests (`test_combined_selection...[missing_usage]` 12.08 s, a success path under
  `Budget(wall_seconds=120)` at `test_combined_stack.py:104`; the 13.01 s publication test is a 12 s injected stall, see section 2.2). `[INFERENCE]`: the per-operation cost is mostly interpreter start plus imports of heavy modules (numpy, PIL,
  skimage), which was not profiled here.
- **Must keep real subprocesses (they test ownership, process groups, cleanup, timeouts):**
  `tests/test_owned_process.py` (all), `tests/test_refinement_owned.py:35, 66`, the `time_limit` stall tests in
  `test_publication.py:27-79`, `test_publication_guards.py:217`, `test_export.py:181, 219-270`, and
  `test_combined_stack.py:156-167` (asserts the stall reaches the actual owned provider worker, `:167`).
  `test_jev_concurrency.py` patches `owned_process.run` (`:49-55`) and runs the real worker module on purpose.
- **Inline candidates:** extending the same `host.run` wrapper to the stateless data operations (`write_json`,
  `read_json`, `append_jsonl`, `runlog_load`, `remove_path`, `load_config`, `tiny_image`, `artifact_current`,
  `qa_checks`) for tests that are not about deadlines or ownership. `[INFERENCE]` The risk is that those same
  operations are the injection points for I/O stalls in the publication and sampling tests, so the inlining must be
  opt-in per test, not autouse.

## 4. Geometry, image, font and reconciliation work

- `tests/test_geometry.py` is 103 lines and emits 48 skimage `DeprecationWarning`s from marching cubes
  (`_marching_cubes_lewiner.py:237`), indicating many solid builds. It did not appear in the top 30 durations. Not a bottleneck.
- `test_export.py::test_export_set_sizes_and_manifest` (5.07 s) generates the full export set (SVG/PNG/ICO/PWA) once.
  Six other export tests in that file call `_concept(...)` plus `export_all`. `[INFERENCE]` repeated `export_all` calls
  across tests share no cached output. A module-scoped fixture would be unsafe where tests mutate outputs, so only the
  read-only assertions (size and manifest checks) could share one.
- `candidate_logo` / `finalize_logo` / `_concept` / `job` setup: 33 references in `test_eligibility.py`, 8 in
  `test_publication_guards.py`, 4 in `test_refinement_owned.py`, 3 in `test_export.py`, 2 each in
  `test_combined_stack.py` and `test_publication.py` (by grep). Each builds a logo directory per test. Not measured individually.
- `scripts/verify_reconciled_refinement.py`: `main` (`:61-76`) loops 7 bundles. `verify` (`:13-58`) calls
  `refinement.digest` (`logo_maker/refinement.py:147-148`, `hashlib.sha256(path.read_bytes())`) once per manifest file
  (`:15-17`), per case render (`:22`), per source (`:27`), per provider asset (`:38`), final image (`:43`) and runtime
  asset (`:52`), plus `verify_execution` per folder. There is no caching, no hashing of the same file twice within one
  bundle that I could confirm, and reads are whole-file (`read_bytes`). `git ls-files benchmarks` shows 2,459 tracked files, of which
  1,187 are under `benchmarks/refinement`; extensions are mostly json (1,164) and png (447). The cost is single-threaded
  and I/O bound. It was not timed here. CI runs it in two jobs (`ci.yml:~42` lint job and `:93` test job), so the
  same hashing happens twice per CI run.
- `test_example_render.py:24` is `@pytest.mark.render`, excluded by `-m "not render"`.
- xdist scheduling: no `--dist` flag anywhere (`pyproject.toml:72`, `justfile:40`, `ci.yml:95`). `[INFERENCE]` The default
  `load` mode hands out tests in small batches. With one 17 s test and many 5 s tests, order matters. The
  `loadscope`/`loadfile` modes would group a module's tests onto one worker and make the slowest-module tail worse,
  because the slow tests are concentrated in `test_sampling_render.py` (about 1,000 lines). `worksteal` is the candidate to measure.

## 5. Hook and linter overhead

- `.pre-commit-config.yaml` has 4 repos: pre-commit-hooks (`:4-15`), ruff (`:17-21`), typos (`:23-28`) and rumdl (`:30-33`).
  Header comment (`:1`): ty and pytest run via `just check` and CI only.
- `check-added-large-files`, `check-merge-conflict`, `check-toml`, `check-yaml`, `end-of-file-fixer` and
  `trailing-whitespace` run over every tracked file. `git ls-files` lists 2,647 files, of which 2,459 are under `benchmarks/`.
  `end-of-file-fixer` and `trailing-whitespace` carry long `exclude` regexes (`:11-15`) for `benchmarks/omp/*` and a growing
  list of dated `benchmarks/refinement/*/(snapshots|validation)/` bundles. Each new bundle needs another alternative, and
  the regex is duplicated between the two hooks.
- `typos` (`:23-28`) and `rumdl` (`:30-33`) have no `exclude`, so both scan the benchmarks tree. `[INFERENCE]` unless
  they have their own config files; I did not look for `_typos.toml`, `typos.toml` or `.rumdl.toml`.
- `pyproject.toml:101`: `extend-exclude = ["js/node_modules", "logos", "benchmarks/refinement/evidence"]`. The ruff hook
  (`ruff-check`, `ruff-format`) gets the file list from pre-commit and honours `extend-exclude`
  `[INFERENCE: prek passes explicit filenames, so ruff would need --force-exclude for the exclusion to apply]`.
  `just lint` runs `ruff check .` (`justfile:21`) over the repo root, so the 57 Python files under `benchmarks/` outside `evidence`
  are linted (the other `benchmarks/refinement/*` bundles are not excluded).
- Duplication between hook stage and CI: `ruff check`/`ruff format` run in both `prek` (`.pre-commit-config.yaml:19-21`)
  and the `lint` job (`ci.yml:32-35`); `just check` runs `hooks lint type test` (`justfile:55`), so ruff runs twice locally.
  `ty check` runs in two CI jobs (`ci.yml:40`, `:89`) and `verify_reconciled_refinement.py` in two (`:42`-ish, `:93`).
- `just hooks` uses `uvx prek run --all-files` (`justfile:51-52`); `uvx` resolves prek outside the locked environment.

## 6. Summary of bottlenecks by estimated value

1. Stall tests wait `wall_seconds - 1` s for real. The 20 s budget at `test_sampling_render.py:278` is the single
   test that sets the 37.7 s `-n auto` wall time; the 6-8 s budgets form the next tier. Fix with Lever A or B.
2. `just test` is serial (`justfile:40`), while CI uses `-n auto`. A serial run did not finish in 280 s.
3. Non-stall tests of 7-13 s spend time in real `host.run` subprocesses that are not inlined (section 3).
4. `scripts/verify_reconciled_refinement.py` is run twice per CI run and hashes whole files serially.
5. Hook `exclude` regexes are duplicated, and `typos`/`rumdl` have none (section 5).

Sections 1-6 are the pre-change inventory. Section 7 records what was then measured and changed; where the two disagree,
section 7 is current (for example `ty check` and the evidence verifier now run in the `prek`-stage hooks locally, and
`just test` is parallel).

## 7. Measured iterations

Machine: Apple M5 Pro, 18 cores (6 + 12), 48 GiB. Command: `PAG_USE_LOCAL_REV=1 uv run --no-sync python -m pytest -q
-m "not render and not live" -n auto [--dist worksteal]` (524 tests), plus `uvx prek run --all-files -v` for the static
hooks. Each row is one run; run-to-run noise is about plus or minus 1.5 s, so changes under that are marked as noise.
Serial baseline before any change: 294.7 s.

| Iter | Change | pytest wall (s) | Slowest test (s) | Verdict |
| ---: | --- | ---: | ---: | --- |
| 0 | baseline: `pytest-xdist` `-n auto`, default `--dist load` | 39.05 | 18.05 | reference |
| 1 | export deadline test `Budget(20)` to `Budget(6)` | 36.69 | 17.08 | reverted in iteration 18: failed 3 times on the hosted runner |
| 2 | stalled image-hash test: `min`-only deadline patch, `+3` s after the FIFO exists | 37.09 | 12.39 | kept |
| 3 | publication stall budgets `8` to `5` s, `+12` to `+6` s (3 s and `+4` broke 4 tests: `publish()` needs more than 4 s) | 33.48 | 10.83 | kept |
| 4 | `test_sampling_render.py` stall budgets `6`/`5` to `3`/`4.5` s (3 s broke 3 render stalls; 4.5 s is the floor) | 33.30 | 10.87 | kept |
| 5 | `--dist worksteal` (A/B: `load` 32.9, `worksteal` 25.5, `loadfile` 54.4); also blocked-QA budget back to 5 s after a 3 s flake | 26.96 | 11.37 | kept |
| 6 | longest-first ordering from pytest's cache (`tests/conftest.py`) | 25.64 | 11.37 | superseded by iteration 19 |
| 7 | `conftest` works under `-p no:cacheprovider`; publication guard read stall `8` to `5` s | 24.00 | 10.66 | kept |
| 8 | exclude benchmark data from `typos` | prek 0.39 s, unchanged | n/a | reverted: typos runs in parallel chunks, no gain in `prek` |
| 9 | `just check` no longer re-runs `lint` and `type` after `hooks` | n/a: 1.35 s to 0.98 s | n/a | kept |
| 10 | lazy `import httpx` in `jev/client.py` (eligibility/judging worker import 50 to 25 ms) | 20.08 | 7.37 | kept, the largest single gain |
| 11 | lazy `coloraide` in `checks.color_report` (export worker import 69 to 44 ms) | 21.77 | 7.35 | kept as an import cut; wall change is within noise |
| 12 | Jev post stall window `+6` to `+4` s | 21.31 | 5.78 | kept (with 13) |
| 13 | lazy `numpy` in `sampling_diagnostics` (`render` import 28 to 14 ms) | 21.31 | 5.78 | kept (with 12) |
| 14 | `--maxschedchunk 1` (A/B 22.4 vs 22.4, 3 runs each) | no change | n/a | not adopted |
| 15 | 1000 px instead of 4000 px synthetic final in the blocked-QA fixture | n/a | n/a | rejected: `asset_corrupt` expects the edge-QA outcome of the 4000 px image |
| 16 | host worker no longer imports `owned_process`, `proc`, `sampling` (parent-only) | 20.74 | 6.83 | kept (`read_json` 26 to 18 ms, `refinement` 48 to 42 ms) |
| 17 | lazy `tomlkit` in `pipeline` | 22.13 | 6.32 | reverted: no measurable change |
| 18 | first hosted run (PR #19, `macos-latest`): `Offline tests` step 157.6 s versus 10m11s before; 3 failures, all `test_export_deadline_stops_tool_and_its_detached_browser`, whose 6 s budget the slower runner could not meet. Restored the original `Budget(20)` | hosted 157.6 | n/a | iteration 1 rolled back |
| 19 | `conftest` deals the slowest tests across xdist worker blocks (with 20 s export budget: sorted-only 37.9 s, dealt 24.5 s) | 24.5 | 18.05 | kept; explains the 39 s baseline |

Findings behind the table:

- Where the time went: of one 5 s test, 4.3 s was 59 `communicate()` calls into `python -m logo_maker.host` workers
  (about 72 ms each when run alone). A bare `python -c pass` is 15 ms and a bare spawn from a 380 MB parent is 18 ms, so the
  remaining per-worker cost was imports. Trimming them paid in production too, not only in tests.
- CPU was not saturated: 215 CPU-s over 22 s is about 9.8 of 18 cores. The 62 s of sleeping stall tests do not use CPU.
- Oversubscription is not free: `-n 24` ran in 22.5 s, but `-n 32` failed 3 export-deadline tests, because the shortened
  budgets leave less headroom under CPU starvation. `-n auto` stays the default.
- `-n 12` took 28.7 s. xdist start-up (18 workers each collecting 524 tests) costs about 2.25 s before any test runs.
- A copied finalized logo tree is not path-equivalent: reusing one `finalize_logo` result across the export-guard cases made
  all 6 cases fail, because the retained records bind absolute paths. Not used.
- `verify_reconciled_refinement.py` is 136 ms for 2,114 hashes. It runs only when files under `logo_maker/` or
  `benchmarks/refinement/` change, so it was left alone.
- Editing `logo_maker/` while the suite runs fails tests (a source fingerprint changes mid-judgment). One of eight
  back-to-back runs failed 8 tests exactly when a source file was edited; the other seven passed.

Why iteration 19 matters: `--dist worksteal` hands each worker one contiguous block of the collected items. The two 18 s
export-deadline cases are adjacent parametrizations, so they landed on one worker and ran back to back (18.1 s then 17.3 s,
finishing at 38.0 s). That, not total CPU, was the 39 s baseline. Dealing the longest tests across blocks puts them on
different workers. On a cold checkout there is no duration cache, so adjacent slow cases can still collide.

Caveat: the numbers are one machine plus one hosted run. The shortened budgets that remain (publication 5 s, render stalls
3-4.5 s, Jev post `+4` s, guard read 5 s) passed on that hosted run but its flake rate is unmeasured. Iteration 1 shows the
risk is real on a slower CPU.
