"""Overlapping native-auth contexts and real cross-process private-file writes."""
import asyncio
import ast
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
            self.assertTrue(route == "/v1/chat/completions" or C.embedding_route(route) or C.responses_route(route))
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

    def responses_request(self, index=0, route="/v1/responses"):
        request = self.request(index)
        request.route = route
        request.scope["model"] = "goal584-r"
        request.headers = {"X-OpenWebUI-User-Id": "untrusted-header-actor", "X-OpenWebUI-Task": "untrusted-task"}
        request.data = {"model": "goal584-r", "input": [
            {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Current source"}]},
            {"type": "function_call", "id": "fc_fixture", "call_id": "call_fixture", "name": "fixture_budget_echo", "arguments": "{}"},
            {"type": "function_call_output", "call_id": "call_fixture", "output": "Actual Tool result"},
            {"type": "reasoning", "id": "rs_fixture", "summary": [{"type": "summary_text", "text": "Synthetic reasoning"}],
             "encrypted_content": "synthetic-opaque-reasoning"}],
            "instructions": "System policy\nAttached template instructions", "max_output_tokens": 16, "stream": True,
            "tools": [{"type": "function", "name": "fixture_budget_echo", "description": "Public Tool schema", "strict": False,
                       "parameters": {"type": "object", "properties": {}, "required": []}}], "tool_choice": "auto",
            "parallel_tool_calls": False, "reasoning": {"effort": "low", "summary": "auto"},
            "include": ["reasoning.encrypted_content"], "store": False, "background": False, "previous_response_id": None,
            "text": {"format": {"type": "text"}}, "truncation": "disabled", "temperature": .2, "top_p": .9,
            "user": "provider-owned-user", "metadata": {"synthetic": "provider metadata", "nested": {"value": index}},
            "litellm_metadata": {"owui_budget_provenance": "eyJmaXh0dXJlIjp0cnVlfQ.c3ludGhldGlj.c2lnbmF0dXJl"}}
        return request

    def responses_auth(self, *, consume=True):
        async def auth(request, api_key):
            if consume:
                request.data["litellm_metadata"].pop("owui_budget_provenance", None)
                request.data["litellm_metadata"]["spend_logs_metadata"] = {"owui_budget": request.scope.copy()}
                request.data["litellm_session_id"] = request.scope["chat_id"]
                request.data["litellm_trace_id"] = request.scope["call_id"]
            return SimpleNamespace(user_id=request.scope["user_id"], api_key="a" * 64, team_id=None)
        return auth

    def responses_validator(self, category):
        self.assertEqual(category, "personal")
        return PROTOCOL.validate_persisted_scope

    def office_request(self, index=0, service=False, route="/v1/responses"):
        request = self.responses_request(index, route)
        request.data["model"] = request.scope["model"] = "gpt-6-luna" if service else "gpt-5.4-mini"
        request.data.pop("reasoning")
        request.data.pop("include")
        if service:
            request.scope = {k: request.scope[k] for k in ("schema", "user_id", "chat_id", "call_id", "model")}
            request.scope.update(category="service", actor_id=str(uuid4()), task="follow_up_generation")
            request.data["reasoning"] = {"effort": "none"}
            request.data.pop("tools")
            request.data.pop("tool_choice")
        return request

    def office_validator(self, category):
        return {"personal": PROTOCOL.validate_persisted_scope,
                "service": PROTOCOL.validate_persisted_service_scope}[category]

    async def test_office_three_primary_continuations_and_service_preserve_full_safe_context(self):
        first = self.office_request()
        file_id = str(uuid4())
        requests = [first]
        for index, output in enumerate((json.dumps({"result_file_id": file_id}), [
                {"type": "input_text", "text": "render_office_file: Image file read successfully."},
                {"type": "input_image", "image_url": "data:image/png;base64,c3ludGhldGlj"}]), 1):
            request = self.office_request(index)
            request.data = copy.deepcopy(requests[-1].data)
            request.data["input"].extend([
                {"type": "function_call", "call_id": "office_" + str(index),
                 "name": ("export_answer_to_word", "render_office_file")[index - 1],
                 "arguments": json.dumps({"file_id": file_id})},
                {"type": "function_call_output", "call_id": "office_" + str(index), "output": output}])
            requests.append(request)
        requests.append(self.office_request(3, service=True))
        before = [copy.deepcopy(r.data) for r in requests]
        with patch.object(C, "product_auth", return_value=self.responses_auth()), patch.object(
                C, "scope_validator", side_effect=self.office_validator) as validator:
            for request in requests:
                returned = await C.gateway_auth(request, "sk-private-native-key")
                self.assertEqual(returned.user_id, request.scope["user_id"])
        rows = self.read()["requests"]
        self.assertEqual([call.args[0] for call in validator.call_args_list], ["personal"] * 3 + ["service"])
        for original, request, row in zip(before, requests, rows):
            expected = {k: v for k, v in original.items() if k != "litellm_metadata"}
            self.assertEqual(row["body"], expected)
            self.assertEqual(row["body_after_auth"], expected)
            self.assertEqual(row["verified_cost_scope"], request.scope)
            self.assertEqual(row["native_auth_user_id"], request.scope["user_id"])
            self.assertEqual(row["native_auth_key_hash"], "a" * 64)
            self.assertTrue(row["attestation_present_before"] and row["provenance_removed_after"])
            self.assertNotIn("user_id", row)
            self.assertNotIn("task", row)
        self.assertNotEqual(rows[-1]["native_auth_user_id"], rows[-1]["verified_cost_scope"]["actor_id"])
        self.assertNotIn("answer_id", rows[-1]["verified_cost_scope"])
        self.assertEqual(rows[2]["body"]["input"][-1]["output"][1]["image_url"], "data:image/png;base64,c3ludGhldGlj")
        self.assertNotIn("sk-private-native-key", json.dumps(rows))
        self.assertNotIn("owui_budget_provenance", json.dumps(rows))

    async def test_office_incomplete_successful_auth_cannot_be_a_complete_capture(self):
        for service in (False, True):
            for mode in ("unsigned", "unconsumed", "missing_scope", "missing_native_identity", "no_auth"):
                with self.subTest(service=service, mode=mode):
                    C.save({"schema": 1, "requests": []})
                    request = self.office_request(service=service)
                    if mode == "unsigned":
                        request.data["litellm_metadata"].pop("owui_budget_provenance")
                    async def auth(actual, key):
                        result = await self.responses_auth(consume=mode != "unconsumed")(actual, key)
                        if mode == "missing_scope":
                            actual.data["litellm_metadata"].pop("spend_logs_metadata")
                        if mode == "missing_native_identity":
                            result.api_key = "sk-private-raw-key"
                        return None if mode == "no_auth" else result
                    with patch.object(C, "product_auth", return_value=auth), patch.object(
                            C, "scope_validator", side_effect=self.office_validator):
                        with self.assertRaises(RuntimeError):
                            await C.gateway_auth(request, "native-secret")
                    self.assertNotIn("verified_cost_scope", self.read()["requests"][0])

    async def test_office_service_scope_is_validated_by_real_owner_and_bound_to_native_payer(self):
        for mode in ("employee_as_payer", "employee_equals_payer", "invented_answer", "invalid_task", "wrong_model"):
            with self.subTest(mode=mode):
                C.save({"schema": 1, "requests": []})
                request = self.office_request(service=True)
                async def auth(actual, key):
                    result = await self.responses_auth()(actual, key)
                    scope = actual.data["litellm_metadata"]["spend_logs_metadata"]["owui_budget"]
                    if mode == "employee_as_payer": result.user_id = scope["actor_id"]
                    elif mode == "employee_equals_payer": scope["actor_id"] = scope["user_id"]
                    elif mode == "invented_answer": scope["answer_id"] = str(uuid4())
                    elif mode == "invalid_task": scope["task"] = "primary_chat"
                    else: scope["model"] = "goal584-r"
                    return result
                with patch.object(C, "product_auth", return_value=auth), patch.object(
                        C, "scope_validator", side_effect=self.office_validator):
                    with self.assertRaises((RuntimeError, PROTOCOL.ProtocolError)):
                        await C.gateway_auth(request, "native-secret")
                self.assertNotIn("verified_cost_scope", self.read()["requests"][0])

    async def test_office_malformed_after_context_fails_success_but_preserves_original_auth_rejection(self):
        for service in (False, True):
            for rejected in (False, True):
                for mode in ("unknown_context", "unsafe_context", "malformed_scope"):
                    with self.subTest(service=service, rejected=rejected, mode=mode):
                        C.save({"schema": 1, "requests": []})
                        request, original = self.office_request(service=service), ValueError("private-product-rejection")
                        async def auth(actual, key):
                            result = await self.responses_auth()(actual, key)
                            if mode == "unknown_context": actual.data["future_context"] = "private-future-value"
                            elif mode == "unsafe_context": actual.data["instructions"] = "sk-" + "x" * 32
                            else: actual.data["litellm_metadata"]["spend_logs_metadata"]["owui_budget"] = {
                                "category": "service" if service else "personal"}
                            if rejected: raise original
                            return result
                        with patch.object(C, "product_auth", return_value=auth), patch.object(
                                C, "scope_validator", side_effect=self.office_validator):
                            with self.assertRaises((RuntimeError, PROTOCOL.ProtocolError, ValueError)) as caught:
                                await C.gateway_auth(request, "native-secret")
                        if rejected: self.assertIs(caught.exception, original)
                        row = self.read()["requests"][0]
                        self.assertNotIn("verified_cost_scope", row)
                        self.assertNotIn("private-product-rejection", json.dumps(row))
                        self.assertNotIn("private-future-value", json.dumps(row))
                        self.assertNotIn("sk-" + "x" * 32, json.dumps(row))

    async def test_responses_aliases_capture_every_supported_context_field_and_only_native_authority(self):
        for index, route in enumerate(("/responses", "/v1/responses", "/openai/v1/responses")):
            request = self.responses_request(index, route)
            original = copy.deepcopy(request.data)
            expected = {k: v for k, v in original.items() if k != "litellm_metadata"}
            with patch.object(C, "product_auth", return_value=self.responses_auth()), patch.object(C, "scope_validator", side_effect=self.responses_validator):
                returned = await C.gateway_auth(request, "sk-private-native-key")
            row = self.read()["requests"][-1]
            self.assertEqual(row["body"], expected)
            self.assertEqual(row["body_after_auth"], expected)
            self.assertEqual(set(expected), set(C.RESPONSES_FIELDS))
            self.assertEqual(row["route"], route)
            self.assertEqual(row["native_auth_user_id"], returned.user_id)
            self.assertEqual(row["native_auth_key_hash"], "a" * 64)
            self.assertEqual(row["verified_cost_scope"], request.scope)
            self.assertTrue(row["attestation_present_before"] and row["provenance_removed_after"])
            self.assertNotIn("native_stream_usage_patch", row)
            self.assertNotIn("user_id", row)
            self.assertNotIn("task", row)
            self.assertEqual(request.data["input"], original["input"])
            self.assertEqual(request.data["metadata"], original["metadata"])
        encoded = json.dumps(self.read())
        for secret in ("eyJmaXh0dXJlIjp0cnVlfQ", "sk-private-native-key", "untrusted-header-actor", "untrusted-task"):
            self.assertNotIn(secret, encoded)

    async def test_responses_fresh_product_scope_overwrites_untrusted_preexisting_scope(self):
        request = self.responses_request()
        forged = {**request.scope, "call_id": str(uuid4())}
        request.data["litellm_metadata"]["spend_logs_metadata"] = {"owui_budget": forged}
        request.data["metadata"]["spend_logs_metadata"] = {"owui_budget": {"provider": "not budget authority"}}
        with patch.object(C, "product_auth", return_value=self.responses_auth()), patch.object(C, "scope_validator", side_effect=self.responses_validator):
            await C.gateway_auth(request, "native-secret")
        row = self.read()["requests"][0]
        self.assertEqual(row["verified_cost_scope"], request.scope)
        self.assertNotEqual(row["verified_cost_scope"], forged)
        self.assertEqual(row["body"]["metadata"], row["body_after_auth"]["metadata"])

    async def test_responses_before_and_after_are_independent_full_copies_of_owner_changes(self):
        request = self.responses_request()
        before = copy.deepcopy(request.data)
        async def auth(actual, key):
            returned = await self.responses_auth()(actual, key)
            actual.data["instructions"] += "\nNative owner addition"
            actual.data["metadata"]["nested"]["value"] = "native-owned-after"
            return returned
        with patch.object(C, "product_auth", return_value=auth), patch.object(C, "scope_validator", side_effect=self.responses_validator):
            await C.gateway_auth(request, "native-secret")
        row = self.read()["requests"][0]
        self.assertEqual(row["body"], {k: v for k, v in before.items() if k != "litellm_metadata"})
        self.assertEqual(row["body_after_auth"], {k: v for k, v in request.data.items() if k in C.RESPONSES_FIELDS})
        self.assertNotEqual(row["body"]["metadata"], row["body_after_auth"]["metadata"])

    async def test_responses_overlapping_calls_use_the_same_capture_ids_and_merge_all_contexts(self):
        requests = [self.responses_request(i) for i in range(4)]
        ready, release, arrivals = asyncio.Event(), asyncio.Event(), []
        async def auth(request, key):
            arrivals.append(request.index)
            if len(arrivals) == 4:
                ready.set()
            await release.wait()
            return await self.responses_auth()(request, key)
        with patch.object(C, "product_auth", return_value=auth), patch.object(C, "scope_validator", side_effect=self.responses_validator):
            pending = [asyncio.create_task(C.gateway_auth(r, "native-secret")) for r in requests]
            await asyncio.wait_for(ready.wait(), 3)
            started = self.read()["requests"]
            self.assertEqual(len(started), 4)
            self.assertTrue(all("body_after_auth" not in r for r in started))
            release.set()
            await asyncio.wait_for(asyncio.gather(*pending), 3)
        final = self.read()["requests"]
        self.assertEqual({r["_observation_id"] for r in started}, {r["_observation_id"] for r in final})
        self.assertEqual(len(final), 4)
        for row in final:
            self.assertEqual(row["body"], row["body_after_auth"])
            self.assertEqual(row["verified_cost_scope"]["user_id"], row["native_auth_user_id"])

    async def test_responses_unsigned_or_unconsumed_or_failed_auth_never_labels_scope_verified(self):
        for mode in ("unsigned", "unconsumed", "failed"):
            request = self.responses_request()
            if mode == "unsigned":
                request.data["litellm_metadata"].pop("owui_budget_provenance")
            request.data["litellm_metadata"]["spend_logs_metadata"] = {"owui_budget": request.scope}
            failure = ValueError("private-native-failure")
            async def auth(actual, key):
                if mode == "failed":
                    raise failure
                return SimpleNamespace(user_id=request.scope["user_id"], api_key="a" * 64)
            with patch.object(C, "product_auth", return_value=auth), patch.object(C, "scope_validator") as validate:
                if mode == "failed":
                    with self.assertRaises(ValueError) as caught:
                        await C.gateway_auth(request, "native-secret")
                    self.assertIs(caught.exception, failure)
                else:
                    await C.gateway_auth(request, "native-secret")
                validate.assert_not_called()
            row = self.read()["requests"][-1]
            self.assertNotIn("verified_cost_scope", row)
            self.assertNotIn("native_stream_usage_patch", row)
            if mode == "failed":
                self.assertNotIn("native_auth_user_id", row)
                self.assertEqual(row["auth_failure"]["scope"], "custom_auth")

    async def test_responses_scope_must_match_returned_native_payer_key_and_model(self):
        for change in ({"user_id": str(uuid4())}, {"api_key": "sk-private-raw-key"}, {"scope_model": "goal584-a"}):
            C.save({"schema": 1, "requests": []})
            request = self.responses_request()
            async def auth(actual, key):
                await self.responses_auth()(actual, key)
                scope = actual.data["litellm_metadata"]["spend_logs_metadata"]["owui_budget"]
                scope["model"] = change.get("scope_model", "goal584-r")
                return SimpleNamespace(user_id=change.get("user_id", actual.scope["user_id"]), api_key=change.get("api_key", "a" * 64))
            with patch.object(C, "product_auth", return_value=auth), patch.object(C, "scope_validator", side_effect=self.responses_validator):
                with self.assertRaisesRegex(RuntimeError, "Conflicting disposable Responses scope identity"):
                    await C.gateway_auth(request, "native-secret")
            self.assertNotIn("verified_cost_scope", self.read()["requests"][0])
            self.assertNotIn("sk-private-raw-key", json.dumps(self.read()))

    async def test_responses_unknown_context_fields_fail_before_auth_or_after_native_change_without_truncating(self):
        request = self.responses_request()
        request.data["new_model_context"] = {"must_not_disappear": True}
        before = copy.deepcopy(request.data)
        with patch.object(C, "product_auth") as owner:
            with self.assertRaisesRegex(RuntimeError, "Unsupported disposable Responses context field"):
                await C.gateway_auth(request, "native-secret")
            owner.assert_not_called()
        self.assertEqual(request.data, before)
        self.assertFalse(C.CAPTURE.exists())
        request = self.responses_request()
        async def auth(actual, key):
            actual.data["new_model_context"] = {"must_not_disappear": True}
            return SimpleNamespace(user_id=request.scope["user_id"], api_key="a" * 64)
        with patch.object(C, "product_auth", return_value=auth):
            with self.assertRaisesRegex(RuntimeError, "Unsupported disposable Responses context field"):
                await C.gateway_auth(request, "native-secret")
        self.assertNotIn("body_after_auth", self.read()["requests"][0])
        self.assertTrue(self.read()["requests"][0]["responses_projection_rejected_after_auth"])
        self.assertIn("new_model_context", request.data)

    async def test_responses_after_context_rejection_does_not_replace_original_auth_failure(self):
        request, failure = self.responses_request(), ValueError("private-original-product-error")
        async def auth(actual, key):
            actual.data["unknown_after_auth"] = "private-context-value"
            raise failure
        with patch.object(C, "product_auth", return_value=auth):
            with self.assertRaises(ValueError) as caught:
                await C.gateway_auth(request, "native-secret")
        self.assertIs(caught.exception, failure)
        row = self.read()["requests"][0]
        self.assertTrue(row["responses_projection_rejected_after_auth"])
        self.assertNotIn("body_after_auth", row)
        self.assertNotIn("verified_cost_scope", row)
        self.assertNotIn("private-context-value", json.dumps(row))
        self.assertNotIn("private-original-product-error", json.dumps(row))

    async def test_auth_failure_identity_survives_observer_read_and_finish_failures_for_cc_e_r(self):
        for factory in (self.request, self.embedding_request, self.responses_request, self.office_request,
                        lambda index: self.office_request(index, service=True)):
            for boundary in ("read_after", "finish"):
                with self.subTest(family=factory.__name__, boundary=boundary):
                    request, original = factory(0), ValueError("original product auth error")
                    observer_error, reads = RuntimeError("observer finalization error"), 0
                    async def read_body(actual):
                        nonlocal reads
                        reads += 1
                        if boundary == "read_after" and reads == 2:
                            raise observer_error
                        return actual.data
                    async def auth(*args):
                        raise original
                    with patch.object(C, "product_auth", return_value=auth), patch.object(C, "_finish", side_effect=observer_error), patch(
                            "litellm.proxy.common_utils.http_parsing_utils._read_request_body", read_body):
                        with self.assertRaises(ValueError) as caught:
                            await C.gateway_auth(request, "native-secret")
                    self.assertIs(caught.exception, original)
                    self.assertEqual(reads, 2)
                    row = self.read()["requests"][-1]
                    self.assertNotIn("body_after_auth", row)
                    self.assertNotIn("verified_cost_scope", row)

    async def test_successful_auth_still_surfaces_observer_read_and_finish_failures_for_cc_e_r(self):
        for factory in (self.request, self.embedding_request, self.responses_request, self.office_request,
                        lambda index: self.office_request(index, service=True)):
            for boundary in ("read_after", "finish"):
                with self.subTest(family=factory.__name__, boundary=boundary):
                    request = factory(0)
                    observer_error, reads = RuntimeError("observer finalization error"), 0
                    async def read_body(actual):
                        nonlocal reads
                        reads += 1
                        if boundary == "read_after" and reads == 2:
                            raise observer_error
                        return actual.data
                    async def auth(actual, key):
                        if C.responses_route(actual.route):
                            return await self.responses_auth()(actual, key)
                        if C.embedding_route(actual.route):
                            actual.data.pop("metadata")
                            actual.data.pop("litellm_metadata")
                        return SimpleNamespace(user_id=str(uuid4()), api_key="a" * 64, team_id=None)
                    with patch.object(C, "product_auth", return_value=auth), patch.object(C, "_finish", side_effect=observer_error), patch.object(
                            C, "scope_validator", side_effect=self.office_validator), patch(
                            "litellm.proxy.common_utils.http_parsing_utils._read_request_body", read_body):
                        with self.assertRaises(RuntimeError) as caught:
                            await C.gateway_auth(request, "native-secret")
                    self.assertIs(caught.exception, observer_error)
                    self.assertEqual(reads, 2)

    async def test_responses_unsafe_jwt_in_actual_model_context_is_rejected_without_export_or_mutation(self):
        token = "eyJmaXh0dXJlIjp0cnVlfQ.c3ludGhldGlj.c2lnbmF0dXJl"
        for field, value in (("metadata", {"nested": {"unsafe": token}}), ("instructions", token),
                             ("input", [{"role": "user", "content": token}]),
                             ("metadata", {"unsafe_key": "sk-" + "x" * 32}),
                             ("metadata", {"owui_budget_provenance": "private-token"})):
            request = self.responses_request()
            request.data[field] = value
            before = copy.deepcopy(request.data)
            with patch.object(C, "product_auth") as owner:
                with self.assertRaisesRegex(RuntimeError, "Unsafe disposable Responses model context"):
                    await C.gateway_auth(request, "native-secret")
                owner.assert_not_called()
            self.assertEqual(request.data, before)
            self.assertFalse(C.CAPTURE.exists())

    async def test_responses_wrong_route_or_model_delegates_once_without_capture(self):
        for route, model in (("/v1/responses/child", "goal584-r"), ("/v1/responses", "goal584-a"),
                             ("/v1/chat/completions", "goal584-r"), ("/v1/responses", "goal584-fake-r"),
                             ("/v1/responses", "goal584-fake-office"), ("/v1/responses", "goal584-fake-office-service"),
                             ("/v1/responses", "gpt-5.4-mini-other"), ("/v1/responses", "gpt-6-luna-other"),
                             ("/v1/chat/completions", "gpt-5.4-mini"), ("/v1/responses/child", "gpt-6-luna")):
            request = self.responses_request(route=route)
            request.data["model"] = model
            before, returned, calls = copy.deepcopy(request.data), object(), []
            async def auth(actual, key):
                calls.append((actual, key))
                return returned
            with patch.object(C, "product_auth", return_value=auth):
                self.assertIs(await C.gateway_auth(request, "native-secret"), returned)
            self.assertEqual(calls, [(request, "native-secret")])
            self.assertEqual(request.data, before)
        self.assertFalse(C.CAPTURE.exists())

    async def test_cached_native_responses_converter_body_is_captured_without_context_loss(self):
        root = Path(os.environ.get("GOAL584_NATIVE_SOURCE_ROOT", str(SOURCE.parents[2] / "local/goal584/cost-display/open-webui/backend/open_webui")))
        path = root / "routers/openai.py"
        if not path.is_file():
            self.skipTest("Cached native Responses converter unavailable; set GOAL584_NATIVE_SOURCE_ROOT")
        tree = ast.parse(path.read_bytes())
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ("_normalize_stored_item", "convert_to_responses_payload")
                 or isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.target.id == "RESPONSES_ALLOWED_FIELDS"]
        self.assertEqual(len(nodes), 3)
        env = {}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), env)
        request = self.responses_request()
        prepared = {"model": "goal584-r", "messages": [{"role": "system", "content": request.data["instructions"]},
            {"role": "user", "content": "Current source"}, {"role": "assistant", "tool_calls": [{"id": "call_fixture",
             "function": {"name": "fixture_budget_echo", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "call_fixture", "content": "Actual Tool result"}],
            "max_tokens": 16, "stream": True, "tools": [{"type": "function", "function": {
                k: v for k, v in request.data["tools"][0].items() if k != "type"}}],
            "metadata": request.data["metadata"], "litellm_metadata": request.data["litellm_metadata"],
            "store": False, "reasoning": {"effort": "low"}}
        request.data = env["convert_to_responses_payload"](copy.deepcopy(prepared))
        before = copy.deepcopy(request.data)
        with patch.object(C, "product_auth", return_value=self.responses_auth()), patch.object(C, "scope_validator", side_effect=self.responses_validator):
            await C.gateway_auth(request, "native-secret")
        row = self.read()["requests"][0]
        self.assertEqual(row["body"], {k: v for k, v in before.items() if k != "litellm_metadata"})
        self.assertEqual(row["body_after_auth"], row["body"])
        self.assertEqual(row["body"]["instructions"], prepared["messages"][0]["content"])
        self.assertEqual(row["body"]["input"][-1]["output"], "Actual Tool result")

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
