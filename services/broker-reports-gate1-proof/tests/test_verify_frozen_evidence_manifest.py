from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.verify_frozen_evidence_manifest import verify


def test_current_frozen_evidence_bytes_are_exact() -> None:
    verify()


def test_changed_frozen_evidence_is_rejected(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "broker_reports_frozen_evidence_manifest_v1",
                "files": [
                    {
                        "path": "docs/stage2/contracts/BROKER_REPORTS_GATE2_TYPE_FIRST_FAIL_CLOSED.v1.md",
                        "sha256": "0" * 64,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError) as rejected:
        verify(manifest)

    assert rejected.value.args == (
        "frozen_evidence_drift:docs/stage2/contracts/"
        "BROKER_REPORTS_GATE2_TYPE_FIRST_FAIL_CLOSED.v1.md",
    )
