"""Real client/provenance/proof owners over memory HTTP leaves; no native RBAC claim."""
import asyncio
import copy
from contextlib import redirect_stdout
from hashlib import sha256
import importlib.util
from io import BytesIO, StringIO
import json
import os
from pathlib import Path
import stat
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

HERE = Path(__file__).resolve().parent
BUDGETS = HERE.parents[1] / "deploy/openwebui-budgets"
sys.path[:0] = [str(HERE), str(BUDGETS)]
for name, filename in (("employee_budget_assignment", "assignment.py"),
                       ("employee_budget_admin_contract", "admin_contract.py"),
                       ("employee_budget_admin_client", "admin_client.py")):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, BUDGETS / filename)
        module = importlib.util.module_from_spec(spec); sys.modules[name] = module
        spec.loader.exec_module(module)
import prove_native_key_block as P
import prove_native_budgets as native_owner
import prove_service_tasks as provider_owner
import prove_gateway_auth as private_owner


class Response(BytesIO):
    headers = {}
    def __init__(self, status, payload):
        super().__init__(json.dumps(payload).encode()); self.code = self.status = status
        self.content = self
    async def __aenter__(self): return self
    async def __aexit__(self, *args): self.close()
    async def iter_chunked(self, size): yield self.read()


class Wire:
    """Native endpoints are explicit IO doubles, never a simulated RBAC acceptance."""
    def __init__(self):
        self.user = self.key = None; self.rows = []; self.physical = []; self.requests = []
        self.operator = "sk-" + "operator" * 8
        self.gateway = "gw-" + "gateway" * 8
        self.model = {"model_name": P.MODEL,
            "litellm_params": {"model": "openai/goal584-fake-a", "api_base": "http://provider:8000/v1"},
            "model_info": {"id": "goal584-deployment-a", "input_cost_per_token": .01, "output_cost_per_token": .02}}
        self.existing = self.orphan = self.ignored_block = self.dispatch_denial = False
        self.mutate_block = self.mutate_after_denial = None
        self.denial_status, self.denial_message = 401, P.BLOCK_MESSAGE
        self.foreign_assignment = False; self.nonpositive_usage = False
        self.wrong_log_nonce = False
        self.inference_claims = []

    def handle(self, method, url, headers, body=None, params=None):
        parsed = urlsplit(url); path = parsed.path
        query = params or {k: v[0] for k, v in parse_qs(parsed.query).items()}
        headers = {k.lower(): v for k, v in headers.items()}
        self.requests.append((method, path, copy.deepcopy(body), dict(headers), copy.deepcopy(query)))
        if parsed.hostname == "provider":
            assert method == "GET" and path == "/__proof/requests"
            return 200, {"synthetic": True, "requests": copy.deepcopy(self.physical)}
        if path != "/v1/chat/completions":
            assert headers["authorization"] == "Bearer " + self.operator
        if path == "/model/info": return 200, {"data": [copy.deepcopy(self.model)]}
        if path == "/user/info":
            if self.user is None and self.existing:
                self.user = {"user_id": query["user_id"], "user_role": "internal_user", "models": [P.MODEL],
                    "max_budget": 2, "spend": 0, "budget_duration": "1mo", "budget_reset_at": "2099-01-01T00:00:00Z"}
            if self.user is None: return 404, {"error": "not found"}
            assert self.user["user_id"] == query["user_id"]
            return 200, {"user_info": copy.deepcopy(self.user), "teams": [], "keys": []}
        if path == "/key/list":
            rows = [copy.deepcopy(self.key)] if self.key else []
            if self.orphan and not rows:
                rows = [{"token": "a" * 64, "user_id": query["user_id"], "key_alias": None, "metadata": None}]
            return 200, {"keys": rows, "current_page": 1, "total_count": len(rows), "total_pages": int(bool(rows))}
        if path == "/user/new":
            assert method == "POST" and self.user is None
            self.user = copy.deepcopy(body) | {"team_id": None, "budget_reset_at": "2099-01-01T00:00:00Z"}
            return 200, {"user_id": body["user_id"]}
        if path == "/key/generate":
            assert method == "POST" and self.key is None
            value = copy.deepcopy(body); token = value.pop("key")
            self.key = value | {"token": sha256(token.encode()).hexdigest(), "expires": None,
                                "budget_reset_at": "2099-01-01T00:00:00Z"}
            if self.foreign_assignment: self.key["models"] = ["foreign"]
            return 200, {"key": token}
        if path == "/key/info":
            assert query["key"] == self.key["token"]
            info = copy.deepcopy(self.key); info.pop("token")  # Actual pinned info_key_fn contract.
            return 200, {"key": query["key"], "info": info}
        if path == "/spend/logs/v2":
            assert query["user_id"] == self.user["user_id"]
            return 200, {"data": copy.deepcopy(self.rows), "total_pages": int(bool(self.rows))}
        if path == "/key/block":
            assert method == "POST" and body == {"key": self.key["token"]}
            if not self.ignored_block: self.key["blocked"] = True
            if self.mutate_block: self.mutate_block(self)
            return 200, {"token": self.key["token"], "blocked": True}  # Ack alone must not suffice.
        assert method == "POST" and path == "/v1/chat/completions"
        assert headers["authorization"] == "Bearer " + self.gateway
        assert headers[P.USER_ID_HEADER.lower()] == self.user["user_id"] and headers[P.TASK_HEADER.lower()] == ""
        claims = P.decode_call(body["litellm_metadata"][P.PROVENANCE_FIELD], self.gateway,
                               user_id=self.user["user_id"], model=P.MODEL)
        assert claims["chat_id"] == claims["root_chat_id"] and claims["answer_id"] == claims["root_answer_id"]
        assert set(body) == set(P.BODY) | {"litellm_metadata"}
        assert {k: body[k] for k in P.BODY} == P.BODY
        self.inference_claims.append(claims)
        if self.key["blocked"]:
            if self.dispatch_denial: self.physical.append({"id": "unexpected"})
            if self.mutate_after_denial: self.mutate_after_denial(self)
            return self.denial_status, {"error": {"type": "auth_error", "message": self.denial_message}}
        identifier = "chatcmpl-goal584-" + uuid4().hex
        self.physical.append({"id": identifier, "body": {"model": "goal584-fake-a",
            "messages": copy.deepcopy(P.BODY["messages"]), "max_tokens": 5}, "usage": copy.deepcopy(P.USAGE)})
        scope = {"schema": 1, "user_id": claims["sub"], "model": P.MODEL, "category": "personal",
                 "call_id": claims["jti"], **{k: claims[k] for k in ("chat_id", "answer_id", "root_chat_id", "root_answer_id")}}
        if self.wrong_log_nonce: scope["call_id"] = str(uuid4())
        self.rows.append({"request_id": "opaque-native-log-" + uuid4().hex, "user": self.user["user_id"],
            "api_key": self.key["token"], "model_group": P.MODEL, "model_id": "goal584-deployment-a",
            "status": "success", "spend": .2, **P.USAGE,
            "metadata": {"spend_logs_metadata": {"owui_budget": scope}}})
        self.user["spend"] = self.key["spend"] = .2
        usage = copy.deepcopy(P.USAGE)
        if self.nonpositive_usage: usage["total_tokens"] = 0
        return 200, {"id": identifier, "usage": usage}

    def open(self, request, timeout):
        body = json.loads(request.data) if request.data else None
        return Response(*self.handle(request.get_method(), request.full_url, dict(request.header_items()), body))

    def session(self, *, trust_env):
        assert trust_env is False
        wire = self
        class Session:
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
            def request(self, method, url, *, params, json, headers, allow_redirects, timeout):
                assert allow_redirects is False and timeout.total > 0
                return Response(*wire.handle(method, url, headers, json, params))
        return Session()


class NativeBlockTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        private = Path(self.temp.name) / "private"; private.mkdir(mode=0o700)
        self.state, self.receipt, operator = [private / n for n in ("block.private.json", "block.safe.json", "operator.private.json")]
        self.wire = Wire()
        if os.name == "nt":
            # Windows permission bits cannot represent the proxy's POSIX modes.
            # Model this filesystem leaf; keep the real private JSON writer/readback.
            self.enterContext(patch.object(private_owner.stat, "S_IMODE",
                side_effect=lambda mode: 0o700 if stat.S_ISDIR(mode) else 0o600))
        P.fixture.write_private(operator, {"schema": 1, "operator_token": self.wire.operator})
        for target, name, value in ((P, "STATE", self.state), (P, "RECEIPT", self.receipt),
                (P.fixture, "OPERATOR_STATE", operator), (P, "ClientSession", self.wire.session),
                (native_owner, "build_opener", lambda *a: self.wire),
                (provider_owner, "build_opener", lambda *a: self.wire)):
            self.enterContext(patch.object(target, name, value))
        self.enterContext(patch.dict(os.environ, {"OWUI_BUDGET_GATEWAY_SECRET": self.wire.gateway}))

    def run_proof(self):
        receipt = {"schema": 1, "proof": P.PROOF, "passed": False}
        return asyncio.run(P.execute(receipt))

    def test_real_client_signed_nonce_and_private_public_boundaries(self):
        receipt = self.run_proof()
        self.assertTrue(receipt["passed"])
        self.assertEqual(receipt["positive_cost_usd"], ".20")
        self.assertEqual(receipt["denied_http_status"], 401)
        self.assertTrue(self.wire.key["blocked"])
        posts = [(path, body) for method, path, body, *_ in self.wire.requests if method == "POST"]
        self.assertEqual([p for p, _ in posts], ["/user/new", "/key/generate", "/v1/chat/completions", "/key/block", "/v1/chat/completions"])
        self.assertEqual(posts[0][1]["models"], [P.MODEL])
        self.assertEqual(posts[0][1]["max_budget"], 2)
        self.assertEqual(posts[1][1]["metadata"], {"owui_budget_namespace": "user-model-v1", "owui_budget_model": P.MODEL})
        self.assertEqual(len({c["jti"] for c in self.wire.inference_claims}), 2)
        self.assertEqual(len({c["chat_id"] for c in self.wire.inference_claims}), 2)
        self.assertEqual(len(self.wire.physical), 1)
        private = P.fixture.read_private(self.state)
        self.assertEqual(private["before"]["rows"], [])
        self.assertEqual(private["positive"]["rows"], private["after"]["rows"])
        self.assertNotEqual(private["positive"]["rows"][0]["request_id"], private["provider_id"])
        P.no_credentials(receipt, [self.wire.operator, self.wire.gateway, posts[1][1]["key"]])
        self.assertFalse(receipt["l1_cache_warm_proven"])
        self.assertFalse(receipt["non_admin_management_tested"])
        self.assertFalse(receipt["unknown_usage_policy_qualified"])
        if os.name == "posix": self.assertEqual(stat.S_IMODE(self.state.stat().st_mode), 0o600)

    def test_non_synthetic_route_or_prices_abort_before_mutation(self):
        for section, field, value in (("litellm_params", "api_base", "https://paid.invalid/v1"),
                ("litellm_params", "model", "openai/paid"), ("model_info", "input_cost_per_token", .03)):
            with self.subTest(field=field):
                original = self.wire.model[section][field]
                self.wire.model[section][field] = value
                with self.assertRaisesRegex(P.ProofError, "non_synthetic"): self.run_proof()
                self.assertFalse(any(r[0] == "POST" for r in self.wire.requests))
                self.state.unlink()
                self.wire.model[section][field] = original

    def test_existing_user_is_not_repaired(self):
        self.wire.existing = True
        with self.assertRaises(P.BudgetAdminError): self.run_proof()
        self.assertFalse(any(r[0] == "POST" for r in self.wire.requests))

    def test_orphan_key_prevents_initialization(self):
        self.wire.orphan = True
        with self.assertRaises(P.BudgetAdminError): self.run_proof()
        self.assertFalse(any(r[0] == "POST" for r in self.wire.requests))

    def test_foreign_assignment_cannot_reach_inference(self):
        self.wire.foreign_assignment = True
        with self.assertRaises(P.BudgetAdminError): self.run_proof()
        self.assertFalse(self.wire.inference_claims)

    def test_wrong_actual_native_scope_nonce_rejects_positive_row(self):
        self.wire.wrong_log_nonce = True
        with self.assertRaisesRegex(P.ProofError, "positive_native_row"): self.run_proof()
        self.assertFalse(self.wire.key["blocked"])

    def test_wrong_actual_client_usage_cannot_establish_positive_control(self):
        self.wire.nonpositive_usage = True
        with self.assertRaisesRegex(P.ProofError, "positive_call_failed"): self.run_proof()
        self.assertFalse(self.wire.key["blocked"])

    def test_native_ack_without_blocked_get_fails(self):
        self.wire.ignored_block = True
        with self.assertRaisesRegex(P.ProofError, "block_commit_readback"): self.run_proof()
        self.assertEqual(len(self.wire.inference_claims), 1)

    def test_block_cannot_reset_spend(self):
        self.wire.mutate_block = lambda w: w.key.update(spend=0)
        with self.assertRaisesRegex(P.ProofError, "block_commit_readback"): self.run_proof()
        self.assertEqual(len(self.wire.inference_claims), 1)

    def test_block_cannot_change_cap(self):
        self.wire.mutate_block = lambda w: w.user.update(max_budget=0)
        with self.assertRaisesRegex(P.ProofError, "block_commit_readback"): self.run_proof()
        self.assertEqual(len(self.wire.inference_claims), 1)

    def test_history_rewrite_is_rejected(self):
        self.wire.mutate_block = lambda w: w.rows[0].update(total_tokens=999)
        with self.assertRaisesRegex(P.ProofError, "history_or_policy"): self.run_proof()

    def test_denial_cannot_dispatch_provider(self):
        self.wire.dispatch_denial = True
        with self.assertRaisesRegex(P.ProofError, "denial_dispatched"): self.run_proof()

    def test_unrelated_auth_denial_is_not_block_acceptance(self):
        self.wire.denial_message = "Wrong credentials"
        with self.assertRaisesRegex(P.ProofError, "expected_native_denial"): self.run_proof()

    def test_non_denial_http_status_is_not_block_acceptance(self):
        self.wire.denial_status = 200
        with self.assertRaisesRegex(P.ProofError, "expected_native_denial"): self.run_proof()

    def test_post_denial_charge_is_rejected(self):
        self.wire.mutate_after_denial = lambda w: w.rows.append({"request_id": "extra", "user": w.user["user_id"],
                                                               "spend": .1, "status": "failure"})
        with self.assertRaisesRegex(P.ProofError, "denial_added_charge"): self.run_proof()

    def test_zero_charge_auth_failure_audit_does_not_destroy_positive_history(self):
        self.wire.mutate_after_denial = lambda w: w.rows.append({"request_id": "auth-denial", "user": w.user["user_id"],
                                                               "spend": 0, "status": "failure"})
        receipt = self.run_proof()
        self.assertTrue(receipt["passed"])
        self.assertEqual(len(self.wire.rows), 2)
        self.assertEqual(self.wire.rows[0]["spend"], .2)

    def test_existing_safe_receipt_is_not_overwritten(self):
        original = {"schema": 1, "original_failure": "retain"}
        P.fixture.write_private(self.receipt, original)
        with redirect_stdout(StringIO()): self.assertEqual(P.main(), 1)
        self.assertEqual(P.fixture.read_private(self.receipt), original)
        self.assertFalse(self.wire.requests)

    def test_nonprivate_operator_file_fails_before_http(self):
        with patch.object(private_owner.stat, "S_IMODE", return_value=0o777):
            with self.assertRaises(P.ProofError): self.run_proof()
        self.assertFalse(self.wire.requests)

    def test_cli_retains_safe_failure_without_unblocking_or_reset(self):
        self.wire.dispatch_denial = True
        stdout = StringIO()
        with redirect_stdout(stdout): self.assertEqual(P.main(), 1)
        safe = P.fixture.read_private(self.receipt)
        self.assertFalse(safe["passed"])
        self.assertEqual(safe["failure"], "block_denial_dispatched_provider")
        self.assertTrue(self.wire.key["blocked"])
        self.assertEqual(self.wire.key["spend"], .2)
        P.no_credentials(json.loads(stdout.getvalue()), [self.wire.operator, self.wire.gateway])

    def test_worker_main_exports_only_safe_receipt_and_actual_owner_hashes(self):
        stdout = StringIO()
        with redirect_stdout(stdout): self.assertEqual(P.main(), 0)
        result = json.loads(stdout.getvalue())
        self.assertEqual(result, P.fixture.read_private(self.receipt))
        self.assertEqual(result["source_sha256"]["prove_native_key_block.py"],
                         sha256(Path(P.__file__).read_bytes()).hexdigest())
        self.assertIn("admin_client.py", result["source_sha256"])
        self.assertIn("provenance.py", result["source_sha256"])
        self.assertNotIn("rows", result)
        self.assertNotIn("scope", P.fixture.read_private(self.state)["before"])
        P.no_credentials(result, [self.wire.operator, self.wire.gateway])

    def test_late_actual_source_read_failure_cannot_publish_success(self):
        original_read = Path.read_bytes
        worker = Path(P.__file__).resolve()
        reads = []
        def fail_second_worker_read(path):
            if path.resolve() == worker:
                reads.append(path)
                if len(reads) == 2:
                    raise OSError("synthetic late source read failure")
            return original_read(path)
        stdout = StringIO()
        with patch.object(Path, "read_bytes", fail_second_worker_read), redirect_stdout(stdout):
            self.assertEqual(P.main(), 1)
        self.assertEqual(len(reads), 2)
        safe = P.fixture.read_private(self.receipt)
        self.assertEqual(safe, json.loads(stdout.getvalue()))
        self.assertFalse(safe["passed"])
        self.assertEqual(safe["failure"], "block_unexpected_worker_failure")
        self.assertNotIn("source_sha256", safe)
        self.assertNotIn("positive_cost_usd", safe)
        private = P.fixture.read_private(self.state)
        self.assertEqual(private["stage"], "complete")
        self.assertEqual(private["positive"]["rows"], private["after"]["rows"])
        self.assertTrue(self.wire.key["blocked"])
        self.assertEqual(len(self.wire.physical), 1)
        P.no_credentials(safe, [self.wire.operator, self.wire.gateway])

    def test_late_real_known_secret_guard_cannot_publish_success_or_candidate(self):
        # A non-key-shaped private credential matches a late candidate field.
        # Execute the real secret collector and guard; do not mock their failure.
        operator = P.fixture.read_private(P.fixture.OPERATOR_STATE)
        operator["password"] = ".20"
        P.fixture.write_private(P.fixture.OPERATOR_STATE, operator)
        stdout = StringIO()
        with redirect_stdout(stdout): self.assertEqual(P.main(), 1)
        safe = P.fixture.read_private(self.receipt)
        self.assertEqual(safe, json.loads(stdout.getvalue()))
        self.assertFalse(safe["passed"])
        self.assertEqual(safe["failure"], "Credential-bearing pricing evidence suppressed")
        self.assertNotIn("source_sha256", safe)
        self.assertNotIn("positive_cost_usd", safe)
        P.no_credentials(safe, [operator["password"], self.wire.operator, self.wire.gateway])
        private = P.fixture.read_private(self.state)
        self.assertEqual(private["stage"], "complete")
        self.assertEqual(private["positive"]["rows"], private["after"]["rows"])
        self.assertTrue(self.wire.key["blocked"])
        self.assertEqual(self.wire.key["spend"], .2)
        self.assertEqual(len(self.wire.physical), 1)


if __name__ == "__main__":
    unittest.main()
