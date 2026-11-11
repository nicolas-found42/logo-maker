"""Fixed CPU/provider operations; killed with the caller's remaining job budget."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main(payload: dict) -> dict:
    if payload["operation"] == "first_seq":
        from logo_maker.jev.client import JevClient
        from logo_maker.paths import LogoDir

        reader = object.__new__(JevClient)
        reader.logo = LogoDir(Path(payload["logo"]))
        return {"seq": reader._first_seq()}
    if payload["operation"] == "publish_log":
        from logo_maker.publication import _record

        path = Path(payload["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        _record(path, payload["record"])
        with (path.parent.parent / "answers.jsonl").open("a") as handle:
            handle.write(json.dumps(payload["line"], sort_keys=True) + "\n")
        if payload.get("assets") is not None:
            from logo_maker.jev.client import _finish_asset_storage
            from logo_maker.paths import LogoDir

            _finish_asset_storage(LogoDir(path.parents[3]), payload["assets"], path)
        return {"published": True}
    if payload["operation"] == "encode_images":
        from logo_maker.jev.client import _encode_images, _load_image

        return _encode_images({key: _load_image(Path(p)) for key, p in payload["paths"].items()})
    if payload["operation"] == "post":
        from logo_maker.jev.client import JevClient

        # Credentials travel only over the owned process's private stdin, never logs.
        if payload["direct"]:
            os.environ["TYPESAFE_API_KEY"] = payload["key"]
        else:
            os.environ.pop("TYPESAFE_API_KEY", None)
            os.environ["OPENROUTER_API_KEY"] = payload["key"]
        client = JevClient(model=payload["body"]["model"])
        client.url = payload["url"]
        return client._post(payload["body"], payload["has_images"])
    raise ValueError("unknown Jev worker operation")


if __name__ == "__main__":
    data = json.loads(sys.stdin.read())
    try:
        print(json.dumps(main(data)), flush=True)
    except Exception as exc:
        message = str(exc)
        if data.get("key"):
            message = message.replace(data["key"], "<REDACTED>")
        print(message, file=sys.stderr)
        raise SystemExit(1) from None
