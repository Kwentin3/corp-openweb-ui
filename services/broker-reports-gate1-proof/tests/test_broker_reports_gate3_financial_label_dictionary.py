from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from broker_reports_gate1 import (
    GATE3_DICTIONARY_CURRENT_VERSION,
    GATE3_DICTIONARY_ID,
    GATE3_DICTIONARY_SCHEMA_VERSION,
    GATE3_DICTIONARY_V1_VERSION,
    Gate3FinancialLabelDictionaryError,
    Gate3FinancialLabelDictionaryFactory,
)
from broker_reports_gate1.gate3_financial_label_dictionary import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    GATE3_DICTIONARY_APPROVAL_SCHEMA_VERSION,
    GATE3_DICTIONARY_V1_FILE_SHA256,
)


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SERVICE_ROOT.parents[1]
PACKAGE = SERVICE_ROOT / "broker_reports_gate1"
RESOURCE = PACKAGE / "gate3_financial_label_dictionary.v1.json"
MODULE = PACKAGE / "gate3_financial_label_dictionary.py"
CLI_MODULE = "broker_reports_gate1.gate3_financial_label_dictionary_cli"
GENERATED_MODEL_VIEW = (
    REPOSITORY_ROOT
    / "docs"
    / "stage2"
    / "research"
    / "BROKER_REPORTS_GATE3_FINANCIAL_LABEL_DICTIONARY.v1.model.generated.md"
)
EXPECTED_LABEL_IDS = [
    "SECURITY_PURCHASE",
    "SECURITY_DISPOSAL",
    "DIVIDEND_INCOME",
    "COUPON_INCOME",
    "INTEREST_INCOME",
    "SECURITIES_LENDING_INCOME",
    "ACCRUED_COUPON_COMPONENT",
    "TRANSACTION_CHARGE",
    "TAX_WITHHELD",
]
DEFERRED_LABEL_IDS = {
    "BROKER_SERVICE_CHARGE",
    "REPO_EVENT",
    "SECURITIES_CUSTODY_CHARGE",
    "RETURN_OF_CAPITAL",
    "STOCK_DISTRIBUTION_EVENT",
    "TAX_SETTLEMENT_OR_REFUND",
}


def _owner():
    return Gate3FinancialLabelDictionaryFactory.create()


def _approval(draft: dict) -> dict:
    template = _owner().review_template(draft)
    template.update(
        {
            "approval_id": "human-review-example-001",
            "decision": "APPROVED",
            "approved_by_role": "goal_setter",
            "approved_at": "2026-08-07",
            "basis": "reviewed exact draft and diff",
        }
    )
    return template


def test_published_v1_is_exactly_the_nine_human_approved_labels() -> None:
    owner = _owner()
    assert owner.list_published_versions() == (
        "1.0.0",
        "2.0.0",
        "2.0.1",
        "2.1.0",
    )
    dictionary = owner.load_published("1.0.0")

    assert dictionary["schema_version"] == GATE3_DICTIONARY_SCHEMA_VERSION
    assert dictionary["dictionary_id"] == GATE3_DICTIONARY_ID
    assert dictionary["semantic_version"] == GATE3_DICTIONARY_V1_VERSION
    assert dictionary["status"] == "PUBLISHED"
    assert dictionary["approval"]["decision"] == "APPROVED"
    assert dictionary["approval"]["approved_by_role"] == "goal_setters"
    label_ids = [item["label_id"] for item in dictionary["labels"]]
    assert label_ids == EXPECTED_LABEL_IDS
    assert set(label_ids).isdisjoint(DEFERRED_LABEL_IDS)

    changed = copy.deepcopy(dictionary)
    changed["labels"][0]["meaning"] = "mutated caller copy"
    assert owner.load_published("1.0.0") == dictionary


def test_current_dictionary_preserves_source_granularity_without_economic_inference() -> None:
    owner = _owner()

    assert GATE3_DICTIONARY_CURRENT_VERSION == "2.0.1"
    dictionary = owner.load_published()
    labels = {item["label_id"]: item for item in dictionary["labels"]}

    assert dictionary["semantic_version"] == "2.0.1"
    commission = next(
        item for item in dictionary["labels"] if item["label_id"] == "COMMISSION"
    )
    assert "Сбор агента при выплате дохода" in commission["examples"]
    assert {
        "COMMISSION",
        "COMMISSION_TOTAL",
        "TAX_WITHHELD_TOTAL",
    } <= set(labels)
    assert "source transaction row" in labels["TRANSACTION_CHARGE"]["meaning"]
    assert "не является налоговой" in labels["TRANSACTION_CHARGE"]["meaning"]
    assert "без связи с конкретной операцией" in labels["COMMISSION"]["meaning"]
    assert "Итого" in labels["COMMISSION_TOTAL"]["examples"]
    assert "Итого удержано" in labels["TAX_WITHHELD_TOTAL"]["examples"]
    rendered = owner.render_model_markdown()
    assert "не суммируй" in rendered.casefold()
    assert "не сверяй" in rendered.casefold()


def test_inactive_g591_candidate_is_minimal_and_broker_neutral() -> None:
    labels = {
        item["label_id"]: item
        for item in _owner().load_published("2.1.0")["labels"]
    }

    assert "TAX_ADJUSTMENT" in labels
    assert "налоговый эффект" in labels["TAX_ADJUSTMENT"]["meaning"]
    assert "направление без явного tax meaning" in (
        labels["TAX_ADJUSTMENT"]["do_not_apply_when"][0]
    )
    assert "us tax" not in json.dumps(labels, ensure_ascii=False).casefold()
    assert not {
        "TAX_REFUND",
        "TAX_REVERSAL",
        "TAX_OTHER_ADJUSTMENT",
    } & set(labels)


def test_model_markdown_is_deterministic_exact_and_not_a_second_authority() -> None:
    owner = _owner()
    first = owner.render_model_markdown("1.0.0")
    second = owner.render_model_markdown("1.0.0")

    assert first == second
    assert GENERATED_MODEL_VIEW.read_text(encoding="utf-8-sig") == first
    assert first.startswith("# Financial labels\n")
    assert first.count("\n## ") == 9
    assert "BROKER_SERVICE_CHARGE" not in first
    assert "integrity_sha256" not in first
    assert "approval_id" not in first
    assert "research" not in first.casefold()
    assert GATE3_DICTIONARY_ID not in first
    assert GATE3_DICTIONARY_V1_VERSION not in first

    module_source = MODULE.read_text(encoding="utf-8")
    dictionary_wording = []
    for label in owner.load_published()["labels"]:
        dictionary_wording.append(label["meaning"])
        for field in (
            "apply_when",
            "do_not_apply_when",
            "examples",
            "confusable_with",
        ):
            dictionary_wording.extend(label[field])
    for owned_wording in dictionary_wording:
        assert owned_wording not in module_source


def test_draft_diff_review_and_prepare_publish_require_human_approval() -> None:
    owner = _owner()
    draft = owner.create_draft(
        base_semantic_version="1.0.0",
        proposed_semantic_version="1.1.0",
        proposal_id="example-interest-wording-change",
    )
    interest = next(
        item for item in draft["labels"] if item["label_id"] == "INTEREST_INCOME"
    )
    interest["examples"].append("Cash interest credited")

    validation = owner.validate_draft(draft)
    assert validation == {
        "valid": True,
        "labels_total": 9,
        "draft_sha256": validation["draft_sha256"],
        "conflicts": [],
    }
    diff = owner.diff_draft(draft)
    assert diff.startswith("--- published-1.0.0\n+++ draft-1.1.0\n")
    assert '+      "Cash interest credited"' in diff

    review = owner.review_template(draft)
    assert review["decision"] == "PENDING"
    assert review["draft_sha256"] == validation["draft_sha256"]
    with pytest.raises(Gate3FinancialLabelDictionaryError) as pending:
        owner.prepare_published_version(draft=draft, approval=review)
    assert pending.value.code == "gate3_dictionary_human_approval_required"

    approval = _approval(draft)
    prepared = owner.prepare_published_version(
        draft=draft,
        approval=approval,
    )
    assert prepared["status"] == "PUBLISHED"
    assert prepared["semantic_version"] == "1.1.0"
    assert prepared["approval"]["approval_id"] == "human-review-example-001"
    assert "integrity_sha256" not in prepared
    assert owner.serialize_prepared_version(prepared) == (
        owner.serialize_prepared_version(prepared)
    )

    with pytest.raises(Gate3FinancialLabelDictionaryError) as inactive:
        owner.load_published("1.1.0")
    assert inactive.value.code == "gate3_dictionary_version_not_published"


@pytest.mark.parametrize(
    ("mutate", "expected_code"),
    [
        (
            lambda draft: draft["labels"].append(
                copy.deepcopy(draft["labels"][0])
            ),
            "gate3_dictionary_label_id_duplicate",
        ),
        (
            lambda draft: draft["labels"][1]["examples"].append(
                draft["labels"][0]["examples"][0]
            ),
            "gate3_dictionary_cross_label_example_conflict",
        ),
        (
            lambda draft: draft["labels"][0]["do_not_apply_when"].append(
                draft["labels"][0]["apply_when"][0]
            ),
            "gate3_dictionary_label_rule_conflict",
        ),
        (
            lambda draft: draft["labels"][0].update(unowned_field=True),
            "gate3_dictionary_label_shape_invalid",
        ),
    ],
)
def test_draft_structure_and_mechanical_conflicts_fail_closed(
    mutate,
    expected_code: str,
) -> None:
    draft = _owner().create_draft(
        base_semantic_version="1.0.0",
        proposed_semantic_version="1.1.0",
        proposal_id="invalid-draft-proof",
    )
    mutate(draft)
    with pytest.raises(Gate3FinancialLabelDictionaryError) as failure:
        _owner().validate_draft(draft)
    assert failure.value.code == expected_code


def test_published_resource_is_hash_pinned_and_closed_world_loadable(
    tmp_path: Path,
) -> None:
    package_copy = tmp_path / "broker_reports_gate1"
    shutil.copytree(PACKAGE, package_copy, ignore=shutil.ignore_patterns("__pycache__"))
    command = [
        sys.executable,
        "-B",
        "-c",
        (
            "from broker_reports_gate1.gate3_financial_label_dictionary import "
            "Gate3FinancialLabelDictionaryFactory as F; "
            "d=F.create().load_published('1.0.0'); "
            "print(d['semantic_version'], len(d['labels']))"
        ),
    ]
    environment = os.environ.copy()
    completed = subprocess.run(
        command,
        cwd=tmp_path,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "1.0.0 9"

    copied_resource = package_copy / RESOURCE.name
    raw = copied_resource.read_bytes()
    assert raw.count("Покупка".encode("utf-8")) >= 1
    copied_resource.write_bytes(
        raw.replace("Покупка".encode("utf-8"), "Покупко".encode("utf-8"), 1)
    )
    tampered = subprocess.run(
        command,
        cwd=tmp_path,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert tampered.returncode != 0
    assert "gate3_dictionary_published_file_hash_mismatch" in tampered.stderr

    import hashlib

    assert hashlib.sha256(RESOURCE.read_bytes()).hexdigest() == (
        GATE3_DICTIONARY_V1_FILE_SHA256
    )


def test_cli_exposes_reviewable_flow_without_silent_activation(
    tmp_path: Path,
) -> None:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"

    show = _run_cli(environment, "show", "--format", "markdown")
    assert show.returncode == 0
    assert show.stdout == _owner().render_model_markdown()

    draft_path = tmp_path / "draft.json"
    create = _run_cli(
        environment,
        "draft",
        "--base-version",
        "1.0.0",
        "--proposed-version",
        "1.1.0",
        "--proposal-id",
        "cli-example",
        "--output",
        str(draft_path),
    )
    assert create.returncode == 0
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    draft["labels"][0]["examples"].append("Executed securities purchase")
    draft_path.write_text(
        json.dumps(draft, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    validate = _run_cli(environment, "validate", "--draft", str(draft_path))
    assert validate.returncode == 0
    assert json.loads(validate.stdout)["valid"] is True
    diff = _run_cli(environment, "diff", "--draft", str(draft_path))
    assert diff.returncode == 0
    assert "Executed securities purchase" in diff.stdout

    approval_path = tmp_path / "approval.json"
    review = _run_cli(
        environment,
        "review-template",
        "--draft",
        str(draft_path),
        "--output",
        str(approval_path),
    )
    assert review.returncode == 0
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    assert approval["schema_version"] == (
        GATE3_DICTIONARY_APPROVAL_SCHEMA_VERSION
    )
    approval.update(
        {
            "approval_id": "cli-human-review-001",
            "decision": "APPROVED",
            "approved_by_role": "goal_setter",
            "approved_at": "2026-08-07",
            "basis": "exact CLI draft and diff reviewed",
        }
    )
    approval_path.write_text(
        json.dumps(approval, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    prepared_path = tmp_path / "prepared-v1.1.0.json"
    prepared = _run_cli(
        environment,
        "prepare-publish",
        "--draft",
        str(draft_path),
        "--approval",
        str(approval_path),
        "--output",
        str(prepared_path),
    )
    assert prepared.returncode == 0
    assert json.loads(prepared_path.read_text(encoding="utf-8"))["status"] == (
        "PUBLISHED"
    )
    repeat = _run_cli(
        environment,
        "prepare-publish",
        "--draft",
        str(draft_path),
        "--approval",
        str(approval_path),
        "--output",
        str(prepared_path),
    )
    assert repeat.returncode == 2
    assert "FileExistsError" in repeat.stderr

    with pytest.raises(Gate3FinancialLabelDictionaryError):
        _owner().load_published("1.1.0")

    assert "Gate3FinancialLabelDictionaryFactory.create" in FACTORY_REQUIRED
    assert "RAG" in FORBIDDEN
    assert "provider" in FORBIDDEN


def _run_cli(environment: dict[str, str], *arguments: str):
    return subprocess.run(
        [sys.executable, "-B", "-m", CLI_MODULE, *arguments],
        cwd=SERVICE_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
