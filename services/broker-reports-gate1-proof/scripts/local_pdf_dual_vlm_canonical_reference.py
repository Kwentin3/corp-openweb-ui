from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_ROOT.parent
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1.pdf_dual_vlm_canonical_table_contracts import (  # noqa: E402
    canonical_json_bytes,
)
from pdf_dual_vlm_canonical_reference import (  # noqa: E402
    build_decisions_template,
    build_review_template,
    finalize_delegated_reference,
    finalize_human_reference,
    validate_delegated_reference,
    validate_delegated_reference_seal,
    validate_human_reference,
    validate_reference_seal,
    validate_review_template,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--controlled-reference", type=Path, required=True)
    prepare.add_argument("--crop-pack", type=Path, required=True)
    prepare.add_argument("--output-dir", type=Path, required=True)

    finalize = subparsers.add_parser("finalize")
    finalize.add_argument("--review-template", type=Path, required=True)
    finalize.add_argument("--decisions", type=Path, required=True)
    finalize.add_argument("--output-dir", type=Path, required=True)

    delegated = subparsers.add_parser("finalize-delegated")
    delegated.add_argument("--review-template", type=Path, required=True)
    delegated.add_argument("--decisions", type=Path, required=True)
    delegated.add_argument("--output-dir", type=Path, required=True)

    args = parser.parse_args(argv)
    if args.command == "prepare":
        return _prepare(args)
    if args.command == "finalize":
        return _finalize(args)
    return _finalize_delegated(args)


def _prepare(args: argparse.Namespace) -> int:
    controlled_bytes = args.controlled_reference.read_bytes()
    crop_pack_bytes = args.crop_pack.read_bytes()
    controlled = json.loads(controlled_bytes.decode("utf-8"))
    crop_pack = json.loads(crop_pack_bytes.decode("utf-8"))
    template = build_review_template(
        controlled_reference=controlled,
        controlled_reference_sha256=hashlib.sha256(controlled_bytes).hexdigest(),
        crop_pack=crop_pack,
        crop_pack_sha256=hashlib.sha256(crop_pack_bytes).hexdigest(),
    )
    decisions = build_decisions_template(template)
    if validate_review_template(template):
        raise RuntimeError("canonical_reference_review_template_invalid")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    template_path = args.output_dir / "review.template.private.json"
    decisions_path = args.output_dir / "review.decisions.private.json"
    _write_new(template_path, canonical_json_bytes(template) + b"\n")
    _write_new(decisions_path, canonical_json_bytes(decisions) + b"\n")
    _print_safe(
        {
            "status": "review_required",
            "cases_total": len(template["entries"]),
            "template_sha256": hashlib.sha256(template_path.read_bytes()).hexdigest(),
            "decisions_template_sha256": hashlib.sha256(
                decisions_path.read_bytes()
            ).hexdigest(),
            "provider_outputs_included": False,
            "consensus_included": False,
        }
    )
    return 0


def _finalize(args: argparse.Namespace) -> int:
    template = json.loads(args.review_template.read_text(encoding="utf-8"))
    decisions = json.loads(args.decisions.read_text(encoding="utf-8"))
    reference, seal = finalize_human_reference(
        review_template=template,
        decisions=decisions,
    )
    if validate_human_reference(reference) or validate_reference_seal(
        reference=reference,
        seal=seal,
    ):
        raise RuntimeError("canonical_human_reference_validation_failed")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    reference_path = args.output_dir / "reference.human-reviewed.private.json"
    seal_path = args.output_dir / "reference.human-reviewed.private.sha256.json"
    _write_new(reference_path, canonical_json_bytes(reference))
    _write_new(seal_path, canonical_json_bytes(seal) + b"\n")
    _print_safe(
        {
            "status": "compatible_and_sealed",
            "cases_total": len(reference["cases"]),
            "reference_sha256": seal["reference_sha256"],
            "seal_sha256": seal["seal_sha256"],
            "human_reviewed": True,
            "provider_outputs_used": False,
            "provider_consensus_used": False,
        }
    )
    return 0


def _finalize_delegated(args: argparse.Namespace) -> int:
    template = json.loads(args.review_template.read_text(encoding="utf-8"))
    decisions = json.loads(args.decisions.read_text(encoding="utf-8"))
    reference, seal = finalize_delegated_reference(
        review_template=template,
        decisions=decisions,
    )
    if validate_delegated_reference(reference) or validate_delegated_reference_seal(
        reference=reference,
        seal=seal,
    ):
        raise RuntimeError("canonical_delegated_reference_validation_failed")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    reference_path = args.output_dir / "reference.delegated-agent.private.json"
    seal_path = args.output_dir / "reference.delegated-agent.private.sha256.json"
    _write_new(reference_path, canonical_json_bytes(reference))
    _write_new(seal_path, canonical_json_bytes(seal) + b"\n")
    _print_safe(
        {
            "status": "compatible_and_sealed_under_explicit_user_delegation",
            "cases_total": len(reference["cases"]),
            "reference_sha256": seal["reference_sha256"],
            "seal_sha256": seal["seal_sha256"],
            "human_reviewed": False,
            "delegated_agent_reviewed": True,
            "delegation_statement_sha256": seal[
                "delegation_statement_sha256"
            ],
            "provider_outputs_used": False,
            "provider_consensus_used": False,
        }
    )
    return 0


def _write_new(path: Path, value: bytes) -> None:
    if path.exists():
        raise RuntimeError("canonical_reference_output_exists")
    path.write_bytes(value)


def _print_safe(value: dict) -> None:
    print((canonical_json_bytes(value) + b"\n").decode("utf-8"), end="")


if __name__ == "__main__":
    raise SystemExit(main())
