"""logo-maker command line. Every stage command takes a logo slug (folder under logos/) or a folder path."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from logo_maker import __version__
from logo_maker.paths import LogoDir, slugify

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
    "run",
    "improve",
)


def resolve_logo(target: str, out: Path | None = None) -> LogoDir:
    if out is not None:
        return LogoDir(out.resolve())
    path = Path(target)
    if path.is_dir() and (path / "brief.toml").exists():
        return LogoDir(path.resolve())
    return LogoDir.default(slugify(target))


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

    logo = resolve_logo(args.slug, args.out)
    pipeline.new(logo, args.name or args.slug.replace("-", " ").title())
    print(
        f"created {logo.root}\nnext: fill {logo.brief} and {logo.root / 'brief-evidence.toml'} "
        f"from project/owner evidence; run `logo-maker brief {args.out or logo.slug}`, "
        f"then author {logo.metaphors} and run `logo-maker run {args.out or logo.slug}`"
    )
    return 0


def cmd_stage(args: argparse.Namespace) -> int:
    from logo_maker import pipeline

    logo = resolve_logo(args.target, args.out)
    if not logo.brief.exists():
        print(
            f"no brief at {logo.brief}; run `logo-maker new {args.target}` first", file=sys.stderr
        )
        return 2
    try:
        if args.command == "export":
            result = pipeline.export(logo)
        elif args.command == "brief":
            result = pipeline.review_brief(logo, revision_reason=args.revision_reason)
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
        print(
            json.dumps(
                {
                    "counts": {
                        k: v
                        for k, v in pipeline.status(logo).items()
                        if k not in {"revisions", "comparisons"}
                    }
                },
                default=str,
            ),
            file=sys.stderr,
        )
        return 3
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
