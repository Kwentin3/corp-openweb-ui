"""Focused protocol and body/cache boundary checks, not a LiteLLM runtime proof.

Run with PyJWT 2.13 and FastAPI installed. The optional pinned-source check
executes the actual two native cache helpers, never a copied approximation.
"""

from __future__ import annotations

import ast
import copy
import importlib.util
import json
import logging
from pathlib import Path
import re
import time
import unittest

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
                    "headers": [(key.lower().encode(), value.encode()) for key, value in headers]})


def apply(data, *, shared=True, required=True, headers=(), chain_id=None, metadata_slot="metadata",
          metadata_session_id=None):
    auth._apply_provenance(request(headers), data, shared_gateway=shared, required=required,
                           secret=SECRET, user_id=USER, model=MODEL,
                           decoder=protocol.decode_call, chain_id=chain_id, metadata_slot=metadata_slot,
                           metadata_session_id=metadata_session_id)


def payload(token=None):
    return {"model": MODEL, "messages": [{"role": "user", "content": "Hi"}],
            "tools": [{"type": "function", "function": {"name": "test", "parameters": {}}}],
            "max_tokens": 5, "stream": True,
            "litellm_metadata": {"owui_budget_provenance": token or call()}}


class ProtocolTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
