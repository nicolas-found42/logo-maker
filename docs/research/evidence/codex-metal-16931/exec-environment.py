"""Keep credentials out of offline and photo jobs and never put them in argv."""

import os
import sys

profile, argv = sys.argv[1], sys.argv[2:]
keys = (
    "PATH",
    "HOME",
    "CODEX_HOME",
    "TMPDIR",
    "BLENDER_USER_RESOURCES",
    "XDG_CACHE_HOME",
    "LOGO_MAKER_CACHE",
    "CYCLES_METAL_DISABLE_BINARY_ARCHIVES",
    "PYTHONDONTWRITEBYTECODE",
)
env = {key: os.environ[key] for key in keys}
if profile == "jev":
    env["OPENROUTER_API_KEY"] = os.environ["OPENROUTER_API_KEY"]
os.execve(argv[0], argv, env)  # noqa: S606 -- launch the explicit Codex binary
