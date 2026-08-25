from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
SCRIPT_PATH = SERVICE_ROOT / "scripts/live_gate5_openwebui_product_path_control.py"
BROWSER_GOAL_PATH = SERVICE_ROOT / "scripts/live_issue306_openwebui_browser_goal.js"
RECEIPT_BUILDER_PATH = (
    SERVICE_ROOT / "scripts/build_issue306_safe_interaction_receipt.py"
)
COMMITTED_TRACE_PATH = (
    REPO_ROOT
    / "docs/reports/2026-08-25/BROKER_REPORTS_ISSUE_308_INTERACTION_TRACE.safe.json"
)
BUNDLE_PATH = (
    SERVICE_ROOT / "openwebui_actions/broker_reports_gate1_pipe_bundled.py"
)
PUBLIC_SOURCE_CORPUS_PATH = SERVICE_ROOT / "tests/fixtures/g537_coverage_corpus.v0.json"


def _load_control_module():
    spec = importlib.util.spec_from_file_location("issue306_live_control", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _receipt_sha256(value: dict) -> str:
    base = {key: item for key, item in value.items() if key != "receipt_sha256"}
    encoded = json.dumps(
        base, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _git_blob_sha256(path: Path, *, revision: str = "HEAD") -> str:
    relative = path.resolve().relative_to(REPO_ROOT).as_posix()
    blob = subprocess.check_output(
        ["git", "show", f"{revision}:{relative}"],
        cwd=REPO_ROOT,
    )
    return hashlib.sha256(blob).hexdigest()


def test_prepare_uses_current_release_owned_valves(monkeypatch, tmp_path: Path) -> None:
    control = _load_control_module()
    release_contracts = importlib.import_module(
        "scripts.broker_reports_atomic_stage_release_contracts"
    )
    accepted_keys = {
        *release_contracts.GATE1_RELEASE_VALVES,
        "ndfl_gate3_private_audit_enabled",
        "ndfl_gate3_private_audit_id",
    }
    captured: dict[str, object] = {}
    monkeypatch.setattr(control.secrets, "token_hex", lambda _size: "a" * 32)

    monkeypatch.setattr(control, "_read_env", lambda _path: {})
    monkeypatch.setattr(control, "_admin_session", lambda _env, _url: object())
    monkeypatch.setattr(
        control,
        "_get_function",
        lambda _session, _url: {"id": control.FUNCTION_ID, "is_global": True},
    )
    legacy = {"id": control.LEGACY_FUNCTION_ID, "is_active": True}
    monkeypatch.setattr(
        control,
        "_get_legacy_function",
        lambda _session, _url: dict(legacy),
    )

    def toggle_function_active(_session, _url, function_id):
        assert function_id == control.LEGACY_FUNCTION_ID
        legacy["is_active"] = not legacy["is_active"]
        return dict(legacy)

    monkeypatch.setattr(control, "_toggle_function_active", toggle_function_active)
    monkeypatch.setattr(control, "_get_valves", lambda _session, _url: {})
    monkeypatch.setattr(
        control,
        "_get_model",
        lambda _session, _url: {
            "id": control.MODEL_ID,
            "access_grants": [],
        },
    )
    monkeypatch.setattr(
        control,
        "_deploy_bundle",
        lambda _session, _url, _function: ("previous-sha", "deployed-sha"),
    )
    monkeypatch.setattr(
        control,
        "_create_user",
        lambda _session, _url, *, suffix, role: {
            "id": f"user-{suffix}",
            "email": f"issue306-{suffix}@example.invalid",
            "password": f"password-{suffix}",
            "role": role,
        },
    )
    monkeypatch.setattr(
        control,
        "_update_model_grants",
        lambda _session, _url, grants: {
            "id": control.MODEL_ID,
            "access_grants": grants,
        },
    )
    monkeypatch.setattr(
        control,
        "_user_model_visibility",
        lambda _url, email, _password: "-a@" in email,
    )
    monkeypatch.setattr(
        control,
        "_delete_user",
        lambda _session, _url, _user_id: None,
    )

    def update_valves(_session, _url, valves):
        captured["submitted_valves"] = dict(valves)
        return {key: value for key, value in valves.items() if key in accepted_keys}

    monkeypatch.setattr(control, "_update_valves", update_valves)

    output_dir = tmp_path / "control"
    args = SimpleNamespace(
        env_file=str(tmp_path / "unused.env"),
        base_url="http://issue306.invalid",
        output_dir=str(output_dir),
        audit_id="",
    )

    assert control._prepare(args) == 0
    submitted = captured["submitted_valves"]
    assert isinstance(submitted, dict)
    for key, expected in release_contracts.GATE1_RELEASE_VALVES.items():
        assert submitted[key] == expected
    assert not (set(submitted) & set(release_contracts.GATE1_RETIRED_VALVE_KEYS))

    private_state = json.loads(
        (output_dir / "control.private.json").read_text(encoding="utf-8")
    )
    safe_state = json.loads(
        (output_dir / "control-prepared.safe.json").read_text(encoding="utf-8")
    )
    assert private_state["deployed_bundle_sha256"] == "deployed-sha"
    assert private_state["control_prepared_receipt_sha256"] == safe_state[
        "receipt_sha256"
    ]
    assert safe_state["status"] == "prepared"
    assert safe_state["control_run_id"] == "a" * 32
    assert private_state["control_run_id"] == safe_state["control_run_id"]
    assert safe_state["temporary_users"] == 2
    assert safe_state["legacy_function_inactive"] is True
    assert private_state["original_legacy_function_active"] is True
    assert legacy["is_active"] is False
    assert safe_state["receipt_sha256"] == _receipt_sha256(safe_state)
    assert safe_state["predecessor_control_prepared_receipt_sha256"] is None

    second_state = dict(private_state, control_run_id="b" * 32)
    second_safe = control._safe_result(second_state, status="prepared")
    assert second_safe["receipt_sha256"] != safe_state["receipt_sha256"]


def test_redeploy_reissues_prepared_receipt_bound_to_new_bundle(
    monkeypatch, tmp_path: Path
) -> None:
    control = _load_control_module()
    state_path = tmp_path / "control.private.json"
    previous_receipt = "a" * 64
    state = {
        "schema_version": "broker_reports_gate5_openwebui_control_private_v0",
        "control_run_id": "b" * 32,
        "base_url": "http://issue310.invalid",
        "deployed_bundle_sha256": "old-bundle",
        "control_prepared_receipt_sha256": previous_receipt,
        "users": [{"id": "user-a"}, {"id": "user-b"}],
        "user_a_model_visible": True,
        "user_b_model_hidden": True,
        "legacy_function_inactive": True,
        "applied_valves": dict(control.GATE1_RELEASE_VALVES),
    }
    control._write_private_state(state_path, state)
    monkeypatch.setattr(control, "_read_env", lambda _path: {})
    monkeypatch.setattr(control, "_admin_session", lambda _env, _url: object())
    monkeypatch.setattr(
        control,
        "_get_function",
        lambda _session, _url: {"id": control.FUNCTION_ID},
    )
    monkeypatch.setattr(
        control,
        "_deploy_bundle",
        lambda _session, _url, _function: ("old-bundle", "new-bundle"),
    )

    assert control._redeploy(
        SimpleNamespace(state=str(state_path), env_file=str(tmp_path / "unused.env"))
    ) == 0

    private_state = json.loads(state_path.read_text(encoding="utf-8"))
    safe_state = json.loads(
        (tmp_path / "control-prepared.safe.json").read_text(encoding="utf-8")
    )
    assert safe_state["status"] == "prepared"
    assert safe_state["deployed_bundle_sha256"] == "new-bundle"
    assert safe_state["predecessor_control_prepared_receipt_sha256"] == (
        previous_receipt
    )
    assert safe_state["receipt_sha256"] == _receipt_sha256(safe_state)
    assert private_state["control_prepared_receipt_sha256"] == safe_state[
        "receipt_sha256"
    ]


def test_browser_goal_driver_cannot_bypass_rendered_openwebui_boundaries() -> None:
    source = BROWSER_GOAL_PATH.read_text(encoding="utf-8")

    assert "chromium.launch" in source
    assert "input[type=file]" in source
    assert "#chat-input" in source
    assert "Скачать XML" in source
    assert "page.evaluate" not in source
    assert ".request." not in source
    assert "fetch(" not in source
    assert "/api/chat" not in source
    assert "getAttribute('href')" in source
    assert "ISSUE306_SOURCE_SMOKE_ONLY" in source
    assert "representative_source_boundary_separation_proven" in source
    assert "representative_source_exact_boundary_receipt_invalid" in source
    assert "hidden_architecture_leaked_into_chat" in source
    assert "/exact status/i" in source
    assert "/case note/i" in source
    assert "/source completeness/i" in source
    assert "ISSUE310_NON_FILING_ROUTE" in source
    assert "ISSUE310_UNSUPPORTED_MODE" in source
    assert "issue310_tax_period_question_not_first" in source
    assert "issue310_non_filing_route_created_download" in source
    assert "issue310_unsupported_profile_created_download" in source
    assert "broker_reports_issue306_browser_run_receipt_v2" in source
    assert "installed_bundle_not_current_tested_bytes" in source
    assert "unanswered_tab_closed_and_second_case_admitted" in source
    assert "same_source_reupload_created_new_logical_file" in source
    assert "same_source_reupload_preserved_logical_file: true" in source
    assert "final_summary_verified" in source
    assert "residency_methodology_provenance_invalid" in source
    assert "residency_user_attested_provenance_invalid" in source
    assert "methodology_residency_section_visible: true" in source
    assert "user_residency_evidence_visible: true" in source
    assert "user_residency_conclusion_absent: true" in source
    assert "answer = 'INITIAL'" not in source
    assert "answer = 'SELF'" not in source
    assert "answer = 'PAYMENT'" not in source
    assert "answer = 'individual_not_ip_not_private_practice'" not in source
    assert "childProcess.execFileSync" in source
    assert "gitBlobSha256" in source
    assert "['show', `${testedCommit}:${relative}`]" in source
    assert "page.close()" in source
    assert "loadPublicRepresentativeSource" in source
    assert "public_source_bytes_not_owner_pinned" in source
    assert "source_artifact: sourceArtifact.receipt" in source


def test_issue306_receipt_builder_uses_owner_xml_and_rejects_tampering(
    tmp_path: Path,
) -> None:
    spec = importlib.util.spec_from_file_location(
        "issue306_receipt_builder", RECEIPT_BUILDER_PATH
    )
    assert spec is not None and spec.loader is not None
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    receipt = {
        "schema_version": "broker_reports_issue306_browser_run_receipt_v2",
        "run_id": "run-a",
        "events": [],
    }
    receipt["receipt_sha256"] = builder._sha_json(receipt)
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")

    assert builder._read_receipt(path)["run_id"] == "run-a"
    receipt["run_id"] = "run-b"
    path.write_text(json.dumps(receipt), encoding="utf-8")
    try:
        builder._read_receipt(path)
    except builder.Issue306ReceiptError as exc:
        assert str(exc) == "issue306_receipt_hash_invalid"
    else:
        raise AssertionError("tampered receipt must fail closed")

    source = RECEIPT_BUILDER_PATH.read_text(encoding="utf-8")
    assert "Gate5FullTargetXmlProjectionRuntimeFactory" in source
    assert "issue306_visible_xml_values_mismatch" in source
    assert "issue306_clean_run_xml_bytes_differ" in source


def test_issue306_source_receipt_requires_owner_pinned_bytes() -> None:
    spec = importlib.util.spec_from_file_location(
        "issue306_receipt_builder_source", RECEIPT_BUILDER_PATH
    )
    assert spec is not None and spec.loader is not None
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    owner = builder._public_source_owner_record()
    receipt = {
        "run_kind": "representative_source",
        "source_kind": "public_representative_broker_report",
        "source_artifact": dict(owner),
        "events": [
            {
                "event": "representative_source_boundary_separation_proven",
                "exact_status": "PREPARATION_INCOMPLETE",
                "exact_terminal": (
                    "ordinary_trade_canonical_evidence_missing"
                ),
                "reason_codes": [
                    "ordinary_trade_canonical_evidence_missing"
                ],
                "source_completeness_status": "CANONICAL_EVIDENCE_MISSING",
                "detected_operation_years": [],
                "selected_tax_period": None,
                "position_evaluation_status": (
                    "NOT_EVALUATED_SOURCE_FACTS_UNAVAILABLE"
                ),
                "profile_support": (
                    "NOT_EVALUATED_SOURCE_COVERAGE_INCOMPLETE"
                ),
                "xml_created": False,
                "private_download_created": False,
                "filing_eligible": False,
            }
        ],
    }
    builder._validate_source_run(receipt)
    for mutation in (
        {"source_kind": "arbitrary_unbound_file"},
        {"source_artifact": {**receipt["source_artifact"], "content_sha256": "0" * 64}},
        {"source_artifact": {**receipt["source_artifact"], "size_bytes": 0}},
        {"source_artifact": {**receipt["source_artifact"], "size_bytes": 639418}},
        {
            "events": [
                {
                    **receipt["events"][0],
                    "exact_terminal": "ordinary_trade_generic_stop",
                }
            ]
        },
    ):
        candidate = {**receipt, **mutation}
        try:
            builder._validate_source_run(candidate)
        except builder.Issue306ReceiptError:
            pass
        else:
            raise AssertionError("unbound representative source must fail closed")

    corpus = json.loads(PUBLIC_SOURCE_CORPUS_PATH.read_text(encoding="utf-8"))
    owner_rows = [
        item
        for item in corpus["samples"]
        if item.get("sample_id") == "g537_tbank_public_pdf_purchase"
    ]
    assert len(owner_rows) == 1
    assert owner["content_sha256"] == owner_rows[0]["content_sha256"]
    assert owner["size_bytes"] == owner_rows[0]["size_bytes"] == 639417


def test_issue306_supported_source_has_owner_visible_direct_expense() -> None:
    fixture = SERVICE_ROOT / "tests/fixtures/issue306_supported_ordinary_trade.csv"
    with fixture.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 2
    disposal = next(row for row in rows if row["Вид"] == "Продажа")
    assert disposal["Комиссия Брокера"] == "1.00"
    assert disposal["Комиссия Биржи"] == "0.00"


def test_committed_issue308_trace_is_bound_to_its_live_tested_code() -> None:
    trace = json.loads(COMMITTED_TRACE_PATH.read_text(encoding="utf-8"))
    assert trace["schema_version"] == "broker_reports_issue308_safe_interaction_proof_v1"
    assert trace["receipt_sha256"] == _receipt_sha256(trace)
    assert trace["exact_base_sha"] == "cf8e9bf2d13354588f569994953e97d8b2daf218"
    assert trace["tested_commit"] == "310f5837d19d85eb590ee5892b6f12a15c6ccd89"

    tested_commit = trace["tested_commit"]
    manifest = trace["tested_code_manifest"]
    assert manifest["generated_bundle_sha256"] == hashlib.sha256(
        subprocess.check_output(
            [
                "git",
                "show",
                f"{tested_commit}:{BUNDLE_PATH.relative_to(REPO_ROOT).as_posix()}",
            ],
            cwd=REPO_ROOT,
        )
    ).hexdigest()
    proof_text_paths = {
        "browser_driver_sha256": BROWSER_GOAL_PATH,
        "control_script_sha256": SCRIPT_PATH,
        "receipt_builder_sha256": RECEIPT_BUILDER_PATH,
    }
    for key, path in proof_text_paths.items():
        assert manifest[key] == _git_blob_sha256(path, revision=tested_commit)

    source = trace["user_mode"]["representative_source_run"]
    assert source["receipt_sha256"] == _receipt_sha256(source)
    assert source["run_kind"] == "representative_source"
    assert source["browser_ui_only"] is True
    assert source["document_contents_recorded"] is False
    assert source["hidden_refs_observed"] is False
    assert source["proof_binding"]["generated_bundle_sha256"] == manifest[
        "generated_bundle_sha256"
    ]
    source_owner = json.loads(PUBLIC_SOURCE_CORPUS_PATH.read_text(encoding="utf-8"))
    source_owner = next(
        item
        for item in source_owner["samples"]
        if item.get("sample_id") == "g537_tbank_public_pdf_purchase"
    )
    assert source["source_artifact"] == {
        "sample_id": source_owner["sample_id"],
        "content_sha256": source_owner["content_sha256"],
        "size_bytes": 639417,
        "source_url": source_owner["evidence_origin"]["source_url"],
    }

    assert source["events"] == [
        {
            "detected_operation_years": [],
            "event": "representative_source_boundary_separation_proven",
            "exact_status": "PREPARATION_INCOMPLETE",
            "exact_terminal": "ordinary_trade_canonical_evidence_missing",
            "filing_eligible": False,
            "mode": "user",
            "position_evaluation_status": (
                "NOT_EVALUATED_SOURCE_FACTS_UNAVAILABLE"
            ),
            "private_download_created": False,
            "profile_support": "NOT_EVALUATED_SOURCE_COVERAGE_INCOMPLETE",
            "reason_codes": ["ordinary_trade_canonical_evidence_missing"],
            "selected_tax_period": None,
            "source_completeness_status": "CANONICAL_EVIDENCE_MISSING",
            "xml_created": False,
        }
    ]

    restored = trace["verification_mode"]["control_restored_receipt"]
    assert restored["status"] == "restored"
    assert restored["state_restored"] is True
    assert restored["receipt_sha256"] == _receipt_sha256(restored)
    assert restored["deployed_bundle_sha256"] == manifest[
        "generated_bundle_sha256"
    ]
    assert restored["predecessor_control_prepared_receipt_sha256"] == source[
        "proof_binding"
    ]["control_prepared_receipt_sha256"]
