# Metal under the Codex macOS sandbox, November 13, 2026

Codex issue #16931 reports that a restricted execution context returns zero Metal devices on an Apple M5 while a normal terminal sees the GPU. A later report reproduces zero devices on an M5 Pro in Codex Desktop's restricted workspace-write executor and describes a downstream Blender EEVEE startup crash. The standalone reproduction in #17644 shows that broadly denying `iokit-open` is enough to reproduce an MLX failure, and proposes broader IOKit access. The class-specific evidence below comes from a separate experiment. [Codex #16931](https://github.com/openai/codex/issues/16931), [M5 Pro report](https://github.com/openai/codex/issues/16931#issuecomment-5581167157), [Codex #17644](https://github.com/openai/codex/issues/17644)

## Smallest published additions to a working Seatbelt base

| Stage | Published observation |
| --- | --- |
| Enumerate the hardware | In a macOS 26.7.2 / M3 Pro default-deny profile, allowing the `AGXDeviceUserClient` IOKit user-client class made the device visible. Removing that allowance returned zero devices. |
| Compile Metal from a source string and dispatch compute | Allowing Mach lookup of `com.apple.MTLCompilerService` by exact global name additionally let a 1,024-element kernel run and return correct results. Removing the lookup grant left enumeration working and failed `makeLibrary(source:)`. |
| Create Metal shared events for MLX | The same reporter needed `IOSurfaceRootUserClient` for MLX. With that additional IOKit class, an MLX text-to-speech model ran with restricted filesystem access and network denied. The simple compute probe worked without this class. |
| Read hardware properties | The reporter's version-1 default-deny profile permitted IOKit property reads. When explicitly denied, `MetalPluginName` and `MetalPluginClassName` needed allowances to recover enumeration. |
| Read sysctls | There is no published one-rule-at-a-time sysctl result in that reproduction. Codex already allows named CPU and OS reads, including `hw.logicalcpu_max`, `hw.memsize`, `hw.model` and `kern.osvariant_status`. The evidence supports testing on the unchanged Codex sysctl base before adding rules. |

The M3 Pro experiment also reported zero devices in the actual Codex sandbox and an empty denial log. These are reported deltas against a working test profile, whose full baseline was not included. Apple describes a complete compute check as obtaining a device, loading a library, creating buffers and a pipeline, dispatching a command, and reading back the result. Apple's sample embeds an Xcode-built library, while the issue's probe compiles a source string at runtime. The compiler lookup observation specifically exercises the latter. [M3 Pro experiment](https://github.com/openai/codex/issues/16931#issuecomment-6846489089), [Codex sysctl base](https://github.com/openai/codex/blob/9825e4b2fe69d997dbf533e228445d50095e6ba8/codex-rs/sandboxing/src/seatbelt_base_policy.sbpl#L23-L82), [Apple Metal compute sample](https://developer.apple.com/documentation/metal/performing-calculations-on-a-gpu)

The exact additions reported for the source-compiling probe were:

```scheme
(allow iokit-open (iokit-user-client-class "AGXDeviceUserClient"))
(allow mach-lookup (global-name "com.apple.MTLCompilerService"))
```

That test did not establish whether an extra sysctl, file path, Mach service or IOKit class is necessary for Blender Cycles, Blender EEVEE, Metal under a different launch session, or other macOS and GPU generations. The report in #17644 proposes `IOGPUDeviceUserClient` but supplies no class-removal result establishing it as necessary. [M3 Pro experiment](https://github.com/openai/codex/issues/16931#issuecomment-6846489089), [Codex #17644](https://github.com/openai/codex/issues/17644)

## First-party policy precedent

- Apple's macOS WebKit GPU process profile directly allows `AGXDeviceUserClient` in one policy branch and allows `IOSurfaceRootUserClient` in its graphics rules. It includes method filtering on its `IOAccelerator` connection, allows the two Metal plugin registry properties, and permits `com.apple.MTLCompilerService` as an XPC service. This is precedent for narrowly identifying classes and the compiler service. Its additional operations cover browser graphics, media and process roles. [WebKit AGX rule](https://github.com/WebKit/WebKit/blob/f74ee3dffa44666d47a2d414bcf64d8cf1d10056/Source/WebKit/GPUProcess/mac/com.apple.WebKit.GPUProcess.sb.in#L80-L89), [WebKit graphics rules](https://github.com/WebKit/WebKit/blob/f74ee3dffa44666d47a2d414bcf64d8cf1d10056/Source/WebKit/GPUProcess/mac/com.apple.WebKit.GPUProcess.sb.in#L181-L222), [WebKit properties](https://github.com/WebKit/WebKit/blob/f74ee3dffa44666d47a2d414bcf64d8cf1d10056/Source/WebKit/GPUProcess/mac/com.apple.WebKit.GPUProcess.sb.in#L593-L606), [WebKit compiler lookup](https://github.com/WebKit/WebKit/blob/f74ee3dffa44666d47a2d414bcf64d8cf1d10056/Source/WebKit/GPUProcess/mac/com.apple.WebKit.GPUProcess.sb.in#L958-L971)
- Chromium's macOS GPU process profile uses the XPC service matcher for the same compiler name. Its WebGL group uses the broader `IOAccelerator` connection and names `IOSurfaceRootUserClient`. Its GPU profile lists six sysctl reads, four of which Codex already has by exact name, with `hw.busfrequency_compat` and `hw.cachelinesize_compat` in Codex where Chromium uses `hw.busfrequency_max` and `hw.cachelinesize`. Chromium also has shader-cache allowances and a file-extension grant for compiler access to on-disk shader sources. Those browser rules do not establish additional prerequisites for the in-memory compute probe. [Chromium GPU profile](https://chromium.googlesource.com/chromium/src/+/835ec8816d81824baeba572ce3695943a50e7e92/sandbox/policy/mac/gpu.sb#39), [Chromium common shader-cache rules](https://chromium.googlesource.com/chromium/src/+/835ec8816d81824baeba572ce3695943a50e7e92/sandbox/policy/mac/common.sb#77), [Codex sysctl base](https://github.com/openai/codex/blob/9825e4b2fe69d997dbf533e228445d50095e6ba8/codex-rs/sandboxing/src/seatbelt_base_policy.sbpl#L23-L76)
- The independently maintained nono project merged an opt-in macOS GPU permission. Its patch adds the two IOKit classes to its own baseline and the patch author shows an M1 Max run that creates a queue, compiles from source, dispatches and checks results. That baseline allowed network outbound. A separate first-hand report in Anthropic's sandbox-runtime identifies an actual `AGXDeviceUserClient` denial. That successful experiment used several Mach grants together, so it does not establish that each one is needed. [nono PR #610](https://github.com/nolabs-ai/nono/pull/610), [sandbox-runtime #560](https://github.com/anthropics/sandbox-runtime/issues/560)

## Codex upstream status

Both openai/codex `main` at `9825e4b2` and the then-latest stable release `rust-v0.169.0` grant `iokit-open` only to `RootDomainUserClient` in the base policy. The builder includes the base with separate filesystem and network policy fragments, and later adds a blanket `mach-lookup` denial for XPC service names. This makes the effective policy important when testing the exact compiler-service selector. The checked-in permission profile schema exposes filesystem, network, and workspace-root settings and has no GPU capability. Both issue reports are open, and the public issue timeline and PR search turned up no shipped Codex fix for this macOS behavior. The similarly named closed Codex PR #8002 concerned Landlock on Linux. [Codex main base](https://github.com/openai/codex/blob/9825e4b2fe69d997dbf533e228445d50095e6ba8/codex-rs/sandboxing/src/seatbelt_base_policy.sbpl#L84-L92), [Stable release](https://github.com/openai/codex/releases/tag/rust-v0.169.0), [Stable base](https://github.com/openai/codex/blob/rust-v0.169.0/codex-rs/sandboxing/src/seatbelt_base_policy.sbpl#L84-L92), [Policy builder](https://github.com/openai/codex/blob/9825e4b2fe69d997dbf533e228445d50095e6ba8/codex-rs/sandboxing/src/seatbelt.rs#L985-L1012), [Permissions profile schema](https://github.com/openai/codex/blob/9825e4b2fe69d997dbf533e228445d50095e6ba8/codex-rs/core/config.schema.json#L4173), [Codex #16931](https://github.com/openai/codex/issues/16931), [Codex #17644](https://github.com/openai/codex/issues/17644), [Codex PR #8002](https://github.com/openai/codex/pull/8002)

## Independent local reproduction

Apple M5 Pro, macOS 27.0.1 (26A434), Codex CLI 0.167.1. A small Objective-C
[probe](evidence/codex-metal-16931/metal-probe.m) compiles a compute kernel from source,
checks all 1,024 outputs, and tests a GPU-signaled shared event. Stock `codex sandbox
-P :workspace --log-denials` reports zero devices, a nil default, and an
`iokit-open-user-client` denial for `AGXDeviceUserClient`.

In a separate Seatbelt experiment, the pinned Codex base policy remained default deny.
The harness granted reads and writes in the test workspace, denied writes elsewhere,
and denied networking. Each variant ran a fresh process:

| Added rules | Enumeration | Compute | Shared event |
| --- | --- | --- | --- |
| None | 0 devices | Not reached | Not reached |
| AGX device class | Apple M5 Pro | Compiler lookup denied (error 159) | Not reached |
| AGX + exact compiler global-name lookup | Apple M5 Pro | 1,024 correct values | Unavailable |
| AGX + exact compiler XPC name lookup after the broad XPC deny | Apple M5 Pro | 1,024 correct values | Unavailable |
| AGX + exact compiler global-name lookup + IOSurface root class | Apple M5 Pro | 1,024 correct values | Signaled value 42 |

This isolates three rules for the probe without adding a sysctl grant, broad IOKit or
Mach access, cache write exceptions, or network access. The shader-cache extension
request logged a denial and the compute result still verified. This first experiment
did not execute Blender or validate the full generated Codex policy.

The [local source patch](evidence/codex-metal-16931/codex-v0.167.1-metal.patch)
adds an explicit `codex sandbox --allow-metal` on arm64 macOS. Its base is
[Codex 0.167.1](https://github.com/openai/codex/tree/0a94398fa60c4fac0e7659e4213a0a36e613dd46).
The switch adds only the three tested grants to an existing Codex-generated
Seatbelt profile. It refuses non-managed profiles, full disk write access, and
resolved write roots outside the selected workspace. It does not alter the installed
Codex or Blender, or turn the option on in default profile construction.

Use a separately named profile with `:root` read, `:workspace_roots` write and
network disabled for the probe. The built-in `:workspace`, selected explicitly,
ignores legacy `sandbox_workspace_write` settings, including the temporary-root
exclusions; a real write-open test observed that it allowed `/private/tmp` access.
The named profile without a temporary-root allowance denied the same write-open.
This matches the [configuration selection code](https://github.com/openai/codex/blob/0a94398fa60c4fac0e7659e4213a0a36e613dd46/codex-rs/core/src/config/mod.rs#L3840-L3875).

### Codex launcher verification

The locally built 0.167.1 CLI reproduced the stock zero-device result with the flag
absent. With the flag, the same named workspace profile enumerated the M5 Pro,
checked the 1,024 results and observed the shared event. Both launchers denied a real
write-open of a scratch file in `/private/tmp` and the repository's `.git/HEAD`,
denied TCP to a listening local socket, and denied writes to the installed Blender
executable. An inherited child also failed the outside write-open. The candidate
refused full access, the built-in temporary-root profile and an explicit writable
outside-temp root. This validates the entry point for an isolated invocation;
it is not a released Desktop or CLI setting.

### Cycles binary archives

Logo-maker's native and Cycles device checks passed with the new flag. A 64 px
render with ordinary binary archives crashed in
`-[MTLCompiler createBinaryArchiveAsRecompileTarget:compilerTask:completionHandler:]`
and Cycles' `MetalKernelPipeline::compile()`. The denial log named a read-extension
request for the interpreter's bin directory. That is a lead, not proof of causation.
Blender ships the [`CYCLES_METAL_DISABLE_BINARY_ARCHIVES` switch](https://github.com/blender/blender/blob/main/intern/cycles/device/metal/kernel.mm#L370-L401),
which bypasses that branch without changing MetalRT or the chosen device.
The follow-up varies only the archive setting; no filesystem or extra IPC grant is
added for the compiler.

With binary archives disabled, the same small Cycles render completed in about
150 seconds. Only the M5 Pro Metal device was enabled, and OIDN 2.5.0 initialized
a Metal device and ran the RT filters at 64 × 64. The extension denial was still
logged, so granting that extension is unnecessary for this render. The setting is
included in logo-maker's render report and environment fingerprint when explicitly
supplied. Fresh sampling controls are therefore required for this configuration.


### Reproduce the local verification

Use an isolated checkout at the pinned tag. Apply the Metal patch and the Blender launch
denial patch, then build the native `codex-cli` binary. The tag bumps the Rust workspace from 0.0.0 to 0.167.1
without updating the corresponding local-crate versions in its lockfile. This
build refreshed those version strings; no third-party dependency version changed.
The V8 archive and binding were obtained from the [Codex V8 release](https://github.com/openai/codex/releases/tag/rusty-v8-v152.2.0)
and checked against the pinned source checksum file before the build.

Copy the [verification files](evidence/codex-metal-16931/) into a scratch
directory one level below this repository's `logos/` directory. In that scratch
directory create empty `home/`, `tmp/` and `modules/` directories. Compile the probe
as arm64 on the same Mac:

```sh
clang -fobjc-arc -fmodules-cache-path=modules -O2 -Wall -Wextra -Werror   -framework Foundation -framework Metal -o metal-probe metal-probe.m
```

Run `../../.venv/bin/python verify-codex.py /absolute/path/to/patched/codex`.
Use `STOCK_CODEX` if the stock CLI is not at `/opt/homebrew/bin/codex`. The verifier
runs the negative cases before the candidate, exercises real file/network denials
and checks that unsafe profiles fail before a command starts. Repeat with
`--blender` to run the full device and 64 px Cycles/OIDN check. For the actual
trials, the [example launcher](evidence/codex-metal-16931/run-workspace-example.sh)
uses separate offline GPU and domain-allowlisted network profiles. The network
profiles use Codex's proxy with CONNECT, rather than TLS interception, and do not
enable Metal.

Local artifact identifiers:

- Patched binary SHA-256: `7179f2ea40380609cbe2034722f88e7cdbf93c9336cd1d9cee17c52ae325759c`.
- Original Metal patch SHA-256: `f8a6ada957d3cd30b96c0a1efc1edf5aeea7f9e53921adb789bd998e392383d7`.
- Committed Metal patch SHA-256: `03cc5ba3bb1e26cc177caa4f0aa4c53589facda265af5d19831f9a2324eb48be`.
- The [64 px execution report](evidence/codex-metal-16931/render-result.json)
  records the actual tracing device, executed OIDN filters, sample settings and file hashes.

### Blender launch denial for campaign trials

Fresh Codex trial shells attempted to launch Blender after a failed Metal probe.
The trial crash reports traced the exits to Blender's Metal backend initialization.
Filesystem read denial alone left a test executable runnable. The additional
[process execution patch](evidence/codex-metal-16931/codex-v0.167.1-blender-exec-denial.patch)
denies executables named `Blender` or `blender` in both Codex trial shells and
campaign workers. The campaign worker checks the rule with an inert copy of
`/usr/bin/true`. Normal executable names still work.

The rebuilt local 0.167.1 binary has SHA-256
`c53dc201b016a2fe2b0613a1f1bd13615c8b676cdab4b53d9be8d539eed4d01c`.
It was built with Rust 1.99.0 and the existing offline dependency cache and lock.
The campaign pins the digest and retains the prior runtime in its version directory.
The matching `codex-code-mode-host` from the same source has SHA-256
`8aeb65c47ad7860691eca84f95b1b577ef85d27b8a8c7b288b3f39b42207ba7a`.
The committed launch-denial patch has SHA-256
`dbf73029c2381a63d2725228bde246c672d279f3fdd8136d12516f18af218c5e`.
The committed patches omit the single-space prefixes on blank context lines.
`git apply --reverse --check` verified both against the source used for the build.

The full rendering policy also exposes a diagnostic distinction: the `sysctl`
executable reports an operation error while direct `sysctlbyname` calls return
the allowed hardware values. The qualification fingerprint built by logo-maker
on this revision therefore records its CLI-probed hardware fields as unknown.
It still binds the actual Metal GPU name/ID, platform, Blender version/build,
renderer code, dependencies, OIDN libraries and the archive override. No read
rule was added to make the executable pass; a subsequent fingerprint change
would require fresh controls.
