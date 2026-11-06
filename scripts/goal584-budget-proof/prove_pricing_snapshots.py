#!/usr/bin/env python3
"""Read native fixture SpendLogs; retain exact published rate snapshots only.

Proxy CLI preparation. No inference, config writes, pricing lookup or cost math.
The existing native_client and protected fixture/operator state own all access.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import re
from uuid import UUID

from prove_native_budgets import MODELS, ProofError, require


STATE = Path("/proof-private/webui-state.private.json")
SNAPSHOT_KEY = "owui_billed_token_rates"
MAX_ROWS = 1000
MAX_BYTES = 2 * 1024 * 1024
PROOF = "goal584-native-pricing-snapshots"
CREDENTIAL = re.compile(r"(?:sk-|gw-)[A-Za-z0-9_-]{16,}|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}")
REQUEST_ID = re.compile(r"chatcmpl-goal584-[0-9a-f]{32}")
ROW_FIELDS = {"request_id", "user_id", "model", "model_group", "model_id", "status", "spend", "usage", "metadata"}
TOKEN_FIELDS = ("prompt_tokens", "completion_tokens", "total_tokens")


def rate_fields():
    # Public representation contract from the actual callback, not a second
    # pricing resolver/catalog. Parent must mount the same frozen module.
    try:
        from pricing_snapshot import RATE_FIELDS
    except ImportError:
        raise ProofError("Frozen pricing callback representation module is unavailable") from None
    return RATE_FIELDS


def encoded(value):
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()
    except (TypeError, ValueError, OverflowError):
        raise ProofError("Pricing evidence is not finite JSON") from None
    require(len(raw) <= MAX_BYTES, "Pricing evidence exceeded byte bound")
    return raw


def no_credentials(value, secrets=()):
    text = encoded(value).decode()
    require(CREDENTIAL.search(text) is None and not any(secret and secret in text for secret in secrets),
            "Credential-bearing pricing evidence suppressed")


def private_credentials(state):
    """Suppress even non-key-shaped fixture passwords; never retain this list."""
    values = []
    def visit(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in ("key", "token", "password", "operator_token") and isinstance(child, str) and child:
                    values.append(child)
                else:
                    visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    visit(state)
    return values


def canonical_id(value):
    try:
        valid = isinstance(value, str) and str(UUID(value)) == value
    except (ValueError, TypeError, AttributeError):
        valid = False
    require(valid, "Pricing fixture identity is not a canonical UUID")
    return value


def number(value):
    try:
        valid = type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        valid = False
    require(valid, "Native pricing value is not a finite numeric primitive")
    return value


def identifier(value, optional=False):
    require(optional and value is None or isinstance(value, str) and IDENTIFIER.fullmatch(value) is not None,
            "Native pricing identity has an unexpected shape")
    return value


def fixture_scope(state):
    require(isinstance(state, dict) and state.get("schema") == 1 and state.get("stage") == "setup_complete"
            and isinstance(state.get("users"), list) and len(state["users"]) == 2,
            "Pricing proof requires the existing completed native fixture")
    try:
        personal = [account["id"] for account in state["users"]] + [state["admin"]["id"], state["bootstrap_fixture"]["employee"]["id"]]
        service = state["service_fixture"]["payer_id"]
        run_id = state["run_id"]
    except (KeyError, TypeError):
        raise ProofError("Pricing fixture omitted a required payer") from None
    require(len(set(canonical_id(value) for value in [*personal, service])) == 5,
            "Pricing proof requires four personal and one separate service payer")
    identifier(run_id)
    return {"run_id": run_id, "personal_payers": sorted(personal), "service_payer": service}


def validate_snapshot(snapshot):
    fields = rate_fields()
    require(isinstance(snapshot, dict) and set(snapshot) == {"schema", "availability", "observed_at_utc", "rates"}
            and type(snapshot["schema"]) is int and snapshot["schema"] == 1,
            "Native pricing snapshot schema differs")
    rates = snapshot["rates"]
    require(isinstance(rates, dict) and set(rates) == set(fields), "Native pricing snapshot omitted a rate field")
    for value in rates.values():
        if value is not None:
            number(value)
    present = sum(value is not None for value in rates.values())
    expected = "available" if present == len(fields) else "partial" if present else "unknown"
    require(snapshot["availability"] == expected, "Native pricing availability contradicts its actual fields")
    stamp = snapshot["observed_at_utc"]
    require(isinstance(stamp, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z", stamp) is not None,
            "Native pricing observation is not explicit UTC")
    try:
        datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        raise ProofError("Native pricing observation timestamp is invalid") from None
    no_credentials(snapshot)
    return copy.deepcopy(snapshot)


def validate_projection(row, payers):
    require(isinstance(row, dict) and set(row) == ROW_FIELDS, "Pricing row projection schema differs")
    identifier(row["request_id"])
    require(canonical_id(row["user_id"]) in payers, "Native pricing row crossed fixture payer scope")
    for key in ("model", "model_group", "model_id"):
        identifier(row[key], optional=True)
    require(row["status"] in (None, "success", "failure", "failed", "blocked", "cancelled", "canceled"),
            "Native pricing row status is unknown")
    require(number(row["spend"]) >= 0, "Native pricing spend is negative")
    usage = row["usage"]
    require(isinstance(usage, dict) and set(usage) == set(TOKEN_FIELDS)
            and all(type(usage[field]) is int and usage[field] >= 0 for field in TOKEN_FIELDS)
            and usage["prompt_tokens"] + usage["completion_tokens"] == usage["total_tokens"],
            "Native pricing row usage is malformed")
    require(isinstance(row.get("metadata"), dict) and set(row["metadata"]) == {"spend_logs_metadata"},
            "Pricing evidence contains unapproved metadata")
    spend_metadata = row["metadata"]["spend_logs_metadata"]
    require(isinstance(spend_metadata, dict) and set(spend_metadata) <= {SNAPSHOT_KEY},
            "Pricing evidence contains unapproved spend metadata")
    if SNAPSHOT_KEY in spend_metadata:
        validate_snapshot(spend_metadata[SNAPSHOT_KEY])
    no_credentials(row)
    return row


def project_row(raw, payers):
    require(isinstance(raw, dict), "Native pricing spend row is malformed")
    key_hash = raw.get("api_key")
    require(isinstance(key_hash, str) and re.fullmatch(r"[0-9a-f]{64}", key_hash) is not None,
            "Native pricing row API identity is not a hash")
    metadata = raw.get("metadata")
    if isinstance(metadata, str):
        require(len(metadata.encode("utf8")) <= MAX_BYTES, "Native pricing metadata exceeded byte bound")
        try:
            metadata = json.loads(metadata, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        except (ValueError, UnicodeError):
            raise ProofError("Native pricing metadata is not finite JSON") from None
    require(metadata is None or isinstance(metadata, dict), "Native pricing metadata is malformed")
    spend_metadata = (metadata or {}).get("spend_logs_metadata")
    require(spend_metadata is None or isinstance(spend_metadata, dict), "Native spend metadata is malformed")
    retained = {}
    if spend_metadata is not None and SNAPSHOT_KEY in spend_metadata:
        retained[SNAPSHOT_KEY] = validate_snapshot(spend_metadata[SNAPSHOT_KEY])
    projected = {"request_id": raw.get("request_id"), "user_id": raw.get("user"),
                 "model": raw.get("model"), "model_group": raw.get("model_group"), "model_id": raw.get("model_id"),
                 "status": raw.get("status"), "spend": raw.get("spend"),
                 "usage": {field: raw.get(field) for field in TOKEN_FIELDS},
                 "metadata": {"spend_logs_metadata": retained}}
    validate_projection(projected, payers)
    projected["api_key_hash"] = key_hash
    no_credentials(projected)
    return projected


def fixture_expectation(input_rate, output_rate, cost, model):
    require((input_rate, output_rate, cost) in (("0.01", "0.02", "0.20"), ("0.02", "0.04", "0.40"))
            and model in MODELS, "Expected values are not a supported synthetic flat-price fixture")
    return {"input_rate": input_rate, "output_rate": output_rate, "cost": cost, "model": model}


def validate_witness(row, expected):
    require(REQUEST_ID.fullmatch(row["request_id"]) is not None and row["status"] == "success"
            and row["model_group"] == expected["model"], "Required pricing witness has wrong fixture identity/model/status")
    suffix = expected["model"][-1]
    require(row["model"] in (expected["model"], "goal584-fake-" + suffix, "openai/goal584-fake-" + suffix),
            "Required pricing witness has wrong native model")
    require([row["usage"][field] for field in TOKEN_FIELDS] == [10, 5, 15]
            and Decimal(str(row["spend"])) == Decimal(expected["cost"]),
            "Required pricing witness has wrong native spend or usage")
    snapshot = row["metadata"]["spend_logs_metadata"].get(SNAPSHOT_KEY)
    require(snapshot is not None, "Required pricing witness is missing the callback snapshot")
    rates = snapshot["rates"]
    require(rates["input_cost_per_token"] is not None and rates["output_cost_per_token"] is not None,
            "Required pricing witness has unknown native billed rates")
    require(Decimal(str(rates["input_cost_per_token"])) == Decimal(expected["input_rate"])
            and Decimal(str(rates["output_cost_per_token"])) == Decimal(expected["output_rate"]),
            "Required pricing witness billed rates differ from the explicit fixture expectation")


def observe(state, native=None):
    scope = fixture_scope(state)
    payers = [*scope["personal_payers"], scope["service_payer"]]
    if native is None:
        from provision_webui import native_client
        native = native_client(state)
    rows, reads = [], []
    for payer in payers:
        observed = native.logs(payer)  # Existing bounded, paginated native GET owner.
        require(isinstance(observed, list) and len(observed) <= MAX_ROWS and len(rows) + len(observed) <= MAX_ROWS,
                "Native pricing row count exceeded bound")
        require(all(isinstance(row, dict) and row.get("user") == payer for row in observed),
                "Native pricing API crossed its queried payer")
        projected = [project_row(row, set(payers)) for row in observed]
        reads.append({"user_id": payer, "rows": len(projected), "positive": sum(row["spend"] > 0 for row in projected),
                      "zero": sum(row["spend"] == 0 for row in projected)})
        rows.extend(projected)
    require(len({row["request_id"] for row in rows}) == len(rows), "Duplicate native pricing request ID")
    return scope, sorted(rows, key=lambda row: row["request_id"]), reads


def validate_published_rows(rows, payers):
    require(isinstance(rows, list) and len(rows) <= MAX_ROWS, "Prior pricing row count exceeded bound")
    for row in rows:
        require(isinstance(row, dict) and set(row) == ROW_FIELDS | {"api_key_hash"}
                and isinstance(row["api_key_hash"], str) and re.fullmatch(r"[0-9a-f]{64}", row["api_key_hash"]) is not None,
                "Prior pricing projection has unexpected fields/API identity")
        validate_projection({key: value for key, value in row.items() if key != "api_key_hash"}, payers)
    require(len({row["request_id"] for row in rows}) == len(rows), "Duplicate prior pricing request ID")


def qualify(scope, rows, reads, expected, witness=None, prior=None, secrets=()):
    payers = set(scope["personal_payers"]) | {scope["service_payer"]}
    validate_published_rows(rows, payers)
    previous = {}
    if prior is not None:
        require(isinstance(prior, dict) and prior.get("schema") == 1 and prior.get("proof") == PROOF
                and prior.get("passed") is True and prior.get("fixture_scope") == scope,
                "Prior pricing receipt belongs to another or incomplete fixture")
        previous_expected = prior.get("expected_fixture", {})
        require(previous_expected != expected and set(previous_expected) == {"input_rate", "output_rate", "cost", "model"},
                "Pricing comparison requires a changed explicit fixture expectation")
        fixture_expectation(previous_expected["input_rate"], previous_expected["output_rate"], previous_expected["cost"], previous_expected["model"])
        require(previous_expected["model"] == expected["model"]
                and tuple(previous_expected[key] for key in ("input_rate", "output_rate", "cost"))
                != tuple(expected[key] for key in ("input_rate", "output_rate", "cost")),
                "Pricing comparison requires changed flat fixture prices on the same witness model")
        validate_published_rows(prior.get("rows"), payers)
        previous = {row["request_id"]: row for row in prior["rows"]}
        current = {row["request_id"]: row for row in rows}
        require(previous and set(previous) <= set(current), "Previously observed native pricing rows were lost")
        require(all(encoded(old) == encoded(current[key]) for key, old in previous.items()),
                "Previously observed native cost/usage/snapshot/identity changed")
    candidates = [row for row in rows if row["request_id"] not in previous]
    if witness is not None:
        require(REQUEST_ID.fullmatch(witness) is not None, "Witness must be an actual synthetic fixture request ID")
        witnesses = [row for row in candidates if row["request_id"] == witness]
        require(len(witnesses) == 1, "Required pricing witness is not a new observed native row")
    else:
        witnesses = []
        for row in candidates:
            snapshot = row["metadata"]["spend_logs_metadata"].get(SNAPSHOT_KEY)
            if row["model_group"] == expected["model"] and row["spend"] > 0 and snapshot is not None:
                rates = snapshot["rates"]
                if all(rates[key] is not None and Decimal(str(rates[key])) == Decimal(expected[value])
                       for key, value in (("input_cost_per_token", "input_rate"), ("output_cost_per_token", "output_rate"))):
                    witnesses.append(row)
        require(witnesses, "No new native fixture witness has known expected billed rates; callback/rates may be missing")
    for row in witnesses:
        validate_witness(row, expected)
    availability = {name: 0 for name in ("missing", "unknown", "partial", "available")}
    for row in rows:
        snapshot = row["metadata"]["spend_logs_metadata"].get(SNAPSHOT_KEY)
        availability["missing" if snapshot is None else snapshot["availability"]] += 1
    result = {"fixture_scope": scope, "expected_fixture": expected, "rows": rows, "native_reads": reads,
              "row_counts": {"total": len(rows), "positive": sum(row["spend"] > 0 for row in rows),
                             "zero": sum(row["spend"] == 0 for row in rows), "snapshot_availability": availability,
                             "nonfixture_model": sum(row["model_group"] not in MODELS for row in rows),
                             "old_immutable": len(previous), "new": len(candidates), "qualified_witnesses": len(witnesses)},
              "witness_request_ids": sorted(row["request_id"] for row in witnesses),
              "source_endpoints": ["/spend/logs/v2"],
              "scope": "All API rows returned for five fixture payers since native fixture start; witness-only flat-price qualification",
              "not_qualified": ["raw cost database privacy", "global or pre-fixture history", "other payers", "unattributed failure/cancel lifecycle",
                                "non-witness and nonfixture tariffs", "tariff source/version/effective interval", "atomic total/rate version binding",
                                "provider calls by this script", "production", "paid provider"]}
    no_credentials(result, secrets)
    return result


def read_prior(path):
    require(path.is_file() and path.stat().st_size <= MAX_BYTES, "Prior pricing receipt unavailable or too large")
    try:
        result = json.loads(path.read_text(encoding="utf8"), parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, UnicodeError):
        raise ProofError("Prior pricing receipt is not finite JSON") from None
    no_credentials(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=("record", "compare"))
    parser.add_argument("--private-state", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--prior-receipt", type=Path)
    parser.add_argument("--expected-input-rate", required=True, choices=("0.01", "0.02"))
    parser.add_argument("--expected-output-rate", required=True, choices=("0.02", "0.04"))
    parser.add_argument("--expected-cost", required=True, choices=("0.20", "0.40"))
    parser.add_argument("--witness-model", default=MODELS[0], choices=MODELS)
    parser.add_argument("--witness-request-id")
    args = parser.parse_args()
    receipt = {"schema": 1, "proof": PROOF, "mode": args.mode, "passed": False,
               "started_at_utc": datetime.now(timezone.utc).isoformat(),
               "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    valid_output = False
    try:
        from provision_webui import OPERATOR_STATE, read_private, write_private
        require(args.private_state.resolve() == STATE.resolve(), "Pricing proof requires the fixed private native fixture state")
        require((args.mode == "compare") == (args.prior_receipt is not None), "Compare alone requires a prior pricing receipt")
        paths = [args.private_state, OPERATOR_STATE, args.receipt] + ([args.prior_receipt] if args.prior_receipt else [])
        require(len({path.resolve() for path in paths}) == len(paths), "Private state/operator/prior/receipt paths must be distinct")
        valid_output = True
        expected = fixture_expectation(args.expected_input_rate, args.expected_output_rate, args.expected_cost, args.witness_model)
        state = read_private(args.private_state)
        scope, rows, reads = observe(state)
        prior = read_prior(args.prior_receipt) if args.prior_receipt else None
        receipt.update(qualify(scope, rows, reads, expected, args.witness_request_id, prior,
                               private_credentials(state)), passed=True)
    except ProofError as error:
        receipt["failure"] = str(error)
    except Exception:
        receipt["failure"] = "Native pricing observation failed before qualification"
    receipt["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    no_credentials(receipt)
    if valid_output:
        write_private(args.receipt, receipt)
    print(json.dumps(receipt, indent=2, allow_nan=False))
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
