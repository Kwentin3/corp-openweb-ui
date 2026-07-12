#!/usr/bin/env python3
"""Profile persisted Gate 2 packages without emitting customer source content."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[2]
SERVICE_ROOT = ROOT / "services" / "broker-reports-gate1-proof"
BUNDLE = SERVICE_ROOT / "openwebui_actions" / "broker_reports_gate2_domain_source_fact_pipe_bundled.py"

sys.path.insert(0, str(SCRIPT_DIR))

from live_case_group_gate2_domain_vertical_proof import _remote_json  # noqa: E402
from live_no_rag_source_intake_smoke import _default_ssh_target, _read_env  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=str(ROOT / ".env"))
    parser.add_argument("--ssh-target", default=None)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--document-packet-ref", default=None)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--include-package-metrics", action="store_true")
    args = parser.parse_args()

    env = _read_env(Path(args.env_file))
    ssh_target = args.ssh_target or env.get("OPENWEBUI_SSH_TARGET") or _default_ssh_target(env)
    result = _profile(
        ssh_target=ssh_target,
        case_id=args.case_id,
        document_packet_ref=args.document_packet_ref,
        timeout=args.timeout,
    )
    if not args.include_package_metrics:
        metrics = result.pop("package_metrics", [])
        result["package_metrics_total"] = len(metrics) if isinstance(metrics, list) else 0
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("status") == "passed" else 2


def _profile(
    *, ssh_target: str, case_id: str, document_packet_ref: str | None, timeout: int
) -> dict[str, object]:
    bundle_source = BUNDLE.read_text(encoding="utf-8")
    code = f'''
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

namespace = {{"__name__": "gate2_context_composition_profile_bundle"}}
exec(compile({bundle_source!r}, "<gate2_context_composition_profile_bundle>", "exec"), namespace)
from broker_reports_gate1 import (
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    Gate2LlmContextPackageFactory,
    candidate_binding_provider_json_schema,
    package_feasibility,
)

CASE_ID = {case_id!r}
DOCUMENT_PACKET_REF = {document_packet_ref!r}
RUN_TYPE = "broker_reports_domain_source_fact_extraction_run_v0"
PACKAGE_TYPE = "broker_reports_domain_extraction_package_v0"
VALIDATION_TYPE = "broker_reports_source_fact_validation_v0"
RAW_TYPE = "broker_reports_source_fact_raw_model_output_v0"

store = ArtifactStoreFactory(ArtifactStoreConfig(
    mode="sqlite",
    sqlite_path=Path("/app/backend/data/broker_reports_gate1/artifacts.sqlite3"),
    payload_root=Path("/app/backend/data/broker_reports_gate1/payloads"),
)).create()
records = store.list_by_case(CASE_ID)
by_ref = {{record.artifact_id: record for record in records}}

def payload(record):
    return store.read_payload(record) if record else {{}}

def obj(value):
    return value if isinstance(value, dict) else {{}}

def rows(value):
    return [item for item in value or [] if isinstance(item, dict)] if isinstance(value, list) else []

def strings(value):
    return [str(item) for item in value or [] if item is not None and str(item)] if isinstance(value, list) else []

def compact_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def chars(value):
    return len(compact_json(value))

def estimate_tokens(value):
    # Safe, tokenizer-independent engineering estimate; provider totals remain authoritative.
    return (chars(value) + 3) // 4

run_payloads = [payload(record) for record in records if record.artifact_type == RUN_TYPE]
package_refs = []
validation_refs = []
raw_refs = []
for run in run_payloads:
    package_refs.extend(strings(obj(run).get("domain_package_refs")))
    validation_refs.extend(strings(obj(run).get("validation_refs")))
    raw_refs.extend(strings(obj(run).get("raw_output_refs")))
package_refs = list(dict.fromkeys(package_refs))
validation_refs = list(dict.fromkeys(validation_refs))
raw_refs = list(dict.fromkeys(raw_refs))
if DOCUMENT_PACKET_REF:
    packet = obj(payload(by_ref.get(DOCUMENT_PACKET_REF)))
    artifact_refs = obj(packet.get("artifacts"))
    package_refs = strings(artifact_refs.get("domain_package_refs"))
    validation_refs = strings(artifact_refs.get("validation_refs"))
    raw_refs = strings(artifact_refs.get("raw_output_refs"))

validation_by_package = {{}}
for ref in validation_refs:
    value = obj(payload(by_ref.get(ref)))
    validation_by_package[str(value.get("package_ref") or "")] = value
raw_by_package = {{}}
for ref in raw_refs:
    value = obj(payload(by_ref.get(ref)))
    raw_by_package[str(value.get("package_artifact_ref") or value.get("package_ref") or "")] = value

component_totals = Counter()
domain_counts = Counter()
outcome_counts = Counter()
validation_errors = Counter()
validation_errors_by_domain = Counter()
validation_errors_by_source_shape = Counter()
failed_selection_shapes = Counter()
provider_status = Counter()
provider_tokens = Counter()
schema_chars_by_domain = Counter()
package_chars_by_domain = Counter()
source_ref_sends = Counter()
header_hash_sends = Counter()
source_text_hash_sends = Counter()
issue_ref_sends = Counter()
package_metrics = []
refactored_totals = Counter()

for package_ref in package_refs:
    package = obj(payload(by_ref.get(package_ref)))
    if package.get("schema_version") != PACKAGE_TYPE:
        continue
    domain = str(package.get("extractor_domain") or "unknown")
    unit = obj(package.get("source_unit"))
    projection = obj(unit.get("normalized_source_projection"))
    candidate_set = obj(package.get("source_value_candidate_set"))
    relation_set = obj(package.get("candidate_relation_set"))
    validation = obj(validation_by_package.get(package_ref))
    raw = obj(raw_by_package.get(package_ref))
    provider = obj(raw.get("provider_execution_safe"))
    errors = rows(validation.get("errors"))
    error_codes = sorted(str(item.get("code") or "unknown") for item in errors)
    if error_codes:
        raw_selection = raw.get("raw_output")
        if isinstance(raw_selection, str):
            try:
                raw_selection = json.loads(raw_selection)
            except Exception:
                raw_selection = {{}}
        selection = obj(raw_selection)
        binding_results = rows(selection.get("binding_results"))
        shape = {{
            "domain": domain,
            "error_codes": error_codes,
            "binding_results": len(binding_results),
            "no_fact_results": len(rows(selection.get("no_fact_results"))),
            "selected_bindings": sum(len(rows(item.get("selected_bindings"))) for item in binding_results),
            "fact_types": dict(sorted(Counter(str(item.get("fact_type") or "unknown") for item in binding_results).items())),
        }}
        failed_selection_shapes[compact_json(shape)] += 1
    for code_value in error_codes:
        validation_errors[code_value] += 1
        validation_errors_by_domain[f"{{code_value}}:{{domain}}"] += 1
        validation_errors_by_source_shape[
            f"{{code_value}}:{{unit.get('source_input_mode') or 'unknown'}}:{{unit.get('unit_kind') or 'unknown'}}"
        ] += 1
    validator_status = str(validation.get("validator_status") or "missing")
    raw_status = str(raw.get("model_call_status") or "missing")
    outcome = "accepted" if validator_status == "passed" else "rejected"
    if any(code == "source_fact_provenance_missing" for code in error_codes):
        outcome = "provenance_missing"
    elif any("required_role" in code for code in error_codes):
        outcome = "required_role_missing"
    elif "gate2_model_provider_error" in error_codes:
        outcome = "provider_error"
    components = {{
        "package_identity": {{key: package.get(key) for key in (
            "schema_version", "package_mode", "package_id", "extraction_run_id",
            "normalization_run_id", "case_id", "document_ref", "base_package_id",
            "domain_route_id", "extractor_domain", "extractor_id", "model_id",
            "package_policy_version", "created_at",
        )}},
        "document_context": package.get("document_context") or {{}},
        "source_projection": {{
            "model_source_projection": unit.get("model_source_projection") or {{}},
            "normalized_source_projection": projection,
        }},
        "header_context": unit.get("normalized_header_descriptors") or [],
        "source_value_index": unit.get("source_value_index") or [],
        "candidate_list": candidate_set,
        "candidate_relations": relation_set,
        "candidate_profile": package.get("candidate_binding_profile") or {{}},
        "issue_context": package.get("issue_context") or [],
        "coverage_contract": package.get("coverage_expectation") or {{}},
        "policy_metadata": {{
            "source_bucket_roles": package.get("source_bucket_roles") or [],
            "segmentation": package.get("segmentation") or {{}},
            "allowed_fact_types": package.get("allowed_fact_types") or [],
            "allowed_evidence_refs": package.get("allowed_evidence_refs") or [],
            "allowed_source_value_refs": package.get("allowed_source_value_refs") or [],
            "allowed_issue_refs": package.get("allowed_issue_refs") or [],
            "forbidden_assumptions": package.get("forbidden_assumptions") or [],
            "prompt_contract": package.get("prompt_contract") or {{}},
            "output_schema": package.get("output_schema") or {{}},
            "structured_output_policy": package.get("structured_output_policy") or {{}},
            "privacy_policy": package.get("privacy_policy") or {{}},
        }},
    }}
    schema = candidate_binding_provider_json_schema(package)
    compact_context = Gate2LlmContextPackageFactory().create().build(package)
    feasibility = package_feasibility(package)
    compact_chars = chars(compact_context)
    compact_schema_chars = chars(schema)
    refactored_totals["compact_context_chars"] += compact_chars
    refactored_totals["compact_context_estimated_tokens"] += (compact_chars + 3) // 4
    refactored_totals["strict_schema_chars"] += compact_schema_chars
    refactored_totals["strict_schema_estimated_tokens"] += (compact_schema_chars + 3) // 4
    if feasibility.get("status") == "blocked":
        refactored_totals["mechanically_impossible_packages"] += 1
    metric = {{name: {{"chars": chars(value), "estimated_tokens": estimate_tokens(value)}} for name, value in components.items()}}
    metric["json_schema"] = {{"chars": chars(schema), "estimated_tokens": estimate_tokens(schema)}}
    total_chars = chars(package) + chars(schema)
    selected_refs = strings(obj(package.get("coverage_expectation")).get("selected_source_refs"))
    for ref in selected_refs:
        source_ref_sends[ref] += 1
    header_value = unit.get("normalized_header_descriptors") or []
    if header_value:
        header_hash_sends[hashlib.sha256(compact_json(header_value).encode()).hexdigest()[:16]] += 1
    source_value = {{"model": unit.get("model_source_projection"), "normalized": projection}}
    source_text_hash_sends[hashlib.sha256(compact_json(source_value).encode()).hexdigest()[:16]] += 1
    for issue_ref in strings(package.get("allowed_issue_refs")):
        issue_ref_sends[issue_ref] += 1
    for name, value in metric.items():
        component_totals[f"{{name}}_chars"] += int(value["chars"])
        component_totals[f"{{name}}_estimated_tokens"] += int(value["estimated_tokens"])
    input_tokens = provider.get("input_tokens")
    if isinstance(input_tokens, int):
        provider_tokens["reported_input_tokens"] += input_tokens
        provider_tokens["reported_calls"] += 1
    provider_status[raw_status] += 1
    domain_counts[domain] += 1
    outcome_counts[outcome] += 1
    schema_chars_by_domain[domain] += chars(schema)
    package_chars_by_domain[domain] += chars(package)
    package_metrics.append({{
        "package_ref_hash": hashlib.sha256(package_ref.encode()).hexdigest()[:16],
        "domain": domain,
        "source_unit_kind": str(unit.get("unit_kind") or "unknown"),
        "source_input_mode": str(unit.get("source_input_mode") or "unknown"),
        "selected_refs_total": len(selected_refs),
        "candidates_total": len(rows(candidate_set.get("candidates"))),
        "relations_total": len(rows(relation_set.get("relations"))),
        "issues_total": len(rows(package.get("issue_context"))),
        "outcome": outcome,
        "validator_status": validator_status,
        "provider_status": raw_status,
        "validation_error_codes": error_codes,
        "component_metrics": metric,
        "combined_package_schema_chars": total_chars,
        "combined_estimated_tokens": (total_chars + 3) // 4,
        "provider_reported_input_tokens": input_tokens if isinstance(input_tokens, int) else None,
        "refactored_compact_context_chars": compact_chars,
        "refactored_strict_schema_chars": compact_schema_chars,
        "refactored_feasibility_status": feasibility.get("status"),
    }})

def repeated(counter):
    return {{
        "unique_total": len(counter),
        "sent_total": sum(counter.values()),
        "repeated_sends_total": sum(max(0, count - 1) for count in counter.values()),
        "items_sent_to_multiple_packages": sum(1 for count in counter.values() if count > 1),
        "max_sends_for_one_item": max(counter.values(), default=0),
    }}

print(json.dumps({{
    "status": "passed",
    "case_id": CASE_ID,
    "safe_output": True,
    "estimation_policy": "utf8_json_chars_divided_by_4_ceil; provider_reported_input_tokens_authoritative",
    "runs_total": len(run_payloads),
    "packages_total": len(package_metrics),
    "domain_counts": dict(sorted(domain_counts.items())),
    "outcome_counts": dict(sorted(outcome_counts.items())),
    "provider_status_counts": dict(sorted(provider_status.items())),
    "validation_error_counts": dict(sorted(validation_errors.items())),
    "validation_errors_by_domain": dict(sorted(validation_errors_by_domain.items())),
    "validation_errors_by_source_shape": dict(sorted(validation_errors_by_source_shape.items())),
    "failed_selection_shapes": dict(sorted(failed_selection_shapes.items())),
    "component_totals": dict(sorted(component_totals.items())),
    "provider_token_totals": dict(sorted(provider_tokens.items())),
    "refactored_projection_totals": dict(sorted(refactored_totals.items())),
    "schema_chars_by_domain": dict(sorted(schema_chars_by_domain.items())),
    "package_chars_by_domain": dict(sorted(package_chars_by_domain.items())),
    "duplication": {{
        "source_refs": repeated(source_ref_sends),
        "header_contexts": repeated(header_hash_sends),
        "source_projections": repeated(source_text_hash_sends),
        "issue_refs": repeated(issue_ref_sends),
    }},
    "package_metrics": package_metrics,
}}, ensure_ascii=False, sort_keys=True))
'''
    return _remote_json(ssh_target, code, timeout=timeout)


if __name__ == "__main__":
    raise SystemExit(main())
