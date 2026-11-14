"""Check enforcement with real operations, plus a read-only installed app check."""

import ctypes as c
import errno
import os
import pathlib
import socket
import subprocess
import sys
import tempfile

if os.environ.get("CODEX_SANDBOX") != "seatbelt":
    raise SystemExit("wrong Codex sandbox")
root = pathlib.Path(sys.argv[1]).resolve()
app = "/Applications/Blender.app/Contents/MacOS/Blender"
metadata = pathlib.Path(sys.argv[2]).resolve() / "HEAD"
outside = sys.argv[3]
with tempfile.NamedTemporaryFile(dir=root) as f:
    f.write(b"workspace sandbox check")
    f.flush()

for name in (str(metadata), outside):
    # Open without O_TRUNC and do not write anything if the policy regresses.
    try:
        fd = os.open(name, os.O_WRONLY)
    except PermissionError:
        print(f"file write denied: {pathlib.Path(name).name}")
    else:
        os.close(fd)
        raise SystemExit(f"file policy unexpectedly allowed writing {name}")

try:
    with socket.create_connection(("127.0.0.1", int(sys.argv[4])), timeout=2):
        raise AssertionError("localhost TCP unexpectedly allowed")
except PermissionError as error:
    if error.errno not in {errno.EACCES, errno.EPERM}:
        raise
    print("network denied: localhost TCP")

api = c.CDLL(None)
check = api.sandbox_check
check.argtypes = (c.c_int, c.c_char_p, c.c_int)
check.restype = c.c_int
if check(os.getpid(), b"file-write-data", 1, c.c_char_p(os.fsencode(app))) <= 0:
    raise SystemExit("policy did not deny writes to the Blender executable")
print("file write denied: installed Blender")
subprocess.run(
    [
        sys.executable,
        "-c",
        """
import os, sys
try:
    os.close(os.open(sys.argv[1], os.O_WRONLY))
except PermissionError:
    print('child inherited write denial')
else:
    raise SystemExit('child unexpectedly allowed writing outside the workspace')
""",
        outside,
    ],
    check=True,
)
