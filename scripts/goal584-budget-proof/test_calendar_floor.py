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
from types import SimpleNamespace
from typing import SupportsIndex, SupportsInt
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
        journal.append({"request_id": rid, "user": uid, "api_key": key_hash, "model_group": P.MODEL,
                        "model_id": "goal584-deployment-a", "spend": .2, "prompt_tokens": 10, "completion_tokens": 5,
                        "total_tokens": 15, "metadata": {"spend_logs_metadata": {"root_answer_id": item["root"],
                            "chat_id": item["chat"], "call_kind": "synthetic_chat"}}, "arbitrary_historical_column": {"keep": True}})
    snapshot = {"users": [row], "keys": [key], "journal": journal}
    counts = {name: 0 for name in P.calendar.TABLES}
    counts.update(dict(zip(P.calendar.TABLES[:3], [1, 1, count])))
    return snapshot, expected, counts, uid, key_hash, boundary


class NativeOwnerTests(unittest.TestCase):
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
