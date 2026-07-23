from __future__ import annotations

import argparse
from collections.abc import Sequence

from .checkpoint_evidence import render_report, verify_checkpoint


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="voodoo")
    commands = parser.add_subparsers(dest="command", required=True)

    evidence = commands.add_parser("evidence", help="verify governed evidence artifacts")
    evidence_commands = evidence.add_subparsers(dest="evidence_command", required=True)

    verify = evidence_commands.add_parser("verify", help="verify one local checkpoint")
    verify.add_argument("checkpoint", help="path to a checkpoint directory")
    verify.add_argument(
        "--canonical",
        action="store_true",
        help="emit canonical single-line JSON",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    if arguments.command == "evidence" and arguments.evidence_command == "verify":
        report = verify_checkpoint(arguments.checkpoint)
        print(render_report(report, canonical=arguments.canonical))
        return 0 if report["valid"] else 1
    raise RuntimeError("unreachable command dispatch")
