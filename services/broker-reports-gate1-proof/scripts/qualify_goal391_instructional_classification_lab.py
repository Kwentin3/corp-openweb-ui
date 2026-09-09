#!/usr/bin/env python3
"""Qualify one managed Prompt against frozen private Goal #391 table cases.

This is an R&D harness, not a Canonical writer or product route.  It sends one
stateless browser-owned request per frozen case and writes a receipt containing
only counts, hashes, statuses, and JSON shapes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
sys.path[:0] = [str(SERVICE_ROOT), str(SCRIPT_DIR)]

from broker_reports_gate1.ordinary_trade_semantic_mapping import OrdinaryTradeSemanticMappingFactory
from goal391_instructional_classification_contract import build_case, prompt_hash, validate_response
from goal391_instructional_classification_request import build
import qualify_goal391_current_mapping_lab as mapping_lab
from qualify_goal391_browser_mapping_lab import Bridge


MODEL_ID = "models/gemini-3.5-flash"
_FORBIDDEN_FORM_KEYS = frozenset({"chat_id", "parent_id", "id", "user_message", "files"})


def _shape(value: Any, depth: int = 0) -> dict[str, Any]:
    """Describe response structure without releasing any private values."""
    if depth > 4:
        return {"type": type(value).__name__}
    if isinstance(value, dict):
        keys = sorted(str(key) for key in value)
        return {"type": "object", "keys": keys, "fields": {key: _shape(value[key], depth + 1) for key in keys}}
    if isinstance(value, list):
        return {"type": "array", "length": len(value), "item_types": sorted({"null" if item is None else type(item).__name__ for item in value})}
    if isinstance(value, str):
        return {"type": "string", "utf8_bytes": len(value.encode("utf-8"))}
    if value is None:
        return {"type": "null"}
    return {"type": type(value).__name__}


def _expected_classification(expectation: Mapping[str, Any]) -> str:
    decisions = (expectation.get("expected_assessment") or {}).get("required_table_decisions")
    if not isinstance(decisions, list) or len(decisions) != 1 or not isinstance(decisions[0], Mapping):
        raise ValueError("instructional_lab_expectation_invalid")
    decision = decisions[0]
    if decision.get("disposition") == "NO_NAMED_CONSUMER":
        if decision.get("no_consumer_kind") != "INSTRUCTIONAL_REFERENCE":
            raise ValueError("instructional_lab_no_consumer_expectation_invalid")
        return "INSTRUCTIONAL_REFERENCE"
    if decision.get("disposition") not in {"SECURITY_TRADES", "SECURITY_TRADES_INCOMPLETE"}:
        raise ValueError("instructional_lab_trade_expectation_invalid")
    return "NOT_INSTRUCTIONAL"


def _case_token(expectation: Mapping[str, Any]) -> str:
    return hashlib.sha256(str(expectation.get("fixture_identity", {})).encode("utf-8")).hexdigest()[:16]


def _prompt_from_preflight(preflight: Mapping[str, Any], *, prompt_id: str, prompt_command: str, prompt_version: str) -> Mapping[str, Any]:
    auth, prompt, history = preflight.get("auth"), preflight.get("prompt"), preflight.get("history")
    if not isinstance(auth, Mapping) or auth.get("role") != "user" or not isinstance(prompt, Mapping) or not isinstance(history, Mapping):
        raise RuntimeError("instructional_lab_ordinary_user_preflight_rejected")
    snapshot = history.get("snapshot")
    if prompt.get("id") != prompt_id or prompt.get("command") != prompt_command or prompt.get("version_id") != prompt_version or history.get("id") != prompt_version or not isinstance(snapshot, Mapping):
        raise RuntimeError("instructional_lab_prompt_pin_rejected")
    if any(snapshot.get(key) != prompt.get(key) for key in ("command", "content", "meta", "tags")) or not isinstance(prompt.get("content"), str):
        raise RuntimeError("instructional_lab_prompt_history_drift")
    return prompt


def _response_content(body: Any) -> Any:
    if not isinstance(body, Mapping):
        return None
    choices = body.get("choices")
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], Mapping):
        return None
    message = choices[0].get("message")
    return message.get("content") if isinstance(message, Mapping) else None


def _load_cases(*, corpus_root: Path, expectation_path: Path) -> list[tuple[Mapping[str, Any], dict[str, Any]]]:
    expectations = mapping_lab._read_json(expectation_path)
    records: list[tuple[Mapping[str, Any], dict[str, Any]]] = []
    for expected in expectations.get("cases", []):
        snapshot_id = expected.get("snapshot_id")
        if not isinstance(snapshot_id, str):
            raise ValueError("instructional_lab_snapshot_id_invalid")
        canonical = mapping_lab._read_json(corpus_root / f"{snapshot_id}.canonical.json")
        records.append((expected, mapping_lab._fixture(canonical=canonical, expected=expected, requires_model_selected_evidence=True)))
    if len(records) != 5:
        raise ValueError("instructional_lab_five_case_corpus_required")
    return records


def run(args: argparse.Namespace) -> dict[str, Any]:
    bridge = Bridge(SCRIPT_DIR / "goal391_browser_session_bridge.mjs")
    receipt: dict[str, Any] = {"schema_version": "goal391_instructional_classification_lab_receipt_v1", "candidate": {"prompt_id": args.prompt_id, "prompt_command": args.prompt_command, "prompt_version": args.prompt_version}, "constraints": {"retries": 0, "best_of_n": False, "canonical_mutation": False, "artifact_store_mutation": False, "chat_persistence": "forbidden"}, "provider_calls": 0, "records": []}
    try:
        receipt["non_qualifying_transport_contract"] = True
        prompt = _prompt_from_preflight(bridge.call({"op": "preflight", "prompt_id": args.prompt_id}), prompt_id=args.prompt_id, prompt_command=args.prompt_command, prompt_version=args.prompt_version)
        receipt["candidate"]["prompt_hash"] = prompt_hash(prompt["content"])
        before = bridge.call({"op": "chat_count"})["chat_count"]
        semantic = OrdinaryTradeSemanticMappingFactory.create()
        for expected, fixture in _load_cases(corpus_root=args.corpus_root, expectation_path=args.expectations):
            package = semantic.build_mapping_package(canonical=fixture["canonical"], confirmed_understandings=fixture["confirmed_understandings"], target_table_node_ids=fixture["target_table_node_ids"])
            case = build_case(table=package["case"]["tables"][0])
            form = build(prompt_content=prompt["content"], case=case, model_id=MODEL_ID)
            if form.get("stream") is not False or _FORBIDDEN_FORM_KEYS.intersection(form):
                raise RuntimeError("instructional_lab_stateless_form_invalid")
            body = bridge.call({"op": "complete", "form_data": form})["body"]
            receipt["provider_calls"] += 1
            content = _response_content(body)
            try:
                response = json.loads(content) if isinstance(content, str) else None
                verified = validate_response(response=response, case=case)
                passed = verified["classification"] == _expected_classification(expected)
                terminal = "PASS" if passed else "WRONG_CLASSIFICATION"
            except Exception as exc:
                terminal = type(exc).__name__
            receipt["records"].append({"case_token": _case_token(expected), "terminal": terminal, "transport_shape": _shape(body), "content_shape": _shape(content)})
        after = bridge.call({"op": "chat_count"})["chat_count"]
        receipt["constraints"]["chat_count_unchanged"] = before == after
        receipt["status"] = "PASSED" if receipt["constraints"]["chat_count_unchanged"] and len(receipt["records"]) == 5 and all(record["terminal"] == "PASS" for record in receipt["records"]) else "FAILED"
    except Exception as exc:
        receipt.update({"status": "FAILED", "terminal_error": type(exc).__name__})
    finally:
        bridge.close()
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus-root", type=Path, required=True)
    parser.add_argument("--expectations", type=Path, required=True)
    parser.add_argument("--safe-receipt", type=Path, required=True)
    parser.add_argument("--prompt-id", required=True)
    parser.add_argument("--prompt-command", required=True)
    parser.add_argument("--prompt-version", required=True)
    args = parser.parse_args()
    receipt = run(args)
    args.safe_receipt.write_text(json.dumps(receipt, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "cases_total": len(receipt["records"]), "passed_total": sum(record["terminal"] == "PASS" for record in receipt["records"]), "provider_calls": receipt["provider_calls"], "chat_count_unchanged": receipt["constraints"].get("chat_count_unchanged")}, sort_keys=True))
    return 0 if receipt["status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
