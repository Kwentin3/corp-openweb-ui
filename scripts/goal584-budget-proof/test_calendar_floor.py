"""Offline source/boundary checks. No native job, Docker, DB or provider runs."""
import ast
import asyncio
import copy
from collections.abc import Mapping
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from threading import Thread
from types import MappingProxyType, ModuleType, SimpleNamespace
from typing import SupportsIndex, SupportsInt, TypedDict, cast
import unittest
from unittest.mock import patch
from uuid import uuid4

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import prove_calendar_floor as P

UPSTREAM = HERE.parents[1] / "local/goal584/litellm/upstream"


def native_bytes(relative):
    env = os.environ.copy()
    env["GIT_NO_LAZY_FETCH"] = "1"
    result = subprocess.run(["git", "-c", "gc.auto=0", "show", P.calendar.REVISION + ":litellm/" + relative],
                            cwd=UPSTREAM, env=env, capture_output=True, timeout=10)
    if result.returncode:
        raise RuntimeError("Required pinned cached blob unavailable; no fetch attempted")
    return result.stdout


def execute(nodes, namespace):
    tree = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), *nodes], type_ignores=[])
    exec(compile(ast.fix_missing_locations(tree), "actual-pinned-native-source", "exec"), namespace)


def packet(count=1, period_spend=P.COST, lifetime=None):
    uid, key_hash = "1d04bb40-7094-4451-83b5-79874cde5dfa", "a" * 64
    boundary = datetime(2026, 12, 31, 21, tzinfo=timezone.utc)
    row = {"user_id": uid, "models": [P.MODEL], "max_budget": .4, "spend": float(period_spend),
           "budget_duration": "1mo", "budget_reset_at": boundary.isoformat(), "teams": [], "user_role": "internal_user"}
    key = {**row, "token": key_hash, "total_spend": float(lifetime if lifetime is not None else count * P.COST),
           "team_id": None, "project_id": None, "organization_id": None, "budget_id": None, "expires": None,
           "metadata": {}, "blocked": False, "allowed_routes": ["llm_api_routes"]}
    expected, journal = {}, []
    for index in range(count):
        rid = "chatcmpl-goal584-" + str(index + 1).zfill(32)
        item = {"root": "root-" + str(index), "chat": uid + "-chat",
                "semantic": {"messages": [{"role": "user", "content": "Hi"}], "max_tokens": 5, "stream": False}}
        expected[rid] = item
        journal.append({"request_id": rid, "status": "success", "user": uid, "api_key": key_hash, "model_group": P.MODEL,
                        "model_id": "goal584-deployment-a", "spend": .2, "prompt_tokens": 10, "completion_tokens": 5,
                        "total_tokens": 15, "metadata": {"spend_logs_metadata": {"root_answer_id": item["root"],
                            "chat_id": item["chat"], "call_kind": "synthetic_chat"}}, "arbitrary_historical_column": {"keep": True}})
    snapshot = {"users": [row], "keys": [key], "journal": journal}
    counts = {name: 0 for name in P.calendar.TABLES}
    counts.update(dict(zip(P.calendar.TABLES[:3], [1, 1, count])))
    return snapshot, expected, counts, uid, key_hash, boundary


def denial_packet(snapshot, label="prime", state=None):
    state = {} if state is None else state
    response = {"error": {"type": "budget_exceeded", "message": P.expected_budget_message.__globals__["BUDGET_MODEL_MESSAGE"]}}
    native = SimpleNamespace(run_id="synthetic-floor", request=lambda *a, **k: (422, response, {}))
    with patch.object(P, "private_save"):
        P.request_call(native, "private-key", snapshot["users"][0]["user_id"], label, {}, state, {}, Path("unused"), long=label == "prime")
    body = state["http"][label]["body"]
    row = {"request_id": str(uuid4()), "user": snapshot["users"][0]["user_id"], "api_key": snapshot["keys"][0]["token"],
        "model_group": P.MODEL, "model_id": "goal584-deployment-a", "status": "failure", "spend": 0,
        "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
        "metadata": {"spend_logs_metadata": copy.deepcopy(body["metadata"]["spend_logs_metadata"]), "status": "failure",
            "error_information": {"error_class": "BudgetExceededError", "error_code": "422", "error_message": "private native detail"}}}
    return row, state


class NativeOwnerTests(unittest.TestCase):
    def test_actual_native_budget_error_information_and_default_failure_logging_policy(self):
        exception = next(n for n in ast.parse(native_bytes("exceptions.py")).body if isinstance(n, ast.ClassDef) and n.name == "BudgetExceededError")
        getter = next(n for n in ast.walk(ast.parse(native_bytes("litellm_core_utils/litellm_logging.py")))
                      if isinstance(n, ast.FunctionDef) and n.name == "get_error_information")
        getter.decorator_list = []
        native_type = next(n for n in ast.parse(native_bytes("types/utils.py")).body
                           if isinstance(n, ast.ClassDef) and n.name == "StandardLoggingPayloadErrorInformation")
        ns = {"litellm": SimpleNamespace(budget_exceeded_status_code=422, log_client_error_tracebacks=False),
            "RateLimitErrorCategory": SimpleNamespace(LITELLM_RATE_LIMIT=SimpleNamespace(value="litellm_rate_limit")),
            "RateLimitType": SimpleNamespace(BUDGET=SimpleNamespace(value="budget")), "TypedDict": TypedDict,
            "is_expected_client_error": lambda _: True, "validate_rate_limit_category": lambda v: v,
            "validate_rate_limit_type": lambda v: v, "_get_provider_request_id": lambda _: None,
            "_redact_string": lambda v: v, "normalize_error": lambda *a: None}
        execute([exception, native_type, getter], ns)
        constants = ModuleType("litellm.constants"); constants.MAXIMUM_TRACEBACK_LINES_TO_LOG = 100
        proxy = ModuleType("litellm.proxy.proxy_server"); proxy.general_settings = {}
        modules = {"litellm.constants": constants, "litellm.proxy.proxy_server": proxy}
        with patch.dict(sys.modules, modules):
            error = ns["BudgetExceededError"](.2, .4, entity_type="key", entity_id="synthetic")
            result = ns["get_error_information"](error)
            self.assertEqual((result["error_class"], result["error_code"]), ("BudgetExceededError", "422"))
            self.assertEqual(result["error_budget_entity_type"], "key")
            tracking = next(n for n in ast.walk(ast.parse(native_bytes("proxy/hooks/proxy_track_cost_callback.py")))
                            if isinstance(n, ast.FunctionDef) and n.name == "_should_track_errors_in_db")
            tracking.decorator_list = []
            execute([tracking], ns)
            self.assertIsNone(ns[tracking.name]())  # hook deliberately checks `is False`
            proxy.general_settings["disable_error_logs"] = True
            self.assertIs(ns[tracking.name](), False)

    def test_actual_failure_callback_and_typed_metadata_projection_retain_original_denial_lineage(self):
        raw, _, _, uid, key_hash, _ = packet()
        _, state = denial_packet(raw)
        body = copy.deepcopy(state["http"]["prime"]["body"])
        lineage = copy.deepcopy(body["metadata"]["spend_logs_metadata"])
        hook_tree = ast.parse(native_bytes("proxy/hooks/proxy_track_cost_callback.py"))
        hook = next(n for n in ast.walk(hook_tree) if isinstance(n, ast.AsyncFunctionDef) and n.name == "async_post_call_failure_hook")
        written = []
        async def released(**kwargs): pass
        async def enrich(**kwargs): return kwargs["metadata"]
        async def update(**kwargs): written.append(kwargs)
        async def no_invalidation(**kwargs): raise AssertionError("no reservation-release error")
        auth = SimpleNamespace(budget_reservation=None, request_route="/v1/chat/completions", user_id=uid,
            end_user_id=None, team_id=None, org_id=None, project_id=None)
        error_information = {"error_class": "BudgetExceededError", "error_code": "422"}
        ns = {"_release_budget_reservation": released, "_invalidate_budget_reservation_counters": no_invalidation,
            "_ProxyDBLogger": SimpleNamespace(_should_track_errors_in_db=lambda: None, _enrich_failure_metadata_unless_db_stalled=enrich),
            "RouteChecks": SimpleNamespace(is_llm_api_route=lambda **k: True, is_info_route=lambda **k: False),
            "LiteLLMProxyRequestSetup": SimpleNamespace(get_sanitized_user_information_from_key=lambda **k: {"user_api_key_user_id": uid}, get_logged_api_key=lambda a: key_hash),
            "StandardLoggingPayloadSetup": SimpleNamespace(get_error_information=lambda **k: error_information),
            "should_suppress_spend_log_tracebacks": lambda: True, "cast": cast, "StandardLoggingPayloadErrorInformation": dict,
            "_sanitize_error_information_for_spend_logs": lambda e, **k: e,
            "_proxy_stamped_used_client_oauth_token": lambda *a: False, "datetime": datetime,
            "litellm": SimpleNamespace(Usage=type("Usage", (), {})), "guardrail_information_cost": lambda _: 0}
        execute([hook], ns)
        asyncio.run(ns[hook.name](SimpleNamespace(_spend_writer=lambda: SimpleNamespace(update_database=update)), body, Exception("budget"), auth))
        self.assertEqual(len(written), 1)
        args = written[0]
        metadata = args["kwargs"]["litellm_params"]["metadata"]
        self.assertEqual((args["response_cost"], args["user_id"], args["token"]), (0, uid, key_hash))
        self.assertEqual(metadata["spend_logs_metadata"], lineage)
        self.assertEqual(metadata["status"], "failure")
        types_tree = ast.parse(native_bytes("proxy/_types.py"))
        native_type = next(n for n in types_tree.body if isinstance(n, ast.ClassDef) and n.name == "SpendLogsMetadata")
        utils_tree = ast.parse(native_bytes("proxy/spend_tracking/spend_tracking_utils.py"))
        nodes = [n for n in utils_tree.body if getattr(n, "name", None) == "_get_spend_logs_metadata"
                 or isinstance(n, ast.AnnAssign) and getattr(n.target, "id", None) == "_STAMPED_METADATA_KEYS"]
        projection = {"TypedDict": TypedDict, "MappingProxyType": MappingProxyType,
            "verbose_proxy_logger": SimpleNamespace(debug=lambda *a: None), "_is_non_secret_key_value": lambda *a, **k: True,
            "_redact_logged_api_key": lambda key, **k: key, "_get_vector_store_request_for_spend_logs_payload": lambda _: None,
            "_sanitize_guardrail_information_for_spend_logs": lambda _: None}
        execute([native_type, *nodes], projection)
        stored = projection["_get_spend_logs_metadata"](metadata)
        self.assertEqual(stored["spend_logs_metadata"], lineage)
        self.assertEqual((stored["status"], stored["error_information"]), ("failure", error_information))
        self.assertIs(type(stored), dict)

    def test_all_18_pinned_owner_blobs_are_actual_cached_revision(self):
        self.assertEqual(len(P.EXTRA_NATIVE), 8)
        self.assertEqual(len(P.NATIVE_HASHES), 18)
        for relative, expected in P.NATIVE_HASHES.items():
            with self.subTest(relative=relative):
                self.assertEqual(hashlib.sha256(native_bytes(relative)).hexdigest(), expected)

    def test_actual_clean_miss_coalesced_write_through_does_not_rewrite_positive_floor(self):
        proxy = ast.parse(native_bytes("proxy/proxy_server.py"))
        reseed = ast.parse(native_bytes("proxy/db/spend_counter_reseed.py"))
        owner = next(n for n in reseed.body if isinstance(n, ast.ClassDef) and n.name == "SpendCounterReseed")
        owner.body = [n for n in owner.body if getattr(n, "name", None) == "coalesced"]
        class Memory:
            def __init__(self): self.values, self.writes = {}, []
            def get_cache(self, *, key): return self.values.get(key)
            def set_cache(self, *, key, value, **kwargs):
                self.values[key] = value
                self.writes.append((key, value, kwargs))
        memory = Memory()
        shared, db = {"value": .2}, {"value": .2}
        db_reads, writes, records = [], [], []
        async def getredis(*, key): return shared["value"]
        async def setredis(*, key, value, nx=False):
            writes.append((key, value, nx))
            if nx and shared["value"] is not None: return False
            shared["value"] = value
            return True
        async def setmax(*, key, value):
            shared["value"] = max(shared["value"], value)
            return shared["value"]
        async def dbread(*args, **kwargs):
            db_reads.append(args[1] if len(args) > 1 else kwargs["counter_key"])
            return db["value"]
        async def no_batch(key): return None
        async def lock(key): return asyncio.Lock()
        ns = {"spend_counter_cache": SimpleNamespace(in_memory_cache=memory, redis_cache=SimpleNamespace(
            async_get_cache=getredis, async_set_cache=setredis, async_set_max=setmax)), "prisma_client": object(),
            "active_spend_counter_batch": lambda: None, "_fail_closed_budget_enforcement": lambda: True,
            "SPEND_DB_FLOOR_CACHE_TTL_SECONDS": 5, "END_USER_COUNTER_PREFIX": "spend:end_user:",
            "forget_spend_counter": lambda k: None, "record_spend_counter_value": lambda *args: records.append(args),
            "verbose_proxy_logger": SimpleNamespace(exception=lambda *a, **k: None)}
        names = {"get_current_spend", "_authoritative_floor_spend", "_repair_stale_spend_counter",
                 "read_spend_counter_cache_value", "_read_spend_counter_estimate", "_floor_spend_from_db"}
        execute([owner, *(n for n in proxy.body if getattr(n, "name", None) in names)], ns)
        native = ns["SpendCounterReseed"]
        native.from_db, native._get_lock, native._read_active_batch = staticmethod(dbread), staticmethod(lock), staticmethod(no_batch)
        async def exercise():
            get, key = ns["get_current_spend"], "spend:user:synthetic"
            floor_key = "spend_db_floor:" + key
            self.assertEqual(await get(key, 0, max_budget=.2), .2)
            self.assertEqual(db_reads, [])  # fully exhausted cannot prime
            self.assertEqual(await get(key, 0, max_budget=.4), .2)
            self.assertEqual(memory.writes[-1], (floor_key, .2, {"ttl": 5}))
            shared["value"], db["value"], memory.values[key] = None, 0, .2
            self.assertEqual(await get(key, .2, max_budget=.4), .2)
            self.assertEqual(writes, [(key, 0, True)])
            self.assertEqual(records[0], (key, 0.0))
            self.assertEqual(memory.values[floor_key], .2)
            self.assertEqual(shared["value"], .2)
            self.assertEqual(db_reads, [key, key])
            shared["value"], db["value"] = .4, .2
            self.assertEqual(await get(key, .2, max_budget=.4), .4)
            self.assertEqual(db_reads, [key, key])
        asyncio.run(exercise())  # actual source, stubbed DB/Redis/locks; never job PASS

    def test_actual_output_estimator_clamps_44_and_strict_remaining_policy_denies(self):
        tree = ast.parse(native_bytes("proxy/spend_tracking/budget_reservation.py"))
        names = {"_estimate_output_tokens", "_requested_output_tokens", "_is_input_only_route", "_to_int", "_apply_over_budget_reservation_policy"}
        nodes = [n for n in tree.body if getattr(n, "name", None) in names or isinstance(n, ast.AnnAssign)
                 and getattr(n.target, "id", None) in ("DEFAULT_MAX_OUTPUT_TOKENS_FALLBACK", "_OUTPUT_TOKEN_FIELDS")]
        class Denied(Exception): pass
        def deny(**kwargs): raise Denied(kwargs)
        async def forbidden(**kwargs): raise AssertionError("strict native branch must not resize")
        ns = {"_key_reservation_should_release_for_throttle": lambda *a: False,
              "_raise_counter_budget_exceeded": deny, "_resize_applied_reservation": forbidden,
              "Mapping": Mapping, "SupportsIndex": SupportsIndex, "SupportsInt": SupportsInt}
        execute(nodes, ns)
        estimate = ns["_estimate_output_tokens"]
        self.assertEqual(estimate({"max_tokens": 44}, "/v1/chat/completions", {"max_output_tokens": 5}), 5)
        self.assertEqual(estimate(P.LONG_BODY, "/v1/chat/completions", {"max_output_tokens": 5}), 5)
        with self.assertRaises(Denied) as caught:
            asyncio.run(ns["_apply_over_budget_reservation_policy"](SimpleNamespace(counter_key="key", max_budget=.4),
                None, {}, [], .98, 1.18, True))
        self.assertAlmostEqual(caught.exception.args[0]["current_cost"], .2)
        self.assertEqual(caught.exception.args[0]["estimated_cost"], .98)

    def test_actual_auth_orders_common_checks_before_reservation_and_scalar_job_only_invalidates_counter(self):
        tree = ast.parse(native_bytes("proxy/auth/user_api_key_auth.py"))
        owner = next(n for n in tree.body if getattr(n, "name", None) == "_run_centralized_common_checks")
        common = [n.lineno for n in ast.walk(owner) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "common_checks"]
        reserve = [n.lineno for n in ast.walk(owner) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "_reserve_budget_after_common_checks"]
        self.assertLess(max(common), min(reserve))
        job = ast.parse(native_bytes("proxy/common_utils/reset_budget_job.py"))
        cls = next(n for n in job.body if isinstance(n, ast.ClassDef) and n.name == "ResetBudgetJob")
        invalidator = next(n for n in cls.body if getattr(n, "name", None) == "_invalidate_spend_counter")
        text = ast.unparse(invalidator)
        self.assertNotIn("spend_db_floor", text)
        self.assertNotIn("broadcast", text)
        self.assertIn("async_delete_cache(key=counter_key)", text)
        coordinator = ast.parse(Path(P.__file__).read_text(encoding="utf-8"))
        calls = [n for n in ast.walk(coordinator) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                 and isinstance(n.func.value, ast.Name) and n.func.value.id == "patch" and n.func.attr == "object"]
        self.assertEqual(len(calls), 2)
        self.assertEqual({n.args[0].id for n in calls}, {"jobs", "tz"})
        self.assertTrue(all(n.args[1].value == "datetime" for n in calls))

    def test_accepted_overlap_actual_source_and_retained_R_binding(self):
        self.assertEqual(hashlib.sha256((HERE / "prove_budget_overlap.py").read_bytes()).hexdigest(), P.HELPERS["prove_budget_overlap.py"])
        self.assertEqual(P.LONG_BODY["max_tokens"], 5)
        self.assertEqual(P.LONG_BODY["messages"][0]["content"], "Hi. Please read this bounded synthetic fixture sentence. " * 8)
        artifact = HERE.parents[1] / "local/goal584/runtime-proof-41660087821/receipts/overlap/overlap.safe.json"
        if artifact.exists():
            receipt = json.loads(artifact.read_text())
            self.assertEqual(receipt["topology"]["source_sha256"]["prove_budget_overlap.py"], P.HELPERS["prove_budget_overlap.py"])
            self.assertEqual(receipt["calibration"]["native_estimates"][P.MODEL], "0.98")

    def test_new_coordinator_only_reuses_readonly_sql_and_no_cache_mutation_or_alternate_reset(self):
        tree = ast.parse(Path(P.__file__).read_text(encoding="utf-8"))
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]
        forbidden = {"execute_raw", "execute_raw_unsafe", "async_delete_cache", "delete_cache", "set_cache",
                     "async_set_cache", "async_set_max", "load_config", "reset_spend"}
        self.assertFalse(any(isinstance(n.func, ast.Attribute) and n.func.attr in forbidden for n in calls))
        queries = [n for n in calls if isinstance(n.func, ast.Attribute) and n.func.attr == "query_raw"]
        self.assertEqual(len(queries), 2)
        self.assertEqual({ast.unparse(n.args[0]) for n in queries}, {"calendar.COUNTS_SQL", "calendar.ROWS_SQL"})
        resets = [n for n in calls if isinstance(n.func, ast.Attribute) and n.func.attr == "reset_budget"]
        self.assertEqual(len(resets), 1)
        http = [n for n in calls if isinstance(n.func, ast.Name) and n.func.id == "request_call"]
        self.assertEqual([n.args[3].value for n in http], ["old", "prime", "post", "final"])

    def test_actual_finally_closes_redis_after_db_failure_and_does_not_claim_closed(self):
        tree = ast.parse(Path(P.__file__).read_text(encoding="utf-8"))
        qualify = next(n for n in tree.body if getattr(n, "name", None) == "qualify")
        owner = next(n for n in qualify.body if isinstance(n, ast.Try))
        for fail_db in (False, True):
            seen, receipt = [], {}
            async def disconnect_db():
                seen.append("db")
                if fail_db: raise RuntimeError("boundary failure")
            async def disconnect_redis(): seen.append("redis")
            ns = {"ps": SimpleNamespace(prisma_client=object()), "db": SimpleNamespace(disconnect=disconnect_db),
                  "redis": SimpleNamespace(disconnect=disconnect_redis), "receipt": receipt}
            cleanup = ast.AsyncFunctionDef(name="cleanup", args=ast.arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]),
                                           body=owner.finalbody, decorator_list=[])
            execute([cleanup], ns)
            if fail_db:
                with self.assertRaises(RuntimeError): asyncio.run(ns["cleanup"]())
            else: asyncio.run(ns["cleanup"]())
            self.assertEqual(seen, ["db", "redis"])
            self.assertIsNone(ns["ps"].prisma_client)
            self.assertEqual(receipt["helper_resources_closed"], not fail_db)


class FinancialBoundaryTests(unittest.TestCase):
    def test_actual_async_population_whole_scan_restarts_for_own_audit_append_then_returns_all_rows(self):
        raw, expected, counts, uid, key_hash, _ = packet(2)
        failure, state = denial_packet(raw)
        appended = {**copy.deepcopy(raw), "journal": copy.deepcopy(raw["journal"]) + [failure]}
        class DB:
            def __init__(self): self.writer_db = self; self.queries = []
            async def query_raw(self, sql):
                self.queries.append(sql)
                if sql == P.calendar.COUNTS_SQL:
                    observed = {**counts, "LiteLLM_SpendLogs": 2 if len(self.queries) == 1 else 3}
                    return [{"name": n, "n": v} for n, v in observed.items()]
                self.assert_rows_sql(sql)
                return [{"payload": copy.deepcopy(appended)}]
            def assert_rows_sql(self, sql):
                if sql != P.calendar.ROWS_SQL: raise AssertionError("unknown query")
        db = DB()
        result = asyncio.run(P.read_population(db, uid, key_hash))
        self.assertEqual(db.queries, [P.calendar.COUNTS_SQL, P.calendar.ROWS_SQL] * 2)
        self.assertEqual(result["journal"], sorted(appended["journal"], key=lambda r: r["request_id"]))
        P.journal(result, expected, uid, key_hash, denials=P.denial_attempts(state), terminal=True)

    def test_population_retry_rejects_foreign_shrink_rewrite_schema_and_exhausted_incoherence(self):
        raw, expected, counts, uid, key_hash, _ = packet(2)
        failure, state = denial_packet(raw)
        appended = {**copy.deepcopy(raw), "journal": copy.deepcopy(raw["journal"]) + [failure]}
        class DB:
            def __init__(self, scans): self.writer_db = self; self.scans = scans; self.calls = 0
            async def query_raw(self, sql):
                index = self.calls // 2; self.calls += 1
                c, s = self.scans[min(index, len(self.scans) - 1)]
                if sql == P.calendar.COUNTS_SQL: return [{"name": n, "n": v} for n, v in c.items()]
                if sql != P.calendar.ROWS_SQL: raise AssertionError("unknown query")
                if isinstance(s, Exception): raise s
                return [{"payload": copy.deepcopy(s)}]
        race = ({**counts, "LiteLLM_SpendLogs": 2}, appended)
        changed = copy.deepcopy(appended); changed["journal"][0]["arbitrary_historical_column"]["keep"] = False
        foreign = copy.deepcopy(appended); foreign["journal"][-1]["user"] = str(uuid4())
        wrong_user = copy.deepcopy(appended); wrong_user["users"].append(copy.deepcopy(wrong_user["users"][0]))
        duplicate = copy.deepcopy(appended); duplicate["journal"][-1]["request_id"] = duplicate["journal"][0]["request_id"]
        malformed = copy.deepcopy(appended); malformed["journal"][-1]["request_id"] = None
        cases = [([race] * 3, 6, "population_append_unsettled"),
            ([race, (counts, raw)], 4, "historical_row_drift"),
            ([race, ({**counts, "LiteLLM_SpendLogs": 3}, changed)], 4, "historical_row_drift"),
            ([({**counts, "LiteLLM_TeamTable": 1}, appended)], 1, "preload_population_guard"),
            ([({**counts, "LiteLLM_SpendLogs": True}, appended)], 1, "preload_population_guard"),
            ([(counts, foreign)], 2, "foreign_journal"),
            ([(counts, wrong_user)], 2, "population_row_counts"),
            ([(counts, duplicate)], 2, "journal_identity"),
            ([(counts, malformed)], 2, "journal_identity"),
            ([({**counts, "LiteLLM_SpendLogs": 3}, raw)], 2, "population_row_counts"),
            ([(counts, {"journal": []})], 2, "population_shape")]
        for scans, calls, leaf in cases:
            with self.subTest(leaf=leaf, calls=calls):
                db = DB(scans)
                with self.assertRaises(P.FloorError) as caught: asyncio.run(P.read_population(db, uid, key_hash))
                self.assertEqual((db.calls, caught.exception.leaf), (calls, leaf))
        db = DB([(counts, RuntimeError("database unavailable"))])
        with self.assertRaises(RuntimeError): asyncio.run(P.read_population(db, uid, key_hash))
        self.assertEqual(db.calls, 2)
        # Scanner validation is not a denial join: unknown own rows still fail
        # the unchanged strict caller journal boundary after a consistent read.
        unknown = copy.deepcopy(appended)
        unknown["journal"][-1]["metadata"]["spend_logs_metadata"]["root_answer_id"] = "unknown"
        db = DB([({**counts, "LiteLLM_SpendLogs": 3}, unknown)])
        result = asyncio.run(P.read_population(db, uid, key_hash))
        with self.assertRaises(P.FloorError):
            P.journal(result, expected, uid, key_hash, denials=P.denial_attempts(state), terminal=True)

    def test_four_raw_rows_account_for_all_successes_and_exact_recorded_denials(self):
        for count, labels in ((3, ("prime",)), (2, ("prime", "final"))):
            with self.subTest(count=count):
                raw, expected, counts, uid, key_hash, boundary = packet(count, P.CAP if count == 3 else P.COST)
                state = {}
                for label in labels:
                    row, state = denial_packet(raw, label, state)
                    raw["journal"].append(row)
                denials = P.denial_attempts(state)
                counts["LiteLLM_SpendLogs"] = 4
                P.population(counts, raw, uid, key_hash)
                audited = P.journal(raw, expected, uid, key_hash, denials=denials, terminal=True)
                self.assertEqual((len(audited["success_ids"]), len(audited["denial_roots"])), (count, len(labels)))
                P.money(raw, P.CAP if count == 3 else P.COST, count * P.COST, boundary, count)
                receipt = {}
                with patch.object(P, "private_save"):
                    P.retain_observation("final", raw, [.4, .4], {"requests": [None] * count}, expected, state, receipt, Path("unused"))
                safe = receipt["last_observation"]
                self.assertEqual(safe["native_snapshot"], P.calendar.public_snapshot(raw))
                self.assertEqual((safe["journal_count"], safe["expected_success_count"], safe["expected_denial_count"]), (4, count, len(labels)))
                self.assertEqual([r["denial_label"] for r in safe["rows"][count:]], list(labels))
                self.assertTrue(all(r["is_recorded_denial_lineage"] and r["is_native_budget_error"] for r in safe["rows"][count:]))
                self.assertNotIn("private native detail", json.dumps(safe))
                self.assertNotIn("spend_logs_metadata", json.dumps(safe))
                pending = {**raw, "journal": raw["journal"][:-1]}
                P.journal(pending, expected, uid, key_hash, denials=denials)
                with self.assertRaises(P.FloorError):
                    P.journal(pending, expected, uid, key_hash, denials=denials, terminal=True)

    def test_failure_zero_requires_exact_lineage_identity_error_type_usage_and_unique_audit(self):
        raw, expected, _, uid, key_hash, _ = packet(2)
        failure, state = denial_packet(raw)
        denials = P.denial_attempts(state)
        mutations = [lambda r: r.update(user=str(uuid4())), lambda r: r.update(api_key="b" * 64),
            lambda r: r.update(model_group="goal584-b"), lambda r: r.update(model_group=""),
            lambda r: r.update(model_id="other"), lambda r: r.update(status="success"),
            lambda r: r.update(spend=.000000001), lambda r: r.update(prompt_tokens=1), lambda r: r.update(total_tokens=False),
            lambda r: r.update(request_id="None"), lambda r: r.update(request_id=next(iter(expected))),
            lambda r: r.update(metadata={}), lambda r: r.update(metadata="malformed"),
            lambda r: r["metadata"]["spend_logs_metadata"].update(root_answer_id="unrecorded"),
            lambda r: r["metadata"]["spend_logs_metadata"].update(chat_id="foreign"),
            lambda r: r["metadata"]["spend_logs_metadata"].update(call_kind="other"),
            lambda r: r["metadata"]["error_information"].update(error_class="AuthenticationError"),
            lambda r: r["metadata"]["error_information"].update(error_code="403")]
        for index, mutate in enumerate(mutations):
            with self.subTest(mutation=index):
                changed = copy.deepcopy(failure); mutate(changed)
                with self.assertRaises(P.ProofError):
                    P.journal({**raw, "journal": raw["journal"] + [changed]}, expected, uid, key_hash, denials=denials)
        for same_id in (True, False):
            extra = copy.deepcopy(failure)
            if not same_id: extra["request_id"] = str(uuid4())
            # Stay inside the global four-attempt bound: only one observed success,
            # so the row count itself does not hide duplicate-ID/root validation.
            two_denials = {**denials, "pending": {"lineage": {}, "label": "final"}}
            with self.assertRaises(P.ProofError):
                P.journal({**raw, "journal": raw["journal"][:1] + [failure, extra]}, expected, uid, key_hash,
                    complete=False, denials=two_denials)
        with self.assertRaises(P.ProofError):
            P.journal({**raw, "journal": raw["journal"] + [failure]}, expected, uid, key_hash)

    def test_denial_binding_requires_validated_original_http_and_rejects_missing_or_malformed_evidence(self):
        raw, expected, _, uid, key_hash, _ = packet()
        failure, state = denial_packet(raw)
        for mutate in (lambda s: s["http"]["prime"].update(response={"error": {"type": "other"}}),
                       lambda s: s["http"]["prime"].update(status=403),
                       lambda s: s["http"]["prime"]["body"].update(model="goal584-b"),
                       lambda s: s["http"]["prime"]["body"]["metadata"].update(session_id="foreign"),
                       lambda s: s["http"].update(prime=None)):
            changed = copy.deepcopy(state); mutate(changed)
            with self.assertRaises(P.ProofError): P.denial_attempts(changed)
        state["http"]["prime"].pop("validated_budget_denial")
        self.assertEqual(P.denial_attempts(state), {})
        with self.assertRaises(P.ProofError):
            P.journal({**raw, "journal": raw["journal"] + [failure]}, expected, uid, key_hash, denials=P.denial_attempts(state))

    def test_delayed_known_failure_append_preserves_history_and_native_reset_policy(self):
        before, expected, _, uid, key_hash, boundary = packet()
        failure, state = denial_packet(before)
        after = copy.deepcopy(before); after["journal"].append(failure)
        later = boundary + timedelta(days=31)
        for row in after["users"] + after["keys"]: row.update(spend=0, budget_reset_at=later.isoformat())
        P.reset_transition(before, after, later, expected, P.denial_attempts(state), uid, key_hash)
        for mutate in (lambda s: s["journal"][0]["arbitrary_historical_column"].update(keep=False),
                       lambda s: s["keys"][0].update(total_spend=0),
                       lambda s: s["journal"][-1]["metadata"]["spend_logs_metadata"].update(root_answer_id="foreign")):
            changed = copy.deepcopy(after); mutate(changed)
            with self.assertRaises(P.ProofError):
                P.reset_transition(before, changed, later, expected, P.denial_attempts(state), uid, key_hash)
        P.journal(before, expected, uid, key_hash, denials=P.denial_attempts(state))  # pending allowed before final
        with self.assertRaises(P.FloorError) as caught:
            P.journal(before, expected, uid, key_hash, denials=P.denial_attempts(state), terminal=True)
        self.assertEqual(caught.exception.leaf, "missing_denial_audit_rows")

        P.journal(after, expected, uid, key_hash, denials=P.denial_attempts(state), terminal=True)
        changed = copy.deepcopy(after)
        changed["journal"][-1]["metadata"]["private_unknown_native_field"] = "changed"
        with self.assertRaises(P.FloorError): P.unchanged_identity(after, changed)

    def test_final_observe_waits_for_known_audit_without_waiting_for_it_in_critical_phase(self):
        raw, expected, _, uid, key_hash, boundary = packet(2)
        failure, state = denial_packet(raw)
        appended = {**copy.deepcopy(raw), "journal": copy.deepcopy(raw["journal"]) + [failure]}
        physical = {"requests": [{"id": rid, "body": {"model": "goal584-fake-a", **{k: v for k, v in item["semantic"].items() if k != "stream"}},
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            "lifecycle": {"terminal": True, "outcome": "completed"}} for rid, item in expected.items()]}
        observe = next(n for n in ast.walk(ast.parse(Path(P.__file__).read_text(encoding="utf-8"))) if isinstance(n, ast.AsyncFunctionDef) and n.name == "observe")
        for label, packets, expected_reads in (("primed", [raw], 1), ("final", [raw, appended], 2)):
            observations = []
            async def read(*args):
                observations.append(1)
                return copy.deepcopy(packets[min(len(observations) - 1, len(packets) - 1)])
            async def counters(): return [.4, .4]
            current_state, receipt = {**copy.deepcopy(state), "snapshots": {}}, {}
            ns = {**vars(P), "read_population": read, "provider": lambda _: physical, "counters": counters,
                "expected": expected, "state": current_state, "receipt": receipt, "args": SimpleNamespace(private_state=Path("unused")),
                "db": None, "local": None, "payer": uid, "key_hash": key_hash, "initial": raw, "prime_start": None,
                "private_save": lambda *a: None}
            execute([observe], ns)
            with patch.object(P, "private_save"):
                final, _ = asyncio.run(ns["observe"](label, P.COST, 2 * P.COST, boundary, 2, settled=label == "final"))
            self.assertEqual(len(observations), expected_reads)
            self.assertEqual(len(final["journal"]), 3 if label == "final" else 2)

        # Terminal60s expiry cannot certify a known denial with its audit missing.
        ns["state"] = {**copy.deepcopy(state), "snapshots": {}}
        ns["time"] = SimpleNamespace(monotonic=iter((0, 61)).__next__)
        packets = [raw]
        execute([observe], ns)
        with patch.object(P, "private_save"), self.assertRaises(P.FloorError) as caught:
            asyncio.run(ns["observe"]("final", P.COST, 2 * P.COST, boundary, 2, settled=True))
        self.assertEqual(caught.exception.leaf, "missing_denial_audit_rows")

        # A complete final read at/after60s must fail after preserving its actual
        # private observation, even though money, counters and audit are ready.
        for elapsed in (59, 60, 61):
            packets = [appended]
            ns["state"] = {**copy.deepcopy(state), "snapshots": {}}
            ns["receipt"] = {}
            ns["time"] = SimpleNamespace(monotonic=iter((0, elapsed)).__next__)
            execute([observe], ns)
            with patch.object(P, "private_save"):
                if elapsed < 60:
                    final, _ = asyncio.run(ns["observe"]("final", P.COST, 2 * P.COST, boundary, 2, settled=True))
                    self.assertEqual(len(final["journal"]), 3)
                else:
                    with self.assertRaises(P.FloorError) as caught:
                        asyncio.run(ns["observe"]("final", P.COST, 2 * P.COST, boundary, 2, settled=True))
                    self.assertEqual(caught.exception.leaf, "native_settlement")
                    self.assertNotIn("final", ns["state"]["snapshots"])
            self.assertEqual(ns["receipt"]["last_observation"]["journal_count"], 3)

    def test_actual_observe_retains_all_three_rows_before_preserving_two_call_failure(self):
        raw, all_expected, counts, uid, key_hash, boundary = packet(3)
        expected = dict(list(all_expected.items())[:2])
        secret = "sk-" + "private-diagnostic-fixture" * 3
        raw["journal"][-1].update(status="failure", spend=0, prompt_tokens=0, completion_tokens=0,
            total_tokens=0, request_id=secret, metadata={"private_body": secret})
        P.population(counts, raw, uid, key_hash)
        provider = {"requests": [{"body": {"private_body": secret}}, {"body": {"private_body": secret}}]}
        async def read(*args): return copy.deepcopy(raw)
        async def counters(): return [.4, .4]
        observe = next(n for n in ast.walk(ast.parse(Path(P.__file__).read_text(encoding="utf-8")))
            if isinstance(n, ast.AsyncFunctionDef) and n.name == "observe")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "observation.private.json"
            state, receipt = {}, {}
            ns = {**vars(P), "read_population": read, "provider": lambda _: provider,
                "counters": counters, "expected": expected, "state": state, "receipt": receipt,
                "args": SimpleNamespace(private_state=path), "db": None, "local": None,
                "payer": uid, "key_hash": key_hash, "initial": raw, "prime_start": None}
            execute([observe], ns)
            # This Windows test uses real atomic writes; Linux POSIX mode guards
            # remain owned by the existing private-I/O tests/native runtime.
            with patch("prove_gateway_auth.private_parent"), self.assertRaises(P.FloorError) as caught:
                asyncio.run(ns["observe"]("post", P.COST, 2 * P.COST, boundary, 2, settled=True))
            self.assertEqual(caught.exception.leaf, "unexpected_journal_rows")
            actual = receipt["last_observation"]
            self.assertEqual((actual["journal_count"], actual["expected_success_count"], actual["provider_count"]), (3, 2, 2))
            self.assertEqual(actual["redis_key_user"], ["0.4", "0.4"])
            self.assertEqual([r["is_expected_success_id"] for r in actual["rows"]], [True, True, False])
            self.assertEqual((actual["rows"][-1]["status"], actual["rows"][-1]["spend_usd"]), ("failure", "0"))
            self.assertEqual(actual["rows"][-1]["request_id_sha256"], P.digest(secret))
            self.assertEqual(actual["rows"][-1]["full_row_sha256"], P.digest(raw["journal"][-1]))
            self.assertTrue(actual["private_raw_retained"])
            retained = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(retained["last_observation"]["snapshot"], raw)
            self.assertEqual(retained["last_observation"]["provider"], provider)
            self.assertNotIn(secret, P.safe_receipt(receipt, [secret]))
            self.assertNotIn("metadata", json.dumps(actual))

    def test_boundary_diagnostics_io_failure_cannot_replace_original_leaf_or_leak(self):
        raw, all_expected, _, uid, key_hash, boundary = packet(3)
        expected = dict(list(all_expected.items())[:2])
        secret = "sk-" + "untrusted-private-error" * 3
        async def read(*args): return copy.deepcopy(raw)
        async def bad_counters(): raise RuntimeError(secret)
        def bad_provider(_): raise RuntimeError(secret)
        observe = next(n for n in ast.walk(ast.parse(Path(P.__file__).read_text(encoding="utf-8")))
            if isinstance(n, ast.AsyncFunctionDef) and n.name == "observe")
        receipt = {}
        ns = {**vars(P), "read_population": read, "provider": bad_provider, "counters": bad_counters,
            "expected": expected, "state": {}, "receipt": receipt,
            "args": SimpleNamespace(private_state=Path("unused")), "db": None, "local": None,
            "payer": uid, "key_hash": key_hash, "initial": raw, "prime_start": None}
        execute([observe], ns)
        with patch.object(P, "private_save", side_effect=OSError(secret)):
            with self.assertRaises(P.FloorError) as caught:
                asyncio.run(ns["observe"]("post", P.COST, 2 * P.COST, boundary, 2, settled=True))
        self.assertEqual(caught.exception.leaf, "unexpected_journal_rows")
        actual = receipt["last_observation"]
        self.assertEqual(actual["journal_count"], 3)
        self.assertIsNone(actual["redis_key_user"])
        self.assertIsNone(actual["provider_count"])
        self.assertEqual(actual["capture_failures"], ["initial_private_retention_failed", "counter_read_failed", "provider_read_failed"])
        self.assertFalse(actual["private_raw_retained"])
        self.assertTrue(receipt["boundary_observation_capture_failed"])
        self.assertNotIn(secret, P.safe_receipt(receipt, [secret]))

    def test_whole_raw_rows_and_exact_counts_accept_three_and_reject_foreign_zero_duplicate_missing(self):
        raw, expected, counts, uid, key_hash, boundary = packet(3, P.CAP)
        P.population(counts, raw, uid, key_hash)
        P.journal(raw, expected, uid, key_hash)
        P.money(raw, P.CAP, 3 * P.COST, boundary, 3)
        for mutate in (lambda r: r["journal"][0].update(user=str(uuid4())),
                       lambda r: r["keys"][0].update(token="b" * 64),
                       lambda r: r["keys"][0].update(models=["goal584-b"]),
                       lambda r: r["users"][0].update(user_role="proxy_admin"),
                       lambda r: r["keys"][0].update(metadata={"throttle_on_budget_exceeded": True})):
            changed = copy.deepcopy(raw); mutate(changed)
            with self.assertRaises(P.ProofError): P.population(counts, changed, uid, key_hash)
        for mutate in (lambda r: r["journal"][0].update(spend=0),
                       lambda r: r["journal"][0].update(request_id=r["journal"][1]["request_id"]),
                       lambda r: r["journal"][0].update(completion_tokens=6),
                       lambda r: r["journal"][0].update(model_group="goal584-b"),
                       lambda r: r["journal"].pop()):
            changed = copy.deepcopy(raw); mutate(changed)
            with self.assertRaises(P.ProofError): P.journal(changed, expected, uid, key_hash)
        changed = copy.deepcopy(raw); changed["journal"].append({"spend": 0})
        with self.assertRaises(P.ProofError): P.population({**counts, "LiteLLM_SpendLogs": 4}, changed, uid, key_hash)

    def test_no_foreign_budget_table_or_extra_row_silently_filtered(self):
        raw, _, counts, uid, key_hash, _ = packet()
        for table in P.calendar.OTHER_TABLES:
            with self.assertRaises(P.ProofError): P.population({**counts, table: 1}, raw, uid, key_hash)
        with self.assertRaises(P.ProofError): P.population({**counts, "LiteLLM_UserTable": True}, raw, uid, key_hash)
        class DB:
            def __init__(self): self.writer_db = self; self.calls = 0
            async def query_raw(self, sql):
                self.calls += 1
                return [{"name": name, "n": value} for name, value in {**counts, "LiteLLM_TeamTable": 1}.items()]
        db = DB()
        with self.assertRaises(P.ProofError): asyncio.run(P.read_population(db, uid, key_hash))
        self.assertEqual(db.calls, 1)  # fail before full raw rows are loaded

    def test_full_historical_unknown_column_and_identity_drift_fail_even_if_hash_recomputed(self):
        before, _, _, _, _, _ = packet()
        after, _, _, _, _, _ = packet(2)
        P.unchanged_identity(before, after)
        after["journal"][0]["arbitrary_historical_column"]["keep"] = False
        self.assertNotEqual(P.digest(before["journal"]), P.digest(after["journal"]))
        with self.assertRaises(P.ProofError): P.unchanged_identity(before, after)
        after = copy.deepcopy(before); after["keys"][0]["max_budget"] = .5
        with self.assertRaises(P.ProofError): P.unchanged_identity(before, after)

    def test_only_complete_healthy_or_exact_defect_pattern_classified(self):
        self.assertEqual(P.outcome([.2, .2], 200, [.4, .4]), "PASS_SELECTED_PROFILE")
        self.assertEqual(P.outcome([.4, .4], 422, [.4, .4]), "FAIL_STALE_POSITIVE_FLOOR")
        for first, status, last in (([.2, .4], 422, [.4, .4]), ([.4, .4], 200, [.4, .4]),
                                    ([.2, .2], 500, [.4, .4]), ([.2], 200, [.4, .4]), ([float("nan"), .2], 200, [.4, .4])):
            with self.assertRaises(P.ProofError): P.outcome(first, status, last)

    def test_five_second_real_epoch_and_monotonic_bound_not_sixty_or_ttl_wait(self):
        start = {"epoch": 100, "monotonic": 50}
        valid = P.window(start, {"epoch": 104.99, "monotonic": 54.99})
        self.assertFalse(valid["marker_epoch_directly_observed"])
        for end in ({"epoch": 105, "monotonic": 55}, {"epoch": 104, "monotonic": 56},
                    {"epoch": 106, "monotonic": 54}, {"epoch": 99, "monotonic": 51},
                    {"epoch": 102, "monotonic": 51}, {"epoch": float("nan"), "monotonic": 51}):
            with self.assertRaises(P.ProofError): P.window(start, end)

    def test_provider_whole_wire_context_usage_and_physical_id_mutations(self):
        _, expected, _, _, _, _ = packet()
        rid = next(iter(expected))
        row = {"id": rid, "body": {"model": "goal584-fake-a", "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 5},
               "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
               "lifecycle": {"terminal": True, "outcome": "completed"}}
        P.provider_evidence({"requests": [row]}, expected)
        for mutate in (lambda r: r["body"].update(messages=[]), lambda r: r["body"].update(api_key="caller"),
                       lambda r: r.update(id="foreign"), lambda r: r["usage"].update(total_tokens=16),
                       lambda r: r["lifecycle"].update(terminal=False)):
            changed = copy.deepcopy(row); mutate(changed)
            with self.assertRaises(P.ProofError): P.provider_evidence({"requests": [changed]}, expected)


class TransportAndEvidenceTests(unittest.TestCase):
    def test_actual_helpers_in_mounted_layout_bind_and_changed_producer_bytes_fail(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)
            for name in P.HELPERS:
                source = HERE / name
                if not source.is_file():
                    source = HERE.parents[1] / "deploy/openwebui-budgets" / {"employee_budget_assignment.py": "assignment.py"}.get(name, name)
                (target / name).write_bytes(source.read_bytes())
            mounted = target / "prove_calendar_floor.py"
            mounted.write_bytes(Path(P.__file__).read_bytes())
            with patch.object(P, "__file__", str(mounted)):
                files = P.source_files()
                self.assertEqual(len(files), 8)
                producer = target / "prove_budget_overlap.py"
                producer.write_bytes(producer.read_bytes().replace(b"max_tokens': 5", b"max_tokens': 44", 1))
                with self.assertRaises(P.ProofError): P.source_files()

    def test_two_actual_parent_attested_worker_bindings_reject_wrong_peer_source_and_extra_fields(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            config_path = root / "config.yaml"; config_path.write_text("private config")
            config_sha = hashlib.sha256(config_path.read_bytes()).hexdigest()
            project = "goal584-calendar-" + "b" * 12
            files = {"actual-producer": "c" * 64}
            workers = [{"id": str(i) * 64, "number": str(i), "image_ref": P.IMAGE, "image_id": "sha256:" + "d" * 64,
                "health": "healthy", "command": P.COMMAND, "project": project, "service": "proxy", "network_mode": project + "_proof",
                "private_mount": "/host/private", "config_sha256": config_sha, "files_sha256": files,
                "native_sha256": P.NATIVE_HASHES, "ipv4": "172.18.0." + str(i + 2)} for i in (1, 2)]
            attest = {"schema": 1, "project": project, "proxy_container_id": workers[1]["id"], "postgres_container_id": "3" * 64,
                "redis_container_id": "4" * 64, "redis_run_id": "a" * 40, "private_mount": "/host/private", "workers": workers}
            config = {"general_settings": {"database_url": "postgresql://goal584:synthetic@postgres:5432/goal584_calendar",
                "disable_reset_budget": True, "coordination_redis": {"host": "redis", "port": 6379}, "fail_closed_budget_enforcement": True},
                "litellm_settings": {"timezone": "Europe/Moscow", "budget_reset_time": "00:00", "num_retries": 0,
                    "callbacks": ["budget_errors.handler", "pricing_snapshot.handler"]},
                "model_list": [{"model_name": "goal584-" + m,
                    "litellm_params": {"model": "openai/goal584-fake-" + m, "api_base": "http://provider:8000/v1"},
                    "model_info": {"id": "goal584-deployment-" + m, "mode": "chat", "max_output_tokens": 5, "max_input_tokens": 10,
                        "max_tokens": 15, "input_cost_per_token": .01, "output_cost_per_token": .02}} for m in ("a", "b")]}
            args = SimpleNamespace(project=project, private_state=root / "state", peer_url="http://172.18.0.3:4000")
            env = {"PROOF_CALENDAR_PROJECT": project, "HOSTNAME": workers[1]["id"][:12], "DATABASE_URL": config["general_settings"]["database_url"]}
            real_path = Path
            with patch.object(P, "Path", side_effect=lambda value: config_path if value == "/proof/config.yaml" else real_path(value)):
                safe = P.topology(args, attest, config, files, P.NATIVE_HASHES, env)
                self.assertNotIn("private_mount", safe["workers"][0])
                for mutate in (lambda a: a["workers"][0].update(id=a["workers"][1]["id"]),
                               lambda a: a["workers"][0].update(config_sha256="0" * 64),
                               lambda a: a["workers"][0].update(native_sha256={}),
                               lambda a: a["workers"][0].update(files_sha256={}),
                               lambda a: a["workers"][0].update(ipv4="8.8.8.8"),
                               lambda a: a["workers"][0].update(caller_secret="unregistered-private-value")):
                    changed = copy.deepcopy(attest); mutate(changed)
                    with self.assertRaises(P.ProofError): P.topology(args, changed, config, files, P.NATIVE_HASHES, env)
                with self.assertRaises(P.ProofError):
                    P.topology(SimpleNamespace(**{**vars(args), "peer_url": "http://172.18.0.9:4000"}), attest, config, files, P.NATIVE_HASHES, env)

    def test_native_http_request_leaf_actual_socket_preserves_body_usage_cost_and_no_fake_persisted(self):
        observed = []
        rid = "chatcmpl-goal584-" + "c" * 32
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_POST(self):
                observed.append((self.path, self.headers["Authorization"], json.loads(self.rfile.read(int(self.headers["Content-Length"])))))
                raw = json.dumps({"id": rid, "choices": [{"message": {"role": "assistant", "content": "Proof", "tool_calls": None}, "finish_reason": "stop"}],
                                  "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15, "prompt_tokens_details": None}}).encode()
                self.send_response(200); self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw))); self.send_header("x-litellm-response-cost", ".20")
                self.end_headers(); self.wfile.write(raw)
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            native = P.NativeProof("http://127.0.0.1:" + str(server.server_port), "operator", 2, {})
            state, expected, receipt = {}, {}, {}
            with patch.object(P, "private_save"):
                result = P.request_call(native, "test-secret", "synthetic-owner", "old", expected, state, receipt, Path("unused"))
            self.assertEqual(result["request_id"], rid)
            self.assertEqual(observed[0][0:2], ("/v1/chat/completions", "Bearer test-secret"))
            self.assertEqual(observed[0][2]["messages"], [{"role": "user", "content": "Hi"}])
            self.assertEqual(observed[0][2]["metadata"]["spend_logs_metadata"]["root_answer_id"], expected[rid]["root"])
            self.assertEqual(result["usage"], {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})
            self.assertNotIn("test-secret", P.safe_receipt(receipt, ["test-secret"]))
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=2)
            self.assertFalse(thread.is_alive())

    def test_generic_transport_or_403_not_accepted_as_budget_denial(self):
        for status, response in ((403, {"error": {"type": "budget_exceeded"}}), (422, {"error": {"type": "transport_error"}})):
            native = SimpleNamespace(run_id="synthetic", request=lambda *a, **k: (status, response, {}))
            with patch.object(P, "private_save"), self.assertRaises(P.ProofError):
                P.request_call(native, "private-key", "own", "prime", {}, {}, {}, Path("unused"), long=True)

    def test_peer_address_cannot_escape_private_attested_port_shape(self):
        self.assertEqual(P.ProfileHTTP("master", "http://172.18.0.4:4000").base_url, "http://172.18.0.4:4000")
        for target in ("http://8.8.8.8:4000", "http://127.0.0.1:4000", "http://provider:4000", "https://172.18.0.4:4000",
                       "http://172.18.0.4:8000", "http://user:secret@172.18.0.4:4000", "http://172.18.0.4:4000/path"):
            with self.assertRaises(P.ProofError): P.ProfileHTTP("master", target)

    def test_private_paths_freshness_and_secret_registry(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            args = SimpleNamespace(attestation=root / "attest", private_state=root / "state", receipt=root / "receipt")
            with patch.object(P, "PRIVATE_ROOT", root):
                P.evidence_paths(args)
                args.private_state.write_text("already")
                with self.assertRaises(P.ProofError): P.evidence_paths(args)
                args.private_state.unlink(); args.receipt = root.parent / "outside"
                with self.assertRaises(P.ProofError): P.evidence_paths(args)
        for value, registry in (({"secret": "sk-" + "a" * 32}, []), ({"secret": "unshaped-private-value"}, ["unshaped-private-value"]),
                                ({"n": float("nan")}, [])):
            with self.assertRaises((P.ProofError, ValueError)): P.safe_receipt(value, registry)

    def test_safe_created_profile_saved_before_timestamp_decoder(self):
        raw, _, _, _, _, _ = packet(0, P.Decimal(0))
        raw["keys"][0].update(password="do-not-export", raw_key="sk-private-not-exported")
        safe = P.calendar.public_snapshot(raw)
        self.assertNotIn("do-not-export", json.dumps(safe))
        self.assertNotIn("sk-private-not-exported", json.dumps(safe))
        tree = ast.parse(Path(P.__file__).read_text(encoding="utf-8"))
        owner = next(n for n in tree.body if getattr(n, "name", None) == "qualify")
        created = [n.lineno for n in ast.walk(owner) if isinstance(n, ast.Assign) and any(
            isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant) and t.slice.value == "created_profile" for t in n.targets)]
        decode = [n.lineno for n in ast.walk(owner) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                  and isinstance(n.func.value, ast.Name) and n.func.value.id == "calendar" and n.func.attr == "timestamp"]
        self.assertLess(created[0], min(decode))

    def test_fixed_failed_phase_does_not_export_native_exception(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); output = io.StringIO(); saved = []
            async def fail(args, attest, receipt, secrets):
                receipt["phase"] = "native_due_reset"
                raise RuntimeError("native SQL contains private-secret-value")
            argv = ["proof", "--project", "goal584-calendar-" + "a" * 12, "--peer-url", "http://172.18.0.4:4000",
                    "--attestation", str(root / "attest"), "--private-state", str(root / "state"), "--receipt", str(root / "receipt")]
            with patch.object(P, "PRIVATE_ROOT", root), patch.object(P, "read_private", return_value={"schema": 1}), \
                 patch.object(P, "qualify", fail), patch.object(P, "write_private", side_effect=lambda p, s: saved.append(s)), \
                 patch.dict(os.environ, {"PROOF_MASTER_KEY": "sk-" + "b" * 32}), patch.object(sys, "argv", argv), redirect_stdout(output):
                self.assertEqual(P.main(), 1)
            receipt = json.loads(output.getvalue())
            self.assertEqual(receipt["failure_phase"], "native_due_reset")
            self.assertEqual(receipt["failure_leaf"], "native_exception")
            self.assertNotIn("private-secret-value", output.getvalue())
            self.assertEqual(saved, [receipt])

    def test_failed_freshness_guard_does_not_overwrite_previous_receipt(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); output = io.StringIO()
            receipt = root / "receipt"; receipt.write_text("retained-original")
            argv = ["proof", "--project", "goal584-calendar-" + "a" * 12, "--peer-url", "http://172.18.0.4:4000",
                    "--attestation", str(root / "attest"), "--private-state", str(root / "state"), "--receipt", str(receipt)]
            with patch.object(P, "PRIVATE_ROOT", root), patch.object(P, "write_private") as writer, \
                 patch.object(sys, "argv", argv), redirect_stdout(output):
                self.assertEqual(P.main(), 1)
            writer.assert_not_called()
            self.assertEqual(receipt.read_text(), "retained-original")
            self.assertEqual(json.loads(output.getvalue())["failure_leaf"], "fresh_evidence_paths")

    def test_mounted_import_has_no_repository_depth_dependency_and_no_noop_persisted(self):
        text = Path(P.__file__).read_text(encoding="utf-8")
        namespace = {"__name__": "mounted_proof_not_main", "__file__": "/proof/prove_calendar_floor.py"}
        exec(compile(text, namespace["__file__"], "exec"), namespace)
        self.assertEqual(namespace["PROOF"], P.PROOF)
        tree = ast.parse(text)
        self.assertFalse(any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "persisted" for n in ast.walk(tree)))


if __name__ == "__main__":
    unittest.main()
