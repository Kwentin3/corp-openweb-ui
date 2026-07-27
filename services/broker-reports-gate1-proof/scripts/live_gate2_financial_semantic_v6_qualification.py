#!/usr/bin/env python3
"""Run the zero-call preflight for the exact one-attempt Nano V6 harness."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import requests


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_qualification import (  # noqa: E402,E501
    Gate2FinancialSemanticV6QualificationFixtureFactory,
    Gate2FinancialSemanticV6QualificationPreflightFactory,
)
from live_gate2_economy_contract_qualification import (  # noqa: E402
    _live_qualification_action,
    _published_model_ids,
)
from live_no_rag_source_intake_smoke import (  # noqa: E402
    _base_url,
    _read_env,
    _signin,
)


DEFAULT_V6_MANIFEST = (
    SERVICE_ROOT / "benchmarks" / "gate2_financial_semantic_v6" / "manifest.json"
)
DEFAULT_BASE_MANIFEST = (
    SERVICE_ROOT / "benchmarks" / "gate2_financial_successor_v2" / "manifest.json"
)
SNAPSHOT_AUTHORITY_KEY = b"gate2-v6-qualification-snapshot-authority-key-v1"
CONTINUATION_KEY = b"gate2-v6-qualification-continuation-key-v1"
FACTORY_REQUIRED = (
    "Gate2FinancialSemanticV6QualificationFixtureFactory.create and "
    "Gate2FinancialSemanticV6QualificationPreflightFactory.create are the "
    "only Goal 11A live-read preflight route"
)
FORBIDDEN = (
    "This Goal 11A CLI must not expose an execute flag, call a provider, "
    "consume an attempt, write evidence, admit production, fallback, repair "
    "or retry"
)


class V6QualificationPreflightCliError(ValueError):
    pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    parser.add_argument("--base-url", default=None)
    args = parser.parse_args()

    env = _read_env(Path(args.env_file))
    base_url = args.base_url.rstrip("/") if args.base_url else _base_url(env)
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    token = _signin(session, base_url, env)
    session.headers.update({"Authorization": f"Bearer {token}"})

    receipt = Gate2FinancialSemanticV6QualificationPreflightFactory().create(
        fixture=_fixture(),
        repository_revision=_repository_revision(),
        stage_action=_live_qualification_action(session, base_url),
        published_model_ids=_published_model_ids(session, base_url),
    )
    print(
        json.dumps(
            receipt,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _fixture():
    manifest = json.loads(DEFAULT_V6_MANIFEST.read_text(encoding="utf-8"))
    base_manifest = json.loads(DEFAULT_BASE_MANIFEST.read_text(encoding="utf-8"))
    return Gate2FinancialSemanticV6QualificationFixtureFactory(
        registry=Gate2FinancialEvidenceRegistryFactory().create(),
        snapshot_authority_key=SNAPSHOT_AUTHORITY_KEY,
        continuation_key=CONTINUATION_KEY,
    ).create(
        manifest=manifest,
        base_manifest=base_manifest,
    )


def _repository_revision() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
    )
    revision = completed.stdout.strip()
    if len(revision) != 40 or any(
        character not in "0123456789abcdef" for character in revision
    ):
        raise V6QualificationPreflightCliError(
            "financial_semantic_v6_repository_revision_invalid"
        )
    return revision


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "code": str(exc)[:200],
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        raise
