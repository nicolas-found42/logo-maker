"""logo-maker command line. Every stage command takes a logo slug (folder under logos/) or a folder path."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path

from logo_maker import __version__
from logo_maker.brief import BriefError
from logo_maker.paths import LogoDir
from logo_maker.paths import resolve_logo as resolve_logo

STAGES = (
    "brief",
    "intake",
    "ideate",
    "plan",
    "motifs",
    "refine",
    "status",
    "preview",
    "finalize",
    "export",
    "study",
    "review-study",
    "campaign",
    "run",
    "improve",
)


def require_brief(target: str, out: Path | None = None) -> LogoDir:
    """The logo a stage runs on; only a logo `new` created qualifies, so a typo creates no folder."""
    logo = resolve_logo(target, out)
    if not logo.brief.exists():
        fix = f"logo-maker new {shlex.quote(target)}"
        if out is not None:
            fix += f" --out {shlex.quote(str(logo.root))}"
        raise BriefError(f"no brief at {logo.brief}; run `{fix}` first")
    return logo


def _print(result: object) -> None:
    if isinstance(result, dict):
        print(
            json.dumps(
                {k: str(v) if isinstance(v, Path) else v for k, v in result.items()},
                indent=2,
                default=str,
            )
        )
    elif isinstance(result, list):
        print("\n".join(str(item) for item in result))
    elif result is not None:
        print(result)


def cmd_doctor(_: argparse.Namespace) -> int:
    from logo_maker.doctor import report

    return report()


def cmd_mcp(_: argparse.Namespace) -> int:
    from logo_maker.mcp_server import serve

    serve()
    return 0


def cmd_new(args: argparse.Namespace) -> int:
    from logo_maker import pipeline

    try:
        logo = resolve_logo(args.slug, args.out)
        pipeline.new(logo, args.name or args.slug.replace("-", " ").title())
    except (ValueError, OSError) as exc:  # unusable slug or path, BriefError: logo exists
        print(f"error: {exc}", file=sys.stderr)
        return 2
    target = shlex.quote(str(logo.root))
    print(
        f"created {logo.root}\nfill {logo.brief} and use logo-maker study with "
        "--concept <id> --preview for 3D concept authoring. For production qualification, "
        f"also fill {logo.root / 'brief-evidence.toml'} "
        f"from project/owner evidence; run `logo-maker brief {target}`, "
        f"then author {logo.metaphors} and run `logo-maker run {target}`"
    )
    return 0


def cmd_stage(args: argparse.Namespace) -> int:
    from logo_maker import pipeline

    try:
        logo = require_brief(args.target, args.out)
    except (ValueError, OSError) as exc:  # unusable slug or path, BriefError: no such logo
        print(exc, file=sys.stderr)
        return 2
    try:
        if args.command == "export":
            result = pipeline.export(logo)
        elif args.command == "brief":
            result = pipeline.review_brief(logo, revision_reason=args.revision_reason)
        elif args.command == "campaign":
            from logo_maker.campaign_runtime import dispatch

            record = json.loads(args.record.read_text()) if args.record else None
            result = dispatch(
                logo, args.action, concepts=args.concept, note=args.note, record=record
            )
        elif args.command in {"study", "review-study"}:
            from logo_maker import study

            if args.command == "study":
                result = study.build(
                    logo,
                    args.concept,
                    preview=args.preview,
                    compare_seed=args.compare_seed,
                    calibrate=args.calibrate,
                    wall_seconds=args.wall_seconds,
                )
            else:
                result = study.review(
                    logo,
                    args.study_id,
                    accepted=args.accept,
                    owner_note=args.note,
                    visual=not args.owner_only,
                )
        else:
            fn = {
                "intake": pipeline.intake,
                "ideate": pipeline.ideate,
                "plan": pipeline.review_plans,
                "motifs": pipeline.motifs,
                "preview": pipeline.preview,
                "refine": pipeline.refine,
                "status": pipeline.status,
                "finalize": pipeline.finalize,
                "run": pipeline.run,
                "improve": pipeline.improve,
            }[args.command]
            result = fn(logo)
    except pipeline.AuthoringNeeded as exc:
        print(f"AUTHORING NEEDED: {exc}", file=sys.stderr)
        if exc.details:
            print(json.dumps(exc.details, indent=2), file=sys.stderr)
        print(json.dumps({"counts": pipeline.status_counts(logo)}, default=str), file=sys.stderr)
        return 3
    except (RuntimeError, ValueError, OSError) as exc:  # ToolError, BriefError, file errors
        print(f"error: {exc}", file=sys.stderr)
        return 2
    _print(result)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="logo-maker", description=__doc__)
    parser.add_argument("--version", action="version", version=f"logo-maker {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    new = sub.add_parser("new", help="create a logo folder with a brief template")
    new.add_argument("slug")
    new.add_argument("--name", help="brand or project name (default: from the slug)")
    new.add_argument("--out", type=Path, help="folder to use instead of logos/<slug>")
    new.set_defaults(func=cmd_new)

    helps = {
        "brief": "review source evidence and freeze requirements before authoring",
        "intake": "judge references; pick palette and fonts when the brief lacks them",
        "ideate": "build the concept pool and run the judging chain to a shortlist of 8",
        "plan": "review concept hypotheses and purposeful detail before rendering",
        "motifs": "build each shortlisted motif and its size sheet; write starter scenes once",
        "refine": "retain previews, inspect, judge and compare creative revisions",
        "status": "report text combinations, authored motifs, renders and refinement rounds",
        "preview": "render previews on the GPU, keep 3 finalists",
        "finalize": "retained final renders, scoped diagnosis and creative QA, pick the winner",
        "export": "write the export set for the winner",
        "study": "preview or deliver named 3D designs on Apple Silicon with or without Jev",
        "review-study": "run Jev on a delivered study or record the owner's acceptance",
        "campaign": "run a persistent Codex branding campaign on Apple Silicon",
        "run": "run every remaining stage",
        "improve": "new round of ideas; replace the logo only if a new winner beats it",
    }
    for name in STAGES:
        stage = sub.add_parser(name, help=helps[name])
        stage.add_argument("target", help="logo slug (logos/<slug>) or folder path")
        stage.add_argument("--out", type=Path, help="logo folder (overrides the slug's default)")
        if name == "brief":
            stage.add_argument(
                "--revision-reason", default="", help="reason for reopening changed requirements"
            )
        elif name == "campaign":
            from logo_maker.campaign import ACTIONS

            stage.add_argument("action", choices=ACTIONS)
            stage.add_argument("--concept", action="append", help="concept ID, repeatable")
            stage.add_argument("--note", default="", help="explicit owner decision or delegation")
            stage.add_argument("--record", type=Path, help="JSON data for the action")
        elif name == "study":
            stage.add_argument(
                "--concept", action="append", required=True, help="concept ID, repeatable"
            )
            stage.add_argument(
                "--preview", action="store_true", help="render a concept comparison sheet"
            )
            stage.add_argument(
                "--compare-seed",
                action="store_true",
                help="render an independent seed for technical comparison",
            )
            stage.add_argument(
                "--calibrate",
                action="store_true",
                help="compare seeds and a lower adaptive threshold",
            )
            stage.add_argument(
                "--wall-seconds", type=float, default=1800, help="whole study render budget"
            )
        elif name == "review-study":
            stage.add_argument("study_id", help="ID returned by study")
            stage.add_argument(
                "--accept", action="append", help="owner-accepted concept ID, repeatable"
            )
            stage.add_argument("--note", default="", help="owner feedback on the named designs")
            stage.add_argument(
                "--owner-only",
                action="store_true",
                help="record owner feedback without calling Jev",
            )
        stage.set_defaults(func=cmd_stage)

    sub.add_parser("doctor", help="check every adapter, the GPU, and API keys").set_defaults(
        func=cmd_doctor
    )
    sub.add_parser("mcp", help="serve each stage as an MCP tool over stdio").set_defaults(
        func=cmd_mcp
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
