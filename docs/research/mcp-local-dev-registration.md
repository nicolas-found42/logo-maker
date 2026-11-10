# logo-maker — registering the MCP server from a live checkout (2026-11-10)

Target machine: macOS arm64, Claude Code 2.1.319, codex-cli 0.166.0, omp (oh-my-pi) with docs via `read omp://`, uv 0.13.6 at `/opt/homebrew/bin/uv`. Repo: `/Users/nicolas/Documents/github/logo-maker`.
Goal: `logo-maker mcp` registered with all three hosts so that (a) it works while `logo-maker` is **not** on PATH and (b) it always runs the **current checkout** (edit, restart/reload the MCP server, test; no reinstall).
Probes were run from `/tmp/mcpprobe/` with a throwaway shell-script "server" that records its `pwd`/argv/env, fed to each host through a temp config (`claude -p --strict-mcp-config --mcp-config`, `codex exec -c mcp_servers.*`, a temp `.omp/mcp.json` in `/tmp`). No host config file, repo source, or `scripts/install.py` was touched.

## Recommended config per host

One launch command works everywhere: **`uv run --quiet --project <abs repo> logo-maker mcp`** (absolute `uv`, absolute repo path). `uv run` syncs the project env (editable install of `logo_maker`), then execs `.venv/bin/logo-maker`, so Python edits are live on the *next server start*. Wrapper stdout stays clean (verified: handshake reply is the first and only stdout line; uv's own chatter goes to stderr). `--project` does not change cwd, and that is fine: stage slugs resolve to `REPO_ROOT/logos/<slug>` (`logo_maker/paths.py:43`), not to cwd.

`UV=/opt/homebrew/bin/uv`, `REPO=/Users/nicolas/Documents/github/logo-maker`.

### 1. Claude Code (user scope, any directory)

```bash
claude mcp add logo-maker --scope user --transport stdio \
  -- /opt/homebrew/bin/uv run --quiet --project /Users/nicolas/Documents/github/logo-maker logo-maker mcp
```

Writes to `~/.claude.json` (user scope, all projects, not committed). Long GPU compile: raise the per-server tool timeout (milliseconds) by editing that entry, or env-wide:

```json
{
  "mcpServers": {
    "logo-maker": {
      "command": "/opt/homebrew/bin/uv",
      "args": ["run", "--quiet", "--project", "/Users/nicolas/Documents/github/logo-maker", "logo-maker", "mcp"],
      "timeout": 3600000
    }
  }
}
```

(Same JSON shape works via `claude mcp add-json logo-maker '<json>' --scope user`.) Claude Code's default tool timeout is already ~28 h (`MCP_TOOL_TIMEOUT` default 100000000 ms) and startup is 30 s (`MCP_TIMEOUT`); the explicit `timeout` is optional but mirrors omp's entry. Reload after code edits: `/mcp` → logo-maker → **Reconnect** (respawns the stdio process).

If the shared project-root `.mcp.json` is kept as-is (`"command": "logo-maker"`) Claude still reports `Executable not found in $PATH`; a user-scope entry of the same name takes lower precedence than project scope (local > project > user), so either remove the bare entry from the repo `.mcp.json`, or change its command to the `uv run` form with an absolute path (see Open decisions).

### 2. Codex CLI (`~/.codex/config.toml`, shared by CLI, IDE, desktop app)

```bash
codex mcp add logo-maker -- /opt/homebrew/bin/uv run --quiet --project /Users/nicolas/Documents/github/logo-maker logo-maker mcp
```

then add the timeouts the CLI flag does not set:

```toml
[mcp_servers.logo-maker]
command = "/opt/homebrew/bin/uv"
args = ["run", "--quiet", "--project", "/Users/nicolas/Documents/github/logo-maker", "logo-maker", "mcp"]
startup_timeout_sec = 120     # default 10 s; first start may sync the env
tool_timeout_sec = 3600       # default 60 s; Metal kernel compile can take minutes
# cwd = "/Users/nicolas/Documents/github/logo-maker"   # optional, ABSOLUTE only
```

Use **absolute paths only**: Codex does not expand `${VAR}` or `~` in `command`/`args`/`env`/`cwd` (probed). Project-scoped alternative: `<repo>/.codex/config.toml` with the same table (loaded only if the project is trusted). Reload: servers are spawned per Codex session; start a new `codex` session (TUI `/mcp` lists status; no reconnect command is documented).

### 3. omp (oh-my-pi)

User scope `~/.omp/agent/mcp.json` (what `scripts/install.py` writes today), project scope `<repo>/.omp/mcp.json`:

```json
{
  "mcpServers": {
    "logo-maker": {
      "type": "stdio",
      "command": "/opt/homebrew/bin/uv",
      "args": ["run", "--quiet", "--project", "/Users/nicolas/Documents/github/logo-maker", "logo-maker", "mcp"],
      "timeout": 3600000
    }
  }
}
```

omp expands `${VAR}`/`${VAR:-default}` in `command`, `args`, `env`, `cwd` (probed) but **not `~`**, so `"${HOME}/Documents/github/logo-maker"` is also valid in the project file. Reload after edits: `/mcp reconnect logo-maker` (one server) or `/mcp reload` (rediscover + reconnect all); `/mcp test logo-maker` for a handshake check. Note omp also reads the repo-root `.mcp.json` as a low-priority fallback source (first definition wins across providers, so the omp-native user entry shadows it).

### Zero-uv-at-runtime alternative (all three hosts)

`/Users/nicolas/Documents/github/logo-maker/.venv/bin/logo-maker` with `args: ["mcp"]` is exactly what `uv run` execs (`uv run --project $REPO which logo-maker` → `$REPO/.venv/bin/logo-maker`, probed) and the `.venv` already contains an editable finder (`__editable___logo_maker_0_1_0_finder.py`). Fastest start, no lock check, but nothing re-syncs dependencies; run `uv sync` yourself after `pyproject.toml`/`uv.lock` edits. Do **not** use `python -m logo_maker`: the package has no `logo_maker/__main__.py` (checked) — module form would be `python -m logo_maker.cli` only if `cli.py` has an `if __name__` guard `[INFERENCE: not checked]`.

## Per-host facts (evidence)

### Config locations and schemas

| | Claude Code | Codex CLI | omp |
|---|---|---|---|
| User scope | `~/.claude.json` (user scope; also holds local scope per project path) | `~/.codex/config.toml`, `[mcp_servers.<name>]` | `~/.omp/agent/mcp.json` (`~/.omp/profiles/<name>/agent/mcp.json` under `--profile`) |
| Project scope | `<repo>/.mcp.json` (`--scope project`) | `<repo>/.codex/config.toml`, trusted projects only | `<repo>/.omp/mcp.json`; also fallback root `mcp.json`/`.mcp.json` |
| Add via CLI | `claude mcp add [-s local\|user\|project] [-e K=V] <name> -- <cmd> [args]`, `add-json` | `codex mcp add <name> [--env K=V] -- <cmd...>` | `/mcp add` wizard in TUI, or edit JSON |
| Stdio keys | `command`, `args`, `env`, `timeout` (ms), `type` | `command`, `args`, `env`, `env_vars`, `cwd`, `startup_timeout_sec`, `startup_timeout_ms`, `tool_timeout_sec`, `enabled`, `required` | `type:"stdio"`, `command`, `args`, `env`, `cwd`, `timeout` (ms), `enabled`, `instructions` |
| Default startup / tool timeout | `MCP_TIMEOUT` 30 s / `MCP_TOOL_TIMEOUT` ~28 h | 10 s / 60 s | 30 s request timeout (`timeout`; `0` disables; `OMP_MCP_TIMEOUT_MS` overrides) |

Sources: Claude scopes and file locations, `claude mcp add` syntax, per-server `timeout`, `MCP_TIMEOUT`, `MCP_TOOL_TIMEOUT` (<https://code.claude.com/docs/en/mcp>, <https://code.claude.com/docs/en/env-vars>); local `claude mcp add --help` (flags `-e`, `-s`, `-t`). Codex keys: <https://developers.openai.com/codex/mcp>, <https://developers.openai.com/codex/config-reference> (`mcp_servers.<id>.cwd`, `startup_timeout_sec` "default 10s", `tool_timeout_sec` "default 60s"); local `codex mcp add --help`. omp: `read omp://mcp-config.md` (Preferred config locations, Supported server fields, `OMP_MCP_TIMEOUT_MS`).

### Variable expansion, `~`, and working directory (probed, not just documented)

| | Claude Code | Codex CLI | omp |
|---|---|---|---|
| `${VAR}` / `${VAR:-d}` | **Yes** in `command`, `args`, `env`, `url`, `headers` of `.mcp.json`/`~/.claude.json` | **No** (literal `${HOME}/y` and `FOO=${HOME}` observed) | **Yes** in `command`, `args`, `env`, `cwd`, `url`, `headers`, `auth`, `oauth` (OMP-native + root fallback files) |
| `~` | **No** (literal `~/x`) | **No** — `cwd="~"` made the server fail to start (no process ran) | **No** in args (literal); `cwd="~"` failed to start |
| `cwd` key | **Ignored** (`cwd:"/tmp"` ran in the session dir; not documented) | Honored, default = session cwd | Honored, default = `getProjectDir()` |
| Effective cwd when unset | Directory `claude` was launched in (probed: repo dir) | Session cwd (probed) | Project dir = omp's cwd (probed `pwd=/tmp/mcpprobe/proj`) |
| Extra env for server | `CLAUDE_PROJECT_DIR` is set in the server's env (probed); not available to `${…}` in `.mcp.json` without a default, e.g. `${CLAUDE_PROJECT_DIR:-.}` (probed: expanded to `.`) | none | none |
| Relative paths | Resolve against that cwd (not the file's directory) | same | same |

Evidence: Claude: <https://code.claude.com/docs/en/mcp> ("Environment variable expansion in `.mcp.json`", Option 3 text on `CLAUDE_PROJECT_DIR` and `${CLAUDE_PROJECT_DIR:-.}`); `~`, `cwd` and cwd results are my probe (`/tmp/mcpprobe/cfg.json`, outputs `out.a.txt`/`out.b.txt`, run from the repo dir). Codex: <https://github.com/openai/codex/blob/main/codex-rs/rmcp-client/src/stdio_server_launcher.rs> (`cwd.map(PathBuf::from).unwrap_or(fallback_cwd)` — a plain path, no expansion; `command.current_dir(&cwd).envs(&envs).args(&args)`), config key type `LegacyAppPathString` in `codex-rs/config/src/mcp_types.rs:407`; probe via `codex exec -c mcp_servers.*`. omp: `read omp://mcp-config.md` § "Discovery-time `${...}` expansion"; `packages/coding-agent/src/mcp/transports/stdio.ts:597` (`this.config.cwd ?? getProjectDir()`); probe with temp `.omp/mcp.json`. Also: omp discovers project config only from its launch directory (a subdirectory of the project did **not** load `.omp/mcp.json`; probed).

### Project `.mcp.json` approval in Claude Code

Interactive sessions prompt before using a project-scoped `.mcp.json` server; until approved it shows `⏸ Pending approval (run claude to approve)` in `claude mcp list/get`, and approvals committed to the repo's `.claude/settings.json` are ignored in an untrusted folder. `claude -p`, Agent SDK and some cloud sessions load project servers without prompting; reset choices with `claude mcp reset-project-choices`. User-scope entries need no approval. Source: <https://code.claude.com/docs/en/mcp> ("Project scope", "Project server approvals and workspace trust"); local `claude mcp get --help` text ("Unapproved .mcp.json servers are shown as ⏸ Pending approval").

### Restart / reload after code edits

- **Claude Code**: stdio servers are spawned per session; they are not hot-reloaded. In an interactive session select **Reconnect** from the server's menu in `/mcp`; `/mcp reconnect all` retries failed/auth servers (v2.1.284+). `list_changed` notifications refresh tool lists only if the server sends them. Plugin servers: `/reload-plugins` reconnects a server only if its *configuration* changed. Sources: <https://code.claude.com/docs/en/mcp> ("Stdio servers that exit or fail to start", "Dynamic tool updates", `/mcp reconnect all`), <https://code.claude.com/docs/en/plugins/components> ("Reload").
- **Codex**: servers start with the session; docs describe `/mcp` as status listing only; no hot-reload or reconnect documented. Plugin installs need an app restart. Practical reload = new session `[INFERENCE: no reconnect command found in docs]`. Sources: <https://developers.openai.com/codex/mcp> (TUI section), <https://developers.openai.com/codex/plugins/build>.
- **omp**: `/mcp reconnect <name>`, `/mcp reload` (`disconnectAll` + rediscovery + `refreshMCPTools`), `/mcp test <name>`; no file watching (reload is explicit; auto-reconnect only on transport close with 500/1000/2000/4000 ms backoff). Source: `read omp://mcp-runtime-lifecycle.md` ("Interactive reload and live-change paths", "Health, reconnect, and partial failure behavior"), `read omp://mcp-config.md` ("`/mcp add` vs editing JSON directly").

When the stdio process is killed mid-call omp does not replay the call; Claude reports the server failed until Reconnect (interactive). Sources as above.

### Timeouts for the long Metal kernel compile

- Claude Code: per-server `"timeout"` (ms, ≥1000) is a hard wall-clock cap per tool call and overrides `MCP_TOOL_TIMEOUT`; default ~28 h. Stdio idle timeout (no response and no progress) is 30 min by default (`CLAUDE_CODE_MCP_TOOL_IDLE_TIMEOUT`, `0` disables) and a per-server `timeout` ≥1000 floors it. A compile longer than 30 min with no progress notifications would hit that idle check unless `timeout` (or the env) is set. `MCP_TIMEOUT` (default 30 s) is startup only — `uv run` with a warm env is ~0.2 s (probed) but a cold sync can exceed it. Sources: <https://code.claude.com/docs/en/mcp> ("per-server `timeout`…hard wall-clock limit", idle floor), <https://code.claude.com/docs/en/env-vars> (`MCP_TIMEOUT`, `MCP_TOOL_TIMEOUT`, `CLAUDE_CODE_MCP_TOOL_IDLE_TIMEOUT`).
- Codex: `tool_timeout_sec` default 60; set per server (seconds). `startup_timeout_sec` default 10; its first start with a cold `uv sync` can exceed that, so raise it or use the prebuilt `.venv/bin/logo-maker` form. No env override documented. Source: <https://developers.openai.com/codex/mcp>, <https://developers.openai.com/codex/config-reference>.
- omp: `timeout` is the MCP request timeout in ms (`3600000` = what `scripts/install.py` writes at line 79); `0` disables client-side timeouts; `OMP_MCP_TIMEOUT_MS` overrides every per-server value, so unset it. Source: `read omp://mcp-config.md` ("Shared fields", `OMP_MCP_TIMEOUT_MS`); local `scripts/install.py:73-91`.
- Repo-side limit (independent of host): `RENDER_TIMEOUT = 900.0` s for the bpy render subprocess, `logo_maker/render.py:19,87`.

## `uv run` vs `uv tool install --editable` vs direct venv

| Option | Live source? | Dependency / entry-point / package-data changes | Startup | Caveats |
|---|---|---|---|---|
| `uv run --quiet --project $REPO logo-maker mcp` | Yes (project installed editable by default) | **Picked up automatically on next start**: uv re-locks and re-syncs unless `--locked`/`--frozen`/`--no-sync` | ~0.2 s warm (probed: 0.18 s default, 0.04 s `--frozen`); cold sync may take minutes (sdf comes from git, bpy is ~760 MB) | A changed `pyproject.toml` can trigger a network re-resolve at server start → exceeds Codex's 10 s startup default. Needs `uv` reachable (use the absolute path) |
| `uv run --frozen …` | Yes | env synced to `uv.lock` without re-locking; stale lock ⇒ stale deps | fastest start | silent drift if you edit deps and forget `uv lock` |
| `uv run --locked …` | Yes | fails (exit non-zero) if `uv.lock` is stale — loud, good for CI | | MCP host just shows "failed" |
| `uv tool install --editable $REPO` | Python source yes | **Not** refreshed automatically: tool env is separate; re-run `uv tool install --editable --reinstall $REPO` (or `uv tool upgrade`) after dependency, entry-point or package-data changes | instant once installed | puts `logo-maker` in `~/.local/bin` (already on this machine's PATH, `uv tool dir --bin`), which also fixes the original "Executable not found" error for every host that inherits PATH; GUI-launched hosts may not inherit it |
| `$REPO/.venv/bin/logo-maker mcp` | Yes (editable finder present) | none until you `uv sync` | instant | breaks if `.venv` is deleted |
| `python -m logo_maker` | — | — | — | **Not available**: no `logo_maker/__main__.py` |

Flags that matter, all from the uv CLI reference <https://docs.astral.sh/uv/reference/cli/>: `--project <dir>` ("only change the project root directory") vs `--directory <dir>` ("Change to the given directory prior to running the command" — also changes cwd, which `logo-maker` does not need); `--quiet/-q` ("-qq: no output to stdout"; in normal mode uv still logs to stderr); `--no-progress`; `--frozen`; `--locked`; `--no-sync` ("Implies --frozen"); `UV_PROJECT_ENVIRONMENT` (absolute path ⇒ used as-is; relative ⇒ workspace root) — set it only if you want the MCP env separated from the dev `.venv`, otherwise concurrent `uv run` from a dev shell and from the host contend on the same `.venv`. Editable default: <https://docs.astral.sh/uv/concepts/projects/config/> ("By default, the project will be installed in editable mode… `--no-editable`"). Lock/sync behavior: <https://docs.astral.sh/uv/concepts/projects/sync/> ("Automatic lock and sync"; `uv run --locked/--frozen/--no-sync`). Tools: <https://docs.astral.sh/uv/concepts/tools/> ("Tool environments may be upgraded via `uv tool upgrade`, or re-created entirely via subsequent `uv tool install`"); local `uv tool install --help` (`-e, --editable`: "changes in the package's source directory are reflected without reinstallation"; `--reinstall`).

stdout hygiene (MCP stdio requires the server to write only protocol messages to stdout; <https://modelcontextprotocol.io/specification/2025-11-25/basic/transports#stdio>): verified `printf '<initialize>' | uv run --project $REPO logo-maker mcp` returns one JSON-RPC line on stdout and nothing else; stderr empty on a warm env. A *cold* sync prints "Resolved/Installed" progress, but uv writes that to stderr, so it cannot corrupt the stream; `--quiet` just keeps host logs clean. `[INFERENCE]` for the cold case (only the warm path was run; stderr routing is uv's documented behavior for status messages).

## Plugin route: does it track the live repo?

Facts (Claude Code):
- A marketplace **added from a local path** whose plugin entry uses a **relative path** `source` (this repo: `.claude-plugin/marketplace.json` has `"source": "."`) loads the plugin **in place**; edits take effect at the next session start or `/reload-plugins`, no version bump. `${CLAUDE_PLUGIN_ROOT}` points at the source directory. `--plugin-dir` plugins are also loaded in place, never copied. Every *other* marketplace plugin (GitHub/URL marketplaces, git sources) is copied to `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/` and stays pinned to that snapshot until the version changes. Source: <https://code.claude.com/docs/en/plugins/loading> ("In-place and copied plugins", "Versions and updates": "loads its current source files at every session start, whatever its version string says"), <https://code.claude.com/docs/en/plugin-marketplaces>.
- `${CLAUDE_PLUGIN_ROOT}` is substituted in a plugin's MCP `command`, `args`, `env`; `${CLAUDE_PROJECT_DIR}` too. Source: <https://code.claude.com/docs/en/plugins-reference> ("Environment variables" table), <https://code.claude.com/docs/en/mcp> ("Plugin-provided MCP servers": `"command": "${CLAUDE_PLUGIN_ROOT}/servers/db-server"`).
- **Probe correction (2026-11-10):** the claim above did not hold here. `claude plugin marketplace add <repo>` + `claude plugin install logo-maker@logo-maker-plugins` produced a **copied snapshot** at `~/.claude/plugins/cache/logo-maker-plugins/logo-maker/0.1.0/`, and `${CLAUDE_PLUGIN_ROOT:-.}` in the plugin's `.mcp.json` expanded to `.`, run from that copy (its own uv env, not the live checkout). The plugin server also appeared next to a same-purpose user-scope entry (`plugin:logo-maker:logo-maker` and `logo-maker`, both Connected, tools doubled), so the "matches by command" dedup did not apply. `scripts/install.py --agent claude` therefore links the skill into `~/.claude/skills` and registers only the user-scope `uv run --project <repo>` server.
- A plugin MCP server cannot be reconnected by editing source; `/reload-plugins` reconnects only if its *config* changed — use `/mcp` Reconnect for code edits.
- `uv` must be resolvable from Claude Code's PATH (`/opt/homebrew/bin` is on this machine's PATH); use `/opt/homebrew/bin/uv` for GUI launches `[INFERENCE: hosts started from Spotlight inherit a minimal PATH]`.

Facts (Codex):
- Marketplace discovery reads `.agents/plugins/marketplace.json` or legacy `.claude-plugin/marketplace.json`; `codex plugin marketplace add ./local-root` is supported. Installing copies the plugin to `~/.codex/plugins/cache/$MARKETPLACE/$PLUGIN/$VERSION/` (`$VERSION` = `local` for local plugins) and "loads the installed copy from that cache path rather than directly from the marketplace entry" — **a snapshot, not live**. Evidence on this machine: `~/.codex/plugins/cache/deckgen-plugins/deckgen/1.0.0/` is a full copy. Source: <https://developers.openai.com/codex/plugins/build> ("ChatGPT installs plugins into `~/.codex/plugins/cache/…`"), `codex plugin marketplace add --help` docs in the same page.
- `${CLAUDE_PLUGIN_ROOT}`-style substitution for Codex plugin `.mcp.json`: not documented `[INFERENCE: none]`; omp's portable Agent Plugins expand only `${PLUGIN_ROOT}`/`${PLUGIN_DATA}` (`read omp://mcp-config.md`). So the repo's shared `.mcp.json` (referenced by `.codex-plugin/plugin.json` `"mcpServers": "./.mcp.json"`) cannot hold one `${…}` form that every host expands. For Codex, an absolute `[mcp_servers.logo-maker]` in `~/.codex/config.toml` is the only route verified to track the live checkout.

Facts (omp): omp does not load Claude/Codex plugins via `--plugin-dir`; it discovers installed Claude marketplace plugins' MCP servers and root `.mcp.json` as lower-priority sources (`read omp://mcp-config.md` "Imported tool configs", "Discovery and precedence"). Prior note: `docs/research/logo-maker-install-facts.md` § "Plugin packaging".

## Open decisions for the repo (not changed here)

1. Root `.mcp.json` currently `command: "logo-maker"`: fails on every host without the binary on PATH, including omp's fallback read. Options: (a) delete it and rely on per-host entries from `scripts/install.py`; (b) change it to `/opt/homebrew/bin/uv run --quiet --project ${CLAUDE_PLUGIN_ROOT} …` (works for Claude plugin install only; omp/Codex see the literal string); (c) keep bare command and have `scripts/install.py` also run `uv tool install --editable` (already does) — then PATH (`~/.local/bin`) must be inherited.
2. `scripts/install.py` `register_omp_mcp` should write the `uv run --project <repo>` form (and `claude mcp add --scope user …` / `codex mcp add …` + `tool_timeout_sec`) instead of `command: "logo-maker"` if "no reinstall" is the goal.

Applied 2026-11-10: root `.mcp.json` now runs `uv run --quiet --project ${CLAUDE_PLUGIN_ROOT:-.} logo-maker mcp`. `${CLAUDE_PLUGIN_ROOT}` is the repo for the Claude local-marketplace plugin; elsewhere the default `.` is the launch cwd, so it works when the host starts in the repo (verified: `claude -p --mcp-config .mcp.json --strict-mcp-config` lists all ten `logo_*` tools). It does not work for Codex plugin installs (no expansion) or hosts started outside the repo; use the user-scope absolute entries above for those.

## Sources

Claude Code: <https://code.claude.com/docs/en/mcp> (scopes, `claude mcp add`, env expansion, approvals, reconnect, timeouts, plugin MCP); <https://code.claude.com/docs/en/env-vars> (`MCP_TIMEOUT`, `MCP_TOOL_TIMEOUT`, `CLAUDE_CODE_MCP_TOOL_IDLE_TIMEOUT`, `CLAUDE_CODE_PLUGIN_DIRS`); <https://code.claude.com/docs/en/plugins/loading> (in-place vs cached, versions); <https://code.claude.com/docs/en/plugins-reference> (`${CLAUDE_PLUGIN_ROOT}`); <https://code.claude.com/docs/en/plugins/components> (MCP servers, reload); <https://code.claude.com/docs/en/plugin-marketplaces>; <https://code.claude.com/docs/en/plugins/cli-reference> (`/reload-plugins`, `--plugin-dir`). Local: `claude mcp --help`, `claude mcp add --help`.
Codex: <https://developers.openai.com/codex/mcp>; <https://developers.openai.com/codex/config-reference>; <https://developers.openai.com/codex/config-basic> (project `.codex/` loaded only when trusted); <https://developers.openai.com/codex/plugins/build> (plugin cache, local marketplace); <https://github.com/openai/codex/blob/main/codex-rs/rmcp-client/src/stdio_server_launcher.rs>; <https://github.com/openai/codex/blob/main/codex-rs/config/src/mcp_types.rs>. Local: `codex mcp add --help`, `~/.codex/plugins/cache/deckgen-plugins/`.
omp: `read omp://mcp-config.md`, `read omp://mcp-runtime-lifecycle.md`; <https://github.com/can1357/oh-my-pi/blob/main/packages/coding-agent/src/mcp/transports/stdio.ts> (cwd default line 597); `~/.omp/agent/mcp.json` (existing entries, `timeout` usage).
uv: <https://docs.astral.sh/uv/reference/cli/> (`uv run`, `uv tool install` flags), <https://docs.astral.sh/uv/concepts/projects/sync/>, <https://docs.astral.sh/uv/concepts/projects/config/>, <https://docs.astral.sh/uv/concepts/tools/>.
MCP spec: <https://modelcontextprotocol.io/specification/2025-11-25/basic/transports> (stdio: stdout carries only protocol messages).
Repo-local: `.mcp.json`, `plugin.json`, `.codex-plugin/plugin.json`, `.claude-plugin/{plugin,marketplace}.json`, `.agents/plugins/marketplace.json`, `scripts/install.py:27,73-91,124`, `logo_maker/cli.py:46,125`, `logo_maker/paths.py:43`, `logo_maker/render.py:19,87`, `pyproject.toml` (`mcp>=2.3.0`, `requires-python >=3.13,<3.14`), `.venv/lib/python3.13/site-packages/__editable___logo_maker_0_1_0_finder.py`.
Probes (this machine, 2026-11-10): `/tmp/mcpprobe/` (probe.sh + temp configs) for Claude `-p --strict-mcp-config --mcp-config`, `codex exec -c mcp_servers.*`, `omp -p` with a temp `.omp/mcp.json`; `uv run --project $REPO logo-maker --version` timings (0.18 s default, 0.03–0.04 s `--frozen`/`--no-sync`); `uv run … logo-maker mcp` initialize handshake (clean stdout, empty stderr).
