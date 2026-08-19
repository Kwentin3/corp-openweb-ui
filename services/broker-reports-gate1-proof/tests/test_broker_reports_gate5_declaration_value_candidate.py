from __future__ import annotations

import copy
import hashlib
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from broker_reports_gate1 import gate5_declaration_semantic_input as module
from broker_reports_gate1.gate5_declaration_semantic_input import (
    Gate5DeclarationSemanticInputError,
    Gate5DeclarationSemanticInputRuntime,
    Gate5DeclarationSemanticInputRuntimeFactory,
)
import test_broker_reports_gate5_end_to_end_full_target_xml as e2e_fixtures


_CANDIDATE_SCHEMA_VERSION = "broker_reports_gate5_declaration_value_candidate_v0"
_CANDIDATE_STATUS = "DECLARATION_VALUE_CANDIDATE_READY_NOT_RELEASED"
_VALUE_CONTRACT = {
    "id": "ru_3ndfl_2025_supplied_case_declaration_values",
    "version": "2026-08-14.0-g545-bounded",
}


def test_ad_view_001_strict_candidate_has_exact_business_values_and_hash() -> None:
    owner = _ValidationOnlyPackageOwner(_sealed_package(audit_seed="first"))
    runtime = Gate5DeclarationSemanticInputRuntime(package_runtime=owner)

    candidate = runtime.compile_declaration_value_candidate(package={"untrusted": True})

    expected_values = _business_values()
    assert candidate == {
        "schema_version": _CANDIDATE_SCHEMA_VERSION,
        "status": _CANDIDATE_STATUS,
        "value_contract": _VALUE_CONTRACT,
        "declaration_values": expected_values,
        "semantic_value_sha256": _sha256(
            {
                "value_contract": _VALUE_CONTRACT,
                "declaration_values": expected_values,
            }
        ),
    }
    assert set(candidate["declaration_values"]) == {
        "tax_period",
        "filing",
        "taxpayer",
        "signer",
        "budget_dispositions",
        "income_group_results",
        "russian_source_income",
        "financial_investment_results",
    }
    assert candidate["declaration_values"]["signer"] == {"capacity": "taxpayer_self"}
    declaration_value_bytes = json.dumps(
        candidate["declaration_values"],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    assert len(declaration_value_bytes) == 2482
    assert hashlib.sha256(declaration_value_bytes).hexdigest() == (
        "6f87e4dd46f1cf514d877bdaaa956f911deada6cda998cd3cf1ce809165b6b81"
    )
    assert candidate["semantic_value_sha256"] == (
        "0970fb26b799eb0c3ae9056122488b23ea6cc4465bb10c68b680e9e6b0271d79"
    )
    assert owner.validation_calls == 1
    assert (
        runtime.validate_declaration_value_candidate(candidate=candidate) == candidate
    )


@pytest.mark.parametrize(
    ("path", "audit_value"),
    [
        (("declaration_values", "package_sha256"), "a" * 64),
        (
            ("declaration_values", "taxpayer", "source_component_sha256"),
            "b" * 64,
        ),
        (
            ("declaration_values", "income_group_results", 0, "obligation_refs"),
            ["obl_income_group_tax_base_results"],
        ),
        (("declaration_values", "filing", "knd"), "1151020"),
    ],
)
def test_ad_view_002_validator_rejects_audit_leakage(
    path: tuple[str | int, ...],
    audit_value,
) -> None:
    runtime, candidate = _candidate()
    changed = copy.deepcopy(candidate)
    _set_path(changed, path, audit_value)
    _rehash_candidate(changed)

    with pytest.raises(Gate5DeclarationSemanticInputError) as exc_info:
        runtime.validate_declaration_value_candidate(candidate=changed)

    assert exc_info.value.code == "gate5_declaration_value_candidate_audit_leakage"


def test_ad_view_003_every_required_path_fails_closed_when_missing(
    path: tuple[str | int, ...],
) -> None:
    runtime, candidate = _candidate()
    changed = copy.deepcopy(candidate)
    _delete_path(changed, path)
    if (
        path != ("semantic_value_sha256",)
        and "semantic_value_sha256" in changed
        and "value_contract" in changed
        and "declaration_values" in changed
    ):
        _rehash_candidate(changed)

    with pytest.raises(Gate5DeclarationSemanticInputError) as exc_info:
        runtime.validate_declaration_value_candidate(candidate=changed)

    assert exc_info.value.code == (
        "gate5_declaration_value_candidate_required_value_missing"
    )


@pytest.mark.parametrize(
    ("row_count", "repeated"),
    [(1, False), (3, False), (3, True)],
    ids=("one-row", "multiple-ordered-rows", "repeated-looking-rows"),
)
def test_ad_view_004_collections_preserve_order_multiplicity_and_exact_values(
    row_count: int,
    repeated: bool,
) -> None:
    values = _business_values(row_count=row_count, repeated=repeated)
    runtime = Gate5DeclarationSemanticInputRuntime(
        package_runtime=_ValidationOnlyPackageOwner(
            _sealed_package(
                audit_seed=f"rows-{row_count}-{repeated}",
                values=values,
            )
        )
    )

    candidate = runtime.compile_declaration_value_candidate(package={})

    for collection in (
        "budget_dispositions",
        "income_group_results",
        "russian_source_income",
        "financial_investment_results",
    ):
        assert candidate["declaration_values"][collection] == values[collection]
        assert len(candidate["declaration_values"][collection]) == row_count
        if repeated and row_count > 1:
            assert (
                candidate["declaration_values"][collection][0]
                == candidate["declaration_values"][collection][1]
            )


def test_ad_id_001_business_hash_is_stable_across_fresh_audit_runs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    packages = []
    original_compile = Gate5DeclarationSemanticInputRuntime.compile

    def capture_package(self, *, package: dict) -> dict:
        packages.append(copy.deepcopy(package))
        return original_compile(self, package=package)

    monkeypatch.setattr(
        Gate5DeclarationSemanticInputRuntime,
        "compile",
        capture_package,
    )
    first_run, _ = e2e_fixtures._run(
        tmp_path / "fresh-store-a",
        e2e_fixtures._proof_input(),
    )
    second_run, _ = e2e_fixtures._run(
        tmp_path / "fresh-store-b",
        e2e_fixtures._proof_input(),
    )
    monkeypatch.setattr(
        Gate5DeclarationSemanticInputRuntime,
        "compile",
        original_compile,
    )
    assert len(packages) == 2
    assert packages[0]["package_sha256"] != packages[1]["package_sha256"]

    runtime = Gate5DeclarationSemanticInputRuntimeFactory.create()
    first = runtime.compile_declaration_value_candidate(package=packages[0])
    second = runtime.compile_declaration_value_candidate(package=packages[1])

    assert (
        first_run["semantic_input"]["semantic_input_sha256"]
        != second_run["semantic_input"]["semantic_input_sha256"]
    )
    assert first["declaration_values"] == second["declaration_values"]
    assert first["semantic_value_sha256"] == second["semantic_value_sha256"]
    assert first["semantic_value_sha256"] == (
        "0970fb26b799eb0c3ae9056122488b23ea6cc4465bb10c68b680e9e6b0271d79"
    )


def test_ad_factory_001_factory_and_compile_route_work_outside_cwd(
    tmp_path: Path,
) -> None:
    method_source = inspect.getsource(
        module.Gate5DeclarationSemanticInputRuntime.compile_declaration_value_candidate
    )
    assert method_source.count("self.compile(package=package)") == 1
    assert "self._package_runtime" not in method_source
    for forbidden in (
        "Gate4FinancialCaseRuntimeFactory",
        "SqliteArtifactStoreAdapter",
        "ArtifactResolver",
        "CanonicalReaderFactory",
        "TaxModel",
        "openai",
        "SELECT ",
        "open(",
    ):
        assert forbidden not in method_source

    service_root = Path(module.__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        filter(
            None,
            (str(service_root), environment.get("PYTHONPATH", "")),
        )
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from broker_reports_gate1.gate5_declaration_semantic_input "
                "import Gate5DeclarationSemanticInputRuntimeFactory; "
                "runtime = Gate5DeclarationSemanticInputRuntimeFactory.create(); "
                "assert runtime.__class__.__name__ == "
                "'Gate5DeclarationSemanticInputRuntime'"
            ),
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


class _ValidationOnlyPackageOwner:
    def __init__(self, package: dict) -> None:
        self._package = copy.deepcopy(package)
        self.validation_calls = 0

    def validate_package(self, *, package: dict) -> dict:
        self.validation_calls += 1
        return copy.deepcopy(self._package)


def _candidate() -> tuple[Gate5DeclarationSemanticInputRuntime, dict]:
    runtime = Gate5DeclarationSemanticInputRuntime(
        package_runtime=_ValidationOnlyPackageOwner(
            _sealed_package(audit_seed="candidate")
        )
    )
    return runtime, runtime.compile_declaration_value_candidate(package={})


def _expected_candidate() -> dict:
    values = _business_values()
    return {
        "schema_version": _CANDIDATE_SCHEMA_VERSION,
        "status": _CANDIDATE_STATUS,
        "value_contract": copy.deepcopy(_VALUE_CONTRACT),
        "declaration_values": values,
        "semantic_value_sha256": _sha256(
            {
                "value_contract": _VALUE_CONTRACT,
                "declaration_values": values,
            }
        ),
    }


def _business_values(*, row_count: int = 1, repeated: bool = False) -> dict:
    budget = {
        "kbk": "18210102030011000110",
        "oktmo": "45382000",
        "payable": _money("4.00"),
        "refundable": _money("0.00"),
    }
    income = {
        "income_group": "resident_securities_and_derivatives_non_iis",
        "total_income": _money("100.00"),
        "non_taxable_income": _money("0.00"),
        "taxable_income": _money("100.00"),
        "tax_deductions": _money("0.00"),
        "accepted_expenses": _money("72.00"),
        "tax_base": _money("28.00"),
        "calculated_tax": _money("4.00"),
        "settlement_amounts": {
            "withheld_at_source": _money("0.00"),
            "material_benefit_withheld": _money("0.00"),
            "trade_fee_credit": _money("0.00"),
            "fixed_advance_credit": _money("0.00"),
            "foreign_tax_credit": _money("0.00"),
            "patent_credit": _money("0.00"),
            "simplified_procedure_returned_or_credited": _money("0.00"),
        },
        "tax_payable": _money("4.00"),
        "tax_refundable": _money("0.00"),
    }
    source = {
        "income_kind": "securities_disposal",
        "source_party": {
            "display_name": "АО Тестовый брокер",
            "inn": "9900000000",
            "kpp": "990001001",
            "oktmo": "45382000",
        },
        "gross_income": _money("100.00"),
        "withheld_tax": _money("0.00"),
    }
    financial = {
        "operation_category": "organized_market_securities_outside_iis",
        "category_gross_income": _money("100.00"),
        "related_expenses": _money("72.00"),
        "allowable_expenses": _money("72.00"),
        "loss_treatment": "none",
    }

    collections = {
        "budget_dispositions": _rows(budget, row_count, repeated, "kbk"),
        "income_group_results": _rows(income, row_count, repeated, "income_group"),
        "russian_source_income": _rows(
            source,
            row_count,
            repeated,
            ("source_party", "display_name"),
        ),
        "financial_investment_results": _rows(
            financial,
            row_count,
            repeated,
            "operation_category",
        ),
    }
    return {
        "tax_period": "2025",
        "filing": {
            "correction_number": 0,
            "declaration_date": "2026-08-11",
            "tax_authority_code": "7705",
        },
        "taxpayer": {
            "inn": "990000000041",
            "name": {
                "last_name": "Тестов",
                "first_name": "Тест",
                "middle_name": "Тестович",
            },
            "period_status": "resident_individual",
            "declarant_category": "other_individual_declaring_article_228_income",
        },
        "signer": {
            "capacity": "taxpayer_self",
        },
        **collections,
    }


def _rows(template: dict, count: int, repeated: bool, varying_path) -> list[dict]:
    rows = []
    for index in range(count):
        row = copy.deepcopy(template)
        if index and not repeated:
            if isinstance(varying_path, tuple):
                row[varying_path[0]][varying_path[1]] += f" {index + 1}"
            else:
                row[varying_path] += f"-{index + 1}"
        rows.append(row)
    return rows


def _sealed_package(*, audit_seed: str, values: dict | None = None) -> dict:
    values = copy.deepcopy(values or _business_values())
    filing = values["filing"]
    taxpayer = values["taxpayer"]
    signer = values["signer"]
    domains = [
        "filing_and_party_identity",
        "declaration_budget_disposition",
        "income_group_tax_results",
        "taxable_income_by_source",
        "financial_investment_results",
    ]
    snapshots = {
        "filing_and_party_identity": {
            "input_snapshot": {
                "filing_instance": {
                    "declaration_instance_ref": f"declaration-{audit_seed}",
                    "correction_kind": "initial",
                    **copy.deepcopy(filing),
                    "tax_period": values["tax_period"],
                    "destination_tax_authority_ref": f"authority-{audit_seed}",
                },
                "taxpayer": {
                    "taxpayer_ref": f"taxpayer-{audit_seed}",
                    "period_status": taxpayer["period_status"],
                    "declarant_category": taxpayer["declarant_category"],
                    **copy.deepcopy(taxpayer["name"]),
                    "inn": taxpayer["inn"],
                },
                "signer": {
                    "signer_ref": "g535-synthetic-user",
                    "signer_capacity": signer["capacity"],
                    "representation_authority": None,
                },
            }
        },
        "declaration_budget_disposition": {
            "disposition": {
                "kind": "additional_payment",
                "calculated_tax": _money("4.00"),
                "credited_or_withheld_amount": _money("0.00"),
                "reduction_amount": _money("0.00"),
                "payment_or_additional_payment_amount": _money("4.00"),
                "refund_available_amount": _money("0.00"),
                "simplified_procedure_returned_or_credited_amount": _money("0.00"),
                "budget_allocations": [
                    {
                        "allocation_kind": "tax_payment",
                        "destination_tax_authority_ref": f"authority-{audit_seed}",
                        "budget_allocation_ref": f"allocation-{audit_seed}-{index}",
                        "kbk": row["kbk"],
                        "oktmo": row["oktmo"],
                        "amount": copy.deepcopy(row["payable"]),
                    }
                    for index, row in enumerate(values["budget_dispositions"])
                ],
            }
        },
        "income_group_tax_results": {
            "group_results": [
                _income_snapshot(row) for row in values["income_group_results"]
            ]
        },
        "taxable_income_by_source": {
            "source_entries": [
                {
                    "source_ref": f"source-{audit_seed}-{index}",
                    "income_group_semantic": (
                        "resident_securities_and_derivatives_non_iis"
                    ),
                    "jurisdiction_kind": "russian_source",
                    "jurisdiction_code": "RU",
                    "income_kind": row["income_kind"],
                    "source_party": {
                        "party_kind": "organization",
                        **copy.deepcopy(row["source_party"]),
                    },
                    "gross_income": copy.deepcopy(row["gross_income"]),
                    "taxable_income": copy.deepcopy(row["gross_income"]),
                    "tax_agent": {
                        "status": "absent",
                        "withheld_tax": copy.deepcopy(row["withheld_tax"]),
                    },
                    "foreign_tax": None,
                }
                for index, row in enumerate(values["russian_source_income"])
            ],
            "obligation_resolutions": [],
        },
        "financial_investment_results": {
            "category_tax_models": [
                {
                    "model_kind": "tax_period_category",
                    "status": "complete",
                    "operation_category": {"value": row["operation_category"]},
                    "category_gross_income": {
                        "value": copy.deepcopy(row["category_gross_income"])
                    },
                    "related_expenses": {
                        "value": copy.deepcopy(row["related_expenses"])
                    },
                    "allowable_expenses": {
                        "value": copy.deepcopy(row["allowable_expenses"])
                    },
                    "loss_treatment": {"value": row["loss_treatment"]},
                }
                for row in values["financial_investment_results"]
            ],
            "obligation_resolutions": [],
        },
    }
    return {
        "status": "DECLARATION_COMPLETE_FOR_SUPPLIED_CASE",
        "package_sha256": _sha256({"package": audit_seed}),
        "definition_binding": {
            "definition_sha256": _sha256({"definition": audit_seed})
        },
        "definition_snapshot": {
            "definition_id": "ru_3ndfl_2025_root_declaration",
            "definition_version": "2026-08-10.1",
            "declaration_identity": {
                "jurisdiction": "RU",
                "form": "3-NDFL",
                "tax_period": values["tax_period"],
            },
            "domains": [
                {
                    "domain_id": domain_id,
                    "semantic_meaning": f"semantic meaning {domain_id}",
                    "obligation_refs": [f"obligation-{index}"],
                }
                for index, domain_id in enumerate(domains)
            ],
        },
        "scope_receipt_snapshot": {
            "receipt_sha256": _sha256({"receipt": audit_seed}),
            "scope_binding": {
                "scope_ref": f"scope-{audit_seed}",
                "taxpayer_scope_ref": f"taxpayer-scope-{audit_seed}",
                "tax_period": values["tax_period"],
                "case_id": f"case-{audit_seed}",
                "scope_binding_sha256": _sha256({"scope": audit_seed}),
            },
        },
        "requirement_resolutions": [
            {"domain_id": domain_id, "state": "RESOLVED"} for domain_id in domains
        ],
        "component_snapshots": [
            {
                "root_coverage": "exact_root_domain",
                "domain_id": domain_id,
                "component_contract_id": f"contract-{domain_id}",
                "content_sha256": _sha256(
                    {"component": domain_id, "audit": audit_seed}
                ),
                "snapshot": copy.deepcopy(snapshots[domain_id]),
            }
            for domain_id in domains
        ],
        "completeness_receipt": {
            "status": "DECLARATION_COMPLETE_FOR_SUPPLIED_CASE",
            "blockers": [],
            "first_blocker": None,
            "component_set_sha256": _sha256({"components": audit_seed}),
            "resolution_manifest_sha256": _sha256({"resolutions": audit_seed}),
            "completeness_kind": "supplied_case_evidence_set",
            "real_world_taxpayer_completeness_asserted": False,
        },
    }


def _income_snapshot(row: dict) -> dict:
    return {
        "income_group_semantic": row["income_group"],
        "income_group_code": "13",
        "tax_base_model": {
            "total_income": {"value": copy.deepcopy(row["total_income"])},
            "input_snapshot": {
                "group_values": {
                    "non_taxable_income": {
                        "value": copy.deepcopy(row["non_taxable_income"])
                    },
                    "tax_deductions": {"value": copy.deepcopy(row["tax_deductions"])},
                }
            },
            "taxable_income": {"value": copy.deepcopy(row["taxable_income"])},
            "accepted_expenses": {"value": copy.deepcopy(row["accepted_expenses"])},
            "tax_base": {"value": copy.deepcopy(row["tax_base"])},
        },
        "derivation": {"rate_band": {"marginal_rate": "0.13"}},
        "calculated_tax": copy.deepcopy(row["calculated_tax"]),
        "settlement_facts": {
            key: {"value": copy.deepcopy(value)}
            for key, value in row["settlement_amounts"].items()
        },
        "tax_payable": copy.deepcopy(row["tax_payable"]),
        "tax_refundable": copy.deepcopy(row["tax_refundable"]),
    }


def _required_paths(
    value, prefix: tuple[str | int, ...] = ()
) -> list[tuple[str | int, ...]]:
    paths: list[tuple[str | int, ...]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            path = (*prefix, key)
            paths.append(path)
            paths.extend(_required_paths(item, path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            path = (*prefix, index)
            paths.append(path)
            paths.extend(_required_paths(item, path))
    return paths


def _set_path(value: dict, path: tuple[str | int, ...], item) -> None:
    parent = value
    for part in path[:-1]:
        parent = parent[part]
    parent[path[-1]] = item


def _delete_path(value: dict, path: tuple[str | int, ...]) -> None:
    parent = value
    for part in path[:-1]:
        parent = parent[part]
    del parent[path[-1]]


def _path_text(path: tuple[str | int, ...]) -> str:
    result = ""
    for part in path:
        result += (
            f"[{part}]" if isinstance(part, int) else ("." if result else "") + part
        )
    return result


def _rehash_candidate(value: dict) -> None:
    value["semantic_value_sha256"] = _sha256(
        {
            "value_contract": value["value_contract"],
            "declaration_values": value["declaration_values"],
        }
    )


def _money(amount: str) -> dict[str, str]:
    return {"kind": "money", "amount": amount, "currency": "RUB"}


def _sha256(value) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def pytest_generate_tests(metafunc) -> None:
    if metafunc.function.__name__ == (
        "test_ad_view_003_every_required_path_fails_closed_when_missing"
    ):
        paths = _required_paths(_expected_candidate())
        metafunc.parametrize("path", paths, ids=[_path_text(path) for path in paths])
