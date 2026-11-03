#!/usr/bin/env python3
"""Prepared, disposable two-worker calendar floor observation; no services started.

Execute once inside the parent's attested worker2. Native stock HTTP, Prisma,
Redis and ResetBudgetJob remain the owners. Raw observations stay private.
"""
from __future__ import annotations

import argparse
import asyncio
import copy
from datetime import timedelta, timezone
from decimal import Decimal
import hashlib
from importlib.metadata import version
from ipaddress import IPv4Address
import json
import math
import os
from pathlib import Path
import re
import time
from unittest.mock import patch
from urllib.parse import urlsplit
from urllib.request import Request
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import prove_calendar_reset as calendar
from prove_budget_overlap import BODY as LONG_BODY
from prove_gateway_auth import read_private, write_private
from prove_native_budgets import NativeProof, ProofError, amount, close_amount, expected_budget_message

PROOF = "goal584-calendar-positive-floor"
MODEL = "goal584-a"
CAP = Decimal(".40")
COST = Decimal(".20")
PRIVATE_ROOT = Path("/proof-private")
IMAGE = "ghcr.io/berriai/litellm:v1.105.1@sha256:b7b9e2c306343721802253d0dd9436b9634a2eb4e14da7c7cf06c5c7b7530802"
COMMAND = ["--config", "/proof/config.yaml", "--host", "0.0.0.0", "--port", "4000", "--num_workers", "1", "--telemetry", "false"]
HELPERS = {
    "prove_calendar_reset.py": "62589e0bf96e3df7673332e28b6a863aa1236b71cd3fee0638e42e7786ee0271",
    "prove_native_budgets.py": "e05bdcb0e14f4833960e4360387df7080adb9a17ca893f7ec65880efe2b897fa",
    "prove_gateway_auth.py": "a506e9f1283d5729d467ee959ceca735e19351e9f2f15b66972d5821c9a6133a",
    "prove_budget_overlap.py": "3c5b9c5b48f35c655063c66286bb0fccf5fe04c243f3f75390dd5d3323d8c522",
    "budget_errors.py": "30a86a662f0320482761a2f52310456c328e112954cf5d0557df09cb20db4abe",
    "pricing_snapshot.py": "9bff480f9939e46f84c6dc2673315e61f2404297c39d734b796774600a9881d6",
    "employee_budget_assignment.py": "72b0026c862cc21adabd32a86e134dfc0cbe9ebf7e5b6ca02e7e088689315b70",
    "native_floor_identity.py": "39d28b28e3d60fb6e5989cdd4b23a2a1341277bc569f2bf3ef0eb9e32deac839",
    "manifest.json": "1695ef5f07b8662e8c8a0bc031c01debb74266f92873bac12cc5f2edac93b99b",
}
EXTRA_NATIVE = {
    "proxy/auth/user_api_key_auth.py": "1d22aa5ccf241f273e69e4baa844e84257b6dd98b17ddb08e8523f862cd187f4",
    "proxy/spend_tracking/budget_reservation.py": "81a0bff3cb00210414f26e14ac9450980dc5f54277740a83029207a112672a8a",
    "proxy/db/spend_counter_reseed.py": "0d76c24ff02b48c4eda9fb8462f8e0fe394dd1c6ba52075f8ed13499adb03b9f",
    "proxy/spend_tracking/spend_counter_batch.py": "9ce9f2719d2af7e80dec004b7199b6213a373c1f4c52d78bb2921416659252af",
    "proxy/hooks/proxy_track_cost_callback.py": "b387f30fc5c896661601b86be402c37aba7fb2990f804d75f60a330457cf754e",
    "caching/in_memory_cache.py": "50a93d8f62ca3938ccd7b24ff76eb3d4e5d98d9efa4fcda395cb1317d77fdf30",
    "caching/dual_cache.py": "e309b4ecb25eced502a205bbb8c499f2015a1e82191e115d7319bf2fdc990188",
    "proxy/common_utils/auth_cache_invalidation_pubsub.py": "1436678f7203c9c1b9f450a5cfda3735519e6c4b86bcebc5740dc7932158a6af",
}
NATIVE_HASHES = {**calendar.NATIVE_HASHES, **EXTRA_NATIVE}
NOT_QUALIFIED = ["raw_live_L1_dump", "live_scheduler_tick", "overdue_advance", "inflight_month_crossing",
                 "restart_or_cache_loss", "cancellation", "global_prompt_privacy", "bare_auth_invalidation",
                 "WebUI_or_gateway", "production", "paid_provider", "whole_GOAL584"]


class FloorError(ProofError):
    def __init__(self, leaf):
        self.leaf = leaf
        super().__init__(leaf)


def check(condition, leaf):
    if not condition:
        raise FloorError(leaf)


def digest(value):
    return calendar.fingerprint(value)


def uuid_value(value):
    try: valid = isinstance(value, str) and str(UUID(value)) == value
    except ValueError: valid = False
    check(valid, "fixture_uuid")
    return value


def private_save(path, state):
    check(len(json.dumps(state, allow_nan=False).encode()) <= 8 * 1024 * 1024, "private_evidence_bound")
    write_private(path, state)


def evidence_paths(args):
    paths = (args.attestation, args.private_state, args.receipt)
    check(len({p.resolve() for p in paths}) == 3 and all(not p.is_symlink() and p.parent.resolve() == PRIVATE_ROOT.resolve()
          for p in paths) and not PRIVATE_ROOT.is_symlink(), "private_paths")
    check(not args.private_state.exists() and not args.receipt.exists(), "fresh_evidence_paths")


def source_files():
    here = Path(__file__).resolve().parent
    observed = {name: hashlib.sha256((here / name).read_bytes()).hexdigest() for name in HELPERS}
    check(observed == HELPERS, "helper_source_binding")
    observed[Path(__file__).name] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    check(LONG_BODY == {"messages": [{"role": "user", "content": "Hi. Please read this bounded synthetic fixture sentence. " * 8}],
                        "max_tokens": 5, "stream": False}, "accepted_long_body")
    return observed


def topology(args, attest, config, files, native_hashes, env=os.environ):
    # Reuse the accepted stock calendar isolation contract for this local worker.
    calendar.require_isolated(args, attest, config, env)
    workers = attest.get("workers")
    check(isinstance(workers, list) and len(workers) == 2, "two_workers")
    check({w.get("number") for w in workers} == {"1", "2"}, "worker_ordinals")
    ids = [w.get("id", "") for w in workers]
    check(len(set(ids)) == 2 and all(re.fullmatch("[0-9a-f]{64}", v) for v in ids), "worker_ids")
    check(len({w.get("image_id") for w in workers}) == 1 and all(re.fullmatch("sha256:[0-9a-f]{64}", w.get("image_id", "")) for w in workers), "worker_image")
    config_sha = hashlib.sha256(Path("/proof/config.yaml").read_bytes()).hexdigest()
    for worker in workers:
        check(set(worker) == {"id", "number", "image_ref", "image_id", "health", "command", "project", "service",
                              "network_mode", "private_mount", "config_sha256", "files_sha256", "native_sha256", "ipv4"}, "worker_fields")
        check(worker.get("image_ref") == calendar.native_sdk.image_ref() and worker.get("health") == "healthy" and worker.get("command") == COMMAND
              and worker.get("project") == args.project and worker.get("service") == "proxy"
              and worker.get("network_mode") == args.project + "_proof"
              and worker.get("private_mount") == attest.get("private_mount") and isinstance(worker.get("private_mount"), str)
              and worker["private_mount"].startswith("/") and worker.get("config_sha256") == config_sha
              and worker.get("files_sha256") == files and worker.get("native_sha256") == native_hashes, "worker_bindings")
        if calendar.native_sdk.variant() != "stock":
            check(worker.get("image_id") == calendar.native_sdk.image_ref(), "derivative_image_id")
        try: address = IPv4Address(worker.get("ipv4", ""))
        except ValueError: raise FloorError("worker_ipv4") from None
        check(address.is_private and not (address.is_loopback or address.is_link_local or address.is_unspecified or address.is_multicast), "worker_ipv4")
    check(len({w["ipv4"] for w in workers}) == 2, "worker_ipv4_distinct")
    local = next(w for w in workers if w["number"] == "2")
    peer = next(w for w in workers if w["number"] == "1")
    check(local["id"] == attest["proxy_container_id"] and env.get("HOSTNAME") == local["id"][:12], "local_worker2")
    check(args.peer_url == "http://" + peer["ipv4"] + ":4000", "peer_url_binding")
    general, settings = config["general_settings"], config["litellm_settings"]
    check(general.get("fail_closed_budget_enforcement") is True and general.get("disable_budget_reservation") in (None, False)
          and general.get("user_api_key_cache_ttl") in (None, 60) and settings.get("redis_ttl") in (None, 60)
          and settings.get("callbacks") == ["budget_errors.handler", "pricing_snapshot.handler"], "native_budget_policy")
    for model in config["model_list"]:
        info = model.get("model_info", {})
        check(info.get("id") == "goal584-deployment-" + model["model_name"][-1] and info.get("mode") == "chat"
              and info.get("max_output_tokens") == 5 and info.get("max_input_tokens") == 10 and info.get("max_tokens") == 15
              and amount(info.get("input_cost_per_token")) == Decimal(".01")
              and amount(info.get("output_cost_per_token")) == Decimal(".02"), "native_fixture_model")
    return {"workers": [{k: v for k, v in w.items() if k != "private_mount"} for w in workers], "config_sha256": config_sha, "peer_url": args.peer_url,
            "native_sha256": native_hashes, "files_sha256": files}


class ProfileHTTP(NativeProof):
    """Only retarget the existing transport to the already-attested worker1 URL."""
    def __init__(self, master, peer_url=None):
        super().__init__("http://127.0.0.1:4000", master, 20, {})
        if peer_url is not None:
            parsed = urlsplit(peer_url)
            try: address = IPv4Address(parsed.hostname or "")
            except ValueError: raise FloorError("peer_url_binding") from None
            check(parsed.scheme == "http" and parsed.port == 4000 and peer_url == "http://" + str(address) + ":4000"
                  and address.is_private and not (address.is_loopback or address.is_link_local or address.is_unspecified or address.is_multicast), "peer_url_binding")
            self.base_url = peer_url  # caller must use topology()'s exact returned URL


def population(counts, snapshot, payer=None, key_hash=None):
    check(set(counts) == set(calendar.TABLES) and all(type(n) is int and n >= 0 for n in counts.values()), "population_counts")
    check(all(counts[name] == 0 for name in calendar.OTHER_TABLES), "foreign_budget_population")
    check(isinstance(snapshot, dict) and set(snapshot) == {"users", "keys", "journal"}
          and all(isinstance(v, list) for v in snapshot.values()), "population_shape")
    expected = int(payer is not None)
    check(counts[calendar.TABLES[0]] == counts[calendar.TABLES[1]] == expected
          and counts[calendar.TABLES[2]] <= (4 if payer else 0), "population_bound")
    check(tuple(map(len, (snapshot["users"], snapshot["keys"], snapshot["journal"]))) == tuple(counts[n] for n in calendar.TABLES[:3]), "population_row_counts")
    identifiers = [row.get("request_id") if isinstance(row, dict) else None for row in snapshot["journal"]]
    check(all(isinstance(value, str) and 0 < len(value) <= 256 and value != "None"
              and not any(c.isspace() for c in value) for value in identifiers)
          and len(set(identifiers)) == len(identifiers), "journal_identity")
    if payer is None:
        return
    uuid_value(payer)
    check(isinstance(key_hash, str) and re.fullmatch("[0-9a-f]{64}", key_hash), "fixture_key_hash")
    user, key = snapshot["users"][0], snapshot["keys"][0]
    check(user.get("user_id") == key.get("user_id") == payer and key.get("token") == key_hash
          and user.get("user_role") == "internal_user" and user.get("models") == key.get("models") == [MODEL] and not user.get("teams")
          and all(key.get(n) is None for n in ("team_id", "project_id", "organization_id", "budget_id", "expires"))
          and key.get("blocked") in (None, False) and key.get("allowed_routes") == ["llm_api_routes"], "foreign_identity")
    metadata = key.get("metadata") or {}
    metadata = json.loads(metadata) if isinstance(metadata, str) else metadata
    check(isinstance(metadata, dict) and metadata.get("throttle_on_budget_exceeded") in (None, False), "key_throttle_policy")
    check(all(r.get("user") == payer and r.get("api_key") == key_hash for r in snapshot["journal"]), "foreign_journal")


async def read_population(db, payer=None, key_hash=None):
    previous = None
    for scan in range(3):  # At most three whole reads; no sleep, row merge or partial retry.
        rows = await db.writer_db.query_raw(calendar.COUNTS_SQL)
        check(len(rows) == len(calendar.TABLES), "population_count_rows")
        counts = {r["name"]: r["n"] for r in rows}
        check(set(counts) == set(calendar.TABLES) and all(type(n) is int and n >= 0 for n in counts.values())
              and all(counts[n] == 0 for n in calendar.OTHER_TABLES)
              and counts[calendar.TABLES[0]] == counts[calendar.TABLES[1]] == int(payer is not None)
              and counts[calendar.TABLES[2]] <= (4 if payer else 0), "preload_population_guard")
        raw = await db.writer_db.query_raw(calendar.ROWS_SQL)
        check(len(raw) == 1, "population_payload")
        snapshot = raw[0]["payload"]
        snapshot = json.loads(snapshot) if isinstance(snapshot, str) else snapshot
        check(len(json.dumps(snapshot, allow_nan=False).encode()) <= 2 * 1024 * 1024, "population_bytes")
        check(isinstance(snapshot, dict) and set(snapshot) == {"users", "keys", "journal"}
              and all(isinstance(v, list) for v in snapshot.values()), "population_shape")
        journal_count = len(snapshot["journal"])
        if counts[calendar.TABLES[2]] < journal_count <= 4:
            # Internal shape/identity validation only, not an observed DB count.
            # The caller still binds every row to its successful call/denial.
            validation_counts = {**counts, calendar.TABLES[2]: journal_count}
            population(validation_counts, snapshot, payer, key_hash)
            if previous is not None:
                unchanged_identity(previous, snapshot)
            check(scan < 2, "population_append_unsettled")
            previous = snapshot
            continue
        population(counts, snapshot, payer, key_hash)
        if previous is not None:
            unchanged_identity(previous, snapshot)
        snapshot["journal"].sort(key=lambda r: r.get("request_id", ""))
        return snapshot


def row_lineage(row):
    metadata = row.get("metadata")
    try:
        metadata = json.loads(metadata) if isinstance(metadata, str) else metadata
    except (ValueError, TypeError):
        raise FloorError("journal_metadata") from None
    check(isinstance(metadata, dict) and isinstance(metadata.get("spend_logs_metadata"), dict), "journal_metadata")
    return metadata, metadata["spend_logs_metadata"]


def denial_attempts(state):
    """Use only validated native422 responses and their original private HTTP bodies."""
    attempts = state.get("http", {})
    check(isinstance(attempts, dict) and len(attempts) <= 4, "http_attempt_bound")
    result = {}
    for label, attempt in attempts.items():
        check(isinstance(attempt, dict), "denial_http_evidence")
        if attempt.get("validated_budget_denial") is not True:
            continue
        check(label in ("prime", "final") and attempt.get("status") == 422
              and isinstance(attempt.get("response"), dict)
              and isinstance(attempt["response"].get("error"), dict)
              and attempt["response"]["error"].get("type") == "budget_exceeded", "denial_http_evidence")
        body = attempt.get("body")
        check(isinstance(body, dict) and body.get("model") == MODEL, "denial_body_evidence")
        _, lineage = row_lineage(body)
        root, chat = lineage.get("root_answer_id"), lineage.get("chat_id")
        check(set(lineage) == {"root_answer_id", "chat_id", "call_kind"}
              and all(isinstance(v, str) and 0 < len(v) <= 256 for v in (root, chat))
              and lineage.get("call_kind") == "synthetic_chat" and body["metadata"].get("session_id") == chat
              and root not in result, "denial_lineage_evidence")
        result[root] = {"lineage": lineage, "label": label, "body_sha256": digest(body)}
    return result


def journal(snapshot, expected, payer, key_hash, *, complete=True, denials=None, terminal=False):
    denials = {} if denials is None else denials
    rows = snapshot["journal"]
    check(len(expected) <= 3 and len(denials) <= 2
          and len(rows) <= len(expected) + len(denials) <= 4, "unexpected_journal_rows")
    success_roots = {item["root"] for item in expected.values()}
    check(len(success_roots) == len(expected) and not success_roots.intersection(denials), "attempt_lineage_collision")
    seen, successes, failures = set(), set(), set()
    for row in rows:
        identifier = row.get("request_id")
        check(isinstance(identifier, str) and 0 < len(identifier) <= 256 and identifier != "None"
              and not any(c.isspace() for c in identifier) and identifier not in seen, "journal_identity")
        seen.add(identifier)
        meta, lineage = row_lineage(row)
        if identifier not in expected:
            root = lineage.get("root_answer_id")
            check(isinstance(root, str) and root in denials and root not in failures
                  and lineage == denials[root]["lineage"], "journal_denial_lineage")
            error = meta.get("error_information")
            check(row.get("user") == payer and row.get("api_key") == key_hash
                  and row.get("status") == meta.get("status") == "failure"
                  and isinstance(error, dict) and error.get("error_class") == "BudgetExceededError" and error.get("error_code") == "422"
                  and amount(row.get("spend")) == 0
                  and all(type(row.get(n)) is int and row[n] == 0 for n in ("prompt_tokens", "completion_tokens", "total_tokens"))
                  and row.get("model_group") == MODEL
                  and row.get("model_id") == "goal584-deployment-a", "journal_denial_identity_cost_usage")
            failures.add(root)
            continue
        successes.add(identifier)
        item = expected[identifier]
        check(row.get("user") == payer and row.get("api_key") == key_hash and row.get("model_group") == MODEL
              and row.get("status") == "success"
              and row.get("model_id") in (None, "goal584-deployment-a") and close_amount(row.get("spend"), COST)
              and tuple(row.get(n) for n in ("prompt_tokens", "completion_tokens", "total_tokens")) == (10, 5, 15)
              and lineage.get("root_answer_id") == item["root"] and lineage.get("chat_id") == item["chat"]
              and lineage.get("call_kind") == "synthetic_chat", "journal_scope_cost_usage")
    if complete:
        check(successes == set(expected), "missing_journal_rows")
    if terminal:
        check(failures == set(denials), "missing_denial_audit_rows")
    return {"success_ids": successes, "denial_roots": failures}


def retain_observation(label, snapshot, values, physical, expected, state, receipt, path, failures=()):
    """Retain the bounded read before assertions; export no arbitrary row fields."""
    observed_at = stamp()
    state["last_observation"] = {"label": label, "at": observed_at,
        "snapshot": snapshot, "redis_key_user": values, "provider": physical}
    def number(value):
        if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
            return None
        try:
            result = Decimal(str(value))
            rendered = str(result)
            return rendered if result.is_finite() and len(rendered) <= 64 else None
        except (ValueError, ArithmeticError):
            return None

    rows = snapshot["journal"]
    try:
        denials = denial_attempts(state)
        denial_ready = True
    except ProofError:
        denials, denial_ready = {}, False
    def denial_label(row):
        try:
            _, lineage = row_lineage(row)
            item = denials.get(lineage.get("root_answer_id"))
            return item if item and lineage == item["lineage"] else None
        except (ProofError, TypeError):
            return None
    def budget_error(row):
        try:
            meta, _ = row_lineage(row)
            error = meta.get("error_information")
            return isinstance(error, dict) and error.get("error_class") == "BudgetExceededError" and error.get("error_code") == "422"
        except ProofError:
            return False
    receipt["last_observation"] = {"label": label, "at": observed_at,
        "journal_count": len(rows), "expected_success_count": len(expected),
        "expected_denial_count": len(denials), "denial_evidence_ready": denial_ready,
        "native_snapshot": calendar.public_snapshot(snapshot),
        "journal_sha256": digest(rows), "redis_key_user": None if values is None else [number(v) for v in values],
        "provider_count": None if physical is None else len(physical["requests"]),
        "capture_failures": list(failures), "private_raw_retained": False,
        "rows": [{"request_id_sha256": digest(row.get("request_id")),
            "is_expected_success_id": isinstance(row.get("request_id"), str) and row["request_id"] in expected,
            "is_recorded_denial_lineage": denial_label(row) is not None,
            "is_native_budget_error": budget_error(row),
            "denial_label": denial_label(row)["label"] if denial_label(row) else None,
            "denial_body_sha256": denial_label(row)["body_sha256"] if denial_label(row) else None,
            "status": row.get("status") if row.get("status") in ("success", "failure", "error", "pending") else "other_or_missing",
            "spend_usd": number(row.get("spend")),
            "usage": {name: row.get(name) if type(row.get(name)) is int and 0 <= row[name] <= 1_000_000 else None
                for name in ("prompt_tokens", "completion_tokens", "total_tokens")},
            "full_row_sha256": digest(row)} for row in rows]}
    private_save(path, state)
    receipt["last_observation"]["private_raw_retained"] = True


async def retain_failed_observation(label, snapshot, counters, read_provider, expected, state, receipt, path):
    """Best effort diagnosis must preserve the already established boundary error."""
    failures, values, physical = [], None, None
    try:
        retain_observation(label, snapshot, None, None, expected, state, receipt, path)
    except Exception:
        failures.append("initial_private_retention_failed")
    try:
        values = await counters()
    except Exception:
        failures.append("counter_read_failed")
    try:
        physical = read_provider()
    except Exception:
        failures.append("provider_read_failed")
    try:
        retain_observation(label, snapshot, values, physical, expected, state, receipt, path, failures)
    except Exception:
        receipt["boundary_observation_capture_failed"] = True


def money(snapshot, spend, lifetime, boundary, count):
    check(sum(row.get("status") == "success" for row in snapshot["journal"]) == count, "successful_journal_count")
    for row in snapshot["users"] + snapshot["keys"]:
        check(amount(row.get("max_budget")) == CAP and close_amount(row.get("spend"), spend)
              and row.get("budget_duration") == "1mo" and calendar.timestamp(row.get("budget_reset_at")) == boundary, "native_money_period")
    check(close_amount(snapshot["keys"][0].get("total_spend"), lifetime), "native_lifetime")


def unchanged_identity(before, after):
    for table in ("users", "keys"):
        omit = {"spend", "total_spend", "budget_reset_at", "updated_at", "last_active"}
        check([{k: v for k, v in r.items() if k not in omit} for r in before[table]]
              == [{k: v for k, v in r.items() if k not in omit} for r in after[table]], "identity_drift")
    old = {r["request_id"]: r for r in before["journal"]}
    new = {r["request_id"]: r for r in after["journal"]}
    check(all(new.get(k) == v for k, v in old.items()), "historical_row_drift")


def reset_transition(before, after, boundary, expected, denials, payer, key_hash):
    journal(after, expected, payer, key_hash, denials=denials)
    unchanged_identity(before, after)
    # The existing reset owner verifies every User/key field, including lifetime.
    # Full raw history was checked above; only explicitly bound late denial audits
    # may be new, so project the retained history for that owner's equality check.
    calendar.reset_delta(before, {**after, "journal": before["journal"]}, boundary)


def stamp():
    return {"epoch": time.time(), "monotonic": time.monotonic()}


def window(start, end):
    check(all(type(s.get(k)) in (int, float) and math.isfinite(s[k]) for s in (start, end) for k in ("epoch", "monotonic")), "clock_values")
    wall, mono = end["epoch"] - start["epoch"], end["monotonic"] - start["monotonic"]
    check(0 <= wall < 5 and 0 <= mono < 5 and abs(wall - mono) < .1, "critical_window")
    return {"real_elapsed_seconds": wall, "monotonic_elapsed_seconds": mono, "floor_ttl_seconds": 5,
            "unchanged_auth_ttl_seconds": 60, "marker_epoch_directly_observed": False}


def provider(proof):
    with proof.opener.open(Request("http://provider:8000/__proof/requests"), timeout=3) as response:
        raw = response.read(4 * 1024 * 1024 + 1)
    check(len(raw) <= 4 * 1024 * 1024, "provider_bytes")
    value = json.loads(raw)
    check(value.get("synthetic") is True and isinstance(value.get("requests"), list) and len(value["requests"]) <= 3, "provider_population")
    control = value.get("control", {})
    check(control.get("prompt_tokens") == 10 and control.get("completion_tokens") == 5 and control.get("delay_ms") == 0
          and all(control.get(k, False) is False for k in ("tool_round", "admin_mode", "title_mode", "native_tasks_mode"))
          and control.get("response_status", 200) == 200 and control.get("after_first_chunk_delay_ms", 0) == 0, "provider_controls")
    return value


def provider_evidence(value, expected):
    rows = value["requests"]
    check(len(rows) == len(expected) and len({r.get("id") for r in rows}) == len(rows), "provider_count")
    for row in rows:
        check(row.get("id") in expected, "provider_id")
        item = expected[row["id"]]
        wanted = {"model": "goal584-fake-a", **copy.deepcopy(item["semantic"])}
        wanted.pop("stream")
        check(row.get("body") == wanted and row.get("usage") == {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
              and row.get("lifecycle", {}).get("terminal") is True and row["lifecycle"].get("outcome") == "completed", "provider_context_usage")


def request_call(proof, token, payer, label, expected, state, receipt, path, *, long=False):
    check(label in ("old", "prime", "post", "final") and label not in state.get("http", {})
          and len(state.get("http", {})) < 4, "http_attempt_bound")
    semantic = copy.deepcopy(LONG_BODY) if long else {"messages": [{"role": "user", "content": "Hi"}], "max_tokens": 5, "stream": False}
    root, chat = proof.run_id + "-answer-" + uuid4().hex[:12], payer + "-chat"
    body = {"model": MODEL, **semantic, "metadata": {"session_id": chat, "spend_logs_metadata": {
        "chat_id": chat, "root_answer_id": root, "call_kind": "synthetic_chat"}}}
    start = stamp()
    status, response, headers = proof.request("POST", "/v1/chat/completions", token=token, body=body)
    end = stamp()
    state.setdefault("http", {})[label] = {"status": status, "body": body, "response": response,
        "cost_header": headers.get("x-litellm-response-cost"), "start": start, "end": end}
    private_save(path, state)
    safe = {"label": label, "status": status, "worker": "1" if label == "old" else "2", "body_sha256": digest(body), "start": start, "end": end}
    if status == 200:
        identifier = response.get("id", "")
        check(re.fullmatch("chatcmpl-goal584-[0-9a-f]{32}", identifier) and identifier not in expected, "response_id")
        choices = response.get("choices")
        check(isinstance(choices, list) and len(choices) == 1 and isinstance(choices[0], dict), "response_choices")
        message = choices[0].get("message", {})
        usage = response.get("usage", {})
        check(tuple(usage.get(k) for k in ("prompt_tokens", "completion_tokens", "total_tokens")) == (10, 5, 15)
              and message.get("role") == "assistant" and message.get("content") == "Proof"
              and message.get("tool_calls") in (None, []) and message.get("function_call") is None
              and choices[0].get("finish_reason") == "stop", "response_context_usage")
        header = headers.get("x-litellm-response-cost")
        check(header not in (None, "", "None") and close_amount(header, COST), "response_native_cost")
        expected[identifier] = {"root": root, "chat": chat, "semantic": semantic}
        safe.update(outcome="success", request_id=identifier, native_cost_usd=str(COST),
                    usage={k: usage[k] for k in ("prompt_tokens", "completion_tokens", "total_tokens")})
    elif status == 422:
        check(isinstance(response.get("error"), dict) and response["error"].get("type") == "budget_exceeded", "native_budget_error")
        expected_budget_message(response, scope="key")
        state["http"][label]["validated_budget_denial"] = True
        safe.update(outcome="budget_exceeded", scope="key", error_type="budget_exceeded")
    else:
        raise FloorError("unexpected_http_status")
    receipt.setdefault("attempts", []).append(safe)
    state["expected"] = expected
    private_save(path, state)
    return safe


def outcome(first_counters, final_status, final_counters):
    healthy = all(close_amount(v, COST) for v in first_counters)
    phantom = all(close_amount(v, CAP) for v in first_counters)
    check(len(first_counters) == len(final_counters) == 2, "counter_shape")
    if healthy and final_status == 200 and all(close_amount(v, CAP) for v in final_counters):
        return "PASS_SELECTED_PROFILE"
    if phantom and final_status == 422 and all(close_amount(v, CAP) for v in final_counters):
        return "FAIL_STALE_POSITIVE_FLOOR"
    raise FloorError("other_counter_or_admission_outcome")


async def qualify(args, attest, receipt, secrets):
    receipt["phase"] = "source_settings"
    import litellm
    from litellm.proxy import proxy_server as ps
    from litellm.proxy.common_utils import reset_budget_job as jobs, timezone_utils as tz
    from litellm.proxy.utils import PrismaClient
    from litellm.constants import DEFAULT_MANAGEMENT_OBJECT_IN_MEMORY_CACHE_TTL
    check(version("litellm") == "1.105.1" and ps.prisma_client is None, "native_standalone_version")
    package = Path(litellm.__file__).parent
    actual = {name: hashlib.sha256((package / name).read_bytes()).hexdigest() for name in NATIVE_HASHES}
    check(actual == calendar.native_sdk.selected_hashes(NATIVE_HASHES) and len(actual) == 18, "native_18_sources")
    receipt["native_artifact"] = calendar.native_sdk.identity()
    files = source_files()
    config = await ps.proxy_config.get_config(config_file_path="/proof/config.yaml")
    check(not os.environ.get("LITELLM_CONFIG_BUCKET_NAME"), "native_local_config")
    secrets.extend([config["general_settings"]["database_url"], urlsplit(config["general_settings"]["database_url"]).password or ""])
    receipt["topology"] = topology(args, attest, config, files, actual)
    check(min(ps.UserAPIKeyCacheTTLEnum.in_memory_cache_ttl.value, DEFAULT_MANAGEMENT_OBJECT_IN_MEMORY_CACHE_TTL) == 60
          and ps.SPEND_DB_FLOOR_CACHE_TTL_SECONDS == 5 and litellm.budget_rollover is False, "native_ttls")
    local, peer = ProfileHTTP(secrets[0]), ProfileHTTP(secrets[0], args.peer_url)
    receipt.update(project=args.project, auth_route="native_stock_virtual_key", native_revision=calendar.REVISION,
                   floor_priming="pinned_source_inferred_not_live_L1_dump", accepted_long_estimate_usd="0.98")
    receipt["phase"] = "native_owner_wiring"
    redis = ps.proxy_config._init_coordination_redis(config=config)
    db = None
    state = {"schema": 1, "proof": PROOF, "stage": "owner_wiring", "snapshots": {}, "expected": {}}
    payer, key_hash = str(uuid4()), None
    try:
        check(redis is not None and redis.namespace is None, "native_coordination_redis")
        ps._set_redis_usage_cache(redis)
        ps.proxy_logging_obj.update_values(redis_cache=redis)
        lock = ps.proxy_logging_obj.db_spend_update_writer.pod_lock_manager
        check(ps.spend_counter_cache.redis_cache is redis and lock.redis_cache is redis, "native_cache_lease_wiring")
        check(redis.get_ttl() == 60, "native_redis_ttl")
        db = PrismaClient(database_url=config["general_settings"]["database_url"], proxy_logging_obj=ps.proxy_logging_obj)
        await db.connect()
        check(await redis.ping() and redis.redis_client.info("server")["run_id"] == attest["redis_run_id"], "redis_identity")
        receipt["phase"] = "empty_population"
        await read_population(db)
        initial_provider = provider(local)
        check(initial_provider["requests"] == [], "fresh_provider")
        local.schema()
        peer.schema()  # liveliness is a native JSON string, not NativeProof's object contract
        receipt["phase"] = "native_creation"
        local.ok("POST", "/user/new", body={"user_id": payer, "user_role": "internal_user", "models": [MODEL],
            "max_budget": float(CAP), "budget_duration": "1mo", "auto_create_key": False, "send_invite_email": False})
        state.update(payer_id=payer, stage="user_created")
        private_save(args.private_state, state)
        created = local.ok("POST", "/key/generate", body={"user_id": payer, "models": [MODEL], "max_budget": float(CAP),
            "budget_duration": "1mo", "duration": None, "key_alias": args.project, "allowed_routes": ["llm_api_routes"]})
        token = created["key"]
        if isinstance(token, str): secrets.append(token)
        check(isinstance(token, str) and token.startswith("sk-") and len(token) >= 20, "created_key_secret")
        key_hash = hashlib.sha256(token.encode()).hexdigest()
        state.update(key=token, key_hash=key_hash, stage="key_created")
        private_save(args.private_state, state)
        receipt["phase"] = "created_profile"
        initial = await read_population(db, payer, key_hash)
        receipt["created_profile"] = calendar.public_snapshot(initial)
        state["snapshots"]["created"] = initial
        private_save(args.private_state, state)
        check(initial["keys"][0].get("key_alias") == args.project, "native_key_alias")
        boundary = calendar.timestamp(initial["users"][0]["budget_reset_at"])
        wall = boundary.astimezone(ZoneInfo("Europe/Moscow"))
        check((wall.day, wall.hour, wall.minute, wall.second, wall.microsecond) == (1, 0, 0, 0, 0), "created_moscow_boundary")
        money(initial, Decimal(0), Decimal(0), boundary, 0)
        next_wall = wall.replace(year=wall.year + (wall.month == 12), month=1 if wall.month == 12 else wall.month + 1)
        next_boundary = next_wall.astimezone(timezone.utc)
        settings = tz.BudgetResetSettings(timezone="Europe/Moscow", reset_time_of_day=tz.parse_budget_reset_time("00:00"))
        job = jobs.ResetBudgetJob(proxy_logging_obj=ps.proxy_logging_obj, prisma_client=db, reset_settings=settings, pod_lock_manager=lock)
        ps.prisma_client = db
        expected = state["expected"]
        counter_keys = ("spend:key:" + key_hash, "spend:user:" + payer)
        prime_start = None

        async def counters():
            return [await redis.async_get_cache(key=k) for k in counter_keys]

        async def observe(label, spend, lifetime, period, count, *, settled=False, allowed_counters=()):
            deadline = time.monotonic() + 60
            while True:
                if prime_start is not None and label != "final":
                    window(prime_start, stamp())
                snapshot = await read_population(db, payer, key_hash)
                try:
                    denials = denial_attempts(state)
                    audit = journal(snapshot, expected, payer, key_hash, complete=False, denials=denials)
                    unchanged_identity(initial, snapshot)
                    previous = state.get("last_observation", {}).get("snapshot")
                    if previous is not None:
                        unchanged_identity(previous, snapshot)
                except ProofError:
                    await retain_failed_observation(label, snapshot, counters, lambda: provider(local),
                        expected, state, receipt, args.private_state)
                    raise
                values = await counters()
                physical = provider(local)
                retain_observation(label, snapshot, values, physical, expected, state, receipt, args.private_state)
                ready = (len(audit["success_ids"]) == count
                    and (label != "final" or audit["denial_roots"] == set(denials))
                    and all(close_amount(r.get("spend"), spend) for r in snapshot["users"] + snapshot["keys"]))
                cache_ready = not allowed_counters or any(all(v is not None and close_amount(v, a) for v in values) for a in allowed_counters)
                if ready and cache_ready:
                    check(label != "final" or time.monotonic() < deadline, "native_settlement")
                    money(snapshot, spend, lifetime, period, count)
                    journal(snapshot, expected, payer, key_hash, denials=denials, terminal=label == "final")
                    provider_evidence(physical, expected)
                    state["snapshots"][label] = snapshot
                    state["stage"] = label
                    state.setdefault("provider", {})[label] = physical
                    state.setdefault("counters", {})[label] = values
                    private_save(args.private_state, state)
                    receipt.setdefault("observations", {})[label] = {**calendar.public_snapshot(snapshot), "redis_key_user": values,
                        "successful_physical_rows": len(audit["success_ids"]), "denial_audit_rows": len(audit["denial_roots"])}
                    return snapshot, values
                if label == "final" and time.monotonic() >= deadline:
                    journal(snapshot, expected, payer, key_hash, denials=denials, terminal=True)
                check(settled and time.monotonic() < deadline, "native_settlement")
                await asyncio.sleep(.05)

        receipt["phase"] = "old_peer_call"
        old_call = request_call(peer, token, payer, "old", expected, state, receipt, args.private_state)
        check(old_call["status"] == 200, "old_admission")
        old, _ = await observe("old", COST, COST, boundary, 1, settled=True, allowed_counters=(COST,))
        receipt["phase"] = "cold_worker2_prime"
        prime = request_call(local, token, payer, "prime", expected, state, receipt, args.private_state, long=True)
        prime_start = prime["start"]
        check(prime["status"] == 422, "prime_reservation_denial")
        primed, _ = await observe("primed", COST, COST, boundary, 1, allowed_counters=(COST,))
        unchanged_identity(old, primed)
        receipt["phase"] = "native_due_reset"
        # Existing full global-population guard, no filtered job or manual writes.
        await read_population(db, payer, key_hash)
        check(await redis.async_get_cache(lock.get_redis_lock_key(jobs.RESET_BUDGET_JOB_NAME)) is None, "reset_lease_unowned")
        at = boundary + timedelta(seconds=1)
        receipt["reset_clock_utc"] = at.isoformat()
        state["job"] = {"clock_utc": at.isoformat(), "start": stamp(), "returned": False}
        state["stage"] = "reset_started"
        private_save(args.private_state, state)
        try:
            with patch.object(jobs, "datetime", calendar.clock_at(at)), patch.object(tz, "datetime", calendar.clock_at(at)):
                await asyncio.wait_for(job.reset_budget(), timeout=30)
            state["job"]["returned"] = True
        finally:
            state["job"]["end"] = stamp()
            private_save(args.private_state, state)
        reset, reset_counters = await observe("reset", Decimal(0), COST, next_boundary, 1)
        reset_transition(primed, reset, next_boundary, expected, denial_attempts(state), payer, key_hash)
        check(reset_counters == [None, None] and await redis.async_get_cache(lock.get_redis_lock_key(jobs.RESET_BUDGET_JOB_NAME)) is None, "native_reset_counter_lease")
        receipt["phase"] = "first_post_reset"
        window(prime_start, stamp())
        post = request_call(local, token, payer, "post", expected, state, receipt, args.private_state)
        check(post["status"] == 200, "post_reset_admission")
        post_snapshot, post_counters = await observe("post", COST, 2 * COST, next_boundary, 2, settled=True, allowed_counters=(COST, CAP))
        unchanged_identity(old, post_snapshot)
        receipt["phase"] = "remaining_headroom"
        window(prime_start, stamp())
        final_call = request_call(local, token, payer, "final", expected, state, receipt, args.private_state)
        receipt["critical_window"] = window(prime_start, final_call["end"])
        count = 3 if final_call["status"] == 200 else 2
        spend = CAP if count == 3 else COST
        final, final_counters = await observe("final", spend, count * COST, next_boundary, count, settled=True, allowed_counters=(CAP,))
        unchanged_identity(post_snapshot, final)
        result = outcome(post_counters, final_call["status"], final_counters)
        receipt.update(outcome=result, passed=result == "PASS_SELECTED_PROFILE", payer_id=payer, key_hash=key_hash,
            successful_calls=count, legitimate_reservation_denials=1, final_probe_status=final_call["status"],
            recorded_budget_denials=len(denial_attempts(state)), raw_journal_rows=len(final["journal"]),
            final_period_spend_usd=str(spend), native_lifetime_spend_usd=str(count * COST), physical_calls=count,
            boundary_utc=boundary.isoformat(), next_boundary_utc=next_boundary.isoformat())
        receipt["phase"] = "observed"
        state["stage"] = result
        private_save(args.private_state, state)
    finally:
        ps.prisma_client = None
        db_closed = db is None
        try:
            if db is not None:
                await db.disconnect()
                db_closed = True
        finally:
            receipt["helper_resources_closed"] = False
            if redis is not None:
                await redis.disconnect()
            receipt["helper_resources_closed"] = db_closed


def safe_receipt(receipt, secrets):
    rendered = json.dumps(receipt, allow_nan=False)
    check(len(rendered.encode()) <= 256 * 1024 and not any(s and s in rendered for s in secrets), "receipt_credentials")
    check(not re.search(r"(?:sk-|gw-|Bearer\s)[A-Za-z0-9_-]{12,}", rendered), "receipt_credentials")
    return rendered


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--peer-url", required=True)
    for name in ("attestation", "private-state", "receipt"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    receipt = {"schema": 1, "proof": PROOF, "passed": False, "phase": "initialization", "not_qualified": NOT_QUALIFIED}
    secrets = [os.environ.get("PROOF_MASTER_KEY", ""), os.environ.get("OWUI_BUDGET_GATEWAY_SECRET", "")]
    paths_valid = False
    try:
        evidence_paths(args)
        paths_valid = True
        check(secrets[0].startswith("sk-") and len(secrets[0]) >= 20, "master_private_handoff")
        asyncio.run(qualify(args, read_private(args.attestation), receipt, secrets))
    except FloorError as error:
        receipt.update(passed=False, failure_phase=receipt["phase"], failure_leaf=error.leaf,
                       outcome="INCONCLUSIVE_TIMING" if error.leaf == "critical_window" else "FAILED_BOUNDARY")
    except ProofError:
        receipt.update(passed=False, failure_phase=receipt["phase"], failure_leaf="native_boundary", outcome="FAILED_BOUNDARY")
    except Exception:
        receipt.update(passed=False, failure_phase=receipt["phase"], failure_leaf="native_exception", outcome="FAILED_BOUNDARY")
    try:
        rendered = safe_receipt(receipt, secrets)
    except (ProofError, ValueError, TypeError):
        receipt = {"schema": 1, "proof": PROOF, "passed": False, "outcome": "FAILED_BOUNDARY", "failure_leaf": "unsafe_receipt"}
        rendered = safe_receipt(receipt, [])
    # Failed path validation must not create an arbitrary output file.
    if paths_valid:
        write_private(args.receipt, receipt)
    print(rendered)
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
