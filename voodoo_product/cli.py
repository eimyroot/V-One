from __future__ import annotations

import argparse
from collections.abc import Sequence

from .checkpoint_capture import capture_runtime_candidate, render_capture_report
from .checkpoint_evidence import render_report, verify_checkpoint
from .checkpoint_producer import finalize_checkpoint, render_finalization_report


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

    finalize = evidence_commands.add_parser(
        "finalize",
        help="freeze and verify one local checkpoint candidate",
    )
    finalize.add_argument("candidate", help="path to a checkpoint candidate directory")
    finalize.add_argument("destination", help="new final checkpoint directory")
    finalize.add_argument(
        "--canonical",
        action="store_true",
        help="emit canonical single-line JSON",
    )

    capture_runtime = evidence_commands.add_parser(
        "capture-runtime",
        help="capture one local runtime checkpoint candidate",
    )
    capture_runtime.add_argument(
        "candidate",
        help="new absolute checkpoint candidate directory outside the repository",
    )
    capture_runtime.add_argument(
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
    if arguments.command == "evidence" and arguments.evidence_command == "finalize":
        report = finalize_checkpoint(arguments.candidate, arguments.destination)
        print(render_finalization_report(report, canonical=arguments.canonical))
        return 0 if report["finalized"] else 1
    if arguments.command == "evidence" and arguments.evidence_command == "capture-runtime":
        report = capture_runtime_candidate(arguments.candidate)
        print(render_capture_report(report, canonical=arguments.canonical))
        return 0 if report["captured"] else 1
    raise RuntimeError("unreachable command dispatch")
