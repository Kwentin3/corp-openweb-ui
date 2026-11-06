"""Focused protocol and body/cache boundary checks, not a LiteLLM runtime proof.

Run with PyJWT 2.13 and FastAPI installed. The optional pinned-source check
executes the actual two native cache helpers, never a copied approximation.
"""

from __future__ import annotations

import ast
import asyncio
import copy
import importlib.util
import json
import logging
import os
from pathlib import Path
import re
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import jwt
from fastapi import HTTPException
from starlette.requests import Request


HERE = Path(__file__).resolve()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


protocol = load("budget_provenance_under_test", HERE.parents[1] / "provenance.py")
auth = load("budget_auth_under_test", HERE.parents[1] / "litellm_auth.py")
SECRET = "synthetic-provenance-test-secret-" * 3
USER = "1296bad0-1491-4c19-b7f2-93e57d812864"
OTHER = "cf931dc8-a099-4471-9173-27b1e296bb59"
CHAT = "3f1971cc-ecae-4544-9dcd-f04916c342ba"
ANSWER = "5c493c1d-89fc-49b2-8707-0bf2fb31567a"
ROOT_CHAT = "738b78d7-23ac-4696-8b58-7af9244eb44c"
ROOT_ANSWER = "aaf0df2e-3fba-48d0-a55f-028a2f6eb854"
MODEL = "goal584-a"


def call(**changes):
    args = dict(user_id=USER, chat_id=CHAT, answer_id=ANSWER,
                root_chat_id=ROOT_CHAT, root_answer_id=ROOT_ANSWER, model=MODEL)
    args.update(changes)
    return protocol.encode_call(SECRET, **args)


def request(headers=()):
    return Request({"type": "http", "method": "POST", "path": "/v1/chat/completions",
                    "query_string": b"",
                    "headers": [(key.lower().encode(), value.encode()) for key, value in headers]})


def apply(data, *, shared=True, required=True, headers=(), chain_id=None, metadata_slot="metadata",
          metadata_session_id=None, task=""):
    auth._apply_provenance(request(headers), data, shared_gateway=shared, required=required,
                           secret=SECRET, user_id=USER, model=MODEL,
                           decoder=protocol.decode_service_call if task else protocol.decode_call,
                           chain_id=chain_id, metadata_slot=metadata_slot,
                           metadata_session_id=metadata_session_id, task=task)


def payload(token=None):
    return {"model": MODEL, "messages": [{"role": "user", "content": "Hi"}],
            "tools": [{"type": "function", "function": {"name": "test", "parameters": {}}}],
            "max_tokens": 5, "stream": True,
            "litellm_metadata": {"owui_budget_provenance": token or call()}}


class ProtocolTests(unittest.TestCase):
    def test_persisted_rag_scope_has_exact_key_owned_tag_without_chat_or_actor(self):
        scope = {"schema": 1, "category": "service", "operation": "rag_embedding"}
        actual = protocol.validate_persisted_rag_scope(scope)
        self.assertEqual(actual, scope)
        self.assertIsNot(actual, scope)
        actual["operation"] = "changed"
        self.assertEqual(scope["operation"], "rag_embedding")
        for validator in (protocol.validate_persisted_scope, protocol.validate_persisted_service_scope):
            with self.assertRaises(protocol.ProtocolError):
                validator(scope)
        self.assertEqual(protocol.SERVICE_TASKS, {"title_generation", "tags_generation", "follow_up_generation"})

    def test_persisted_rag_scope_rejects_missing_extra_identity_and_wrong_values_or_types(self):
        scope = {"schema": 1, "category": "service", "operation": "rag_embedding"}
        invalid = [None, [], "rag_embedding", {}, {k: v for k, v in scope.items() if k != "operation"}]
        invalid += [scope | {field: USER} for field in ("actor_id", "user_id", "payer_id", "chat_id", "answer_id",
                    "root_chat_id", "root_answer_id", "call_id", "model", "task", "extra")]
        invalid += [scope | changes for changes in ({"schema": True}, {"schema": "1"}, {"schema": 1.0}, {"schema": 2},
                    {"category": "personal"}, {"category": None}, {"category": 1},
                    {"operation": "title_generation"}, {"operation": "rag_embedding "},
                    {"operation": None}, {"operation": False}, {"operation": []})]
        for value in invalid:
            with self.subTest(value=value), self.assertRaisesRegex(protocol.ProtocolError, "Invalid budget provenance"):
                protocol.validate_persisted_rag_scope(value)

    def test_persisted_scope_is_exact_and_bounded(self):
        valid = {"schema": 1, "user_id": USER, "chat_id": CHAT, "answer_id": ANSWER,
                 "root_chat_id": ROOT_CHAT, "root_answer_id": ROOT_ANSWER, "model": MODEL,
                 "call_id": OTHER, "category": "personal"}
        self.assertEqual(protocol.validate_persisted_scope(valid), valid)
        self.assertIsNot(protocol.validate_persisted_scope(valid), valid)
        missing = valid.copy()
        missing.pop("answer_id")
        for invalid in [missing, {**valid, "extra": "field"}, {**valid, "chat_id": "caller-id"},
                        {**valid, "category": "service"}, {**valid, "schema": True},
                        {**valid, "model": " whitespace "}, None]:
            with self.subTest(invalid_type=type(invalid).__name__), self.assertRaises(protocol.ProtocolError):
                protocol.validate_persisted_scope(invalid)

    def test_call_and_root_have_separate_audiences(self):
        claims = protocol.decode_call(call(), SECRET, user_id=USER, model=MODEL)
        self.assertEqual((claims["chat_id"], claims["root_answer_id"]), (CHAT, ROOT_ANSWER))
        self.assertEqual(claims["exp"] - claims["iat"], 300)
        root = protocol.encode_root(SECRET, user_id=USER, root_chat_id=ROOT_CHAT,
                                    root_answer_id=ROOT_ANSWER)
        root_claims = protocol.decode_root(root, SECRET)
        self.assertEqual(root_claims["sub"], USER)
        self.assertEqual(root_claims["exp"] - root_claims["iat"], 86400)
        self.assertNotIn("model", root_claims)
        for token, decoder in [(root, lambda t: protocol.decode_call(t, SECRET, user_id=USER, model=MODEL)),
                               (call(), lambda t: protocol.decode_root(t, SECRET))]:
            with self.assertRaises(protocol.ProtocolError):
                decoder(token)

    def test_tampered_actual_token_and_wrong_secret_rejected(self):
        token = call()
        head, body, signature = token.split(".")
        parsed = json.loads(jwt.utils.base64url_decode(body.encode()))
        parsed["model"] = "goal584-b"
        altered = jwt.utils.base64url_encode(json.dumps(parsed).encode()).decode()
        for candidate, secret in [(f"{head}.{altered}.{signature}", SECRET),
                                  (token, "different-test-secret-" * 4)]:
            with self.assertRaisesRegex(protocol.ProtocolError, "^Invalid budget provenance$"):
                protocol.decode_call(candidate, secret, user_id=USER, model=MODEL)

    def test_foreign_user_model_and_expiration_rejected(self):
        token = call()
        for user, model in [(OTHER, MODEL), (USER, "goal584-b")]:
            with self.assertRaises(protocol.ProtocolError):
                protocol.decode_call(token, SECRET, user_id=user, model=model)
        with self.assertRaises(protocol.ProtocolError):
            protocol.decode_call(call(now=int(time.time()) - 301), SECRET, user_id=USER, model=MODEL)

    def test_signed_invalid_claims_and_algorithms_rejected(self):
        claims = jwt.decode(call(), SECRET, algorithms=["HS256"], audience=protocol.CALL_AUDIENCE)
        for changes in [{"schema": True}, {"exp": claims["iat"] + 301}, {"iat": str(claims["iat"])},
                        {"chat_id": "not-a-uuid"}, {"sub": USER.upper()}, {"aud": [protocol.CALL_AUDIENCE]},
                        {"model": " padded "}, {"unexpected": "extra"}]:
            invalid = jwt.encode({**claims, **changes}, SECRET, algorithm="HS256")
            with self.subTest(changes=changes), self.assertRaises(protocol.ProtocolError):
                protocol.decode_call(invalid, SECRET, user_id=USER, model=MODEL)
        invalid = jwt.encode(claims, SECRET, algorithm="HS384")
        with self.assertRaises(protocol.ProtocolError):
            protocol.decode_call(invalid, SECRET, user_id=USER, model=MODEL)

    def test_encoder_rejects_noncanonical_ids_and_unbounded_lifetimes(self):
        for changes in [{"ttl_seconds": 301}, {"ttl_seconds": 0}, {"ttl_seconds": True},
                        {"user_id": USER.upper()}, {"answer_id": "opaque-client-id"}, {"model": ""}]:
            with self.subTest(changes=changes), self.assertRaises(protocol.ProtocolError):
                call(**changes)
        with self.assertRaises(protocol.ProtocolError):
            protocol.encode_root(SECRET, user_id=USER, root_chat_id=ROOT_CHAT,
                                 root_answer_id=ROOT_ANSWER, ttl_seconds=86401)


class BoundaryTests(unittest.TestCase):
    def test_gateway_wires_native_route_slot_and_canonical_cache_setter(self):
        tree = ast.parse((HERE.parents[1] / "litellm_auth.py").read_text(encoding="utf-8"))
        gateway = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)
                       and node.name == "gateway_auth")
        calls = [node for node in ast.walk(gateway) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)]
        prepare = next(node for node in calls if node.func.id == "_apply_provenance")
        slot = next(item.value for item in prepare.keywords if item.arg == "metadata_slot")
        self.assertIsInstance(slot, ast.Call)
        self.assertEqual(slot.func.id, "metadata_variable_name_for_route")
        self.assertEqual([arg.id for arg in slot.args], ["route"])
        extractor = next(item.value for item in prepare.keywords if item.arg == "metadata_session_id")
        self.assertEqual(extractor.func.id, "_get_anthropic_session_id_from_metadata")
        self.assertEqual(ast.unparse(extractor.args[0]), "request_data.get('metadata')")
        normalize = next(node for node in calls if node.func.id == "_metadata_maps")
        self.assertLess(normalize.lineno, prepare.lineno)
        setter = next(node for node in calls if node.func.id == "_safe_set_request_parsed_body")
        validation = next(node for node in calls if node.func.id == "validate_resolved_virtual_key")
        self.assertLess(prepare.lineno, setter.lineno)
        self.assertLess(setter.lineno, validation.lineno)
        admission = next(node for node in calls if node.func.id == "_require_declared_buffered_profile")
        self.assertLess(validation.lineno, admission.lineno)
        self.assertEqual([ast.unparse(arg) for arg in admission.args],
                         ["request", "request_data", "auth", "proxy_server.llm_router", "route"])
        self.assertLess(admission.lineno, next(node.lineno for node in gateway.body if isinstance(node, ast.Return)))
        self.assertEqual({item.arg: item.value.id for item in setter.keywords},
                         {"request": "request", "parsed_body": "request_data"})
        imports = [node for node in gateway.body if isinstance(node, ast.ImportFrom)]
        self.assertTrue(any(node.module == "litellm.proxy.litellm_pre_call_utils"
                            and "metadata_variable_name_for_route" in [name.name for name in node.names]
                            and "_get_anthropic_session_id_from_metadata" in [name.name for name in node.names]
                            for node in imports))
        self.assertTrue(any(node.module == "litellm.proxy.common_utils.http_parsing_utils"
                            and "_safe_set_request_parsed_body" in [name.name for name in node.names]
                            for node in imports))

    def test_exact_native_metadata_session_stage_cannot_drift_after_auth(self):
        source = HERE.parents[3] / "local/goal584/litellm/upstream/litellm/proxy/litellm_pre_call_utils.py"
        if not source.exists():
            self.skipTest("Exact pinned session stage unavailable; actual-image proof remains required")
        tree = ast.parse(source.read_text(encoding="utf-8"))
        extractor = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                         and node.name == "_get_anthropic_session_id_from_metadata")
        regex = next(node for node in tree.body if isinstance(node, ast.AnnAssign)
                     and isinstance(node.target, ast.Name) and node.target.id == "_ANTHROPIC_SESSION_ID_VALUE_RE")
        owner = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                     and node.name == "LiteLLMProxyRequestSetup")
        stage = next(node for node in owner.body if isinstance(node, ast.FunctionDef)
                     and node.name == "add_litellm_metadata_from_request_headers")
        # Execute the actual fallback and final update nodes, without substituting
        # their session policy or running unrelated header/OTel integration glue.
        fallback = next(node for node in stage.body if isinstance(node, ast.If)
                        and isinstance(node.test, ast.Name) and node.test.id == "chain_id").orelse
        final_update = stage.body[-2]
        self.assertIsInstance(final_update, ast.If)
        namespace = {"re": re, "verbose_proxy_logger": logging.getLogger("budget-test-native-stage")}
        flags = __import__("__future__").annotations.compiler_flag
        exec(compile(ast.Module(body=[regex, extractor], type_ignores=[]), str(source), "exec", flags=flags), namespace)
        derive = namespace["_get_anthropic_session_id_from_metadata"]
        later = compile(ast.Module(body=[*fallback, final_update], type_ignores=[]), str(source), "exec", flags=flags)
        for slot in ("metadata", "litellm_metadata"):
            for foreign in ({"session_id": OTHER}, f"customer_session_{OTHER}"):
                for serialized in (False, True):
                    metadata = {"customer": "synthetic", "user_id": foreign}
                    data = payload()
                    data["metadata"] = json.dumps(metadata) if serialized else metadata
                    auth._metadata_maps(data)  # gateway's native-compatible normalization
                    with self.subTest(slot=slot, foreign_type=type(foreign).__name__, serialized=serialized):
                        self.assertEqual(derive(data["metadata"]), OTHER)
                        with self.assertRaises(HTTPException) as caught:
                            apply(data, metadata_slot=slot, metadata_session_id=derive(data["metadata"]))
                        self.assertEqual(caught.exception.status_code, 403)
                        self.assertEqual(data["metadata"]["user_id"], foreign)
            for allowed in ({"session_id": ROOT_CHAT}, f"customer_session_{ROOT_CHAT}", "ordinary-provider-user"):
                data = payload()
                data["metadata"] = {"customer": "synthetic", "user_id": copy.deepcopy(allowed)}
                apply(data, metadata_slot=slot, metadata_session_id=derive(data["metadata"]))
                self.assertEqual(data["metadata"]["user_id"], allowed)  # auth does not rewrite provider fields
                exec(later, {**namespace, "data": data, "metadata_from_headers": {}, "_metadata_variable_name": slot})
                self.assertEqual(data[slot]["session_id"], ROOT_CHAT)
                self.assertEqual(data["litellm_session_id"], ROOT_CHAT)
                self.assertEqual(data[slot]["trace_id"], ROOT_ANSWER)
                self.assertEqual(data["metadata"]["customer"], "synthetic")

    def test_canonical_scope_replaces_competing_aliases_without_changing_input(self):
        data = payload()
        data["metadata"] = {"user_api_key_user_id": USER, "unrelated": "keep",
                            "trace_id": "forged", "session_id": "forged",
                            "spend_logs_metadata": {"unrelated": "keep", "owui_budget": {"user_id": OTHER}}}
        model_input = copy.deepcopy({key: data[key] for key in ("model", "messages", "tools", "max_tokens", "stream")})
        held_metadata = data["metadata"]
        held_spend = held_metadata["spend_logs_metadata"]
        token = data["litellm_metadata"]["owui_budget_provenance"]
        data["metadata"]["owui_budget_provenance"] = "forged-alias"
        data["metadata"]["chat_context"] = {"owui_budget_root": "synthetic-root-token", "keep": True}
        apply(data)
        self.assertEqual(model_input, {key: data[key] for key in model_input})
        self.assertIs(data["metadata"], held_metadata)
        self.assertIs(held_metadata["spend_logs_metadata"], held_spend)
        self.assertEqual(held_metadata["user_api_key_user_id"], USER)
        self.assertEqual(held_spend["unrelated"], "keep")
        self.assertEqual(data["metadata"]["session_id"], ROOT_CHAT)
        self.assertEqual(data["metadata"]["trace_id"], ROOT_ANSWER)
        self.assertEqual(data["metadata"]["spend_logs_metadata"]["owui_budget"],
                         {"schema": 1, "user_id": USER, "chat_id": CHAT, "answer_id": ANSWER,
                          "root_chat_id": ROOT_CHAT, "root_answer_id": ROOT_ANSWER, "model": MODEL,
                          "call_id": protocol.decode_call(token, SECRET, user_id=USER, model=MODEL)["jti"],
                          "category": "personal"})
        self.assertEqual(data["litellm_metadata"], {})
        serialized = json.dumps(data)
        self.assertNotIn(token, serialized)
        self.assertNotIn("forged-alias", serialized)
        self.assertNotIn("synthetic-root-token", serialized)

    def test_responses_native_route_preserves_provider_metadata(self):
        source = HERE.parents[3] / "local/goal584/litellm/upstream/litellm/proxy/litellm_pre_call_utils.py"
        if not source.exists():
            self.skipTest("Exact pinned route helper unavailable; actual-image proof remains required")
        tree = ast.parse(source.read_text(encoding="utf-8"))
        nodes = [node for node in tree.body if
                 (isinstance(node, ast.FunctionDef) and node.name == "metadata_variable_name_for_route")
                 or (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
                     and node.target.id == "LITELLM_METADATA_ROUTES")]
        self.assertEqual(len(nodes), 2)
        namespace = {}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec",
                     flags=__import__("__future__").annotations.compiler_flag), namespace)
        route_slot = namespace["metadata_variable_name_for_route"]
        self.assertEqual(route_slot("/v1/chat/completions"), "metadata")
        for route in ("/responses", "/v1/responses"):
            data = payload()
            data["input"] = data.pop("messages")
            data["metadata"] = {"customer": "synthetic"}
            provider_metadata = data["metadata"]
            provider_input = copy.deepcopy(data["input"])
            apply(data, metadata_slot=route_slot(route))
            self.assertIs(data["metadata"], provider_metadata)
            self.assertEqual(data["metadata"], {"customer": "synthetic"})
            self.assertEqual(data["input"], provider_input)
            self.assertEqual(data["litellm_metadata"]["session_id"], ROOT_CHAT)
            self.assertEqual(data["litellm_metadata"]["trace_id"], ROOT_ANSWER)
            self.assertEqual(data["litellm_metadata"]["spend_logs_metadata"]["owui_budget"]["answer_id"], ANSWER)
            self.assertNotIn("owui_budget_provenance", json.dumps(data))

    def test_unsigned_legacy_and_native_keys_cannot_stamp_trusted_namespace(self):
        for shared in (True, False):
            data = {"model": MODEL, "metadata": {"spend_logs_metadata": {"owui_budget": {"user_id": OTHER},
                                                                         "keep": 7}},
                    "litellm_metadata": {"owui_budget_provenance": call(),
                                         "spend_logs_metadata": {"owui_budget": {"user_id": OTHER}}}}
            if shared:
                data["litellm_metadata"].pop("owui_budget_provenance")
            apply(data, shared=shared, required=False)
            self.assertEqual(data["metadata"]["spend_logs_metadata"], {"keep": 7})
            self.assertEqual(data["litellm_metadata"]["spend_logs_metadata"], {})
            self.assertNotIn("owui_budget_provenance", json.dumps(data))

    def test_missing_foreign_or_invalid_provenance_fails_closed(self):
        for data in [{"model": MODEL}, payload("invalid"), payload(call(user_id=OTHER)),
                     payload(call(model="goal584-b"))]:
            with self.subTest(data_keys=list(data)), self.assertRaises(HTTPException) as caught:
                apply(data)
            self.assertEqual(caught.exception.status_code, 403)

    def test_competing_headers_cannot_override_verified_scope(self):
        for headers, chain_id in [([("x-litellm-spend-logs-metadata", '{"unrelated":1}')], None),
                                  ([("x-litellm-session-id", OTHER)], OTHER),
                                  ([("traceparent", "synthetic")], None),
                                  ([("baggage", "session_id=foreign")], None)]:
            with self.subTest(headers=headers), self.assertRaises(HTTPException):
                apply(payload(), headers=headers, chain_id=chain_id)

    def test_raw_header_namespace_forgery_rejected_for_all_branches(self):
        for shared in (False, True):
            with self.assertRaises(HTTPException):
                apply({"model": MODEL}, shared=shared, required=False,
                      headers=[("x-litellm-spend-logs-metadata", '{"owui_budget":{"user_id":"forged"}}')])

    def test_string_or_nonscalar_spend_envelopes_cannot_hide_forged_namespace(self):
        for shared in (False, True):
            for spend in ['{"owui_budget":{"user_id":"forged"}}', ["owui_budget"]]:
                with self.subTest(shared=shared, spend_type=type(spend).__name__), self.assertRaises(HTTPException):
                    apply({"model": MODEL, "metadata": {"spend_logs_metadata": spend}},
                          shared=shared, required=False)

    def test_string_metadata_alias_is_cleaned(self):
        data = payload()
        data["metadata"] = json.dumps({"owui_budget_provenance": "forged", "unrelated": 4,
                                        "spend_logs_metadata": {"owui_budget": {"user_id": OTHER}}})
        apply(data)
        self.assertEqual(data["metadata"]["unrelated"], 4)
        self.assertEqual(data["metadata"]["spend_logs_metadata"]["owui_budget"]["user_id"], USER)
        self.assertNotIn("forged", json.dumps(data))

    def test_exact_native_cache_helpers_retain_new_canonical_keys(self):
        source = HERE.parents[3] / "local/goal584/litellm/upstream/litellm/proxy/common_utils/http_parsing_utils.py"
        if not source.exists():
            self.skipTest("Exact pinned source unavailable; actual-image proof remains required")
        tree = ast.parse(source.read_text(encoding="utf-8"))
        names = {"_safe_get_request_parsed_body", "_safe_set_request_parsed_body"}
        nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
        self.assertEqual(len(nodes), 2)
        namespace = {}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec",
                     flags=__import__("__future__").annotations.compiler_flag), namespace)
        get, put = namespace["_safe_get_request_parsed_body"], namespace["_safe_set_request_parsed_body"]
        req = request()
        initial = payload()
        put(request=req, parsed_body=initial)
        auth_copy = get(request=req)
        self.assertIsNot(auth_copy, initial)
        held = initial["litellm_metadata"]
        apply(auth_copy)
        self.assertNotIn("owui_budget_provenance", held)
        self.assertNotIn("metadata", get(request=req))  # accepted_keys captured before our new slot
        put(request=req, parsed_body=auth_copy)
        downstream = get(request=req)
        self.assertEqual(downstream["metadata"]["session_id"], ROOT_CHAT)
        self.assertEqual(downstream["metadata"]["spend_logs_metadata"]["owui_budget"]["answer_id"], ANSWER)
        self.assertEqual(downstream["litellm_metadata"], {})


class ServiceProtocolTests(unittest.TestCase):
    def token(self, **changes):
        fields = {"user_id": USER, "payer_id": OTHER, "chat_id": CHAT,
                  "model": MODEL, "task": "title_generation"}
        fields.update(changes)
        return protocol.encode_service_call(SECRET, **fields)

    def decode(self, token, **changes):
        fields = {"user_id": USER, "model": MODEL, "task": "title_generation"}
        fields.update(changes)
        return protocol.decode_service_call(token, SECRET, **fields)

    def test_service_token_binds_distinct_actor_payer_chat_task_and_audience(self):
        claims = self.decode(self.token())
        self.assertEqual(claims["sub"], USER)
        self.assertEqual(claims["payer_id"], OTHER)
        self.assertEqual(claims["chat_id"], CHAT)
        self.assertEqual(claims["aud"], protocol.SERVICE_AUDIENCE)
        self.assertNotIn("answer_id", claims)
        self.assertNotIn("root_answer_id", claims)
        for change in ({"user_id": OTHER}, {"model": "other-model"}, {"task": "tags_generation"}):
            with self.subTest(change=change), self.assertRaises(protocol.ProtocolError):
                self.decode(self.token(), **change)
        with self.assertRaises(protocol.ProtocolError):
            protocol.decode_call(self.token(), SECRET, user_id=USER, model=MODEL)
        with self.assertRaises(protocol.ProtocolError):
            self.decode(call())
        with self.assertRaises(protocol.ProtocolError):
            protocol.decode_service_call(self.token(), SECRET + "wrong", user_id=USER,
                                         model=MODEL, task="title_generation")

    def test_service_grammar_rejects_extra_fields_bad_ids_unknown_task_and_invalid_time(self):
        for changes in ({"payer_id": USER}, {"payer_id": "service-name"}, {"chat_id": "chat-name"},
                        {"task": "embeddings"}, {"task": []}, {"ttl_seconds": protocol.CALL_TTL + 1},
                        {"ttl_seconds": 0}, {"model": "model\nheader"}):
            with self.subTest(changes=changes), self.assertRaises(protocol.ProtocolError):
                self.token(**changes)
        claims = self.decode(self.token())
        for changes in ({"root_answer_id": ANSWER}, {"category": "personal"}, {"schema": True},
                        {"jti": "not-a-uuid"}, {"exp": claims["iat"] - 1},
                        {"exp": claims["iat"] + protocol.CALL_TTL + 1}):
            token = jwt.encode(claims | changes, SECRET, algorithm="HS256")
            with self.subTest(changes=changes), self.assertRaises(protocol.ProtocolError):
                self.decode(token)

    def test_service_log_scope_keeps_personal_contract_separate(self):
        claims = self.decode(self.token())
        scope = {"schema": 1, "user_id": claims["payer_id"], "actor_id": claims["sub"],
                 "chat_id": claims["chat_id"], "call_id": claims["jti"], "model": claims["model"],
                 "category": "service", "task": claims["task"]}
        self.assertEqual(protocol.validate_persisted_service_scope(scope), scope)
        with self.assertRaises(protocol.ProtocolError):
            protocol.validate_persisted_scope(scope)
        for changes in ({"user_id": USER}, {"category": "personal"}, {"task": "unknown"},
                        {"answer_id": ANSWER}, {"actor_id": "forged-user"}):
            with self.subTest(changes=changes), self.assertRaises(protocol.ProtocolError):
                protocol.validate_persisted_service_scope(scope | changes)

    def test_three_native_task_names_bind_actual_task_without_changing_personal_serialization(self):
        self.assertEqual(protocol.SERVICE_TASKS, {"title_generation", "tags_generation", "follow_up_generation"})
        personal = protocol.decode_call(call(), SECRET, user_id=USER, model=MODEL)
        self.assertEqual(set(personal), {"schema", "iss", "aud", "sub", "jti", "iat", "exp", "chat_id",
                                        "answer_id", "root_chat_id", "root_answer_id", "model"})
        for task in ("title_generation", "tags_generation", "follow_up_generation"):
            with self.subTest(task=task):
                token = self.token(task=task)
                claims = self.decode(token, task=task)
                self.assertEqual((claims["sub"], claims["payer_id"], claims["task"]), (USER, OTHER, task))
                self.assertEqual(set(claims), {"schema", "iss", "aud", "sub", "jti", "iat", "exp",
                                              "payer_id", "chat_id", "model", "task"})
                with self.assertRaises(protocol.ProtocolError):
                    protocol.decode_call(token, SECRET, user_id=USER, model=MODEL)
                with self.assertRaises(protocol.ProtocolError):
                    self.decode(call(), task=task)


class ServiceBoundaryTests(unittest.TestCase):
    def token(self, **changes):
        fields = dict(user_id=USER, payer_id=OTHER, chat_id=CHAT, model=MODEL, task="title_generation")
        return protocol.encode_service_call(SECRET, **(fields | changes))

    def test_service_projection_preserves_full_model_context_and_consumes_aliases(self):
        for slot in ("metadata", "litellm_metadata"):
            token = self.token()
            data = payload(token)
            data.update(temperature=0.3, tool_choice="auto", stop=["END"], seed=42,
                        response_format={"type": "json_object"})
            data["messages"] = [{"role": "system", "content": "Create a title"},
                                {"role": "user", "content": [{"type": "text", "text": "Actual input"}]}]
            data["metadata"] = {"customer": "keep", "owui_budget_provenance": "forged-alias",
                                "chat_context": {"owui_budget_root": "private-root", "keep": 1},
                                "spend_logs_metadata": {"owui_budget": {"user_id": USER}, "keep": 2}}
            expected_context = copy.deepcopy({key: value for key, value in data.items()
                                              if key not in ("metadata", "litellm_metadata")})
            apply(data, metadata_slot=slot, task="title_generation", required=False)
            self.assertEqual({key: data[key] for key in expected_context}, expected_context)
            claims = protocol.decode_service_call(token, SECRET, user_id=USER, model=MODEL,
                                                   task="title_generation")
            scope = data[slot]["spend_logs_metadata"]["owui_budget"]
            self.assertEqual(protocol.validate_persisted_service_scope(scope),
                             {"schema": 1, "user_id": OTHER, "actor_id": USER, "chat_id": CHAT,
                              "call_id": claims["jti"], "model": MODEL, "category": "service",
                              "task": "title_generation"})
            self.assertEqual(data[slot]["session_id"], "owui-service:" + CHAT)
            self.assertEqual(data[slot]["trace_id"], claims["jti"])
            self.assertEqual(data["litellm_session_id"], "owui-service:" + CHAT)
            self.assertEqual(data["litellm_trace_id"], claims["jti"])
            self.assertEqual(data["metadata"]["customer"], "keep")
            self.assertEqual(data["metadata"]["chat_context"], {"keep": 1})
            self.assertEqual(data["metadata"]["spend_logs_metadata"]["keep"], 2)
            for private in (token, "forged-alias", "private-root", "answer_id", "root_chat_id"):
                self.assertNotIn(private, json.dumps(data))
            if slot == "litellm_metadata":
                self.assertNotIn("owui_budget", data["metadata"]["spend_logs_metadata"])

    def test_native_background_tasks_keep_one_service_scope_and_leave_model_context_intact(self):
        for task in ("title_generation", "tags_generation", "follow_up_generation"):
            token = self.token(task=task)
            data = payload(token)
            data.update(response_format={"type": "json_object"}, temperature=0, max_tokens=5)
            context = copy.deepcopy({key: value for key, value in data.items()
                                     if key not in ("metadata", "litellm_metadata")})
            with self.subTest(task=task):
                apply(data, task=task)
                self.assertEqual({key: data[key] for key in context}, context)
                scope = protocol.validate_persisted_service_scope(data["metadata"]["spend_logs_metadata"]["owui_budget"])
                self.assertEqual((scope["user_id"], scope["actor_id"], scope["task"]), (OTHER, USER, task))
                self.assertEqual(data["litellm_session_id"], "owui-service:" + CHAT)
                self.assertFalse(any(field in scope for field in ("answer_id", "root_chat_id", "root_answer_id")))
                self.assertNotIn(token, json.dumps(data))

    def test_unsigned_wrong_scope_audience_and_extra_claims_never_authorize_service(self):
        claims = protocol.decode_service_call(self.token(), SECRET, user_id=USER, model=MODEL,
                                               task="title_generation")
        invalid = [None, "invalid", call(), self.token(user_id=OTHER, payer_id=USER),
                   self.token(model="other-model"),
                   jwt.encode(claims | {"task": "tags_generation"}, SECRET, algorithm="HS256"),
                   jwt.encode(claims | {"extra": True}, SECRET, algorithm="HS256")]
        for token in invalid:
            data = payload(token) if token is not None else {"model": MODEL}
            with self.subTest(token_present=token is not None), self.assertRaises(HTTPException) as caught:
                apply(data, task="title_generation", required=False)
            self.assertEqual(caught.exception.status_code, 403)
        with self.assertRaises(HTTPException):
            apply(payload(self.token()), task="tags_generation")
        with self.assertRaises(HTTPException):
            apply(payload(self.token()), task="title_generation", shared=False, required=False)
        with self.assertRaises(HTTPException):
            apply(payload(self.token()))  # service audience cannot enter personal path

    def test_service_correlation_competitors_are_rejected(self):
        for kwargs in ({"chain_id": OTHER}, {"headers": [("traceparent", "forged")]},
                       {"headers": [("baggage", "session_id=foreign")]},
                       {"headers": [("x-litellm-spend-logs-metadata", "{}")]},
                       {"metadata_session_id": CHAT}, {"metadata_session_id": ROOT_CHAT}):
            with self.subTest(kwargs=kwargs), self.assertRaises(HTTPException):
                apply(payload(self.token()), task="title_generation", **kwargs)

    def test_exact_native_later_session_stage_keeps_service_namespace(self):
        source = HERE.parents[3] / "local/goal584/litellm/upstream/litellm/proxy/litellm_pre_call_utils.py"
        if not source.exists():
            self.skipTest("Exact pinned native session stage unavailable")
        tree = ast.parse(source.read_text(encoding="utf-8"))
        extractor = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                         and node.name == "_get_anthropic_session_id_from_metadata")
        regex = next(node for node in tree.body if isinstance(node, ast.AnnAssign)
                     and isinstance(node.target, ast.Name) and node.target.id == "_ANTHROPIC_SESSION_ID_VALUE_RE")
        owner = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                     and node.name == "LiteLLMProxyRequestSetup")
        stage = next(node for node in owner.body if isinstance(node, ast.FunctionDef)
                     and node.name == "add_litellm_metadata_from_request_headers")
        fallback = next(node for node in stage.body if isinstance(node, ast.If)
                        and isinstance(node.test, ast.Name) and node.test.id == "chain_id").orelse
        flags = __import__("__future__").annotations.compiler_flag
        namespace = {"re": re, "verbose_proxy_logger": logging.getLogger("service-native-stage")}
        exec(compile(ast.Module(body=[regex, extractor], type_ignores=[]), str(source), "exec", flags=flags), namespace)
        later = compile(ast.Module(body=[*fallback, stage.body[-2]], type_ignores=[]), str(source), "exec", flags=flags)
        for slot in ("metadata", "litellm_metadata"):
            for provider_user in ({"session_id": CHAT}, "customer_session_" + CHAT):
                data = payload(self.token())
                data["metadata"] = {"user_id": provider_user}
                derived = namespace["_get_anthropic_session_id_from_metadata"](data["metadata"])
                with self.assertRaises(HTTPException):
                    apply(data, task="title_generation", metadata_slot=slot, metadata_session_id=derived)
            data = payload(self.token())
            data["metadata"] = {"user_id": "ordinary-provider-user", "customer": "keep"}
            apply(data, task="title_generation", metadata_slot=slot)
            before = copy.deepcopy(data)
            exec(later, {**namespace, "data": data, "metadata_from_headers": {}, "_metadata_variable_name": slot})
            self.assertEqual(data, before)


class ServiceGatewayTests(unittest.TestCase):
    """Execute actual gateway control flow with owner I/O doubles, not native runtime acceptance."""

    def run_gateway(self, *, token=None, task="title_generation", actor=USER, body_model=MODEL,
                    native_model=MODEL, api_key=SECRET, resolved_user=None, validated_user=None,
                    required=False, assignment_user=OTHER, llm_route=True,
                    fresh_blocked=False, fresh_db_failure=False):
        assignment = load("gateway_assignment_under_test", HERE.parents[1] / "assignment.py")
        events = []
        row = SimpleNamespace(user_id=assignment_user, team_id=None, models=[MODEL],
                              key_alias=assignment.assignment_alias(assignment_user, MODEL),
                              metadata=assignment.assignment_metadata(MODEL), token="synthetic-key-hash")
        identity = copy.deepcopy(row)
        identity.user_id = assignment_user if resolved_user is None else resolved_user
        identity.blocked = fresh_blocked
        cached_identity = copy.deepcopy(identity)
        cached_identity.blocked = False
        async def find_many(**kwargs):
            events.append(("assignment", kwargs))
            return [row]
        class Store:
            def __init__(self, *args, **kwargs):
                pass
            @staticmethod
            def key_from_principal(principal):
                return principal
            async def resolve(self, **kwargs):
                events.append(("resolve", kwargs))
                return cached_identity
        async def get_key_object(**kwargs):
            events.append(("fresh", kwargs))
            if fresh_db_failure:
                raise HTTPException(503, "Synthetic native writer unavailable")
            return identity
        async def validate(**kwargs):
            events.append(("validate", kwargs))
            return SimpleNamespace(user_id=assignment_user if validated_user is None else validated_user,
                                   budget_reservation=None)
        data = {"model": body_model, "messages": [{"role": "user", "content": "actual task context"}],
                "metadata": {"payer_id": USER, "task": "title_generation"}}
        if token is not None:
            data["litellm_metadata"] = {"owui_budget_provenance": token}
        async def read(req):
            return data
        def symbol(name, **kwargs):
            events.append(("decoder", name))
            return getattr(protocol, name.split(".")[1])
        tree = ast.parse((HERE.parents[1] / "litellm_auth.py").read_text(encoding="utf-8"))
        gateway = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)
                       and node.name == "gateway_auth")
        # Keep the actual function body; substitute only late-imported external owners.
        gateway.body = [node for node in gateway.body if not isinstance(node, (ast.Import, ast.ImportFrom))]
        proxy = SimpleNamespace(version=auth.REQUIRED_VERSION, master_key="synthetic-master",
                                general_settings={"custom_auth_run_common_checks": True,
                                                  "fail_closed_budget_enforcement": True},
                                prisma_client=object(), llm_router=None, user_api_key_cache=None,
                                proxy_logging_obj=None)
        namespace = {**vars(auth), "version": lambda name: auth.REQUIRED_VERSION,
                     "litellm": SimpleNamespace(block_requests_for_models_without_pricing=True),
                     "proxy_server": proxy, "LiteLLMRoutes": SimpleNamespace(master_key_only_routes=SimpleNamespace(value=[])),
                     "get_request_route": lambda req: "/v1/chat/completions" if llm_route else "/key/info",
                     "RouteChecks": SimpleNamespace(is_llm_api_route=lambda route: llm_route),
                     "PrismaDBExceptionHandler": SimpleNamespace(should_allow_request_on_db_unavailable=lambda: False),
                     "get_model_from_request": lambda *args, **kwargs: native_model,
                     "_read_request_body": read, "_safe_set_request_parsed_body": lambda **kwargs: events.append(("cache", kwargs)),
                     "VerificationTokenRepository": lambda db: SimpleNamespace(table=SimpleNamespace(find_many=find_many)),
                     "assignment_alias": assignment.assignment_alias, "_assignment_matches": assignment.assignment_matches,
                     "get_instance_fn": symbol, "get_chain_id_from_headers": lambda headers: None,
                     "metadata_variable_name_for_route": lambda route: "metadata",
                     "_get_anthropic_session_id_from_metadata": lambda metadata: None,
                     "IdentityStore": Store, "get_key_object": get_key_object,
                     "validate_resolved_virtual_key": validate,
                     "hash_token": lambda secret: "native-hash"}
        exec(compile(ast.Module(body=[gateway], type_ignores=[]), "actual_gateway_auth", "exec",
                     flags=__import__("__future__").annotations.compiler_flag), namespace)
        headers = [(auth.USER_ID_HEADER, actor)]
        if task is not None:
            headers.append((auth.TASK_HEADER, task))
        with patch.dict(auth.os.environ, {"OWUI_BUDGET_GATEWAY_SECRET": SECRET,
                                         "OWUI_BUDGET_REQUIRE_PROVENANCE": str(required).lower()}):
            try:
                result = asyncio.run(namespace["gateway_auth"](request(headers), api_key))
            except HTTPException as exc:
                return exc, events, data
        return result, events, data

    def test_valid_signed_service_selects_payer_before_lookup_and_validates_once(self):
        token = protocol.encode_service_call(SECRET, user_id=USER, payer_id=OTHER, chat_id=CHAT,
                                             model=MODEL, task="title_generation")
        result, events, data = self.run_gateway(token=token)
        self.assertNotIsInstance(result, HTTPException)
        self.assertEqual(result.user_id, OTHER)
        lookup = next(value for name, value in events if name == "assignment")
        self.assertEqual(lookup["where"]["user_id"], OTHER)
        self.assertEqual(events[0], ("decoder", "provenance.decode_service_call"))
        self.assertEqual(sum(name == "resolve" for name, value in events), 0)
        self.assertEqual(sum(name == "fresh" for name, value in events), 1)
        self.assertEqual(sum(name == "validate" for name, value in events), 1)
        self.assertEqual(data["metadata"]["spend_logs_metadata"]["owui_budget"]["actor_id"], USER)
        self.assertEqual(data["messages"], [{"role": "user", "content": "actual task context"}])
        self.assertNotIn(token, json.dumps(data))

    def test_raw_task_and_invalid_service_scope_fail_before_any_assignment(self):
        valid = protocol.encode_service_call(SECRET, user_id=USER, payer_id=OTHER, chat_id=CHAT,
                                             model=MODEL, task="title_generation")
        claims = protocol.decode_service_call(valid, SECRET, user_id=USER, model=MODEL, task="title_generation")
        for kwargs in ({}, {"token": "invalid"}, {"token": call()}, {"token": valid, "actor": OTHER},
                       {"token": valid, "task": "tags_generation"},
                       {"token": valid, "native_model": "other-model"},
                       {"token": valid, "body_model": "other-model"},
                       {"token": jwt.encode(claims | {"category": "service"}, SECRET, algorithm="HS256")},
                       {"token": valid, "api_key": "sk-native-test"}):
            result, events, data = self.run_gateway(**kwargs)
            with self.subTest(kwargs=list(kwargs)):
                self.assertIsInstance(result, HTTPException)
                self.assertEqual(result.status_code, 403)
                self.assertFalse(any(name in ("assignment", "resolve", "fresh", "validate") for name, value in events))

    def test_three_native_tasks_use_the_same_payer_and_unsigned_known_tasks_stay_denied(self):
        for task in ("title_generation", "tags_generation", "follow_up_generation"):
            token = protocol.encode_service_call(SECRET, user_id=USER, payer_id=OTHER, chat_id=CHAT,
                                                 model=MODEL, task=task)
            result, events, data = self.run_gateway(token=token, task=task)
            with self.subTest(task=task, signed=True):
                self.assertNotIsInstance(result, HTTPException)
                self.assertEqual(result.user_id, OTHER)
                self.assertEqual(next(value for name, value in events if name == "assignment")["where"]["user_id"], OTHER)
                self.assertEqual(sum(name == "validate" for name, value in events), 1)
                scope = protocol.validate_persisted_service_scope(data["metadata"]["spend_logs_metadata"]["owui_budget"])
                self.assertEqual((scope["actor_id"], scope["user_id"], scope["task"]), (USER, OTHER, task))
            result, events, _ = self.run_gateway(task=task)
            with self.subTest(task=task, signed=False):
                self.assertIsInstance(result, HTTPException)
                self.assertEqual(result.status_code, 403)
                self.assertFalse(any(name in ("assignment", "resolve", "fresh", "validate") for name, value in events))

    def test_resolved_and_validated_identity_must_belong_to_payer(self):
        token = protocol.encode_service_call(SECRET, user_id=USER, payer_id=OTHER, chat_id=CHAT,
                                             model=MODEL, task="title_generation")
        for kwargs in ({"resolved_user": USER}, {"validated_user": USER}):
            result, events, data = self.run_gateway(token=token, **kwargs)
            self.assertIsInstance(result, HTTPException)
            self.assertEqual(result.status_code, 403)
            self.assertEqual(sum(name == "validate" for name, value in events), int("validated_user" in kwargs))

    def test_service_audience_cannot_pass_empty_personal_task(self):
        token = protocol.encode_service_call(SECRET, user_id=USER, payer_id=OTHER, chat_id=CHAT,
                                             model=MODEL, task="title_generation")
        result, events, data = self.run_gateway(token=token, task="", assignment_user=USER)
        self.assertIsInstance(result, HTTPException)
        self.assertEqual(result.status_code, 403)
        self.assertFalse(any(name == "validate" for name, value in events))

    def test_personal_signed_path_still_selects_actor_and_keeps_original_scope(self):
        result, events, data = self.run_gateway(token=call(), task="", assignment_user=USER, required=True)
        self.assertNotIsInstance(result, HTTPException)
        self.assertEqual(result.user_id, USER)
        lookup = next(value for name, value in events if name == "assignment")
        self.assertEqual(lookup["where"]["user_id"], USER)
        scope = data["metadata"]["spend_logs_metadata"]["owui_budget"]
        self.assertEqual(protocol.validate_persisted_scope(scope), scope)
        self.assertEqual(data["litellm_session_id"], ROOT_CHAT)
        self.assertEqual(data["litellm_trace_id"], ROOT_ANSWER)
        self.assertEqual(sum(name == "validate" for name, value in events), 1)

    def test_inference_forwards_writer_fresh_blocked_identity_to_native_validator(self):
        # This exercises the adapter's read choice and exact validation input.
        # The native validator remains the blocked-key/reservation owner.
        result, events, _ = self.run_gateway(token=call(), task="", assignment_user=USER,
                                           required=True, fresh_blocked=True)
        self.assertNotIsInstance(result, HTTPException)  # External validator is an I/O double here.
        self.assertFalse(any(name == "resolve" for name, _ in events))
        fresh = [value for name, value in events if name == "fresh"]
        self.assertEqual(len(fresh), 1)
        self.assertIs(fresh[0]["check_db_only"], True)
        self.assertEqual(fresh[0]["hashed_token"], "synthetic-key-hash")
        validated = [value for name, value in events if name == "validate"]
        self.assertEqual(len(validated), 1)
        self.assertIs(validated[0]["valid_token"].blocked, True)
        self.assertEqual(validated[0]["valid_token"].user_id, USER)
        self.assertLess(next(i for i, (name, _) in enumerate(events) if name == "fresh"),
                        next(i for i, (name, _) in enumerate(events) if name == "validate"))

    def test_inference_writer_failure_never_falls_back_to_cached_identity(self):
        result, events, _ = self.run_gateway(token=call(), task="", assignment_user=USER,
                                           required=True, fresh_db_failure=True)
        self.assertIsInstance(result, HTTPException)
        self.assertEqual(result.status_code, 503)
        self.assertEqual(sum(name == "fresh" for name, _ in events), 1)
        self.assertFalse(any(name in ("resolve", "validate") for name, _ in events))

    def test_native_management_path_keeps_existing_identity_store(self):
        result, events, _ = self.run_gateway(task=None, api_key="sk-synthetic-operator",
                                           llm_route=False)
        self.assertNotIsInstance(result, HTTPException)
        self.assertEqual(sum(name == "resolve" for name, _ in events), 1)
        self.assertFalse(any(name == "fresh" for name, _ in events))
        validated = [value for name, value in events if name == "validate"]
        self.assertEqual(len(validated), 1)
        self.assertEqual(validated[0]["route"], "/key/info")


class DeclaredBufferedProfileTests(unittest.TestCase):
    """Real native Router descriptors; profile shape only, not native auth acceptance.

    Full proxy imports require the existing image's dependencies. These tests
    never replace validate_resolved_virtual_key with a successful fake.
    """
    @classmethod
    def setUpClass(cls):
        try:
            import litellm
            from litellm import Router
            from litellm.proxy._types import UserAPIKeyAuth
            from importlib.metadata import version
        except ImportError as exc:
            if os.environ.get("GOAL584_REQUIRE_BUFFERED_NATIVE_COMPONENT") == "1":
                raise RuntimeError("Mandatory native buffered auth component is unavailable") from exc
            raise unittest.SkipTest("Pinned native SDK unavailable; actual-image auth preflight remains required") from exc
        if version("litellm") != auth.REQUIRED_VERSION:
            if os.environ.get("GOAL584_REQUIRE_BUFFERED_NATIVE_COMPONENT") == "1":
                raise RuntimeError("Mandatory native buffered auth component requires exact SDK 1.105.1")
            raise unittest.SkipTest("Exact native SDK 1.105.1 is required")
        cls.Router = Router
        cls.Auth = UserAPIKeyAuth
        cls.litellm = litellm

    def setUp(self):
        costs = patch.dict(self.litellm.model_cost, copy.deepcopy(self.litellm.model_cost), clear=True)
        costs.start(); self.addCleanup(costs.stop)
        assignment = load("buffered_native_assignment", HERE.parents[1] / "assignment.py")
        self.assignment = assignment
        self.identity = self.Auth(user_id=USER, team_id=None, models=[MODEL],
            key_alias=assignment.assignment_alias(USER, MODEL), metadata=assignment.assignment_metadata(MODEL))
        self.symbols = patch.object(auth, "_assignment_matches", assignment.assignment_matches)
        self.symbols.start(); self.addCleanup(self.symbols.stop)

    def router(self, flags=(False,), *, modes=None, aliases=None):
        rows = []
        for index, flag in enumerate(flags):
            info = {"id": "buffered-test-" + str(index), "mode": (modes or ["responses"] * len(flags))[index]}
            if flag is not None:
                info["supports_native_streaming"] = flag
            rows.append({"model_name": MODEL, "litellm_params": {"model": "openai/gpt-4o-mini",
                        "api_key": "synthetic-local-not-a-provider-call"}, "model_info": info})
        router = self.Router(model_list=rows, model_group_alias=aliases or {})
        self.addCleanup(router.discard)
        return router

    def admit(self, router, data=None, *, path="/v1/responses", method="POST", identity=None):
        req = Request({"type": "http", "method": method, "path": path, "headers": [], "query_string": b""})
        body = {"model": MODEL, "input": [{"role": "user", "content": "unchanged actual context"}]} if data is None else data
        original = copy.deepcopy(body)
        try:
            return auth._require_declared_buffered_profile(req, body, identity or self.identity, router, path)
        finally:
            self.assertEqual(body, original)

    def test_all_native_deployments_false_accept_exact_responses_shapes(self):
        router = self.router((False, False))
        for route in ("/responses", "/v1/responses", "/openai/v1/responses"):
            for stream in (None, False, True):
                with self.subTest(route=route, stream=stream):
                    data = {"model": MODEL, "input": "same user context"}
                    if stream is not None:
                        data["stream"] = stream
                    self.assertIsNone(self.admit(router, data, path=route))

    def test_declared_profile_rejects_wrong_route_method_model_and_stream_type(self):
        router = self.router()
        cases = [("/v1/chat/completions", "POST", {"model": MODEL}),
                 ("/v1/responses", "GET", {"model": MODEL}),
                 ("/v1/responses/compact", "POST", {"model": MODEL}),
                 ("/v1/responses", "POST", {"model": "foreign"})]
        cases += [("/v1/responses", "POST", {"model": MODEL, "stream": value})
                  for value in ("true", "false", 0, 1, None, [], {})]
        for path, method, data in cases:
            with self.subTest(path=path, method=method, data=data), self.assertRaises(HTTPException) as caught:
                self.admit(router, data, path=path, method=method)
            self.assertEqual(caught.exception.status_code, 403)

    def test_mixed_or_nonresponses_native_descriptors_reject(self):
        for flags, modes in (((False, True), None), ((False, None), None), ((False,), ["chat"]),
                             ((False, False), ["responses", "chat"])):
            with self.subTest(flags=flags, modes=modes), self.assertRaises(HTTPException) as caught:
                self.admit(self.router(flags, modes=modes))
            self.assertEqual(caught.exception.status_code, 503)

    def test_all_false_native_router_alias_is_accepted(self):
        self.identity.models = ["buffered-alias"]
        self.identity.key_alias = self.assignment.assignment_alias(USER, "buffered-alias")
        self.identity.metadata = self.assignment.assignment_metadata("buffered-alias")
        router = self.router((False, False), aliases={"buffered-alias": MODEL})
        self.assertIsNone(self.admit(router, {"model": "buffered-alias", "stream": True}))

    def test_router_alias_expansion_includes_every_matching_deployment(self):
        self.identity.models = ["buffered-alias"]
        self.identity.key_alias = self.assignment.assignment_alias(USER, "buffered-alias")
        self.identity.metadata = self.assignment.assignment_metadata("buffered-alias")
        router = self.router((False, True), aliases={"buffered-alias": MODEL})
        with self.assertRaises(HTTPException) as caught:
            self.admit(router, {"model": "buffered-alias", "stream": True})
        self.assertEqual(caught.exception.status_code, 503)

    def test_known_client_router_paths_cannot_select_a_different_profile(self):
        router = self.router()
        for field in ("user_config", "router_settings_override", "specific_deployment", "fallbacks",
                      "context_window_fallbacks", "content_policy_fallbacks"):
            with self.subTest(field=field), self.assertRaises(HTTPException) as caught:
                self.admit(router, {"model": MODEL, "stream": True, field: {}})
            self.assertEqual(caught.exception.status_code, 403)

    def test_undeclared_legacy_and_noncanonical_identity_are_unchanged(self):
        for flags in ((True,), (None,), (True, None)):
            router = self.router(flags)
            self.assertIsNone(self.admit(router, {"model": MODEL, "stream": "legacy-shape"}, path="/chat/completions"))
        self.assertIsNone(self.admit(None, {"model": MODEL, "stream": True}))
        router = self.router()
        foreign = copy.deepcopy(self.identity); foreign.key_alias = "operator-native-key"
        self.assertIsNone(self.admit(router, {"model": MODEL, "stream": "legacy-shape"},
                                     path="/key/info", identity=foreign))
        # Caller model_info is not an authoritative profile declaration.
        self.assertIsNone(self.admit(self.router((True,)), {"model": MODEL, "stream": "legacy-shape",
            "model_info": {"supports_native_streaming": False, "mode": "responses"}}, path="/chat/completions"))


if __name__ == "__main__":
    unittest.main()
