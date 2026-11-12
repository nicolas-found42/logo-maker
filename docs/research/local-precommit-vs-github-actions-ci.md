# Local pre-commit/pre-push vs GitHub Actions CI

**Date:** 2026-11-11. **Evidence limits:** One workstation (Apple M5 Pro, 18 cores, 48 GiB: `sysctl` reported `Apple M5 Pro`, `18`, `51539607552`; `prek 0.5.10`). GitHub timings come from `gh api repos/nicolas-found42/logo-maker/actions/runs/43116585820/jobs` (one run; step timestamps have 1 s resolution) plus run start/end times of three later `ci` runs. Local timings are single wall-clock runs, warm caches, uv/ruff/ty already installed; the serial `pytest` figure was measured twice on a busy machine (294.66 s here; the coordinating agent saw 298.14 s). The `-n auto` figure is one run. Nothing was changed in production code, workflows or hook config. The GitHub docs quotes are from the rendered "Available rules for rulesets" page; the `integration_id` behaviour for commit statuses was not tested against the live repository.

## Conclusions

1. **Almost all of CI wall time is the `test` job on `macos-latest`: 12m25s** (run 43116585820). Everything else finishes in 14–22 s. Of the 12m25s, 1m57s is setup before pytest, and **10m11s is the single `pytest` step** (not ~8m50s). The type check (1 s) and the refinement-evidence verifier (1 s) are negligible.
2. **Locally, everything except pytest takes under ~1 s each**: `prek run --all-files` 0.84 s, `ruff check` 0.77 s, `ruff format --check` 0.04 s, `skill_check.py` 0.04 s, `ty check` 0.17 s, `verify_reconciled_refinement.py` 0.16 s, `uv lock --check` 0.01 s. All of them fit a `pre-commit` hook (total about 2.1 s measured in one shell loop).
3. **Offline pytest is ~295 s locally because of wall-clock deadline tests, not CPU work.** The slowest 25 calls are mostly 4–18 s each, and they sleep or stall until a `Budget(wall_seconds=...)` fires. **`pytest-xdist -n auto` brought the same 524 tests to 39.5 s** on this 18-core Mac with no code change (multi-run stability and hosted-runner core counts are evaluated in the telemetry iterations).
4. **The `Protect main` ruleset requires `template/pr`, `lint`, `prek`, `test`, each with `integration_id: 15368` (GitHub Actions).** Moving `test` off Actions without changing the ruleset makes every PR unmergeable. Per GitHub docs, a status posted by anyone else is rejected for a check pinned to an app; "any source" is needed for a locally published status.
5. **Client-side hooks are advisory** (`git commit/push --no-verify`, or hooks never installed). They speed the feedback loop; they do not enforce anything on the server.
6. **Recommendation:** install `prek` hooks (`pre-commit`: fast static checks + lock/skill/type/evidence verifiers; `pre-push`: parallel `pytest -n auto`), and speed up the test suite and check pipeline iteratively with telemetry.

## 1. What runs where today

| Surface | What runs | Source |
| --- | --- | --- |
| `ci.yml` job `lint` (ubuntu) | `uv lock --check`, `uv sync --locked --only-group dev`, `ruff check`, `ruff format --check`, `scripts/skill_check.py` | `.github/workflows/ci.yml:21-42` |
| `ci.yml` job `prek` (ubuntu) | `j178/prek-action` with `--all-files` | `.github/workflows/ci.yml:44-52` |
| `ci.yml` job `test` (macos) | setup-uv, setup-node 24, `brew install` node-canvas libs, `npm ci --prefix js`, PWA Chrome provision, `uv sync --locked`, `ty check`, `verify_reconciled_refinement.py`, `pytest -q -m "not render and not live"` with `PAG_USE_LOCAL_REV=1` | `.github/workflows/ci.yml:54-95` |
| `template-validation.yml` | `pull_request_target` and `issues` events; runs `python3 scripts/template_check.py --github` on the trusted base SHA and publishes status `template/pr` (`statuses: write`) | `.github/workflows/template-validation.yml:3-40`; `scripts/template_check.py:PR_CONTEXT = "template/pr"` |
| `.pre-commit-config.yaml` | pre-commit-hooks (large files, merge conflict, toml, yaml, EOF, whitespace), `ruff-check`, `ruff-format`, `typos`, `rumdl`. File header: "Commit-stage hooks only: fast checks. ty and pytest run via `just check` and CI." | `.pre-commit-config.yaml:1-40` |
| `justfile` | `hooks` = `uvx prek run --all-files`; `lint`; `type`; `test`; `check: hooks lint type test render-example` | `justfile` |
| Not in CI | `render`-marked tests (GPU) and `live` tests | `pyproject.toml:66-72`; `ci.yml:4` comment |

The hooks are not installed in this clone (`ls .git/hooks` shows only `*.sample`; `git config core.hooksPath` empty), so the local commit path currently runs nothing automatically.

### GitHub timings (run 43116585820, PR event)

| Job (runner) | Wall | Step breakdown (from `steps[].started_at/completed_at`) |
| --- | --- | --- |
| `prek` (ubuntu) | 14 s (23:02:09–23:02:23) | checkout 5 s, prek-action 6 s |
| `lint` (ubuntu) | 22 s (23:02:09–23:02:31) | checkout 5 s, lock check 1 s, ruff steps <1 s. The run predates the `Skill check` step, so it is absent from the steps. |
| `test` (macos) | **12m25s** (23:02:09–23:14:34) | set up 2 s, checkout 12 s, setup-uv 19 s, setup-node 1 s, **brew 22 s**, **npm ci 50 s**, PWA browser 6 s, uv sync 3 s, ty 1 s, verify 1 s, **pytest 10m11s** (23:04:06–23:14:17), post/cleanup ~5 s |

Pre-pytest overhead is 117 s (23:02:09→23:04:06). Whole-run durations of later `ci` runs: 43118569859 (push) 23:16:40→23:30:50 = 14m10s; 43119451490 (PR) 23:23:28→23:34:48 = 11m20s. So the pytest step on the hosted Mac varies roughly 9–12 min and takes ~2x the local serial time. `gh api .../actions/runners` returns `total_count: 0`: no self-hosted runner exists.

### Local timings (warm, one run each)

| Command | Wall |
| --- | --- |
| `uvx prek run --all-files` | 0.84 s |
| `uv lock --check` | 0.01 s |
| `uv run --locked ruff check .` | 0.77 s |
| `uv run --locked ruff format --check .` | 0.04 s |
| `uv run --locked python scripts/skill_check.py` | 0.04 s |
| `uv run --locked ty check` | 0.17 s |
| `uv run --locked python scripts/verify_reconciled_refinement.py` | 0.16 s |
| `PAG_USE_LOCAL_REV=1 pytest -q -m "not render and not live"` (serial) | **294.66 s**: `524 passed, 6 deselected` |
| same with `uv run --with pytest-xdist ... -n auto` | **39.5 s**: `524 passed` |

## 2. Why pytest is slow

`--durations=25` from the serial run: the top call is 18.04 s, and the top 25 are all >= 4.10 s. The head of the list:

| Test | Duration |
| --- | --- |
| `test_export.py::test_export_deadline_stops_tool_and_its_detached_browser[deadline]` / `[denied_live]` | 18.04 s / 17.34 s (`Budget(wall_seconds=20)`, `tests/test_export.py:265`) |
| `test_sampling_render.py::test_stalled_image_hash_stops_at_wall_budget_and_keeps_prior_result` | 17.10 s (`wall_seconds=20`, `tests/test_sampling_render.py:278`) |
| `test_publication.py::test_finalize_interrupted_winner_publication_restores_winner_and_run_state` | 11.23 s (`tests/test_publication.py:118`, asserts `< 14` s) |
| `test_publication.py::test_committed_cleanup_stall_is_bounded...` | 7.07 s (`wall_seconds=8`, lines 61/79) |
| `test_combined_stack.py` timeout/selection cases | 5.2–6.0 s each (`Budget(wall_seconds=60/120)`, lines 104/164, with a worker stalled until release) |
| `test_publication_guards.py::test_export_publication_input_edit...[6 params]` | ~5.4 s each (`wall_seconds=30`, lines 61/147/191) |
| `test_sampling_render.py::test_finalize_blocked_qa_cannot_overrun...[5 params]` | ~5.07 s each (`wall_seconds=6`, line 559; asserts `< 9`) |
| `test_sampling_render.py::test_stalled_cached_image_check...` | 5.07 s |

Other fixed-deadline tests use `wall_seconds=6` (`test_export.py:181`, `test_sampling_render.py:122,187,770`), 8 (`test_publication.py`, `test_publication_guards.py:217`) and 4/8 (`test_refinement_owned.py:35,66`). Many other `Budget` uses (e.g. `wall_seconds=1` with an injected `clock`, `test_export.py:95`, `test_sampling_render.py:63`) use a fake clock and cost nothing. These tests deliberately stall a file read, hash or subprocess (FIFOs, detached browser child processes spawned with `sys.executable`, `tests/test_export.py:225-245`) and assert the budget kills it in time. The comments in `test_export.py:263` and `test_combined_stack.py:103` explicitly add slack for "slower hosted" CI machines.

**Subprocess spawning vs sleeping:** `logo_maker/host.py:19` runs `owned_process.run([sys.executable, "-m", "logo_maker.host"], ...)` whenever `pipeline.finalize`, `pipeline.preview`, `pipeline.export`, `render.artifact_current`, or `judging`/`eligibility`/`publication` call `host.run(...)`. In `tests/test_eligibility.py` (lines 11-16), `inline_refinement_workers` only inlines 3 of the 23 `host.py` operations (`refinement`, `concept_states`, `pipeline_inputs`), so each `pipeline.finalize` test still spawns ~14 `python -m logo_maker.host` child processes (28 spawns across 2 tests in `test_eligibility.py` took 1.98 s locally), and `test_export.py` / `test_owned_process.py:78,110` / `test_jev_concurrency.py:48` also spawn `sys.executable` helper children. Even so, the 7.5x `pytest-xdist -n auto` speedup (294.66 s → 39.5 s) shows that serial wall time is dominated by concurrent-friendly waiting and subprocess I/O rather than saturated 18-core CPU work.

**Options and effect (local, M5 Pro, 18 cores):**

| Option | Measured/expected | Cost |
| --- | --- | --- |
| `pytest-xdist -n auto` | 39.5 s measured (all 524 tests, no edits) | add `pytest-xdist` to the `dev` group in `pyproject.toml`/`uv.lock`; tests that share fixed paths or ports could race (none failed in this run). The floor is the longest single test (~18 s) plus startup. |
| `@pytest.mark.slow` + `-m "not render and not live and not slow"` for `pre-push` | [INFERENCE] ~10–20 s serial once the ~15 tests >= 5 s are excluded; not measured because no marker exists | must edit tests and register the marker (`pyproject.toml:68-71`); then slow tests only run in CI or `just check`. |
| Both | not measured | keeps a ~10–20 s pre-push and full coverage on the server. |

On GitHub's 4-vCPU-class macOS runner [INFERENCE: runner core count not queried], `-n auto` would help less than on 18 cores but the sleeping tests overlap regardless; the test step would likely fall well below 10 min. This is untested.

## 3. Hook stages and what fits where

Official semantics (pre-commit, https://pre-commit.com/#confining-hooks-to-run-at-certain-stages; prek mirrors them): `stages` limits a hook to `pre-commit`, `pre-push`, `commit-msg`, `manual`, etc.; `pre-commit` receives the staged files, `pre-push` runs on `git push` and can be given `--from-ref/--to-ref`; `manual` hooks only run via `prek run --hook-stage manual`. prek 0.5.10's CLI accepts `--stage` values `manual, commit-msg, post-checkout, post-commit, post-merge, post-rewrite, pre-commit, pre-merge-commit, pre-push, pre-rebase, prepare-commit-msg` (`uvx prek run --help`), and `prek install -t/--hook-type` installs a shim per type (`uvx prek install --help`). `repo: local` hooks with `language: system` and `pass_filenames: false` run a repo command once, not per file (pre-commit docs, "repository local hooks"). Install both shims with `prek install -t pre-commit -t pre-push`.

| Check | Local wall | Verdict |
| --- | --- | --- |
| existing prek hooks (ruff, typos, rumdl, yaml/toml, whitespace) | 0.84 s for all files | `pre-commit` (already configured) |
| `uv lock --check` | 0.01 s | `pre-commit` (local hook, `pass_filenames: false`; optionally `files: ^(pyproject.toml|uv.lock)$`) |
| `scripts/skill_check.py` | 0.04 s | `pre-commit` |
| `ruff check` / `format --check` | 0.77 / 0.04 s | already covered by `ruff-check`/`ruff-format` hooks; the CI `lint` job duplicates them |
| `ty check` | 0.17 s | `pre-commit` is acceptable; `pre-push` is safer if later slower |
| `verify_reconciled_refinement.py` | 0.16 s | `pre-commit` or `pre-push` |
| offline pytest, serial | ~295 s | neither; a hook that long will be bypassed |
| offline pytest with `-n auto` | ~40 s | `pre-push` |
| `render` tests | GPU, minutes | `manual` only (`just render-example`) |
| `npm ci`/brew/PWA provisioning | ~78 s on CI | not a hook concern; local env is already provisioned by `just setup` |
| `template-validation.yml` | n/a | Cannot run as a git hook: it validates PR/issue bodies that exist only on GitHub (`pull_request_target`/`issues` events). A local draft of a PR body can be checked by hand with `scripts/template_check.py`, but the required `template/pr` status is published by the workflow. |

## 4. Rulesets and moving checks off Actions

Live ruleset `Protect main` (id 26965992, `enforcement: active`, target `refs/heads/main`, `bypass_actors: []`), from `gh api repos/nicolas-found42/logo-maker/rulesets/26965992`:

- `required_status_checks`: `template/pr`, `lint`, `prek`, `test`, each `integration_id: 15368`; `strict_required_status_checks_policy: true` (branch must be up to date); `do_not_enforce_on_create: false`.
- Also `deletion`, `non_fast_forward`, and `pull_request` (0 required approvals, review thread resolution required, stale reviews dismissed).
- No bypass actors (`bypass_actors: []`), so `gh pr merge --admin` cannot bypass a missing check directly, though a repository admin can still edit or temporarily disable the ruleset via the REST API.

GitHub docs (https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets, "Require status checks to pass"): "Any person or integration with write permissions to a repository can set the state of any status check... When you add a required status check rule, you can select an app as the expected source... If the status is set by any other person or integration, merging won't be allowed. If you select 'any source,' you can still manually verify the author of each status". So `integration_id: 15368` is a restriction on who can publish `test`: a `gh api` status posted with a user token will not satisfy it.

| Pattern | What changes | Enforcement / tradeoff |
| --- | --- | --- |
| **A. Fast CI + local hooks.** Remove `test` from the ruleset (or from `ci.yml` plus the ruleset), keep `template/pr`, `lint`, `prek` (14–22 s on ubuntu); run xdist pytest in `pre-push`. | Merge latency ~25 s. | Tests are no longer server-enforced; `--no-verify` or a missing hook install bypasses them silently. Acceptable only as a deliberate single-developer policy. Dropping `test` also drops `ty` and the evidence verifier from the server unless moved into `lint` (they take ~1 s each on a runner once dependencies sync). |
| **A′. Keep required `test`, but make it fast.** Add `pytest-xdist`, run `-n auto` on the runner; optionally split `ty`/verifier into the cheap `lint` job. | Not measured on a hosted Mac. | Full server enforcement retained; no ruleset change. |
| **B. Local hook/`just push` posts a commit status.** After running checks, `gh api -X POST repos/{owner}/{repo}/statuses/$SHA -f state=success -f context=test`. | Requires editing the `test` entry to *any source* (omit `integration_id`) in the ruleset. | Enforcement becomes honor-system: anyone with write access can post `success` without running anything; it is no stronger than Pattern A, only more visible. Statuses are per-SHA, so with `strict` any rebase/merge-up needs a re-post. It cannot satisfy the existing `integration_id: 15368` entry. |
| **C. Self-hosted runner on this Mac** (`runs-on: self-hosted` for `test`). | None to the ruleset: the job is still GitHub Actions, so `integration_id: 15368` is satisfied. Removes brew/npm/browser cold setup (~100 s) and uses native speed. | Real server-side enforcement. Costs: Mac must be online for any merge (no runners exist today per `actions/runners`); GitHub advises against self-hosted runners on public repos because forks' PRs run code on your machine [INFERENCE: repository visibility not queried]; shared state between runs; ephemeral/clean-environment guarantees are lost. |

Pre-commit/pre-push hooks are client-side: `git commit --no-verify` and `git push --no-verify` skip them, and they only exist after `prek install`. Therefore hooks should be treated as a fast feedback layer, and whichever checks must be mandatory stay behind a required check (A′ or C, not A or B).

## 5. Actionable options (ordered)

1. `prek install -t pre-commit -t pre-push` locally; add `uv lock --check`, `skill_check.py`, `ty check` and the verifier as `repo: local` hooks (`language: system`, `pass_filenames: false`), pre-commit stage (~1.2 s combined from the table).
2. Add `pytest-xdist` to the `dev` group and use `-n auto` in `just test`, the `pre-push` hook and the CI `test` step; re-measure the hosted Mac before deciding anything about Pattern C.
3. Only if CI latency is still unacceptable, consider Pattern C or restructuring (A) with an explicit decision that tests are not server-enforced.
4. Optionally split the 5–18 s deadline tests behind a `slow` marker for a ~10–20 s serial `pre-push` (needs a measurement after adding the marker).
