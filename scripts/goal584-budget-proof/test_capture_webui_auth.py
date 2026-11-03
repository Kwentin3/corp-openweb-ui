"""Overlapping native-auth contexts and real cross-process private-file writes."""
import asyncio
import copy
import importlib.util
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import stat
import tempfile
import time
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4


SOURCE = Path(__file__).with_name("capture_webui_auth.py")
SPEC = importlib.util.spec_from_file_location("capture_concurrency_under_test", SOURCE)
C = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(C)
PROTOCOL_SPEC = importlib.util.spec_from_file_location("capture_rag_protocol_test",
    SOURCE.parents[2] / "deploy/openwebui-budgets/provenance.py")
PROTOCOL = importlib.util.module_from_spec(PROTOCOL_SPEC)
PROTOCOL_SPEC.loader.exec_module(PROTOCOL)


def file_writer(path, index, barrier, results):
    """Each spawned process imports the real owner and uses its real OS lock."""
    try:
        C.CAPTURE = Path(path)
        record = {"user_id": "worker-" + str(index), "body": {"worker": index}}
        C._append(record)
        barrier.wait(timeout=15)
        record.update(body_after_auth={"worker": index}, native_auth_user_id="native-" + str(index))
        C._finish(record)
        results.put({"index": index, "ok": True})
    except Exception as error:
        results.put({"index": index, "ok": False, "error_type": type(error).__name__})
        raise


def module(**values):
    result = ModuleType("native_capture_fixture")
    result.__dict__.update(values)
    return result


class CaptureContextsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.file = patch.object(C, "CAPTURE", Path(self.directory.name) / "context.private.json")
        self.file.start()
        self.addCleanup(self.file.stop)
        self.router = object()
        async def read_body(request):
            return request.data
        def estimate(body, route, router):
            self.assertIs(router, self.router)
            self.assertTrue(route == "/v1/chat/completions" or C.embedding_route(route))
            return .30
        def usage_patch(**kwargs):
            self.assertEqual(kwargs["route_type"], "acompletion")
            self.assertTrue(kwargs["supports_stream_options"]())
            return {"stream_options": {"include_usage": True}} if kwargs["data"].get("stream") else {}
        modules = {name: module() for name in ("litellm", "litellm.proxy", "litellm.proxy.auth",
            "litellm.proxy.common_utils", "litellm.proxy.spend_tracking")}
        modules.update({"litellm.proxy.auth.auth_utils": module(get_request_route=lambda request: request.route),
            "litellm.proxy.common_utils.http_parsing_utils": module(_read_request_body=read_body),
            "litellm.proxy.spend_tracking.budget_reservation": module(estimate_request_max_cost=estimate),
            "litellm.proxy.common_request_processing": module(_stream_usage_tracking_updates=usage_patch,
                _model_deployments_support_stream_options=lambda **kwargs: True)})
        modules["litellm.proxy"].proxy_server = SimpleNamespace(llm_router=self.router, general_settings={})
        self.native = patch.dict("sys.modules", modules)
        self.native.start()
        self.addCleanup(self.native.stop)

    def request(self, index):
        user, chat, answer, call = [str(uuid4()) for _ in range(4)]
        scope = {"schema": 1, "user_id": user, "chat_id": chat, "answer_id": answer,
                 "root_chat_id": chat, "root_answer_id": answer, "call_id": call,
                 "model": "goal584-a", "category": "personal"}
        body = {"model": "goal584-a", "messages": [{"role": "system", "content": "Full instruction " + str(index)},
                {"role": "user", "content": "Hi"}], "stream": True, "max_tokens": 5,
                "tools": [{"type": "function", "function": {"name": "native_fixture", "parameters": {
                    "type": "object", "properties": {"value": {"type": "string"}}, "required": ["value"]}}}],
                "litellm_metadata": {"owui_budget_provenance": "private-token-" + str(index)},
                "_observation_id": "caller-forged", "unrelated_native_value": {"preserve": index}}
        return SimpleNamespace(index=index, data=body, scope=scope, route="/v1/chat/completions",
            headers={"X-OpenWebUI-User-Id": user, "X-OpenWebUI-Task": ""})

    def read(self):
        with C.capture_lock():
            return C._read_locked()

    def embedding_request(self, index, route="/v1/embeddings"):
        return SimpleNamespace(index=index, route=route, headers={"X-OpenWebUI-User-Id": "caller-not-the-payer",
            "X-OpenWebUI-Task": ""}, data={"model": "goal584-e", "input": ["document: Hi\nline", "query: Hi"],
            "dimensions": 3, "encoding_format": "float", "user": "caller-end-user-diagnostic",
            "litellm_call_id": "caller-forged-call-id", "_observation_id": "caller-forged",
            "metadata": {"spend_logs_metadata": {"owui_budget": {"schema": 1, "category": "service",
                "operation": "rag_embedding"}}}, "litellm_metadata": {"owui_budget_provenance": "private-token"}})

    async def test_embedding_aliases_preserve_context_and_observe_only_safe_returned_native_identity(self):
        payer, key_hash = str(uuid4()), hashlib.sha256(b"fixture-native-key").hexdigest()
        returned = SimpleNamespace(user_id=payer, api_key=key_hash, team_id=None)
        calls = []
        async def auth(request, api_key):
            calls.append((request, api_key))
            # External native auth owner double; capture itself changes no body.
            request.data.pop("metadata")
            request.data.pop("litellm_metadata")
            return returned
        routes = ("/embeddings", "/v1/embeddings", "/engines/goal584-e/embeddings",
                  "/engines/nested/goal584-e/embeddings", "/openai/deployments/goal584-e/embeddings")
        with patch.object(C, "product_auth", return_value=auth), patch.object(C, "scope_validator") as validate:
            for index, route in enumerate(routes):
                request = self.embedding_request(index, route)
                original = copy.deepcopy(request.data)
                self.assertIs(await C.gateway_auth(request, "sk-private-native-key"), returned)
                row = self.read()["requests"][-1]
                expected = {field: original[field] for field in C.EMBEDDING_FIELDS if field in original}
                self.assertEqual(row["body"], expected)
                self.assertEqual(row["body_after_auth"], expected)
                self.assertEqual(row["route"], route)
                self.assertEqual(row["native_auth_user_id"], payer)
                self.assertEqual(row["native_auth_key_hash"], key_hash)
                self.assertNotIn("user_id", row)
                self.assertNotIn("actor_id", row)
                self.assertNotIn("task", row)
                self.assertNotIn("native_stream_usage_patch", row)
                self.assertNotIn("verified_cost_scope", row)
                self.assertNotIn("unverified_rag_scope", row)
                self.assertNotIn("litellm_call_id", row)
                self.assertEqual(request.data, {k: v for k, v in original.items() if k not in ("metadata", "litellm_metadata")})
            validate.assert_not_called()
        self.assertEqual(len(calls), len(routes))
        encoded = json.dumps(self.read())
        for private in ("private-token", "sk-private-native-key", "caller-forged-call-id", "caller-not-the-payer"):
            self.assertNotIn(private, encoded)

    async def test_embedding_postauth_tag_is_only_syntax_not_verified_origin(self):
        request = self.embedding_request(0)
        request.data.pop("litellm_metadata")
        returned = SimpleNamespace(user_id=str(uuid4()), api_key="a" * 64)
        async def auth(*args):
            return returned
        with patch.object(C, "product_auth", return_value=auth), patch.object(C, "scope_validator",
                side_effect=lambda category: PROTOCOL.validate_persisted_rag_scope if category == "rag" else self.fail(category)):
            self.assertIs(await C.gateway_auth(request, "native-secret"), returned)
        row = self.read()["requests"][0]
        self.assertEqual(row["unverified_rag_scope"], {"schema": 1, "category": "service", "operation": "rag_embedding"})
        self.assertNotIn("verified_cost_scope", row)
        self.assertNotIn("call_id", row)
        self.assertNotIn("chat_id", row)
        self.assertNotIn("actor_id", row)

    async def test_embedding_failure_keeps_original_exception_and_cannot_label_forged_scope_or_identity(self):
        request = self.embedding_request(0)
        class NativeFailure(Exception):
            status_code = 401
            detail = "private-native-detail"
        failure = NativeFailure("sk-private-error-body")
        calls = []
        async def auth(actual, api_key):
            calls.append((actual, api_key))
            raise failure
        with patch.object(C, "product_auth", return_value=auth), patch.object(C, "scope_validator") as validate:
            with self.assertRaises(NativeFailure) as caught:
                await C.gateway_auth(request, "sk-private-native-secret")
            validate.assert_not_called()
        self.assertIs(caught.exception, failure)
        self.assertEqual(len(calls), 1)
        row = self.read()["requests"][0]
        self.assertEqual(row["auth_failure"], {"scope": "custom_auth", "status_code": 401, "code": "unclassified"})
        for name in ("native_auth_user_id", "native_auth_key_hash", "verified_cost_scope", "unverified_rag_scope"):
            self.assertNotIn(name, row)
        self.assertNotIn("private-", json.dumps(row))

    async def test_embedding_overlapping_auth_records_merge_without_invented_identity_or_raw_key_leak(self):
        requests = [self.embedding_request(index) for index in range(4)]
        arrived, release, calls = asyncio.Event(), asyncio.Event(), []
        native = SimpleNamespace(user_id="not-a-native-uuid", api_key="sk-private-raw-key")
        async def auth(request, api_key):
            calls.append(request.index)
            if len(calls) == 4:
                arrived.set()
            await release.wait()
            request.data.pop("metadata")
            request.data.pop("litellm_metadata")
            return native
        with patch.object(C, "product_auth", return_value=auth):
            pending = [asyncio.create_task(C.gateway_auth(request, "native-secret")) for request in requests]
            await asyncio.wait_for(arrived.wait(), timeout=3)
            self.assertEqual(len(self.read()["requests"]), 4)
            self.assertTrue(all("body_after_auth" not in row for row in self.read()["requests"]))
            release.set()
            actual = await asyncio.wait_for(asyncio.gather(*pending), timeout=3)
        self.assertTrue(all(value is native for value in actual))
        records = self.read()["requests"]
        self.assertEqual(len({row["_observation_id"] for row in records}), 4)
        self.assertTrue(all(row["body"] == row["body_after_auth"] for row in records))
        self.assertTrue(all("native_auth_user_id" not in row and "native_auth_key_hash" not in row for row in records))
        self.assertNotIn("sk-private", json.dumps(records))

    async def test_wrong_embedding_route_or_model_does_not_expand_capture_or_native_authority(self):
        requests = [self.embedding_request(0, "/v1/embeddings/unregistered-child"), self.embedding_request(1)]
        requests[1].data["model"] = "goal584-a"
        native = object()
        calls = []
        async def auth(request, api_key):
            calls.append(request)
            return native
        with patch.object(C, "product_auth", return_value=auth):
            for request in requests:
                before = copy.deepcopy(request.data)
                self.assertIs(await C.gateway_auth(request, "native-secret"), native)
                self.assertEqual(request.data, before)
        self.assertEqual(calls, requests)
        self.assertFalse(C.CAPTURE.exists())

    async def test_eight_overlapping_auth_calls_preserve_all_initial_and_final_contexts(self):
        requests = [self.request(index) for index in range(8)]
        original = [copy.deepcopy(request.data) for request in requests]
        ready, release = asyncio.Event(), asyncio.Event()
        calls, returned = [], []
        async def auth(request, api_key):
            self.assertEqual(api_key, "native-secret-" + str(request.index))
            calls.append(request.index)
            if len(calls) == 8:
                ready.set()
            await release.wait()
            request.data["litellm_metadata"].pop("owui_budget_provenance")
            request.data["litellm_metadata"]["spend_logs_metadata"] = {"owui_budget": request.scope}
            result = SimpleNamespace(user_id=request.headers["X-OpenWebUI-User-Id"], team_id=None)
            returned.append(result)
            return result
        def validator(category):
            self.assertEqual(category, "personal")
            return lambda scope: copy.deepcopy(scope)
        with patch.object(C, "product_auth", return_value=auth), patch.object(C, "scope_validator", side_effect=validator):
            pending = [asyncio.create_task(C.gateway_auth(request, "native-secret-" + str(request.index))) for request in requests]
            await asyncio.wait_for(ready.wait(), timeout=3)
            started = self.read()["requests"]
            self.assertEqual(len(started), 8)
            self.assertTrue(all("body_after_auth" not in row for row in started))
            self.assertTrue(all(not task.done() for task in pending))
            release.set()
            actual = await asyncio.wait_for(asyncio.gather(*pending), timeout=3)
        records = self.read()["requests"]
        self.assertEqual(len(records), 8)
        self.assertEqual(sorted(calls), list(range(8)))
        self.assertEqual({id(value) for value in actual}, {id(value) for value in returned})
        self.assertEqual(len({record["_observation_id"] for record in records}), 8)
        self.assertNotIn("caller-forged", {record["_observation_id"] for record in records})
        by_user = {record["user_id"]: record for record in records}
        for index, request in enumerate(requests):
            record = by_user[request.headers["X-OpenWebUI-User-Id"]]
            expected = {field: original[index][field] for field in C.FIELDS if field in original[index]}
            self.assertEqual(record["body"], expected)
            self.assertEqual(record["body_after_auth"], expected)
            self.assertEqual(record["verified_cost_scope"], request.scope)
            self.assertEqual(record["native_auth_user_id"], request.scope["user_id"])
            self.assertTrue(record["provenance_removed_after"])
            self.assertTrue(record["attestation_present_before"])
            expected_native = copy.deepcopy(original[index])
            expected_native["litellm_metadata"] = {"spend_logs_metadata": {"owui_budget": request.scope}}
            self.assertEqual(request.data, expected_native)
        self.assertNotIn("native-secret-", json.dumps(records))
        self.assertNotIn("private-token-", json.dumps(records))

    async def test_failed_auth_is_not_retried_or_labeled_as_verified_and_exception_is_preserved(self):
        request, count = self.request(0), 0
        request.data["metadata"] = {"spend_logs_metadata": {"owui_budget": request.scope}}
        error = ValueError("Native fixed failure")
        async def auth(*args):
            nonlocal count
            count += 1
            raise error
        with patch.object(C, "product_auth", return_value=auth), patch.object(C, "scope_validator") as validate:
            with self.assertRaises(ValueError) as caught:
                await C.gateway_auth(request, "native-secret")
        self.assertIs(caught.exception, error)
        self.assertEqual(count, 1)
        validate.assert_not_called()
        record = self.read()["requests"][0]
        self.assertIn("body_after_auth", record)
        self.assertFalse(record["provenance_removed_after"])
        self.assertNotIn("verified_cost_scope", record)
        self.assertNotIn("native_auth_user_id", record)
        self.assertEqual(record["auth_failure"], {"scope": "custom_auth", "status_code": None, "code": "unclassified"})

    async def test_overlapping_rejections_project_only_known_status_code_and_preserve_exception_identity(self):
        class NativeFailure(Exception):
            def __init__(self, status, detail):
                super().__init__("private-token-exception-text")
                self.status_code, self.detail = status, detail
        requests = [self.request(index) for index in range(8)]
        errors = [NativeFailure(403, "Invalid signed budget provenance") if index % 2 == 0
                  else NativeFailure(True, {"private": "sk-" + "x" * 40}) for index in range(8)]
        ready, release, calls = asyncio.Event(), asyncio.Event(), []
        async def auth(request, api_key):
            calls.append(request.index)
            if len(calls) == 8:
                ready.set()
            await release.wait()
            raise errors[request.index]
        with patch.object(C, "product_auth", return_value=auth):
            pending = [asyncio.create_task(C.gateway_auth(request, "secret-api-key")) for request in requests]
            await asyncio.wait_for(ready.wait(), timeout=3)
            self.assertEqual(len(self.read()["requests"]), 8)
            release.set()
            actual = await asyncio.wait_for(asyncio.gather(*pending, return_exceptions=True), timeout=3)
        self.assertEqual(sorted(calls), list(range(8)))
        self.assertTrue(all(actual[index] is errors[index] for index in range(8)))
        records = self.read()["requests"]
        self.assertEqual(len(records), 8)
        by_user = {row["user_id"]: row for row in records}
        for index, request in enumerate(requests):
            row = by_user[request.headers["X-OpenWebUI-User-Id"]]
            self.assertEqual(row["auth_failure"], {"scope": "custom_auth", "status_code": 403 if index % 2 == 0 else None,
                "code": "invalid_signed_budget_provenance" if index % 2 == 0 else "unclassified"})
            self.assertIn("body_after_auth", row)
            self.assertNotIn("verified_cost_scope", row)
        encoded = json.dumps(records)
        self.assertNotIn("private-token-exception-text", encoded)
        self.assertNotIn("sk-" + "x" * 40, encoded)
        self.assertNotIn("secret-api-key", encoded)

    async def test_unobserved_route_delegates_once_without_creating_files_or_mutating_payload(self):
        request, calls, result = self.request(0), [], object()
        request.route = "/v1/responses"
        before = copy.deepcopy(request.data)
        async def auth(actual_request, api_key):
            calls.append((actual_request, api_key))
            return result
        with patch.object(C, "product_auth", return_value=auth):
            self.assertIs(await C.gateway_auth(request, "native-secret"), result)
        self.assertEqual(calls, [(request, "native-secret")])
        self.assertEqual(request.data, before)
        self.assertFalse(C.CAPTURE.exists())
        self.assertFalse(C.CAPTURE.with_name(C.CAPTURE.name + ".lock").exists())

    async def test_record_limit_and_file_bounds_are_enforced_before_overwriting_valid_state(self):
        for index in range(32):
            C._append({"body": {"index": index}})
        before = C.CAPTURE.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "bound exceeded"):
            C._append({"body": {"index": 32}})
        self.assertEqual(C.CAPTURE.read_bytes(), before)
        with self.assertRaisesRegex(RuntimeError, "byte bound exceeded"):
            C.save({"schema": 1, "requests": [{"body": "x" * C.MAX_BYTES}]})
        self.assertEqual(C.CAPTURE.read_bytes(), before)

    async def test_finish_cannot_overwrite_another_record_after_reset_and_save_is_compatible(self):
        stale = {"body": {"producer": "old"}}
        C._append(stale)
        C.save({"schema": 1, "requests": []})
        current = {"body": {"producer": "current"}}
        C._append(current)
        before = self.read()
        stale["body_after_auth"] = {"producer": "old"}
        with self.assertRaisesRegex(RuntimeError, "identity missing or ambiguous"):
            C._finish(stale)
        self.assertEqual(self.read(), before)
        C.save({"schema": 1, "requests": []})
        self.assertEqual(self.read(), {"schema": 1, "requests": []})


class CaptureProcessesTests(unittest.TestCase):
    def test_eight_processes_append_and_finalize_distinct_records_without_lost_updates(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "context.private.json"
            context = multiprocessing.get_context("spawn")
            barrier, results = context.Barrier(8), context.Queue()
            workers = [context.Process(target=file_writer, args=(str(path), index, barrier, results)) for index in range(8)]
            try:
                for worker in workers:
                    worker.start()
                deadline = time.monotonic() + 25
                for worker in workers:
                    worker.join(timeout=max(0, deadline - time.monotonic()))
                self.assertTrue(all(not worker.is_alive() for worker in workers), "Capture worker exceeded the common deadline")
                self.assertTrue(all(worker.exitcode == 0 for worker in workers))
                self.assertTrue(all(results.get(timeout=1)["ok"] for _ in range(8)))
                state = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(len(state["requests"]), 8)
                self.assertEqual(len({record["_observation_id"] for record in state["requests"]}), 8)
                by_worker = {record["body"]["worker"]: record for record in state["requests"]}
                self.assertEqual(set(by_worker), set(range(8)))
                for index, record in by_worker.items():
                    self.assertEqual(record["body_after_auth"], {"worker": index})
                    self.assertEqual(record["native_auth_user_id"], "native-" + str(index))
                if os.name != "nt":
                    self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
                    self.assertEqual(stat.S_IMODE(path.with_name(path.name + ".lock").stat().st_mode), 0o600)
            finally:
                for worker in workers:
                    if worker.is_alive():
                        worker.terminate()
                    worker.join(timeout=1)
                results.close()
                results.join_thread()


if __name__ == "__main__":
    unittest.main()
