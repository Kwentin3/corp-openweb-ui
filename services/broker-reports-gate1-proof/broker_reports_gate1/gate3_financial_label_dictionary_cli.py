from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from .gate3_financial_label_dictionary import (
    Gate3FinancialLabelDictionaryError,
    Gate3FinancialLabelDictionaryFactory,
)


def main(argv: list[str] | None = None) -> int:
    # Keep redirected CLI output deterministic on Windows hosts whose console
    # code page is not UTF-8.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="Inspect and prepare human-reviewed Gate 3 dictionary versions."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    show = commands.add_parser("show")
    show.add_argument("--version", default="1.0.0")
    show.add_argument("--format", choices=("json", "markdown"), default="markdown")

    draft = commands.add_parser("draft")
    draft.add_argument("--base-version", default="1.0.0")
    draft.add_argument("--proposed-version", required=True)
    draft.add_argument("--proposal-id", required=True)
    draft.add_argument("--output", type=Path, required=True)

    validate = commands.add_parser("validate")
    validate.add_argument("--draft", type=Path, required=True)

    diff = commands.add_parser("diff")
    diff.add_argument("--draft", type=Path, required=True)

    review = commands.add_parser("review-template")
    review.add_argument("--draft", type=Path, required=True)
    review.add_argument("--output", type=Path, required=True)

    prepare = commands.add_parser("prepare-publish")
    prepare.add_argument("--draft", type=Path, required=True)
    prepare.add_argument("--approval", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)

    args = parser.parse_args(argv)
    owner = Gate3FinancialLabelDictionaryFactory.create()
    try:
        if args.command == "show":
            if args.format == "markdown":
                sys.stdout.write(owner.render_model_markdown(args.version))
            else:
                sys.stdout.write(_pretty(owner.load_published(args.version)))
            return 0
        if args.command == "draft":
            value = owner.create_draft(
                base_semantic_version=args.base_version,
                proposed_semantic_version=args.proposed_version,
                proposal_id=args.proposal_id,
            )
            _write_exclusive(args.output, _pretty(value).encode("utf-8"))
            return 0
        if args.command == "validate":
            sys.stdout.write(_pretty(owner.validate_draft(_read_json(args.draft))))
            return 0
        if args.command == "diff":
            sys.stdout.write(owner.diff_draft(_read_json(args.draft)))
            return 0
        if args.command == "review-template":
            value = owner.review_template(_read_json(args.draft))
            _write_exclusive(args.output, _pretty(value).encode("utf-8"))
            return 0
        if args.command == "prepare-publish":
            value = owner.prepare_published_version(
                draft=_read_json(args.draft),
                approval=_read_json(args.approval),
            )
            _write_exclusive(
                args.output,
                owner.serialize_prepared_version(value),
            )
            return 0
    except (Gate3FinancialLabelDictionaryError, OSError, ValueError) as exc:
        code = getattr(exc, "code", type(exc).__name__)
        print(code, file=sys.stderr)
        return 2
    raise RuntimeError("gate3_dictionary_command_unreachable")


def _read_json(path: Path) -> dict[str, Any]:
    value: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("gate3_dictionary_json_object_required")
    return value


def _pretty(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        indent=2,
        allow_nan=False,
    ) + "\n"


def _write_exclusive(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(value)
        handle.flush()


if __name__ == "__main__":
    raise SystemExit(main())
