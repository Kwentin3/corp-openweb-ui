"""Bounded native HTTP clock and administrator creation-order fixture checks."""
import copy
from contextlib import redirect_stdout
from datetime import datetime, timezone
from email.utils import format_datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from io import BytesIO, StringIO
import os
from pathlib import Path
import sys
import threading
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parents[1] / "deploy/openwebui-budgets")]
import provision_webui as P
import prove_gateway_auth as private_owner


CONTROL = "ffffffff-ffff-4fff-8fff-ffffffffffff"
OWNER = "11111111-1111-4111-8111-111111111111"  # Wins native UUID tie-break if timestamps tie.
CREATED = 1793664000


class NativeClockTests(unittest.TestCase):
    def setUp(self):
        self.records = {CONTROL: {"id": CONTROL, "role": "admin", "created_at": CREATED},
                        OWNER: {"id": OWNER, "role": "admin", "created_at": CREATED + 1}}
        self.dates, self.requests = [], []
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                owner.requests.append((self.path, self.headers.get("Authorization")))
                user_id = self.path.removeprefix("/api/v1/users/")
                if user_id not in owner.records:
                    self.send_error(404)
                    return
                data = json.dumps(owner.records[user_id]).encode()
                self.send_response_only(200)
                date = owner.dates.pop(0) if owner.dates else CREATED
                if date is not None:
                    self.send_header("Date", date if isinstance(date, str) else
                                     format_datetime(datetime.fromtimestamp(date, timezone.utc), usegmt=True))
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.target = patch.object(P, "WEBUI_URL", "http://127.0.0.1:" + str(self.server.server_port))
        self.target.start()
        self.webui = P.WebUI()
        self.control = {"id": CONTROL, "token": "synthetic-controller-session"}

    def tearDown(self):
        self.target.stop()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.assertFalse(self.thread.is_alive(), "Owned native-clock HTTP fixture did not stop")

    def state(self):
        return {"role_probe_control": self.control, "admin": {"id": OWNER, "token": "synthetic-owner-session"},
                "admin_creation_order": {"controller_created_at": CREATED, "server_second_before_owner_create": CREATED + 1}}

    def test_wait_uses_actual_response_date_and_rechecks_until_next_second(self):
        self.dates = [CREATED, CREATED, CREATED + 1]
        with patch.object(P.time, "sleep") as sleep:
            evidence = P.wait_after_controller_creation(self.webui, self.control)
        self.assertEqual(evidence, {"controller_created_at": CREATED, "server_second_before_owner_create": CREATED + 1})
        self.assertEqual(len(self.requests), 3)
        self.assertEqual(sleep.call_count, 2)
        self.assertEqual(self.requests, [("/api/v1/users/" + CONTROL, "Bearer synthetic-controller-session")] * 3)

    def test_server_already_in_later_second_needs_no_sleep(self):
        self.dates = [CREATED + 5]
        with patch.object(P.time, "sleep") as sleep:
            self.assertEqual(P.wait_after_controller_creation(self.webui, self.control)["server_second_before_owner_create"], CREATED + 5)
        sleep.assert_not_called()

    def test_stalled_server_date_times_out_without_using_runner_wall_clock(self):
        with patch.object(P.time, "monotonic", side_effect=[0.0, 1.0, 6.0]), patch.object(P.time, "sleep") as sleep:
            with self.assertRaisesRegex(P.ProofError, "clock did not advance"):
                P.wait_after_controller_creation(self.webui, self.control, timeout=5)
        self.assertEqual(len(self.requests), 2)
        sleep.assert_called_once_with(.1)

    def test_missing_or_invalid_date_never_reuses_previous_response_clock(self):
        for value in (None, "invalid native date"):
            self.dates = [CREATED + 1, value]
            P.native_admin_created_at(self.webui, self.control, self.control)
            self.assertEqual(self.webui.server_second, CREATED + 1)
            with self.subTest(date=value), self.assertRaisesRegex(P.ProofError, "HTTP Date is unavailable"):
                P.wait_after_controller_creation(self.webui, self.control)
            self.assertIsNone(self.webui.server_second)

    def test_strict_readback_rejects_uuid_tie_and_same_primary_identity(self):
        self.assertLess(OWNER, CONTROL)
        self.records[OWNER]["created_at"] = CREATED
        with self.assertRaisesRegex(P.ProofError, "strictly older"):
            P.read_admin_creation_order(self.webui, self.state())
        state = self.state()
        state["admin"]["id"] = CONTROL
        with self.assertRaisesRegex(P.ProofError, "ordering evidence is missing"):
            P.read_admin_creation_order(self.webui, state)

    def test_readback_binds_native_role_identity_and_timestamps(self):
        state = self.state()
        evidence = P.read_admin_creation_order(self.webui, state)
        self.assertEqual(evidence, {"controller_created_at": CREATED, "owner_created_at": CREATED + 1,
                                    "server_second_before_owner_create": CREATED + 1})
        state["admin_creation_order"] = evidence
        self.records[OWNER]["created_at"] += 1
        with self.assertRaisesRegex(P.ProofError, "strictly older"):
            P.read_admin_creation_order(self.webui, state)
        self.records[OWNER]["created_at"] -= 1
        for field, value in (("id", CONTROL), ("role", "user"), ("created_at", True), ("created_at", None)):
            original = copy.deepcopy(self.records[OWNER])
            self.records[OWNER][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(P.ProofError):
                P.read_admin_creation_order(self.webui, state)
            self.records[OWNER] = original


class OfficeServiceReadbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Reuse native TaskConfigForm/FunctionModel and actual existing Pipe
        # registration from the Office source fixture, not handwritten results.
        from test_office_compatibility import service_profile_inputs
        cls.native_inputs = service_profile_inputs.__wrapped__()

    def setUp(self):
        self.directory = self.enterContext(TemporaryDirectory(prefix="goal584-office-worker-"))
        self.path = Path(self.directory) / "webui-state.private.json"
        self.receipt = Path(self.directory) / "readback.safe.json"
        self.inputs = copy.deepcopy(self.native_inputs)
        admin = self.inputs["service_baseline"]["target_model"]["user_id"]
        actor = self.inputs["service_tasks"]["workspace_model"]["access_grants"][0]["principal_id"]
        self.state = {"schema": 1, "stage": "setup_complete", "admin": {"id": admin, "token": "synthetic-admin-token"},
            "users": [{"id": actor, "token": "synthetic-actor-token"}],
            "native_keys": [{"key": "sk-synthetic-private-key", "retain": [1, 2]}], "unrelated": {"keep": "whole"}}
        # Windows cannot report POSIX 0700/0600. Only these filesystem permission
        # observations are doubled there; the actual atomic writer/read path runs.
        if os.name == "nt":
            self.enterContext(patch.object(private_owner, "private_parent"))
            self.enterContext(patch.object(private_owner.stat, "S_IMODE", return_value=0o600))
        self.mode, self.requests, self.fault = "baseline", [], None
        self.source_fault = None
        self.open_modes = []
        original_open = private_owner.os.open
        def record_open(path, flags, mode=0o777, *args, **kwargs):
            self.open_modes.append(mode)
            return original_open(path, flags, mode, *args, **kwargs)
        self.enterContext(patch.object(private_owner.os, "open", side_effect=record_open))
        P.write_private(self.path, self.state)
        original_path_open = Path.open
        def mounted_source(path, *args, **kwargs):
            if path == Path("/proof/budgets/service_pipe.py"):
                if isinstance(self.source_fault, Exception): raise self.source_fault
                return BytesIO(self.source_fault if self.source_fault is not None else self.inputs["service_source"].encode("utf8"))
            return original_path_open(path, *args, **kwargs)
        self.enterContext(patch.object(Path, "open", mounted_source))
        owner = self
        class Response(BytesIO):
            code = 200
            headers = {}
        class NativeTransport:
            def open(self, request, timeout):
                method, path, token = request.get_method(), urlsplit(request.full_url).path, request.get_header("Authorization")
                query = parse_qs(urlsplit(request.full_url).query)
                owner.requests.append((method, path, query, token, request.data, timeout))
                if owner.fault:
                    result = owner.fault(method, path, query, token)
                    if isinstance(result, Exception): raise result
                    if isinstance(result, bytes): return Response(result)
                owner.assertEqual(method, "GET")
                owner.assertIsNone(request.data)
                owner.assertEqual(timeout, 20)
                if path == "/api/v1/auths/":
                    account, role = ((owner.state["admin"], "admin") if token == "Bearer synthetic-admin-token"
                        else (owner.state["users"][0], "user"))
                    value = {"id": account["id"], "role": role}
                elif path == "/api/models":
                    owner.assertEqual(query, {"refresh": ["true"]})
                    owner.assertEqual(token, "Bearer synthetic-actor-token")
                    value = {"data": [copy.deepcopy(owner.inputs["service_" + ("baseline" if owner.mode == "baseline" else "tasks")]["target_catalog"]),
                        {"id": "gpt-5.4-mini", "owned_by": "openai"}]}
                else:
                    owner.assertEqual(token, "Bearer synthetic-admin-token")
                    readback = owner.inputs["service_baseline" if owner.mode == "baseline" else "service_tasks"]
                    if path == "/api/v1/tasks/config": value = readback["task_config"]
                    elif path == "/api/v1/models/model":
                        model = query.get("id", [None])[0]
                        owner.assertIn(model, ("gpt-6-luna", "employee_budget_service"))
                        value = readback["target_model" if model == "gpt-6-luna" else "workspace_model"]
                    elif path == "/api/v1/functions/id/employee_budget_service": value = readback["function"]
                    elif path == "/api/v1/functions/id/employee_budget_service/valves": value = readback["valves"]
                    else: raise AssertionError("Unexpected native API path")
                return Response(json.dumps(value).encode("utf8"))
        self.enterContext(patch.object(P, "build_opener", return_value=NativeTransport()))
        self.enterContext(patch.object(P, "snapshot", side_effect=AssertionError("Readback must not run old snapshot or inference")))

    def phase(self, phase):
        output = StringIO()
        argv = ["provision_webui.py", "--phase", "office-service-" + phase,
            "--private-state", str(self.path), "--receipt", str(self.receipt)]
        with patch.object(sys, "argv", argv), redirect_stdout(output): result = P.main()
        safe = json.loads(output.getvalue())
        self.assertEqual(json.loads(self.receipt.read_text()), safe)
        self.assertTrue(safe["readback_only"])
        self.assertFalse(safe["native_office_accepted"])
        for private in ("synthetic-admin-token", "synthetic-actor-token", "sk-synthetic-private-key", "SERVICE_SYSTEM_SENTINEL",
                        "native_extra", "class Pipe:", "native-template-FOLLOW_UP_GENERATION_PROMPT_TEMPLATE", "PRIVATE_FAILURE_SENTINEL"):
            self.assertNotIn(private, output.getvalue())
        self.assertTrue(all(mode == 0o600 for mode in self.open_modes))
        return result, safe

    def successful_pair(self):
        self.assertEqual(self.phase("baseline")[0], 0)
        self.mode = "current"
        self.assertEqual(self.phase("current")[0], 0)

    def test_callable_baseline_current_reads_real_methods_paths_and_separate_tokens(self):
        task_params = self.inputs["service_baseline"]["task_config"]["TASK_MODEL_PARAMS"]
        self.assertIsNone(task_params.get("reasoning_effort"))
        self.assertEqual(task_params["custom_params"]["reasoning"]["effort"], "none")
        result, receipt = self.phase("baseline")
        self.assertEqual(result, 0)
        self.assertEqual(receipt["office_service_readback"]["status"], "baseline_collected")
        saved = P.read_private(self.path)
        self.assertEqual(saved["office_service_readback"], {"baseline": self.inputs["service_baseline"]})
        self.assertEqual({k: v for k, v in saved.items() if k != "office_service_readback"}, self.state)
        self.mode = "current"
        result, receipt = self.phase("current")
        self.assertEqual(result, 0)
        status = receipt["office_service_readback"]
        self.assertEqual(status["status"], "current_contract_checked")
        self.assertTrue(status["readback_only"])
        self.assertFalse(status["native_office_accepted"])
        self.assertEqual(len(status["observation_sha256"]), 64)
        self.assertEqual(len(status["trusted_source_sha256"]), 64)
        self.assertEqual(P.read_private(self.path)["office_service_readback"],
            {"baseline": self.inputs["service_baseline"], "current": self.inputs["service_tasks"]})
        self.assertEqual([(method, path, query, token) for method, path, query, token, _, _ in self.requests], [
            ("GET", "/api/v1/auths/", {}, "Bearer synthetic-admin-token"),
            ("GET", "/api/v1/auths/", {}, "Bearer synthetic-actor-token"),
            ("GET", "/api/v1/tasks/config", {}, "Bearer synthetic-admin-token"),
            ("GET", "/api/v1/models/model", {"id": ["gpt-6-luna"]}, "Bearer synthetic-admin-token"),
            ("GET", "/api/models", {"refresh": ["true"]}, "Bearer synthetic-actor-token"),
        ] * 2 + [
            ("GET", "/api/v1/functions/id/employee_budget_service", {}, "Bearer synthetic-admin-token"),
            ("GET", "/api/v1/functions/id/employee_budget_service/valves", {}, "Bearer synthetic-admin-token"),
            ("GET", "/api/v1/models/model", {"id": ["employee_budget_service"]}, "Bearer synthetic-admin-token")])

    def test_baseline_is_not_overwritten_and_current_needs_it_before_any_get(self):
        original = self.path.read_bytes()
        self.assertEqual(self.phase("current")[0], 1)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertFalse(self.requests)
        self.assertEqual(self.phase("baseline")[0], 0)
        original, count = self.path.read_bytes(), len(self.requests)
        self.assertEqual(self.phase("baseline")[0], 1)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(len(self.requests), count)

    def test_invalid_baseline_never_replaces_credentials_or_saves_observation(self):
        mutations = [lambda b: b["target_model"].update(id="foreign-target"),
            lambda b: b["target_model"].update(write_access=False), lambda b: b["target_model"].update(is_active=False),
            lambda b: b["target_catalog"].update(id="foreign-target"), lambda b: b["target_catalog"].update(pipe={"type": "pipe"}),
            lambda b: b["target_catalog"].update(owned_by="arena"), lambda b: b["task_config"].update(TASK_MODEL="foreign-selector")]
        original = self.path.read_bytes()
        for mutation in mutations:
            self.inputs = copy.deepcopy(self.native_inputs)
            mutation(self.inputs["service_baseline"])
            with self.subTest(mutation=mutation):
                self.assertEqual(self.phase("baseline")[0], 1)
                self.assertEqual(self.path.read_bytes(), original)

    def test_duplicate_or_malformed_catalog_does_not_save_baseline(self):
        original = self.path.read_bytes()
        for data in ([self.inputs["service_baseline"]["target_catalog"]] * 2, [None], [], "wrong"):
            self.fault = lambda m, p, q, t: json.dumps({"data": data}).encode() if p == "/api/models" else None
            with self.subTest(data=data):
                self.assertEqual(self.phase("baseline")[0], 1)
                self.assertEqual(self.path.read_bytes(), original)

    def test_current_pure_contract_rejects_changed_native_artifacts_and_retains_old_current(self):
        self.successful_pair()
        original = self.path.read_bytes()
        for field, change in (("target_model", lambda row: row["params"].update(system="foreign system")),
                ("function", lambda row: row.update(content="foreign source")),
                ("valves", lambda row: row.update(target_model_id="gpt-5.4-mini")),
                ("workspace_model", lambda row: row.update(params={"temperature": .81})),
                ("task_config", lambda row: row.update(ENABLE_FOLLOW_UP_GENERATION=False))):
            self.inputs = copy.deepcopy(self.native_inputs)
            change(self.inputs["service_tasks"][field])
            with self.subTest(field=field):
                code, receipt = self.phase("current")
                self.assertEqual(code, 1)
                self.assertTrue(receipt["failure"].startswith("office_service_"))
                self.assertEqual(self.path.read_bytes(), original)

    def test_current_pure_owner_rejects_coherent_legacy_top_level_task_reasoning(self):
        # Both observations agree, but equality alone cannot admit the wrong
        # native task shape. Baseline collection is not profile qualification.
        legacy = {"reasoning_effort": None, "custom_params": {"reasoning_effort": "none"}}
        for name in ("service_baseline", "service_tasks"):
            self.inputs[name]["task_config"]["TASK_MODEL_PARAMS"] = copy.deepcopy(legacy)
        self.assertEqual(self.phase("baseline")[0], 0)
        original = self.path.read_bytes()
        self.mode = "current"
        code, safe = self.phase("current")
        self.assertEqual(code, 1)
        self.assertEqual(safe["failure"], "office_service_task_config")
        self.assertEqual(self.path.read_bytes(), original)
        self.assertNotIn("current", P.read_private(self.path)["office_service_readback"])

    def test_native_transport_parse_bound_and_role_failures_keep_prior_current(self):
        self.successful_pair()
        original = self.path.read_bytes()
        faults = [lambda m, p, q, t: TimeoutError("PRIVATE_FAILURE_SENTINEL") if p == "/api/v1/tasks/config" else None,
            lambda m, p, q, t: b"PRIVATE_FAILURE_SENTINEL" if p == "/api/models" else None,
            lambda m, p, q, t: b"x" * (4 * 1024 * 1024 + 1) if p == "/api/models" else None,
            lambda m, p, q, t: json.dumps({"id": self.state["admin"]["id"], "role": "admin"}).encode()
                if p == "/api/v1/auths/" and t == "Bearer synthetic-actor-token" else None]
        for fault in faults:
            self.fault = fault
            with self.subTest(fault=fault):
                self.assertEqual(self.phase("current")[0], 1)
                self.assertEqual(self.path.read_bytes(), original)

    def test_source_import_and_atomic_writer_failures_keep_previous_private_bytes(self):
        self.successful_pair()
        original = self.path.read_bytes()
        for fault in (OSError("PRIVATE_FAILURE_SENTINEL"), b"x" * (128 * 1024 + 1), b"\xff"):
            self.source_fault = fault
            with self.subTest(fault=type(fault)):
                self.assertEqual(self.phase("current")[0], 1)
                self.assertEqual(self.path.read_bytes(), original)
        self.source_fault = None
        original_import = __import__
        def missing_validator(name, *args, **kwargs):
            if name == "prove_office_compatibility": raise ModuleNotFoundError("PRIVATE_FAILURE_SENTINEL")
            return original_import(name, *args, **kwargs)
        with patch("builtins.__import__", side_effect=missing_validator):
            self.assertEqual(self.phase("current")[0], 1)
        self.assertEqual(self.path.read_bytes(), original)
        original_replace = private_owner.os.replace
        def fail_private_replace(source, target):
            if Path(target) == self.path: raise OSError("PRIVATE_FAILURE_SENTINEL")
            return original_replace(source, target)
        with patch.object(private_owner.os, "replace", side_effect=fail_private_replace):
            self.assertEqual(self.phase("current")[0], 1)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertFalse(list(self.path.parent.glob(self.path.name + ".tmp-*")))


class OfficeSetupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        OfficeServiceReadbackTests.setUpClass.__func__(cls)
        import test_service_tasks
        cls.budget_module = sys.modules["employee_budget_admin_client"]

    def setUp(self):
        OfficeServiceReadbackTests.setUp(self)
        import hashlib
        from types import SimpleNamespace
        from officecli_openapi_proof.app import create_app
        from test_guidance_routes import RecordingOfficeCli
        self.office_path = Path(self.directory) / "office-state.private.json"
        self.actor_id = "22222222-2222-4222-8222-222222222222"
        self.gateway = "gw-synthetic-office-reservation-only"
        self.enterContext(patch.dict(os.environ, OWUI_BUDGET_GATEWAY_SECRET=self.gateway))
        self.enterContext(patch.object(P, "OPERATOR_STATE", Path(self.directory) / "operator.private.json"))
        P.write_private(P.OPERATOR_STATE, {"schema": 1, "operator_token": "sk-synthetic-office-operator"})
        self.state["users"].append({"id": "33333333-3333-4333-8333-333333333333", "token": "synthetic-old-second-token"})
        P.write_private(self.path, self.state)
        self.common_bytes = self.path.read_bytes()
        self.config = {"ENABLE_OPENAI_API": True, "OPENAI_API_BASE_URLS": ["http://proxy:4000/v1", "http://old-internal/v1"],
            "OPENAI_API_KEYS": [self.gateway, "synthetic-old-key"], "OPENAI_API_CONFIGS": {
                "0": {"enable": True, "model_ids": ["goal584-a"], "headers": {"X-OpenWebUI-User-Id": "{{USER_ID}}", "X-OpenWebUI-Task": "{{TASK}}"}},
                "1": {"enable": True, "api_type": "responses", "model_ids": ["goal584-b"], "headers": {"X-Preserve": "sentinel"}, "prefix_id": ""}}}
        self.before_config = copy.deepcopy(self.config)
        self.rows = {model: {"id": model, "name": model, "base_model_id": None, "user_id": self.state["admin"]["id"],
            "is_active": True, "write_access": True, "params": {"system": "OLD_SYSTEM_SENTINEL", "custom_params": {"keep": [1, "full"]}},
            "meta": {"capabilities": {"builtin_tools": False}}, "access_grants": []} for model in ("goal584-a", "goal584-b")}
        self.before_rows = copy.deepcopy(self.rows)
        root = HERE.parents[1]
        self.cost_source = (root / "deploy/openwebui-budgets/cost_filter.py").read_text(encoding="utf8")
        self.filter_source = (root / "deploy/openwebui-functions/officecli_auto_attach_filter.py").read_text(encoding="utf8")
        import importlib.util
        spec = importlib.util.spec_from_file_location("office_setup_filter_fixture", root / "deploy/openwebui-functions/officecli_auto_attach_filter.py")
        filter_owner = importlib.util.module_from_spec(spec)
        self.enterContext(patch.dict(sys.modules, {spec.name: filter_owner}))
        spec.loader.exec_module(filter_owner)
        self.native_filter_valves = filter_owner.Filter.Valves().model_dump()
        self.functions = {"employee_budget_cost": {"id": "employee_budget_cost", "type": "filter", "content": self.cost_source,
            "user_id": self.state["admin"]["id"], "is_active": True, "is_global": False, "meta": {}}}
        self.valves = {"employee_budget_cost": {"ledger_base_url": "http://proxy:4000"}}
        self.servers = {"TOOL_SERVER_CONNECTIONS": [{"url": "http://unrelated", "path": "openapi.json", "type": "openapi",
            "auth_type": "none", "forward_cookies": False, "headers": None, "key": None,
            "config": {"enable": False}, "info": {"id": "unrelated"}}]}
        self.tasks = copy.deepcopy(self.inputs["service_baseline"]["task_config"])
        self.chat_config = {"ENABLE_CONTEXT_COMPACTION": False, "CONTEXT_COMPACTION_MODEL": "",
            "CONTEXT_COMPACTION_TOKEN_CAP": 80000, "CONTEXT_COMPACTION_PROMPT_TEMPLATE": "PRIVATE_CHAT_CONTEXT",
            "ENABLE_TOOL_PERMISSIONS": False, "ENABLE_TOOL_SEARCH": False}
        self.openapi = create_app(RecordingOfficeCli()).openapi()
        self.aliases = [{"model_name": name, "litellm_params": {"api_base": "http://provider:8000/v1", "model": "openai/" + wire},
            "model_info": {"id": "synthetic-" + name, "mode": "responses", "input_cost_per_token": .01, "output_cost_per_token": .02}}
            for name, wire in (("gpt-5.4-mini", "goal584-fake-office"), ("gpt-6-luna", "goal584-fake-service-unqualified"))]
        self.native_reads, self.budget_requests, self.budget_user, self.budget_rows = [], [], None, []
        def native_ok(method, path):
            self.native_reads.append((method, path))
            self.assertEqual((method, path), ("GET", "/model/info"))
            return {"data": copy.deepcopy(self.aliases)}
        self.enterContext(patch.object(P, "native_client", return_value=SimpleNamespace(ok=native_ok)))
        original_open = Path.open
        def source_open(path, *args, **kwargs):
            if path == Path("/proof/officecli_auto_attach_filter.py"): return BytesIO(self.filter_source.encode())
            if path == Path("/proof/budgets/cost_filter.py"): return StringIO(self.cost_source)
            return original_open(path, *args, **kwargs)
        self.enterContext(patch.object(Path, "open", source_open))
        owner = self
        class Response(BytesIO):
            headers = {}
            def __init__(self, status, value):
                super().__init__(json.dumps(value).encode()); self.code = status
        class Transport:
            def open(self, request, timeout):
                method, path = request.get_method(), urlsplit(request.full_url).path
                query, token = parse_qs(urlsplit(request.full_url).query), request.get_header("Authorization")
                body = json.loads(request.data) if request.data else None
                owner.requests.append((method, path, query, token, body, timeout))
                if owner.fault:
                    value = owner.fault(method, path, query, token)
                    if isinstance(value, Exception): raise value
                if method == "POST":
                    saved = P.read_private(owner.office_path)
                    owner.assertFalse(saved["office_setup"]["journal"][-1]["returned"])
                    owner.assertEqual(token, "Bearer synthetic-admin-token")
                if path == "/api/v1/auths/":
                    accounts = [(owner.state["admin"], "admin"), *[(a, "user") for a in owner.state["users"]],
                        ({"id": owner.actor_id, "token": "synthetic-office-token"}, "user")]
                    account, role = next((a, role) for a, role in accounts if token == "Bearer " + a["token"])
                    value = {"id": account["id"], "role": role}
                elif path == "/api/v1/auths/add": value = {"id": owner.actor_id, "role": "user", "token": "synthetic-office-token"}
                elif path == "/openai/config": value = owner.config
                elif path == "/openai/config/update": owner.config = copy.deepcopy(body); value = body
                elif path == "/api/models":
                    value = {"data": []}
                    for idx, config in owner.config["OPENAI_API_CONFIGS"].items():
                        for model in config["model_ids"]:
                            row = owner.rows.get(model)
                            if row is None or token not in ("Bearer synthetic-admin-token", "Bearer synthetic-office-token") and model.startswith("gpt-"): continue
                            info = copy.deepcopy(row)
                            if token != "Bearer synthetic-admin-token": info["params"] = {}
                            value["data"].append({"id": model, "owned_by": "openai", "urlIdx": int(idx), "info": info})
                    if getattr(owner, "catalog_change", None): owner.catalog_change(value)
                elif path == "/api/v1/models/model":
                    model = query["id"][0]
                    if model not in owner.rows: return Response(404, {"detail": "absent"})
                    value = owner.rows[model]
                elif path in ("/api/v1/models/create", "/api/v1/models/model/update"):
                    value = copy.deepcopy(body) | {"user_id": owner.state["admin"]["id"], "write_access": True}
                    owner.rows[body["id"]] = value
                elif path == "/api/v1/configs/tool_servers":
                    if method == "POST": owner.servers = copy.deepcopy(body)
                    value = owner.servers
                elif path == "/api/v1/configs/tool_servers/verify": value = owner.openapi
                elif path == "/api/v1/functions/export":
                    value = [dict(f, valves=owner.valves.get(k, {})) for k, f in reversed(list(owner.functions.items()))]
                elif path == "/api/v1/functions/create":
                    value = copy.deepcopy(body) | {"type": "filter", "user_id": owner.state["admin"]["id"], "is_active": False, "is_global": False}
                    owner.functions[body["id"]] = value
                    owner.valves[body["id"]] = copy.deepcopy(owner.native_filter_valves)
                elif path.startswith("/api/v1/functions/id/"):
                    identifier = path.split("/")[5]; suffix = path.split(identifier, 1)[1]
                    if suffix == "/valves/update": owner.valves[identifier] = copy.deepcopy(body)
                    elif suffix == "/toggle": owner.functions[identifier]["is_active"] = not owner.functions[identifier]["is_active"]
                    elif suffix == "/toggle/global": owner.functions[identifier]["is_global"] = not owner.functions[identifier]["is_global"]
                    value = owner.valves[identifier] if suffix.startswith("/valves") else owner.functions[identifier]
                elif path == "/api/v1/tasks/config": value = owner.tasks
                elif path == "/api/v1/chats/config": value = owner.chat_config
                elif path == "/api/v1/tools/": value = [{"id": "server:officecli"}]
                else: raise AssertionError("Unexpected native Office setup path: " + path)
                return Response(200, copy.deepcopy(value))
        self.enterContext(patch.object(P, "build_opener", return_value=Transport()))
        async def budget_request(client, method, route, *, params=None, body=None):
            self.budget_requests.append((method, route, copy.deepcopy(params), copy.deepcopy(body)))
            uid = params.get("user_id") if params else body.get("user_id")
            self.assertEqual(uid, self.actor_id)
            if method == "POST":
                self.assertEqual(P.read_private(self.office_path)["office_setup"]["journal"][-1]["stage"], "native-budget-initialize-post")
                self.assertFalse(P.read_private(self.office_path)["office_setup"]["journal"][-1]["returned"])
            if route == "/user/info":
                if self.budget_user is None: raise self.budget_module.BudgetAdminError("native_http_404")
                return {"user_info": self.budget_user, "teams": []}
            if route == "/key/list": return {"keys": self.budget_rows, "current_page": 1, "total_count": len(self.budget_rows), "total_pages": int(bool(self.budget_rows))}
            if route == "/user/new": self.budget_user = dict(body, team_id=None, budget_reset_at="2099-01-01T00:00:00Z"); return {"user_id": "misleading POST"}
            if route == "/key/generate":
                row = copy.deepcopy(body); key = row.pop("key")
                row.update(token=hashlib.sha256(key.encode()).hexdigest(), expires=None, budget_reset_at="2099-01-01T00:00:00Z")
                self.budget_rows.append(row); return {"key": "misleading POST"}
            raise AssertionError("Unexpected native budget route")
        self.enterContext(patch.object(self.budget_module.BudgetAdminClient, "_request", budget_request))

    def setup_phase(self, *, office_path=True):
        output = StringIO()
        argv = ["provision_webui.py", "--phase", "office-setup", "--private-state", str(self.path), "--receipt", str(self.receipt)]
        if office_path: argv += ["--office-state", str(self.office_path)]
        with patch.object(sys, "argv", argv), redirect_stdout(output): result = P.main()
        safe = json.loads(output.getvalue())
        self.assertEqual(self.path.read_bytes(), self.common_bytes)
        for value in ("synthetic-admin-token", "synthetic-office-token", "sk-synthetic-office-operator", "OLD_SYSTEM_SENTINEL", "PRIVATE_CHAT_CONTEXT", "class Filter:", self.gateway):
            self.assertNotIn(value, output.getvalue())
        self.assertFalse(safe["native_office_accepted"])
        return result, safe

    def test_setup_creates_real_actor_handoff_preserves_old_routes_and_uses_actual_budget_owner(self):
        result, safe = self.setup_phase()
        self.assertEqual(result, 0, safe)
        saved = P.read_private(self.office_path)
        self.assertEqual(saved["stage"], "setup_complete")
        self.assertEqual(saved["users"][0]["id"], self.actor_id)
        self.assertEqual(safe["office_setup"]["status"], "readback_ready")
        self.assertEqual(self.rows["goal584-a"], self.before_rows["goal584-a"])
        self.assertEqual(self.rows["goal584-b"], self.before_rows["goal584-b"])
        self.assertEqual(self.config["OPENAI_API_BASE_URLS"][1:], self.before_config["OPENAI_API_BASE_URLS"])
        self.assertEqual(self.config["OPENAI_API_KEYS"][1:], self.before_config["OPENAI_API_KEYS"])
        self.assertEqual({str(int(k)-1): v for k, v in self.config["OPENAI_API_CONFIGS"].items() if k != "0"}, self.before_config["OPENAI_API_CONFIGS"])
        self.assertEqual(saved["office_setup"]["budget"]["models"][0]["model"], "gpt-5.4-mini")
        self.assertEqual(self.rows["gpt-5.4-mini"]["params"], {"function_calling": "native", "max_tokens": 1024,
            "custom_params": {"parallel_tool_calls": False, "store": False, "include": ["reasoning.encrypted_content"]}})
        self.assertEqual(P.Decimal(saved["office_setup"]["budget"]["max_budget"]), P.Decimal(1000))
        posts = [(route, body) for method, route, _, body in self.budget_requests if method == "POST"]
        self.assertEqual([route for route, _ in posts], ["/user/new", "/key/generate"])
        self.assertEqual(posts[0][1]["models"], ["gpt-5.4-mini"])
        self.assertEqual(posts[0][1]["max_budget"], 1000)
        self.assertEqual(posts[1][1]["max_budget"], 1000)
        self.assertEqual(self.servers["TOOL_SERVER_CONNECTIONS"][0]["info"]["id"], "unrelated")
        self.assertIn("terminal_file_extensions", saved["office_setup"]["valves"])
        self.assertEqual(self.tasks, self.inputs["service_baseline"]["task_config"])
        self.assertEqual(saved["office_setup"]["before"]["chat_config"], self.chat_config)
        self.assertEqual(self.rows["gpt-6-luna"]["params"], {})
        self.assertEqual(self.tasks["TASK_MODEL_PARAMS"]["custom_params"]["reasoning"]["effort"], "none")
        self.assertFalse(any("completions" in path or "responses" in path for _, path, *_ in self.requests))
        self.assertEqual(len([j for j in saved["office_setup"]["journal"] if j["stage"] == "native-budget-initialize-post"]), 2)
        # The existing readback phase accepts this actual new actor handoff.
        result = P.office_service_readback(P.WebUI(), saved, self.office_path, "office-service-baseline")
        self.assertEqual(result["office_service_readback"]["status"], "baseline_collected")

    def test_setup_preconditions_stop_before_signup_and_do_not_create_handoff(self):
        original = copy.deepcopy((self.aliases, self.config, self.filter_source))
        mutations = [lambda: self.aliases.pop(), lambda: self.aliases[0]["litellm_params"].update(api_base="https://external.invalid"),
            lambda: self.aliases[0]["model_info"].update(output_cost_per_token=.01),
            lambda: self.config["OPENAI_API_CONFIGS"].update(legacy={}), lambda: setattr(self, "filter_source", "foreign Filter")]
        for mutation in mutations:
            self.aliases, self.config, self.filter_source = copy.deepcopy(original)
            self.requests.clear(); mutation()
            with self.subTest(mutation=mutation):
                self.assertEqual(self.setup_phase()[0], 1)
                self.assertFalse(any(method == "POST" for method, *_ in self.requests))
                self.assertFalse(self.office_path.exists())
        self.assertEqual(self.setup_phase(office_path=False)[0], 1)

    def test_setup_partial_failure_is_journaled_never_retried_or_marked_ready(self):
        def stop(method, path, query, token):
            if method == "POST" and path == "/api/v1/models/create": return TimeoutError("PRIVATE_FAILURE_SENTINEL")
        self.fault = stop
        self.assertEqual(self.setup_phase()[0], 1)
        saved = P.read_private(self.office_path)
        self.assertEqual(saved["stage"], "office_setup_in_progress")
        self.assertEqual(saved["users"][0]["id"], self.actor_id)
        self.assertFalse(saved["office_setup"]["journal"][-1]["returned"])
        before = len(self.requests)
        self.assertEqual(self.setup_phase()[0], 1)
        self.assertEqual(len(self.requests), before)
        self.assertFalse(self.budget_requests)

    def test_setup_rejects_wrong_cached_route_or_changed_old_full_model_body_before_budget(self):
        def changed(payload):
            if "officecli_auto_attach_filter" not in self.functions: return
            for row in payload["data"]:
                if row["id"] == "goal584-a": row["info"]["params"]["system"] = "foreign old context"
        self.catalog_change = changed
        result, safe = self.setup_phase()
        self.assertEqual(result, 1)
        self.assertIn("existing native model body", safe["failure"])
        self.assertFalse(self.budget_requests)
        self.assertEqual(P.read_private(self.office_path)["stage"], "office_setup_in_progress")

    def test_setup_rejects_wrong_cached_connection_even_when_saved_model_body_is_unchanged(self):
        def changed(payload):
            if "officecli_auto_attach_filter" not in self.functions: return
            for row in payload["data"]:
                if row["id"] == "goal584-a": row["urlIdx"] = 0
        self.catalog_change = changed
        result, safe = self.setup_phase()
        self.assertEqual(result, 1)
        self.assertIn("logical connection changed", safe["failure"])
        self.assertFalse(self.budget_requests)
        self.assertEqual(self.rows["goal584-a"], self.before_rows["goal584-a"])

    def test_setup_never_reinitializes_an_existing_native_user_even_for_a_fresh_webui_actor(self):
        self.budget_user = {"user_id": self.actor_id, "user_role": "internal_user", "models": ["gpt-5.4-mini"],
            "teams": [], "team_id": None, "max_budget": 1000, "spend": 0, "budget_duration": "1mo", "budget_reset_at": "2099-01-01T00:00:00Z"}
        original = copy.deepcopy(self.budget_user)
        result, safe = self.setup_phase()
        self.assertEqual(result, 1)
        self.assertIn("initialization_requires_absence", safe["failure"])
        self.assertFalse(any(method == "POST" for method, *_ in self.budget_requests))
        self.assertEqual(self.budget_user, original)
        self.assertFalse(self.budget_rows)

    def test_setup_rejects_changed_full_native_valves_before_budget(self):
        def changed(method, path, query, token):
            if path.endswith("officecli_auto_attach_filter/valves") and self.functions.get("officecli_auto_attach_filter", {}).get("is_global"):
                self.valves["officecli_auto_attach_filter"]["terminal_file_extensions"] = ".foreign"
        self.fault = changed
        result, safe = self.setup_phase()
        self.assertEqual(result, 1)
        self.assertIn("Valves/scope", safe["failure"])
        self.assertFalse(self.budget_requests)

    def test_setup_requires_effective_compaction_false_before_signup(self):
        self.chat_config["ENABLE_CONTEXT_COMPACTION"] = True
        code, safe = self.setup_phase()
        self.assertEqual(code, 1)
        self.assertIn("context compaction must be disabled", safe["failure"])
        self.assertFalse(self.office_path.exists())
        self.assertFalse(any(method == "POST" for method, *_ in self.requests))

    def test_setup_rejects_chat_config_drift_and_retains_original_private_readback(self):
        original = copy.deepcopy(self.chat_config)
        def changed(method, path, query, token):
            if path == "/api/v1/chats/config" and "officecli_auto_attach_filter" in self.functions:
                self.chat_config["CONTEXT_COMPACTION_TOKEN_CAP"] = 12345
        self.fault = changed
        code, safe = self.setup_phase()
        self.assertEqual(code, 1)
        self.assertIn("chat config", safe["failure"])
        saved = P.read_private(self.office_path)
        self.assertEqual(saved["office_setup"]["before"]["chat_config"], original)
        self.assertEqual(saved["stage"], "office_setup_in_progress")


class OfficeServiceSetupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from test_service_tasks import ServiceInstallTargetTests
        cls.installer_fixture = ServiceInstallTargetTests
        ServiceInstallTargetTests.setUpClass.__func__(cls)

    def setUp(self):
        from urllib.parse import urlsplit
        import prove_service_tasks as service
        self.installer_fixture.setUp(self)
        self.service = service
        self.tasks.update(TASK_MODEL="goal584-a", TASK_MODEL_EXTERNAL="goal584-a")
        self.tasks.update({flag: False for flag in P.TASK_FLAGS})
        self.tasks["TASK_MODEL_PARAMS"] = {"reasoning_effort": None, "temperature": .17,
            "custom_params": {"reasoning": {"effort": "low", "summary": "auto", "native_extra": {"keep": [1, "full"]}},
                "vendor_params": {"keep": ["PRIVATE_TASK_SENTINEL", 2]}}}
        self.original_tasks = copy.deepcopy(self.tasks)
        self.task_posts, self.fail_task_post, self.after_task_post = [], None, None
        transport = P.WebUI().opener
        installed_open = transport.open
        owner = self
        class Response(BytesIO):
            headers = {}
            code = 200
        def task_open(request, timeout):
            if (request.get_method(), urlsplit(request.full_url).path) != ("POST", "/api/v1/tasks/config/update"):
                return installed_open(request, timeout)
            self.assertEqual(request.get_header("Authorization"), "Bearer synthetic-admin-token")
            self.assertEqual(timeout, 20)
            body = json.loads(request.data)
            saved = P.read_private(self.office_path)
            marker = saved["office_service_setup"]
            self.assertEqual(marker["stage"], "service_setup_in_progress")
            self.assertEqual(marker["original_tasks"], self.original_tasks)
            self.assertFalse(marker["journal"][-1]["returned"])
            self.assertEqual(marker["journal"][-1]["body"], body)
            self.task_posts.append(copy.deepcopy(body))
            if len(self.task_posts) == 1:
                self.assertNotIn("service_fixture", saved)
            else:
                self.assertEqual(saved["service_fixture"]["stage"], "setup_complete")
                self.assertIn("baseline", saved["office_service_readback"])
            if self.fail_task_post == len(self.task_posts): raise TimeoutError("PRIVATE_TASK_SENTINEL")
            self.tasks = copy.deepcopy(body)
            if self.after_task_post: self.after_task_post(len(self.task_posts), body)
            return Response(json.dumps(body).encode())
        self.enterContext(patch.object(transport, "open", side_effect=task_open))
        original_budget_request = service.BudgetAdminClient._request
        async def budget_request(client, method, route, **kwargs):
            if method == "POST":
                saved = P.read_private(self.office_path)
                self.assertIn("baseline", saved["office_service_readback"])
                self.assertNotIn("current", saved["office_service_readback"])
            return await original_budget_request(client, method, route, **kwargs)
        self.enterContext(patch.object(service.BudgetAdminClient, "_request", budget_request))

    def service_setup_phase(self):
        output = StringIO()
        argv = ["provision_webui.py", "--phase", "office-service-setup", "--private-state", str(self.office_path), "--receipt", str(self.receipt)]
        with patch.object(sys, "argv", argv), redirect_stdout(output): code = P.main()
        safe = json.loads(output.getvalue())
        self.assertFalse(safe["inference_issued"])
        self.assertFalse(safe["native_office_accepted"])
        for private in ("synthetic-admin-token", "synthetic-office-token", self.gateway, "PRIVATE_TASK_SENTINEL", "class Pipe:"):
            self.assertNotIn(private, output.getvalue())
        self.assertEqual(self.path.read_bytes(), self.common_bytes)
        return code, safe

    def test_callable_service_setup_prepares_baseline_installs_then_validates_real_current(self):
        with patch.object(self.service, "install", wraps=self.service.install) as installer:
            code, safe = self.service_setup_phase()
        self.assertEqual(code, 0, safe)
        self.assertEqual(installer.call_count, 1)
        self.assertEqual(installer.call_args.kwargs, {"target_model": "gpt-6-luna", "cap": P.Decimal(1000)})
        saved = P.read_private(self.office_path)
        marker = saved["office_service_setup"]
        self.assertEqual(marker["stage"], "readback_ready")
        self.assertEqual(marker["original_tasks"], self.original_tasks)
        baseline = copy.deepcopy(self.original_tasks)
        baseline.update(TASK_MODEL="gpt-6-luna", TASK_MODEL_EXTERNAL="gpt-6-luna", ENABLE_FOLLOW_UP_GENERATION=True)
        baseline["TASK_MODEL_PARAMS"]["custom_params"]["reasoning"]["effort"] = "none"
        self.assertEqual(self.task_posts, [baseline, {**baseline, "TASK_MODEL": "employee_budget_service", "TASK_MODEL_EXTERNAL": "employee_budget_service"}])
        self.assertEqual(marker["baseline_tasks"], baseline)
        self.assertTrue(all(entry["returned"] for entry in marker["journal"]))
        self.assertEqual(saved["office_service_readback"]["baseline"]["task_config"], baseline)
        self.assertEqual(saved["office_service_readback"]["current"]["task_config"], self.task_posts[-1])
        self.assertEqual(saved["office_service_readback"]["current"]["target_model"]["params"], {})
        self.assertEqual(saved["service_fixture"]["target_model_id"], "gpt-6-luna")
        self.assertEqual(saved["office_setup"]["models"], self.original_install_state["office_setup"]["models"])
        self.assertEqual([body["models"] for _, body in self.service_posts], [["gpt-6-luna"]] * 2)
        self.assertTrue(all(body["max_budget"] == 1000 for _, body in self.service_posts))
        self.assertEqual(safe["office_service_setup"]["status"], "readback_ready")
        self.assertFalse(safe["office_service_setup"]["actual_followup_accepted"])
        self.assertFalse(any("completions" in path or "responses" in path for _, path, *_ in self.service_requests))

    def test_legacy_nonnull_effort_and_malformed_nested_params_reject_before_posts(self):
        original = self.office_path.read_bytes()
        cases = [lambda p, v=v: p["custom_params"].update(reasoning_effort=v) for v in ("none", "low", False, "")]
        cases += [lambda p: p.update(custom_params=[]), lambda p: p["custom_params"].update(reasoning="none")]
        for change in cases:
            self.tasks = copy.deepcopy(self.original_tasks)
            change(self.tasks["TASK_MODEL_PARAMS"])
            with self.subTest(change=change):
                self.assertEqual(self.service_setup_phase()[0], 1)
                self.assertEqual(self.office_path.read_bytes(), original)
        self.assertFalse(self.task_posts)
        self.assertFalse(self.service_posts)

    def test_legacy_null_is_preserved_without_repairing_a_nonnull_override(self):
        self.tasks["TASK_MODEL_PARAMS"]["custom_params"]["reasoning_effort"] = None
        self.original_tasks = copy.deepcopy(self.tasks)
        code, safe = self.service_setup_phase()
        self.assertEqual(code, 0, safe)
        self.assertIsNone(self.task_posts[-1]["TASK_MODEL_PARAMS"]["custom_params"]["reasoning_effort"])
        self.assertEqual(self.task_posts[-1]["TASK_MODEL_PARAMS"]["custom_params"]["reasoning"]["effort"], "none")

    def test_target_or_source_prerequisite_failure_leaves_no_marker_or_native_post(self):
        original = self.office_path.read_bytes()
        self.rows["gpt-6-luna"]["params"] = {"custom_params": {"reasoning_effort": "none"}}
        self.assertEqual(self.service_setup_phase()[0], 1)
        self.rows = copy.deepcopy(self.original_rows)
        bad = Path(self.directory) / "oversized-service.py"
        bad.write_bytes(b"x" * (128 * 1024 + 1))
        with patch.object(self.service, "SOURCE", bad): self.assertEqual(self.service_setup_phase()[0], 1)
        self.assertEqual(self.office_path.read_bytes(), original)
        self.assertFalse(self.task_posts)
        self.assertFalse(self.service_posts)

    def test_failed_selector_update_keeps_baseline_installed_state_originals_and_blocks_rerun(self):
        self.fail_task_post = 2
        self.assertEqual(self.service_setup_phase()[0], 1)
        original = self.office_path.read_bytes()
        saved = P.read_private(self.office_path)
        self.assertEqual(saved["office_service_setup"]["stage"], "service_setup_in_progress")
        self.assertEqual(saved["office_service_setup"]["original_tasks"], self.original_tasks)
        self.assertFalse(saved["office_service_setup"]["journal"][-1]["returned"])
        self.assertEqual(saved["service_fixture"]["stage"], "setup_complete")
        self.assertIn("baseline", saved["office_service_readback"])
        self.assertNotIn("current", saved["office_service_readback"])
        counts = (len(self.task_posts), len(self.service_requests), len(self.service_posts))
        self.assertEqual(self.service_setup_phase()[0], 1)
        self.assertEqual(self.office_path.read_bytes(), original)
        self.assertEqual((len(self.task_posts), len(self.service_requests), len(self.service_posts)), counts)

    def test_native_task_readback_cannot_silently_drop_unrelated_nested_context(self):
        def drop(index, body): self.tasks["TASK_MODEL_PARAMS"]["custom_params"].pop("vendor_params")
        self.after_task_post = drop
        code, safe = self.service_setup_phase()
        self.assertEqual(code, 1)
        self.assertIn("task config readback differs", safe["failure"])
        saved = P.read_private(self.office_path)
        self.assertEqual(saved["office_service_setup"]["original_tasks"], self.original_tasks)
        self.assertNotIn("office_service_readback", saved)
        self.assertFalse(self.service_posts)

    def test_target_drift_at_selector_update_is_rejected_by_existing_pure_owner(self):
        def drift(index, body):
            if index == 2: self.rows["gpt-6-luna"]["params"]["system"] = "foreign target"
        self.after_task_post = drift
        code, safe = self.service_setup_phase()
        self.assertEqual(code, 1)
        self.assertEqual(safe["failure"], "office_service_target")
        saved = P.read_private(self.office_path)
        self.assertIn("baseline", saved["office_service_readback"])
        self.assertNotIn("current", saved["office_service_readback"])
        self.assertEqual(saved["office_service_setup"]["stage"], "service_setup_in_progress")

    def test_primary_drift_never_becomes_phase_readback_ready(self):
        def drift(index, body):
            if index == 2: self.rows["gpt-5.4-mini"]["params"]["max_tokens"] = 9
        self.after_task_post = drift
        code, safe = self.service_setup_phase()
        self.assertEqual(code, 1)
        self.assertIn("prepared model changed", safe["failure"])
        self.assertEqual(P.read_private(self.office_path)["office_service_setup"]["stage"], "service_setup_in_progress")

    def test_changed_mounted_pipe_between_baseline_and_install_cannot_pass_phase(self):
        source = Path(self.directory) / "service-pipe.py"
        source.write_bytes(self.service.SOURCE.read_bytes())
        def drift(index, body):
            if index == 1: source.write_bytes(source.read_bytes() + b"\n# changed source artifact\n")
        self.after_task_post = drift
        with patch.object(self.service, "SOURCE", source): code, safe = self.service_setup_phase()
        self.assertEqual(code, 1)
        self.assertIn("changed task/source baseline", safe["failure"])
        saved = P.read_private(self.office_path)
        self.assertIn("baseline", saved["office_service_readback"])
        self.assertNotIn("current", saved["office_service_readback"])
        self.assertEqual(len(self.task_posts), 1)


if __name__ == "__main__":
    unittest.main()
