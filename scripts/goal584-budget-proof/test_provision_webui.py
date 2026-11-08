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
        self.workflow_source = (root / "deploy/openwebui-skills/artifact-workflow.md").read_text(encoding="utf8")
        self.skills = {"unrelated-private": {"id": "unrelated-private", "user_id": self.state["admin"]["id"],
            "name": "Foreign Skill", "description": "Keep unchanged", "content": "PRIVATE_FOREIGN_SKILL",
            "is_active": False, "version_id": OWNER, "access_grants": [], "meta": {"tags": ["keep"]}}}
        self.before_skills = copy.deepcopy(self.skills)
        self.skill_fault = None
        self.history_fault = None
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
            if path == Path("/proof/artifact-workflow.md"): return BytesIO(self.workflow_source.encode())
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
                elif path == "/api/v1/skills/export":
                    value = [{"id": skill["id"], "name": skill["name"], "description": skill["description"],
                        "files": [{"path": "SKILL.md", "content": skill["content"]}], "meta": skill.get("meta", {}),
                        "is_active": skill["is_active"]} for skill in owner.skills.values()]
                elif path == "/api/v1/skills/create":
                    owner.assertEqual(body["id"], P.WORKFLOW_SKILL_ID)
                    owner.assertNotIn(body["id"], owner.skills)
                    skill = copy.deepcopy(body) | {"user_id": owner.state["admin"]["id"], "version_id": str(P.uuid.uuid4())}
                    owner.skills[body["id"]] = skill
                    value = {k: v for k, v in skill.items() if k != "content"}  # Native SkillResponse excludes content.
                elif path.startswith("/api/v1/skills/id/"):
                    identifier = path.split("/")[5]
                    skill = copy.deepcopy(owner.skills[identifier])
                    if owner.skill_fault and identifier == P.WORKFLOW_SKILL_ID:
                        owner.skill_fault(token, skill)
                    if "/history/" in path:
                        owner.assertEqual(path.rsplit("/", 1)[1], skill["version_id"])
                        value = {"id": skill["version_id"], "snapshot": {"name": skill["name"], "content": skill["content"]}}
                        if owner.history_fault: owner.history_fault(value)
                    else: value = skill | {"write_access": token == "Bearer synthetic-admin-token"}
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
        root = saved["office_setup"]["workflow_skill"]
        self.assertEqual(root["content"], self.workflow_source)
        self.assertEqual(root["version_id"], safe["office_setup"]["workflow_skill_version_id"])
        self.assertEqual(safe["office_setup"]["workflow_skill_sha256"], P.WORKFLOW_SKILL_SHA256)
        self.assertEqual(self.skills["unrelated-private"], self.before_skills["unrelated-private"])
        root_posts = [j for j in saved["office_setup"]["journal"] if j["stage"] == "/api/v1/skills/create"]
        self.assertEqual(len(root_posts), 1); self.assertTrue(root_posts[0]["returned"])
        self.assertEqual(root_posts[0]["body"]["content"], self.workflow_source)
        self.assertEqual(saved["office_setup"]["valves"]["artifact_workflow_skill_id"], P.WORKFLOW_SKILL_ID)
        self.assertFalse(any(path.endswith("/skills/id/unrelated-private/update") or path.endswith("/tasks/config/update")
            for _, path, *_ in self.requests))
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

    def test_exact_root_source_and_fresh_native_id_gate_before_any_post(self):
        original = self.workflow_source
        self.workflow_source = original[:-1]
        self.assertEqual(self.setup_phase()[0], 1)
        self.assertFalse(any(method == "POST" for method, *_ in self.requests))
        self.assertFalse(self.office_path.exists())
        self.workflow_source = original
        self.skills[P.WORKFLOW_SKILL_ID] = dict(self.skills["unrelated-private"], id=P.WORKFLOW_SKILL_ID)
        self.requests.clear()
        self.assertEqual(self.setup_phase()[0], 1)
        self.assertFalse(any(method == "POST" for method, *_ in self.requests))
        self.assertFalse(self.office_path.exists())

    def test_native_root_readback_rejects_content_version_acl_owner_and_inactive(self):
        mutations = {"content": self.workflow_source[:-1], "version_id": CONTROL,
            "access_grants": [], "user_id": CONTROL, "is_active": False}
        for field, value in mutations.items():
            with self.subTest(field=field):
                def fault(token, skill):
                    if token == "Bearer synthetic-office-token": skill[field] = value
                self.skill_fault = fault
                self.assertEqual(self.setup_phase()[0], 1)
                saved = P.read_private(self.office_path)
                self.assertEqual(saved["stage"], "office_setup_in_progress")
                self.assertTrue(saved["office_setup"]["journal"][-1]["returned"])
                self.assertEqual(saved["office_setup"]["journal"][-1]["stage"], "/api/v1/skills/create")
                self.assertFalse(self.budget_requests)
                before = len(self.requests)
                self.assertEqual(self.setup_phase()[0], 1)
                self.assertEqual(len(self.requests), before)
                self.office_path.unlink()
                self.skills = copy.deepcopy(self.before_skills)

    def test_workflow_create_timeout_preserves_unreturned_native_journal(self):
        def stop(method, path, query, token):
            if method == "POST" and path == "/api/v1/skills/create": return TimeoutError("PRIVATE_ROOT_CREATE")
        self.fault = stop
        self.assertEqual(self.setup_phase()[0], 1)
        saved = P.read_private(self.office_path)
        self.assertEqual(saved["stage"], "office_setup_in_progress")
        entry = saved["office_setup"]["journal"][-1]
        self.assertEqual(entry["stage"], "/api/v1/skills/create")
        self.assertFalse(entry["returned"])
        self.assertEqual(entry["body"]["content"], self.workflow_source)
        self.assertFalse(self.budget_requests)
        before = len(self.requests)
        self.assertEqual(self.setup_phase()[0], 1)
        self.assertEqual(len(self.requests), before)

    def test_native_snapshot_truncation_does_not_earn_ready_or_reach_budget(self):
        self.history_fault = lambda value: value["snapshot"].update(content=self.workflow_source[:-1])
        self.assertEqual(self.setup_phase()[0], 1)
        saved = P.read_private(self.office_path)
        self.assertEqual(saved["stage"], "office_setup_in_progress")
        self.assertNotIn("workflow_skill", saved["office_setup"])
        self.assertFalse(self.budget_requests)

    def test_unrelated_skill_acl_drift_cannot_be_claimed_preserved(self):
        def drift(method, path, query, token):
            if method == "POST" and path == "/api/v1/functions/create":
                self.skills["unrelated-private"]["access_grants"] = [
                    {"principal_type": "user", "principal_id": "*", "permission": "read"}]
        self.fault = drift
        self.assertEqual(self.setup_phase()[0], 1)
        saved = P.read_private(self.office_path)
        self.assertEqual(saved["stage"], "office_setup_in_progress")
        self.assertEqual(saved["office_setup"]["before"]["skills"]["unrelated-private"]["access_grants"], [])
        self.assertFalse(any(method == "POST" and "/api/v1/skills/id/unrelated-private" in path
            for method, path, *_ in self.requests))

    def test_workflow_mounts_bind_exact_git_sources_read_only(self):
        import yaml
        root = HERE.parents[1]
        config = yaml.safe_load((root / "compose/goal584.office-proof.yml").read_text(encoding="utf8"))
        mounts = {v["target"]: v for v in config["services"]["proxy"]["volumes"] if isinstance(v, dict)}
        for target, relative in (("/proof/artifact-workflow.md", "deploy/openwebui-skills/artifact-workflow.md"),
                ("/proof/corporate_template_models.json", "deploy/openwebui-tools/corporate_template_models.json"),
                ("/proof/corporate_templates.py", "deploy/openwebui-tools/corporate_templates.py")):
            mount = mounts[target]
            self.assertTrue(mount["read_only"]); self.assertFalse(mount["bind"]["create_host_path"])
            self.assertEqual((root / "compose" / mount["source"]).resolve(), (root / relative).resolve())

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


def native_publication_chat_get(record, actor):
    """Exact pinned native response owner; only DB/stream/context IO leaves."""
    import ast, asyncio, builtins
    from types import SimpleNamespace
    from pydantic import BaseModel, field_validator
    from starlette.requests import Request
    native = Path(os.environ.get('GOAL584_NATIVE_SOURCE_ROOT', str(HERE.parents[1]/
        'local/goal584/cost-display/open-webui/backend/open_webui')))
    model = (native/'models/chats.py').read_bytes().replace(b'\r\n', b'\n')
    routes = (native/'routers/chats.py').read_bytes().replace(b'\r\n', b'\n')
    assert P.sha256(model).hexdigest() == 'b784d932eb521cc0d20f1ce753285d4f7951e32232578feccbb07d4e86305faa'
    assert P.sha256(routes).hexdigest() == '510269b6f69c8f634d2d93a6dc0605453fd5ececebf55c3ef3575532b3bc5eb3'
    user = SimpleNamespace(**actor)
    class UsersIO:
        @staticmethod
        async def get_users_by_user_ids(ids, db=None):
            assert ids == [user.id]
            return [user]
    original_import = builtins.__import__
    def dependency_import(name, *args, **kwargs):
        if name == 'open_webui.models.users': return SimpleNamespace(Users=UsersIO)
        return original_import(name, *args, **kwargs)
    namespace = {'BaseModel': BaseModel, 'field_validator': field_validator,
        '__builtins__': dict(vars(builtins), __import__=dependency_import)}
    response = next(node for node in ast.parse(model).body if isinstance(node, ast.ClassDef) and node.name == 'ChatResponse')
    exec(compile(ast.Module(body=[response], type_ignores=[]), 'exact-native-chat-response', 'exec'), namespace)
    nodes = [node for node in ast.parse(routes).body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in ('shared_chat_response', 'overlay_response_streams', 'get_chat_by_id')]
    assert len(nodes) == 3
    for node in nodes:
        node.decorator_list = []
        if node.name == 'get_chat_by_id': node.args.defaults = []  # Explicit user/db instead of FastAPI injection.
    chat = SimpleNamespace(**copy.deepcopy(record), title=record['chat']['title'], created_at=1, updated_at=1, archived=False)
    class ChatsIO:
        @staticmethod
        async def get_accessible_chat_by_id(identifier, current_user, **kwargs):
            assert identifier == chat.id and current_user.id == user.id
            return chat
    async def streams_io(*args): return []
    async def context_io(*args): return None
    namespace.update(Chats=ChatsIO, get_response_streams_by_chat_id=streams_io, get_chat_context_usage=context_io)
    module = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), *nodes], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), 'exact-native-chat-get', 'exec'), namespace)
    request = Request({'type': 'http', 'app': SimpleNamespace(state=SimpleNamespace(redis=None))})
    return asyncio.run(namespace['get_chat_by_id'](chat.id, request, user, None))


class PublicationHTTPWorld:
    """Explicit native API IO leaves for the unchanged real publisher owner."""
    def __init__(self, owner, actor, *, files=None, skills=None, fault=None):
        self.owner, self.actor, self.fault = owner, actor, fault
        self.files = {} if files is None else files
        self.skills = {} if skills is None else skills
        self.knowledge_id = '88888888-1111-4111-8111-111111111111'
        self.knowledge, self.chats, self.processed, self.linked, self.requests = None, {}, set(), set(), []
        self.config = {'status': True, 'BYPASS_EMBEDDING_AND_RETRIEVAL': False,
            'RAG_TEMPLATE': 'PRIVATE_RAG_TEMPLATE', 'TOP_K': 7, 'web': {'KEEP_PRIVATE': ['a', 9]}}
        self.baseline = copy.deepcopy(self.config)

    def route(self, method, path, token, body=None, query=None):
        self.requests.append((method, path, token, copy.deepcopy(body)))
        if self.fault:
            result = self.fault(self, method, path, token, body)
            if result is not None: return result
        if path == '/api/v1/auths/':
            return 200, {'id': OWNER if token == 'Bearer synthetic-admin-token' else self.actor,
                         'role': 'admin' if token == 'Bearer synthetic-admin-token' else 'user',
                         'name': 'Synthetic administrator' if token == 'Bearer synthetic-admin-token' else 'Synthetic employee'}
        if path == '/api/v1/retrieval/config': return 200, copy.deepcopy(self.config)
        if path == '/api/v1/retrieval/config/update':
            assert set(body) == {'BYPASS_EMBEDDING_AND_RETRIEVAL'}
            self.config.update(copy.deepcopy(body)); return 200, copy.deepcopy(self.config)
        if path == '/api/v1/knowledge/create':
            assert self.config['BYPASS_EMBEDDING_AND_RETRIEVAL'] is True
            self.knowledge = copy.deepcopy(body) | {'id': self.knowledge_id, 'user_id': OWNER}
            return 200, copy.deepcopy(self.knowledge)
        if path.startswith('/api/v1/knowledge/'):
            base = '/api/v1/knowledge/' + self.knowledge_id
            assert path.startswith(base)
            value = copy.deepcopy(self.knowledge) | {'write_access': token == 'Bearer synthetic-admin-token'}
            if path == base: return 200, value
            if path.endswith('/file/add'):
                assert self.config['BYPASS_EMBEDDING_AND_RETRIEVAL'] is True and body['file_id'] in self.processed
                self.linked.add(body['file_id'])
                return 200, value | {'files': [{'id': identifier} for identifier in self.linked]}
            if path.endswith('/files'):
                return 200, {'total': len(self.linked), 'items': [{'id': identifier} for identifier in self.linked]}
        if path == '/api/v1/chats/new':
            identifier = str(P.uuid.uuid4())
            self.chats[identifier] = {'id': identifier, 'user_id': OWNER, 'chat': copy.deepcopy(body['chat'])}
            return 200, copy.deepcopy(self.chats[identifier])
        if path.startswith('/api/v1/chats/'):
            return 200, native_publication_chat_get(self.chats[path.rsplit('/', 1)[1]],
                {'id': OWNER, 'name': 'Synthetic administrator', 'role': 'admin'})
        if path == '/api/v1/skills/create':
            value = copy.deepcopy(body) | {'user_id': OWNER, 'write_access': True, 'meta': {}, 'version_id': str(P.uuid.uuid4())}
            self.skills[body['id']] = value
            return 200, {k: v for k, v in value.items() if k != 'content'}
        if path.startswith('/api/v1/skills/id/'):
            identifier = path.split('/')[5]; value = self.skills[identifier]
            if path.endswith('/update'):
                assert body['expected_version_id'] == value['version_id']
                value.update(copy.deepcopy(body) | {'version_id': str(P.uuid.uuid4())})
            if path.endswith('/files'):
                return 200, {'version_id': value['version_id'], 'files': [
                    {'path': 'SKILL.md', 'size': len(value['content'].encode('utf8')), 'encoding': None}]}
            return 200, copy.deepcopy(value)
        if path == '/api/v1/retrieval/process/file':
            assert self.config['BYPASS_EMBEDDING_AND_RETRIEVAL'] is True and body['file_id'] in self.files
            self.processed.add(body['file_id'])
            return 200, {'status': True}  # Explicit modeled extraction response, never runtime evidence.
        if path.startswith('/api/v1/files/'):
            identifier = path.split('/')[4]
            if path.endswith('/content'): return 200, self.files[identifier]
            return 200, {'id': identifier, 'user_id': self.actor, 'filename': 'goal584-delegated-source.docx',
                'path': 'native-saved-original/' + identifier + '.docx',
                'data': {'content': 'Modeled HTTP leaf extraction result'} if identifier in self.processed else {}}
        raise AssertionError((method, path))

    def session(self, **options):
        world = self
        if 'base_url' in options:
            assert options['base_url'] == P.WEBUI_URL and options['trust_env'] is False
            assert options['headers'] == {'Authorization': 'Bearer synthetic-admin-token'}
        class Response:
            def __init__(self, status, value): self.status, self.value = status, value
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
            async def json(self): return copy.deepcopy(self.value)
        class Session:
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
            def request(self, method, path, *, allow_redirects, json=None, params=None):
                assert allow_redirects is False
                return Response(*world.route(method, path, 'Bearer synthetic-admin-token', json, params))
        return Session()


class DelegatedPublicationTests(unittest.TestCase):
    def test_actual_native_config_form_submits_only_the_single_owned_flag(self):
        import ast
        from pydantic import BaseModel, Field
        from typing import Union
        native = Path(os.environ.get('GOAL584_NATIVE_SOURCE_ROOT', str(HERE.parents[1]/
            'local/goal584/cost-display/open-webui/backend/open_webui')))
        raw = (native/'routers/retrieval.py').read_bytes()
        nodes = [node for node in ast.parse(raw).body if isinstance(node, ast.ClassDef)
            and node.name in {'WebConfig', 'ConfigForm'}]
        self.assertEqual(len(nodes), 2)
        namespace = {'BaseModel': BaseModel, 'Field': Field, 'Union': Union}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), 'exact-native-retrieval-forms', 'exec'), namespace)
        for value in (False, True):
            form = namespace['ConfigForm'].model_validate({'BYPASS_EMBEDDING_AND_RETRIEVAL': value})
            self.assertEqual(form.model_dump(exclude={'web'}, exclude_none=True), {'BYPASS_EMBEDDING_AND_RETRIEVAL': value})

    def test_actual_native_knowledge_metadata_embedding_failure_is_best_effort(self):
        import ast, asyncio
        from types import SimpleNamespace
        native = Path(os.environ.get('GOAL584_NATIVE_SOURCE_ROOT', str(HERE.parents[1]/
            'local/goal584/cost-display/open-webui/backend/open_webui')))
        raw = (native/'routers/knowledge.py').read_bytes()
        nodes = [node for node in ast.parse(raw).body if isinstance(node, ast.AsyncFunctionDef)
            and node.name == 'embed_knowledge_base_metadata']
        self.assertEqual(len(nodes), 1)
        attempted = []
        async def embedding_leaf(content, **kwargs):
            attempted.append((content, kwargs)); raise RuntimeError('synthetic inactive embedding leaf')
        namespace = {'Request': object, 'RAG_EMBEDDING_CONTENT_PREFIX': 'document:',
            'log': SimpleNamespace(error=lambda *args: None)}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), 'exact-native-metadata-owner', 'exec'), namespace)
        request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(EMBEDDING_FUNCTION=embedding_leaf,
            BYPASS_EMBEDDING_AND_RETRIEVAL=True)))
        self.assertFalse(asyncio.run(namespace['embed_knowledge_base_metadata'](request, 'native-id', 'Synthetic', 'Agreed')))
        self.assertEqual(len(attempted), 1)

    def exercise(self, fault=None):
        import aiohttp, types
        raw = (HERE.parents[1]/'deploy/openwebui-tools/corporate_templates.py').read_bytes().replace(b'\r\n', b'\n')
        self.assertEqual(P.sha256(raw).hexdigest(), P.TEMPLATE_PUBLISHER_SHA256)
        publisher = types.ModuleType('goal584_exact_publisher_test')
        exec(compile(raw, 'exact-current-publisher', 'exec'), publisher.__dict__)
        actor = {'id': CONTROL, 'token': 'synthetic-actor-token'}
        file_id, skill_id = '77777777-1111-4111-8111-111111111111', 'goal584-source'
        raw_source = P.delegated_source_docx()
        original_skill = {'id': skill_id, 'user_id': OWNER, 'name': 'Synthetic instructions', 'description': 'Agreed',
            'content': P.delegated_skill_content(file_id, P.sha256(raw_source).hexdigest()),
            'version_id': OWNER, 'write_access': True, 'is_active': True, 'meta': {},
            'access_grants': [{'principal_type': 'user', 'principal_id': CONTROL, 'permission': 'read'}]}
        world = PublicationHTTPWorld(self, CONTROL, files={file_id: raw_source}, skills={skill_id: copy.deepcopy(original_skill)}, fault=fault)
        state = {'schema': 1, 'admin': {'id': OWNER, 'token': 'synthetic-admin-token'}, 'office_delegation_setup': {
            'stage': 'preparing', 'journal': [], 'actor': actor, 'source_file': {'id': file_id, 'filename': 'goal584-delegated-source.docx'},
            'source_sha256': P.sha256(raw_source).hexdigest(), 'skill': copy.deepcopy(original_skill)}}
        class Response(BytesIO):
            headers = {}
            def __init__(self, status, value):
                super().__init__(value if isinstance(value, bytes) else json.dumps(value).encode()); self.code = status
        class Transport:
            def open(self, request, timeout):
                parts = urlsplit(request.full_url)
                return Response(*world.route(request.get_method(), parts.path, request.get_header('Authorization'),
                    json.loads(request.data) if request.data else None, parse_qs(parts.query)))
        with TemporaryDirectory() as directory:
            path = Path(directory)/'publication.private.json'
            if os.name == 'nt':
                self.enterContext(patch.object(private_owner, 'private_parent'))
                self.enterContext(patch.object(private_owner.stat, 'S_IMODE', return_value=0o600))
            def before(stage, body=None):
                state['office_delegation_setup']['journal'].append({'stage': stage, 'body': copy.deepcopy(body), 'returned': False})
                P.write_private(path, state)
            def post(route, body):
                before(route, body)
                value = webui.ok('POST', route, token=state['admin']['token'], body=body)
                state['office_delegation_setup']['journal'][-1].update(returned=True, response=value)
                P.write_private(path, state)
                return value
            error = None
            with patch.object(P, 'build_opener', return_value=Transport()), patch.object(aiohttp, 'ClientSession', world.session):
                webui = P.WebUI()
                try: P.publish_delegated_template(webui, state, path, publisher, before, post)
                except (P.ProofError, ValueError) as caught: error = caught
            saved = P.read_private(path)
        return error, saved['office_delegation_setup'], world, original_skill

    def test_actual_publisher_full_skill_native_binding_and_scoped_restore(self):
        error, selected, world, original = self.exercise()
        self.assertIsNone(error)
        self.assertEqual(selected['publication']['stage'], 'readback_ready')
        self.assertTrue(selected['publication']['config_restored']); self.assertEqual(world.config, world.baseline)
        self.assertEqual(selected['publication']['receipt']['status'], 'published')
        self.assertTrue(selected['skill']['content'].startswith(original['content'].rstrip()))
        self.assertNotEqual(selected['skill']['version_id'], original['version_id'])
        self.assertIn('## Original template', selected['skill']['content'])
        self.assertEqual(selected['publication']['membership']['total'], 1)
        self.assertEqual(selected['publication']['saved_turn']['user_id'], OWNER)
        self.assertTrue(all(message['role'] == 'user' for message in selected['publication']['saved_turn']['chat']['messages']))

    def test_exact_native_get_reproduces_old_failure_and_preserves_full_record(self):
        error, selected, world, _ = self.exercise()
        self.assertIsNone(error)
        actual = selected['publication']['saved_turn']
        submitted = world.chats[actual['id']]['chat']
        self.assertNotEqual(actual['chat'], submitted)  # Old source failed here before publisher invocation.
        self.assertEqual(actual['chat']['share_mode'], 'continue')
        before = copy.deepcopy((actual, submitted))
        P.validate_publication_turn(actual, submitted, actual['id'],
            {'id': OWNER, 'name': 'Synthetic administrator', 'role': 'admin'})
        self.assertEqual((actual, submitted), before)
        for message in [*actual['chat']['history']['messages'].values(), *actual['chat']['messages']]:
            self.assertEqual(message['user_id'], OWNER)
            self.assertEqual(message['user'], {'id': OWNER, 'name': 'Synthetic administrator'})

    def test_native_enrichment_does_not_relax_any_submitted_field_or_author_scope(self):
        error, selected, world, _ = self.exercise()
        self.assertIsNone(error)
        original = selected['publication']['saved_turn']; submitted = world.chats[original['id']]['chat']
        admin = {'id': OWNER, 'name': 'Synthetic administrator', 'role': 'admin'}
        mutations = [lambda r:r.update(id=CONTROL), lambda r:r.update(user_id=CONTROL),
            lambda r:r['chat'].update(share_mode=None), lambda r:r['chat'].update(models=['foreign']),
            lambda r:r['chat'].update(params={'foreign':True}), lambda r:r['chat'].update(tags=['foreign']),
            lambda r:r['chat'].update(timestamp=0), lambda r:r['chat'].update(title='changed'),
            lambda r:r['chat'].update(extra='unsupported'), lambda r:r['chat']['history'].update(currentId=CONTROL),
            lambda r:r['chat']['history']['messages'].clear(), lambda r:r['chat']['messages'].append({})]
        for location in ('history', 'messages'):
            for field, value in (('id', CONTROL), ('role','assistant'), ('content','truncated'), ('parentId',CONTROL),
                    ('childrenIds',[CONTROL]), ('timestamp',0), ('user_id',CONTROL),
                    ('user',{'id':CONTROL,'name':'Synthetic administrator'}), ('user',{'id':OWNER,'name':'foreign name'})):
                def mutate(record, location=location, field=field, value=value):
                    target = next(iter(record['chat']['history']['messages'].values())) if location == 'history' else record['chat']['messages'][0]
                    target[field] = value
                mutations.append(mutate)
        for mutation in mutations:
            changed = copy.deepcopy(original); mutation(changed)
            with self.subTest(mutation=mutation), self.assertRaisesRegex(P.ProofError, 'saved primary turn differs'):
                P.validate_publication_turn(changed, submitted, original['id'], admin)

    def test_changed_native_saved_turn_stops_before_publisher_and_restores_config(self):
        def changed(world, method, path, token, body):
            if method == 'GET' and path.startswith('/api/v1/chats/'):
                value = native_publication_chat_get(world.chats[path.rsplit('/',1)[1]],
                    {'id': OWNER, 'name': 'Synthetic administrator', 'role':'admin'})
                value['chat']['models'] = ['changed']
                return 200, value
        error, selected, world, _ = self.exercise(changed)
        self.assertIsNotNone(error); self.assertEqual(selected['publication']['stage'], 'partial')
        self.assertTrue(selected['publication']['config_restored'])
        self.assertNotIn('receipt', selected['publication'])
        self.assertEqual(selected['publication']['saved_turn']['chat']['models'], ['changed'])
        self.assertFalse(any(path == '/api/v1/retrieval/process/file' for _,path,*_ in world.requests))

    def test_partial_native_processing_and_foreign_knowledge_never_earn_ready_and_restore(self):
        for variant in ('process', 'foreign_knowledge', 'skill_id', 'skill_version', 'skill_acl', 'source_bytes'):
            def fault(world, method, path, token, body):
                if variant == 'process' and path == '/api/v1/retrieval/process/file': return 500, {'error': 'synthetic IO failure'}
                if variant == 'foreign_knowledge' and path == '/api/v1/knowledge/' + world.knowledge_id:
                    return 200, {'id': OWNER, 'user_id': OWNER, 'write_access': True, 'access_grants': world.knowledge['access_grants']}
                if token == 'Bearer synthetic-actor-token' and path == '/api/v1/skills/id/goal584-source':
                    value = copy.deepcopy(world.skills['goal584-source'])
                    if variant == 'skill_id': value['id'] = 'foreign-skill'; return 200, value
                    if variant == 'skill_version': value['version_id'] = CONTROL; return 200, value
                    if variant == 'skill_acl': value['access_grants'] = []; return 200, value
                if variant == 'source_bytes' and path.endswith('/content'): return 200, b'changed-source'
            with self.subTest(variant=variant):
                error, selected, world, _ = self.exercise(fault)
                self.assertIsNotNone(error); self.assertEqual(selected['publication']['stage'], 'partial')
                self.assertTrue(selected['publication']['config_restored']); self.assertEqual(world.config, world.baseline)

    def test_enable_timeout_can_commit_but_finally_restores_and_retains_unreturned_journal(self):
        def fault(world, method, path, token, body):
            if path == '/api/v1/retrieval/config/update' and body['BYPASS_EMBEDDING_AND_RETRIEVAL'] is True:
                world.config.update(body)
                raise TimeoutError('PRIVATE_ENABLE_TIMEOUT')
        error, selected, world, _ = self.exercise(fault)
        self.assertIsNotNone(error); self.assertEqual(world.config, world.baseline)
        self.assertTrue(selected['publication']['config_restored'])
        self.assertFalse(selected['journal'][0]['returned'])

    def test_restoration_failure_is_explicit_and_cannot_earn_readiness(self):
        def fault(world, method, path, token, body):
            if path == '/api/v1/retrieval/config/update' and body['BYPASS_EMBEDDING_AND_RETRIEVAL'] is False:
                return 503, {'error': 'PRIVATE_RESTORE_FAILURE'}
        error, selected, world, _ = self.exercise(fault)
        self.assertIsNotNone(error); self.assertEqual(selected['publication']['stage'], 'restore_failed')
        self.assertFalse(selected['publication']['config_restored'])
        self.assertTrue(world.config['BYPASS_EMBEDDING_AND_RETRIEVAL'])

    def test_already_enabled_bypass_needs_no_mutation_and_unrelated_drift_is_never_overwritten(self):
        def enabled(world, method, path, token, body):
            if path == '/api/v1/retrieval/config' and not getattr(world, 'enabled_at_start', False):
                world.enabled_at_start = True
                world.config['BYPASS_EMBEDDING_AND_RETRIEVAL'] = True
                world.baseline = copy.deepcopy(world.config)
        error, selected, world, _ = self.exercise(enabled)
        self.assertIsNone(error); self.assertTrue(selected['publication']['config_restored'])
        self.assertFalse(any(path == '/api/v1/retrieval/config/update' for _, path, *_ in world.requests))
        def drift(world, method, path, token, body):
            if path == '/api/v1/retrieval/config/update' and body['BYPASS_EMBEDDING_AND_RETRIEVAL'] is False:
                world.config['TOP_K'] = 99
        error, selected, world, _ = self.exercise(drift)
        self.assertIsNotNone(error); self.assertEqual(world.config['TOP_K'], 99)
        self.assertFalse(world.config['BYPASS_EMBEDDING_AND_RETRIEVAL'])
        self.assertEqual(selected['publication']['stage'], 'restore_failed')


class DelegatedProvisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # The deployed /proof aliases are real sibling sources, not auth doubles.
        import importlib.util
        for name, filename in (('employee_budget_assignment', 'assignment.py'),
                ('employee_budget_admin_contract', 'admin_contract.py'), ('employee_budget_admin_client', 'admin_client.py')):
            if name not in sys.modules:
                spec = importlib.util.spec_from_file_location(name, HERE.parents[1] / 'deploy/openwebui-budgets' / filename)
                module = importlib.util.module_from_spec(spec); sys.modules[name] = module; spec.loader.exec_module(module)

    def test_complete_synthetic_docx_and_skill_bind_every_field_to_native_source(self):
        from hashlib import sha256
        from zipfile import ZipFile
        from xml.etree import ElementTree as ET
        raw = P.delegated_source_docx()
        self.assertEqual(raw, P.delegated_source_docx())
        with ZipFile(BytesIO(raw)) as package:
            document = ET.fromstring(package.read('word/document.xml'))
            text = ''.join(document.itertext())
            for value in ('Employee: {{employee}}', 'Case: {{case}}', 'FIXED CLAUSE: preserve this sentence.', 'FIXED TABLE'):
                self.assertEqual(text.count(value), 1)
            self.assertIn('FIXED FOOTER: GOAL584 synthetic only.', package.read('word/footer1.xml').decode())
        file_id = '1296bad0-1491-4c19-b7f2-93e57d812864'
        content = P.delegated_skill_content(file_id, sha256(raw).hexdigest())
        self.assertIn('Native source File ID: ' + file_id + '\n', content)
        self.assertIn('Native source SHA256: ' + sha256(raw).hexdigest() + '\n', content)
        self.assertIn('each occurs exactly once', content)
        self.assertIn('Ada Example', content); self.assertIn('G584-2026', content)
        # Exact pinned native Skill preview owner, not a shortened stand paraphrase.
        import ast
        source = Path(os.environ.get('GOAL584_NATIVE_SOURCE_ROOT', str(HERE.parents[1] /
            'local/goal584/cost-display/open-webui/backend/open_webui'))) / 'utils/skill_files.py'
        if not source.is_file():
            if 'GOAL584_NATIVE_SOURCE_ROOT' in os.environ: raise AssertionError('Selected native source is unavailable')
            self.skipTest('New opt-in native Skill source unavailable; no preview substitute')
        names = {'skill_content_page', 'bounded_skill_manifest', 'skill_overview'}
        tree = ast.parse(source.read_bytes()); selected = [n for n in tree.body if getattr(n, 'name', None) in names
            or isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id.startswith('SKILL_') for t in n.targets)]
        namespace = {'json': json}
        exec(compile(ast.Module(body=selected, type_ignores=[]), str(source), 'exec'), namespace)
        result = namespace['skill_overview'](content, [{'path': 'SKILL.md', 'size': len(content.encode())}])
        self.assertEqual(result['content'], content); self.assertIsNone(result['next_offset'])

    def test_synthetic_source_binding_rejects_non_native_id_and_bad_hash(self):
        for file_id, digest in [('invented', 'a' * 64), (OWNER, 'not-a-hash'), (OWNER, 'G' * 64)]:
            with self.subTest(file_id=file_id, digest=digest), self.assertRaises((ValueError, P.ProofError)):
                P.delegated_skill_content(file_id, digest)

    def test_wrong_tool_source_stops_before_any_native_read_or_mutation(self):
        with TemporaryDirectory() as directory:
            tool = Path(directory) / 'tool.py'; tool.write_bytes(b'not-the-reviewed-tool')
            profiles = Path(directory) / 'profiles.json'
            profiles.write_bytes((HERE.parents[1] / 'deploy/openwebui-tools/corporate_template_models.json').read_bytes())
            with patch.object(P, 'native_client', side_effect=AssertionError('Native read before source gate')):
                with self.assertRaisesRegex(P.ProofError, 'Tool/profile source differs'):
                    P.office_delegation_setup(object(), {'stage': 'setup_complete', 'office_setup': {'present': True}},
                        Path(directory) / 'state.json', tool_source=tool, profiles_source=profiles)

    def test_exact_profiles_and_tool_valves_keep_current_worker_contract(self):
        from hashlib import sha256
        raw = (HERE.parents[1] / 'deploy/openwebui-tools/corporate_template_models.json').read_bytes().replace(b'\r\n', b'\n')
        self.assertEqual(sha256(raw).hexdigest(), P.DELEGATION_PROFILES_SHA256)
        profiles = {v['id']: v for v in json.loads(raw)}
        self.assertEqual(profiles['corporate-documents']['params']['max_tokens'], 12000)
        worker = profiles['corporate-office-worker']
        parent = profiles['corporate-documents']
        self.assertTrue(parent['meta']['capabilities']['builtin_tools'])
        self.assertTrue(parent['meta']['builtinTools']['tasks'])
        self.assertFalse(worker['meta']['builtinTools']['tasks'])
        self.assertIn('native artifact-workflow Skill', parent['params']['system'])
        self.assertEqual(worker['params']['max_tokens'], 6000)
        for required in ('load_officecli_skill', 'Inspect before editing', 'apply_office_batch', 'Inspect the published result', 'render_office_file'):
            self.assertIn(required, worker['params']['system'])
        self.assertEqual(P.DELEGATION_VALVES['DEFAULT_MODEL'], worker['id'])
        self.assertEqual(P.DELEGATION_VALVES['MAX_ITERATIONS'], 12)
        self.assertIs(P.DELEGATION_VALVES['APPLY_INLET_FILTERS'], True)
        self.assertIs(P.DELEGATION_VALVES['ENABLE_CONTEXT_COMPACTION'], False)
        self.assertEqual(P.DELEGATION_VALVES['LARGE_TOOL_RESULT_MODE'], 'raw')

    def test_new_phase_uses_actual_admin_owner_to_create_two_fresh_assignments(self):
        self.exercise_delegated_setup()

    def test_delegated_base_rows_require_strict_absence_before_any_mutation(self):
        for status in (200, 401, 403, 500):
            with self.subTest(status=status):
                self.exercise_delegated_setup(base_absence=status, expect_failure='base Workspace Model')

    def test_delegated_final_catalog_requires_both_base_rows_and_profile_bindings(self):
        for mutate in (lambda rows: rows.pop('gpt-6.1-sol'),
                       lambda rows: rows['corporate-documents']['info'].update(base_model_id='gpt-6.1-terra')):
            with self.subTest(mutate=mutate):
                self.exercise_delegated_setup(alter_catalog=mutate, expect_failure='Delegated actor')

    def exercise_delegated_setup(self, *, base_absence=404, alter_catalog=None, expect_failure=None):
        """Real provision/client/private owners; explicit native HTTP/config leaves."""
        import hashlib, importlib.util, yaml
        from email import policy
        from email.parser import BytesParser
        from types import SimpleNamespace
        import office_fixture
        import employee_budget_admin_client as budget
        original = HERE.parents[1].with_name('corp-openweb ui')
        tool_path = Path(os.environ.get('GOAL584_COMMUNITY_TOOL_SOURCE', str(original / 'local/subagent-office-trial-20261029/sub_agent.py')))
        if not tool_path.is_file():
            if 'GOAL584_COMMUNITY_TOOL_SOURCE' in os.environ: raise AssertionError('Selected pinned Tool source unavailable')
            self.skipTest('New opt-in pinned Tool fixture unavailable; no Tool substitute')
        self.assertEqual(hashlib.sha256(tool_path.read_bytes()).hexdigest(), P.DELEGATION_TOOL_SHA256)
        spec = importlib.util.spec_from_file_location('provision_exact_pinned_tool', tool_path)
        native_tool = importlib.util.module_from_spec(spec); sys.modules[spec.name] = native_tool; spec.loader.exec_module(native_tool)
        info = yaml.safe_load(office_fixture.prepare_delegated_office_config(HERE.joinpath('litellm_config.yaml').read_bytes()))['model_list']
        actor = str(P.uuid.uuid4()); admin = {'id': OWNER, 'token': 'synthetic-admin-token'}
        workflow = {'id': P.WORKFLOW_SKILL_ID, 'user_id': OWNER, 'content': (HERE.parents[1] /
            'deploy/openwebui-skills/artifact-workflow.md').read_text(encoding='utf8'),
            'version_id': CONTROL, 'is_active': True,
            'access_grants': [{'principal_type': 'user', 'principal_id': '*', 'permission': 'read'}]}
        state = {'schema': 1, 'stage': 'setup_complete', 'admin': admin, 'users': [{'id': CONTROL}],
                 'office_setup': {'untouched': [1, 2], 'workflow_skill': workflow}, 'native_keys': [{'keep': 'legacy'}]}
        frozen = copy.deepcopy(state)
        config = {'OPENAI_API_BASE_URLS': ['http://proxy:4000/v1'], 'OPENAI_API_KEYS': ['gw-synthetic-delegated'],
            'OPENAI_API_CONFIGS': {'0': {'api_type': 'responses', 'auth_type': 'bearer', 'model_ids': ['gpt-5.4-mini', 'gpt-6-luna']}}}
        rows, tools, files, skills, requests, budget_requests = {}, {}, {}, {P.WORKFLOW_SKILL_ID: workflow}, [], []
        publication = PublicationHTTPWorld(self, actor, files=files, skills=skills)
        user, keys = None, []
        class Response(BytesIO):
            headers = {}
            def __init__(self, status, value, binary=False):
                super().__init__(value if binary else json.dumps(value).encode()); self.code = status
        owner = self
        class Transport:
            def open(self, request, timeout):
                nonlocal config
                method, path = request.get_method(), urlsplit(request.full_url).path
                token = request.get_header('Authorization'); query = parse_qs(urlsplit(request.full_url).query)
                requests.append((method, path))
                if path.startswith(('/api/v1/retrieval/', '/api/v1/knowledge/', '/api/v1/chats/', '/api/v1/skills/')):
                    body = json.loads(request.data) if request.data else None
                    return Response(*publication.route(method, path, token, body, query))
                if path == '/api/v1/files/' and method == 'POST':
                    parts = BytesParser(policy=policy.default).parsebytes(b'Content-Type: ' + request.get_header('Content-type').encode()
                        + b'\r\nMIME-Version: 1.0\r\n\r\n' + request.data)
                    body = next(parts.iter_parts()).get_payload(decode=True)
                    identifier = str(P.uuid.uuid4()); files[identifier] = body
                    return Response(200, {'id': identifier, 'user_id': actor, 'filename': 'goal584-delegated-source.docx'})
                if path.startswith('/api/v1/files/'): return Response(200, files[path.split('/')[4]], True)
                body = json.loads(request.data) if request.data else None
                if path == '/api/v1/auths/': return Response(200, {'id': OWNER if token == 'Bearer synthetic-admin-token' else actor,
                    'role': 'admin' if token == 'Bearer synthetic-admin-token' else 'user',
                    'name': 'Synthetic administrator' if token == 'Bearer synthetic-admin-token' else 'Synthetic employee'})
                if path == '/api/v1/auths/add': return Response(200, {'id': actor, 'role': 'user', 'token': 'synthetic-new-actor-token'})
                if path == '/openai/config': return Response(200, config)
                if path == '/openai/config/update': config = copy.deepcopy(body); return Response(200, config)
                if path == '/api/v1/models/create' or path == '/api/v1/models/model/update':
                    rows[body['id']] = copy.deepcopy(body) | {'user_id': OWNER, 'write_access': True}
                    return Response(200, rows[body['id']])
                if path == '/api/v1/models/model':
                    identifier = query['id'][0]
                    return Response(200, rows[identifier]) if identifier in rows else Response(
                        base_absence if identifier in ('gpt-6.1-sol', 'gpt-6.1-terra') else 404, {})
                if path == '/api/models':
                    catalog = {mid: {'id': mid, 'info': copy.deepcopy(row), 'owned_by': 'openai',
                        **({'urlIdx': 0} if row['base_model_id'] is None else {'preset': True})} for mid, row in rows.items()}
                    if alter_catalog: alter_catalog(catalog)
                    return Response(200, {'data': list(catalog.values())})
                if path == '/api/v1/tools/': return Response(200, [])
                if path == '/api/v1/tools/create': tools[body['id']] = copy.deepcopy(body); return Response(200, body)
                if path.endswith('/valves/update'): tools['valves'] = native_tool.Tools.Valves(**body).model_dump(); return Response(200, tools['valves'])
                if path.endswith('/valves'): return Response(200, tools.get('valves', native_tool.Tools.Valves().model_dump()))
                if path == '/api/v1/tools/id/' + P.DELEGATION_TOOL_ID: return Response(200, tools[P.DELEGATION_TOOL_ID])
                if path == '/api/v1/skills/create':
                    skills[body['id']] = copy.deepcopy(body) | {'version_id': str(P.uuid.uuid4())}; return Response(200, skills[body['id']])
                if path.startswith('/api/v1/skills/id/'): return Response(200, skills[path.rsplit('/', 1)[1]])
                raise AssertionError((method, path))
        async def native_request(client, method, route, *, params=None, body=None):
            nonlocal user
            budget_requests.append((method, route, copy.deepcopy(body)))
            if route == '/user/info':
                if user is None: raise budget.BudgetAdminError('native_http_404')
                return {'user_info': user, 'teams': []}
            if route == '/key/list': return {'keys': copy.deepcopy(keys), 'current_page': 1, 'total_count': len(keys), 'total_pages': int(bool(keys))}
            if route == '/user/new':
                owner.assertIsNone(user)
                user = copy.deepcopy(body) | {'team_id': None, 'budget_reset_at': '2099-01-01T00:00:00Z'}
                return {'user_id': 'POST ack is not authority'}
            if route == '/key/generate':
                row = copy.deepcopy(body); raw = row.pop('key')
                keys.append(row | {'token': hashlib.sha256(raw.encode()).hexdigest(), 'expires': None,
                                   'budget_reset_at': '2099-01-01T00:00:00Z'})
                return {'key': 'POST ack is not authority'}
            raise AssertionError(route)
        with TemporaryDirectory() as directory:
            target, operator = Path(directory) / 'office.json', Path(directory) / 'operator.json'
            if os.name == 'nt':
                self.enterContext(patch.object(private_owner, 'private_parent'))
                self.enterContext(patch.object(private_owner.stat, 'S_IMODE', return_value=0o600))
            P.write_private(operator, {'schema': 1, 'operator_token': 'sk-synthetic-operator'})
            original_open = Path.open
            publisher_source = (HERE.parents[1]/'deploy/openwebui-tools/corporate_templates.py').read_bytes()
            def mounted_publisher(path, *args, **kwargs):
                if path == Path('/proof/corporate_templates.py'): return BytesIO(publisher_source)
                return original_open(path, *args, **kwargs)
            import aiohttp
            with patch.object(P, 'build_opener', return_value=Transport()), patch.object(P, 'OPERATOR_STATE', operator), \
                    patch.object(P, 'native_client', return_value=SimpleNamespace(ok=lambda *args: {'data': copy.deepcopy(info)})), \
                    patch.object(budget.BudgetAdminClient, '_request', native_request), \
                    patch.object(Path, 'open', mounted_publisher), patch.object(aiohttp, 'ClientSession', publication.session), \
                    patch.dict(os.environ, OWUI_BUDGET_GATEWAY_SECRET='gw-synthetic-delegated'):
                if expect_failure:
                    with self.assertRaisesRegex(P.ProofError, expect_failure):
                        P.office_delegation_setup(P.WebUI(), state, target, tool_source=tool_path,
                            profiles_source=HERE.parents[1] / 'deploy/openwebui-tools/corporate_template_models.json')
                    if base_absence != 404:
                        self.assertFalse(any(method == 'POST' for method, _ in requests))
                        self.assertFalse(target.exists())
                    self.assertEqual(state, frozen)
                    return
                safe = P.office_delegation_setup(P.WebUI(), state, target, tool_source=tool_path,
                    profiles_source=HERE.parents[1] / 'deploy/openwebui-tools/corporate_template_models.json')
            saved = P.read_private(target)['office_delegation_setup']
            self.assertEqual(state, frozen)
            self.assertEqual(saved['stage'], 'readback_ready')
            self.assertEqual(saved['publication']['stage'], 'readback_ready')
            self.assertTrue(saved['publication']['config_restored'])
            self.assertEqual(publication.config, publication.baseline)
            self.assertEqual([m['model'] for m in saved['budget']['models']], ['gpt-6.1-sol', 'gpt-6.1-terra'])
            self.assertEqual([path for method, path, body in budget_requests if method == 'POST'], ['/user/new', '/key/generate', '/key/generate'])
            self.assertEqual(user['models'], ['gpt-6.1-sol', 'gpt-6.1-terra'])
            self.assertEqual(len(keys), 2); self.assertTrue(all(k['spend'] == 0 for k in keys))
            self.assertEqual(user['max_budget'], 2000)
            self.assertEqual(sum(k['max_budget'] for k in keys), user['max_budget'])
            self.assertTrue(all(k['max_budget'] == 1000 for k in keys))
            self.assertFalse(safe['office_delegation_setup']['inference_issued'])
            self.assertEqual(rows['corporate-documents']['params']['max_tokens'], 12000)
            self.assertEqual(rows['corporate-office-worker']['params']['max_tokens'], 6000)
            self.assertTrue(rows['corporate-documents']['meta']['builtinTools']['tasks'])
            self.assertFalse(rows['corporate-office-worker']['meta']['builtinTools']['tasks'])
            self.assertEqual(set(saved['base_models']), {'gpt-6.1-sol', 'gpt-6.1-terra'})
            self.assertEqual(set(saved['actor_catalog']), {'corporate-documents', 'corporate-office-worker',
                                                         'gpt-6.1-sol', 'gpt-6.1-terra'})
            for profile, alias, output in (('corporate-documents', 'gpt-6.1-sol', 12000),
                                           ('corporate-office-worker', 'gpt-6.1-terra', 6000)):
                self.assertIsNone(rows[alias]['base_model_id'])
                self.assertEqual(rows[alias]['params'], {'max_tokens': output})
                self.assertEqual(rows[alias]['meta']['filterIds'], ['employee_budget_cost'])
                self.assertEqual(rows[alias]['access_grants'], [
                    {'principal_type': 'user', 'principal_id': actor, 'permission': 'read'}])
                self.assertEqual(rows[profile]['base_model_id'], alias)


class DelegatedNativeBaseAccessTests(unittest.IsolatedAsyncioTestCase):
    """Exact native access/parameter owners; only DB/grant IO is substituted."""
    @classmethod
    def setUpClass(cls):
        import ast, hashlib, logging
        from typing import Callable
        import collections.abc
        root = Path(os.environ.get('GOAL584_NATIVE_SOURCE_ROOT', str(HERE.parents[1] /
            'local/goal584/cost-display/open-webui/backend/open_webui')))
        pins = {'utils/models.py': '20d6ad7ef8d62b521cf46d2224ac4ff83998dadbfcb90d7105da3c14cc468690',
            'utils/access_control/__init__.py': 'aed18ea3b7788597a8b4eaf741d32e07b0244bc390ab792e44bda611d324b568',
            'utils/payload.py': 'c4fa395b43f0cdfd1fa95461749dfa283f0ae9b780acffd53e86046eed018fdb',
            'utils/misc.py': '24b39f1c7c7ef24c5cc436820af62df2e3eae11d94e498ae30fe9fda33b7d6c1',
            'utils/filter.py': '6f94e65e9b793de3da6544e410019440a17fbab5848eedf1d03aa30a6e3bda2f',
            'routers/openai.py': 'af02463b799a817b307da5d03af25874ca14f477b883e913051b3b797d365955'}
        cls.trees = {}
        for relative, expected in pins.items():
            source = root / relative
            if not source.is_file():
                if 'GOAL584_NATIVE_SOURCE_ROOT' in os.environ: raise AssertionError('Pinned native source unavailable')
                raise unittest.SkipTest('Set GOAL584_NATIVE_SOURCE_ROOT for exact native base-chain component proof')
            raw = source.read_bytes().replace(b'\r\n', b'\n')
            assert hashlib.sha256(raw).hexdigest() == expected, relative
            cls.trees[relative] = ast.parse(raw)
        cls.namespace = {'log': logging.getLogger('native-base-component'), 'Callable': Callable,
                         'collections': collections, 'copy': copy}
        def load(relative, names, namespace):
            nodes = [copy.deepcopy(n) for n in cls.trees[relative].body if getattr(n, 'name', None) in names]
            assert len(nodes) == len(names), (relative, names)
            exec(compile(ast.Module(body=nodes, type_ignores=[]), relative, 'exec',
                flags=__import__('__future__').annotations.compiler_flag), namespace)
        cls.load_native = staticmethod(load)
        load('utils/access_control/__init__.py', {'has_base_model_access'}, cls.namespace)
        load('utils/models.py', {'check_model_access'}, cls.namespace)
        load('utils/misc.py', {'deep_update'}, cls.namespace)
        load('utils/payload.py', {'remove_open_webui_params', 'apply_model_params_to_body',
                                'apply_model_params_to_body_openai'}, cls.namespace)
        load('utils/filter.py', {'get_model_filter_ids'}, cls.namespace)
        load('routers/openai.py', {'_normalize_stored_item', 'convert_to_responses_payload'}, cls.namespace)
        allowed = next(n for n in cls.trees['routers/openai.py'].body if isinstance(n, ast.AnnAssign)
            and isinstance(n.target, ast.Name) and n.target.id == 'RESPONSES_ALLOWED_FIELDS')
        exec(compile(ast.Module(body=[allowed], type_ignores=[]), 'native-response-fields', 'exec'), cls.namespace)

    async def asyncSetUp(self):
        from types import SimpleNamespace, ModuleType
        self.actor = SimpleNamespace(id=CONTROL, role='user')
        self.profiles = {p['id']: copy.deepcopy(p) for p in json.loads((HERE.parents[1] /
            'deploy/openwebui-tools/corporate_template_models.json').read_text(encoding='utf8'))}
        self.profiles['corporate-documents']['base_model_id'] = 'gpt-6.1-sol'
        self.rows = {mid: SimpleNamespace(**{k: p[k] for k in ('id', 'base_model_id')}, user_id=OWNER,
            params=SimpleNamespace(model_dump=lambda p=p: copy.deepcopy(p['params'])))
            for mid, p in self.profiles.items()}
        self.grants = {(CONTROL, mid) for mid in ('corporate-documents', 'corporate-office-worker')}
        self.queries = []
        async def model(identifier, **kwargs):
            self.queries.append(('model', identifier)); return self.rows.get(identifier)
        async def groups(user_id, **kwargs): return []
        async def access(**kwargs):
            assert kwargs['resource_type'] == 'model' and kwargs['permission'] == 'read'
            self.queries.append(('grant', kwargs['user_id'], kwargs['resource_id']))
            return (kwargs['user_id'], kwargs['resource_id']) in self.grants
        self.namespace = dict(type(self).namespace, Models=SimpleNamespace(get_model_by_id=model),
            Groups=SimpleNamespace(get_groups_by_member_id=groups), AccessGrants=SimpleNamespace(has_access=access))
        self.load_native('utils/access_control/__init__.py', {'has_base_model_access'}, self.namespace)
        self.load_native('utils/models.py', {'check_model_access'}, self.namespace)
        modules = {}
        for name, value in [('open_webui.models.models', {'Models': self.namespace['Models']}),
                            ('open_webui.models.access_grants', {'AccessGrants': self.namespace['AccessGrants']})]:
            module = ModuleType(name); module.__dict__.update(value); modules[name] = module
        self.enterContext(patch.dict(sys.modules, modules))

    def register_bases(self):
        from types import SimpleNamespace
        for profile, maximum in [('corporate-documents', 12000), ('corporate-office-worker', 6000)]:
            alias = self.profiles[profile]['base_model_id']
            bodies = {}
            def post(route, body): bodies[body['id']] = copy.deepcopy(body) | {'user_id': OWNER}
            webui = SimpleNamespace(model=lambda token, identifier: copy.deepcopy(bodies[identifier]))
            record = P.create_office_base_model(webui, {'id': OWNER, 'token': 'synthetic'},
                {'id': CONTROL}, alias, {'max_tokens': maximum}, post)
            self.assertEqual(record['access_grants'], [{'principal_type': 'user', 'principal_id': CONTROL, 'permission': 'read'}])
            self.rows[alias] = SimpleNamespace(id=alias, base_model_id=None, user_id=OWNER,
                params=SimpleNamespace(model_dump=lambda maximum=maximum: {'max_tokens': maximum}))
            self.grants.add((CONTROL, alias))

    async def test_exact_native_missing_or_unreadable_base_rejects_before_new_actor_grant_passes(self):
        check = self.namespace['check_model_access']
        for profile in ('corporate-documents', 'corporate-office-worker'):
            with self.assertRaisesRegex(Exception, '^Model not found$'):
                await check(self.actor, {'id': profile})
        self.register_bases()
        for profile in ('corporate-documents', 'corporate-office-worker'):
            await check(self.actor, {'id': profile})
            await check(self.actor, {'id': self.profiles[profile]['base_model_id']})
        self.grants.remove((CONTROL, 'gpt-6.1-terra'))
        with self.assertRaisesRegex(Exception, '^Model not found$'):
            await check(self.actor, {'id': 'corporate-office-worker'})

    async def test_exact_native_base_chain_does_not_grant_foreign_actor_profile_escape(self):
        from types import SimpleNamespace
        self.register_bases()
        foreign = SimpleNamespace(id='22222222-2222-4222-8222-222222222222', role='user')
        self.grants.add((foreign.id, 'corporate-documents'))  # Profile access alone never grants its base.
        for identifier in ('corporate-documents', 'corporate-office-worker', 'gpt-6.1-sol', 'gpt-6.1-terra'):
            with self.subTest(identifier=identifier), self.assertRaisesRegex(Exception, '^Model not found$'):
                await self.namespace['check_model_access'](foreign, {'id': identifier})

    async def test_native_parameter_prefix_preserves_profile_context_with_new_base_rows(self):
        import ast
        from types import SimpleNamespace
        namespace = dict(self.namespace)
        self.load_native('utils/access_control/__init__.py', {'check_model_access'}, namespace)
        function = next(n for n in self.trees['routers/openai.py'].body if getattr(n, 'name', None) == 'generate_chat_completion')
        start = next(i for i, n in enumerate(function.body) if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == 'payload' for t in n.targets))
        end = next(i for i, n in enumerate(function.body) if isinstance(n, ast.If)
            and isinstance(n.test, ast.Name) and n.test.id == 'model_info')
        prefix = ast.parse('async def native_prefix(request, form_data, user, bypass_filter=False, bypass_system_prompt=True):\n pass').body[0]
        prefix.body = copy.deepcopy(function.body[start:end+1]) + [ast.Return(value=ast.Name(id='payload', ctx=ast.Load()))]
        ast.fix_missing_locations(prefix)
        exec(compile(ast.Module(body=[prefix], type_ignores=[]), 'actual-native-route-parameter-prefix', 'exec'), namespace)
        before = {}
        for identifier in ('corporate-documents', 'corporate-office-worker'):
            body = {'model': identifier, 'store': False, 'include': ['reasoning.encrypted_content'],
                'messages': [{'role': 'system', 'content': self.profiles[identifier]['params']['system']},
                             {'role': 'user', 'content': 'Complete representative source and two field facts'},
                             {'role': 'tool', 'tool_call_id': 'native_call', 'content': 'Complete representative native result'}],
                'tools': [{'type': 'function', 'function': {'name': 'native_fixture', 'parameters': {'type': 'object'}}}]}
            # Before this fix only the native admin could pass the missing-base path.
            prepared = await namespace['native_prefix'](SimpleNamespace(state=SimpleNamespace()), copy.deepcopy(body),
                SimpleNamespace(id=OWNER, role='admin'))
            before[identifier] = namespace['convert_to_responses_payload'](prepared)
        self.register_bases()
        for identifier, old in before.items():
            body = {'model': identifier, 'store': False, 'include': ['reasoning.encrypted_content'],
                'messages': [{'role': 'system', 'content': self.profiles[identifier]['params']['system']},
                             {'role': 'user', 'content': 'Complete representative source and two field facts'},
                             {'role': 'tool', 'tool_call_id': 'native_call', 'content': 'Complete representative native result'}],
                'tools': [{'type': 'function', 'function': {'name': 'native_fixture', 'parameters': {'type': 'object'}}}]}
            current = namespace['convert_to_responses_payload'](await namespace['native_prefix'](
                SimpleNamespace(state=SimpleNamespace()), copy.deepcopy(body), self.actor))
            self.assertEqual(current, old)
            self.assertEqual(current['max_output_tokens'], self.profiles[identifier]['params']['max_tokens'])
            self.assertEqual(current['model'], self.profiles[identifier]['base_model_id'])
            self.assertIs(current['store'], False)
            self.assertEqual(current['include'], ['reasoning.encrypted_content'])
            self.assertEqual(current['instructions'], self.profiles[identifier]['params']['system'])

    async def test_native_filter_selection_keeps_one_budget_filter_for_base_or_profile(self):
        select = self.namespace['get_model_filter_ids']
        active = [('employee_budget_cost', False), ('officecli_auto_attach_filter', True)]
        for identifier in ('corporate-documents', 'corporate-office-worker', 'gpt-6.1-sol', 'gpt-6.1-terra'):
            filters = select({'id': identifier, 'info': {'meta': {'filterIds': ['employee_budget_cost']}}}, active)
            self.assertEqual(filters.count('employee_budget_cost'), 1)
            self.assertEqual(filters.count('officecli_auto_attach_filter'), 1)


class TerminalProvisionTests(unittest.TestCase):
    """Actual provision/private/native-budget owners; explicit HTTP/DB leaves."""
    @classmethod
    def setUpClass(cls):
        import test_service_tasks
        cls.budget = sys.modules['employee_budget_admin_client']

    def exercise(self, change=None, *, cli=False):
        from types import SimpleNamespace
        from hashlib import sha256
        from provision_cost_display import FILTER_ID
        actor = {'id': '33333333-3333-4333-8333-333333333333', 'token': 'synthetic-terminal-actor'}
        admin, foreign = {'id': OWNER, 'token': 'synthetic-terminal-admin'}, {'id': CONTROL, 'token': 'synthetic-terminal-foreign'}
        key = 'synthetic-terminal-only-' + 'k' * 40
        grants = [{'principal_type':'user','principal_id':actor['id'],'permission':'read'}]
        profiles = json.loads((HERE.parents[1]/'deploy/openwebui-tools/corporate_template_models.json').read_text(encoding='utf8'))
        parent = copy.deepcopy(next(row for row in profiles if row['id'] == 'corporate-documents'))
        parent.update(base_model_id='gpt-6.1-sol', access_grants=grants, user_id=OWNER, write_access=True)
        parent['meta']['filterIds'] = [FILTER_ID]
        parent['params']['untouched_native'] = {'nested': [True, 17]}
        base = {'id':'gpt-6.1-sol','name':'gpt-6.1-sol','base_model_id':None,'user_id':OWNER,'write_access':True,
            'params':{'max_tokens':12000},'meta':{'filterIds':[FILTER_ID]},'access_grants':grants,'is_active':True}
        workflow = {'id':P.WORKFLOW_SKILL_ID,'content':'actual complete root Skill','version_id':OWNER,
            'is_active':True,'access_grants':grants}
        state = {'schema':1,'stage':'setup_complete','admin':admin,'users':[foreign],
            'office_setup':{'workflow_skill':workflow},'office_delegation_setup':{'stage':'readback_ready',
                'actor':actor,'models':{'corporate-documents':parent},'base_models':{'gpt-6.1-sol':base}}}
        old = dict(id='existing-terminal',name='Preserved',enabled=False,url='http://old-terminal:8000',path='/openapi.json',
            key='old-private-sentinel',auth_type='bearer',forward_cookies=False,config={'access_grants':[]},
            server_type=None,policy_id=None,vendor_extra={'untouched':[1,2]})
        world = SimpleNamespace(state=state, rows={'corporate-documents':copy.deepcopy(parent),'gpt-6.1-sol':copy.deepcopy(base)},
            registry={'TERMINAL_SERVER_CONNECTIONS':[old]}, tools={}, valves={}, calls=[], budget_calls=[],
            key=key, actor=actor, admin=admin, foreign=foreign, health={'status':'ok'},
            schema={'openapi':'3.1.0','info':{'version':'0.14.0'},'paths':{'/execute':{'post':{'operationId':'run_command',
                'requestBody':{'content':{'application/json':{'schema':{'$ref':'#/components/schemas/ExecRequest'}}}}}}},
                'components':{'schemas':{'ExecRequest':{'type':'object','required':['command'],
                    'properties':{'command':{'type':'string'},'cwd':{'anyOf':[{'type':'string'},{'type':'null'}]},
                                  'env':{'anyOf':[{'type':'object'},{'type':'null'}]}}}}}},
            fault=None, model_absence=404, foreign_session=None, failed_post=None, mutate_after_model=None, source_fault=False)
        user = {'user_id':actor['id'],'user_role':'internal_user','max_budget':2000,'spend':0,'budget_duration':'1mo','budget_reset_at':None}
        keys = [dict(token=str(index+1)*64,user_id=actor['id'],team_id=None,models=[alias],
            key_alias=self.budget.assignment_alias(actor['id'],alias),metadata=self.budget.assignment_metadata(alias),max_budget=1000,
            spend=0,budget_duration='1mo',budget_reset_at=None,blocked=False) for index,alias in enumerate(('gpt-6.1-sol','gpt-6.1-terra'))]
        world.budget_user, world.budget_keys = user, keys

        class Response(BytesIO):
            headers = {}
            def __init__(self,status,value): self.code=status; super().__init__(json.dumps(value).encode())
        def permitted(account, record):
            return account is admin or any(g.get('principal_id') in (account['id'],'*') and g.get('permission')=='read'
                                           for g in record.get('access_grants',[]))
        class Transport:
            def open(transport,request,timeout):
                parsed=urlsplit(request.full_url);route=parsed.path;method=request.method
                token=request.get_header('Authorization');account=next(a for a in (admin,actor,foreign) if token=='Bearer '+a['token'])
                body=json.loads(request.data) if request.data else None
                world.calls.append((method,route,account['id'],copy.deepcopy(body)))
                if method=='POST':
                    journal=P.read_private(world.target)['journal'][-1]
                    assert journal['route']==route and journal['body']==body and journal['returned'] is False
                    if world.failed_post==route:return Response(500,{'detail':'native failed'})
                    if route=='/api/v1/configs/terminal_servers':world.registry=copy.deepcopy(body)
                    elif route=='/api/v1/tools/create':
                        specs=[{'name':name,'parameters':{'type':'object','properties':{arg:{'type':'string'}},'required':[arg]}}
                            for name,arg in (('stage_chat_file','file_id'),('publish_terminal_file','path'))]
                        world.tools[body['id']]=copy.deepcopy(body)|{'user_id':OWNER,'write_access':True,'specs':specs}
                        world.valves={'openwebui_base_url':'http://127.0.0.1:8080','max_file_mib':32}
                    elif route.endswith('/valves/update'):world.valves=copy.deepcopy(body)
                    elif route=='/api/v1/models/create':
                        world.rows[body['id']]=copy.deepcopy(body)|{'user_id':OWNER,'write_access':True}
                        if world.mutate_after_model:world.mutate_after_model(world)
                    else:raise AssertionError('Unexpected Terminal write')
                    return Response(200,world.registry if route=='/api/v1/configs/terminal_servers' else {'ok':True})
                if route=='/api/v1/auths/':
                    return Response(200,world.foreign_session if account is foreign and world.foreign_session else
                        {'id':account['id'],'role':'admin' if account is admin else 'user'})
                if route=='/api/v1/configs/terminal_servers':return Response(200,world.registry)
                if route=='/openai/config':return Response(200,{'OPENAI_API_CONFIGS':{'0':{'api_type':'responses','model_ids':['gpt-6.1-sol','gpt-6.1-terra']}}})
                if route=='/api/v1/tasks/config':return Response(200,{'ENABLE_FOLLOW_UP_GENERATION':True,'unchanged':17})
                if route=='/api/v1/skills/id/'+P.WORKFLOW_SKILL_ID:return Response(200,workflow)
                if route.startswith('/api/v1/functions/id/'):
                    return Response(200,{'ledger_base_url':'http://proxy:4000'} if route.endswith('/valves') else {'is_active':True,'id':FILTER_ID})
                if route=='/api/v1/models/model':
                    identifier=parse_qs(parsed.query)['id'][0]
                    if identifier not in world.rows:return Response(world.model_absence,{})
                    return Response(200,world.rows[identifier]) if permitted(account,world.rows[identifier]) else Response(401,{'detail':'denied'})
                if route=='/api/models':
                    rows=[]
                    for identifier,record in world.rows.items():
                        if permitted(account,record):
                            info=copy.deepcopy(record)
                            if account is not admin:info['params']={}
                            row={'id':identifier,'owned_by':'openai','info':info}
                            if record.get('base_model_id') is None:row['urlIdx']=0
                            rows.append(row)
                    return Response(200,{'data':rows})
                if route=='/api/v1/terminals/':
                    return Response(200,[{'id':entry['id']} for entry in world.registry['TERMINAL_SERVER_CONNECTIONS'] or []
                        if entry.get('enabled') and permitted(account,{'access_grants':entry.get('config',{}).get('access_grants',[])})])
                if route.startswith('/api/v1/terminals/'+P.TERMINAL_ID+'/'):
                    connection=world.registry['TERMINAL_SERVER_CONNECTIONS'][-1]
                    if not permitted(account,{'access_grants':connection['config']['access_grants']}):return Response(403,{'detail':'denied'})
                    return Response(200,world.schema if route.endswith('openapi.json') else world.health)
                if route.startswith('/api/v1/tools/id/'+P.TERMINAL_TOOL_ID):
                    if P.TERMINAL_TOOL_ID not in world.tools:return Response(404,{})
                    value=world.tools[P.TERMINAL_TOOL_ID]
                    if not permitted(account,value):return Response(401,{'detail':'denied'})
                    if route.endswith('/valves'):return Response(200,world.valves)
                    value=copy.deepcopy(value)
                    if account is not admin:value.update(write_access=False);value.pop('content',None)
                    return Response(200,value)
                raise AssertionError('Unexpected Terminal read: '+route)
        async def budget_request(client,method,route,*,params=None,body=None):
            self.assertEqual(method,'GET');world.budget_calls.append((method,route))
            if route=='/user/info':return {'user_info':copy.deepcopy(world.budget_user)}
            self.assertEqual(route,'/key/list')
            return {'current_page':1,'total_pages':1,'total_count':2,'keys':copy.deepcopy(world.budget_keys)}
        with TemporaryDirectory() as directory:
            root=Path(directory);root.chmod(0o700);world.target=root/'terminal-state.private.json'
            operator=root/'operator.json';operator.write_text(json.dumps({'schema':1,'operator_token':'sk-synthetic-operator'}));operator.chmod(0o600)
            source=HERE.parents[1]/'deploy/openwebui-tools/terminal_file_transfer.py'
            if change:change(world)
            if world.source_fault:
                changed=root/'wrong-transfer.py';changed.write_bytes(source.read_bytes()+b'\n# altered source\n');source=changed
            frozen=copy.deepcopy(state);result=error=None
            original=root/'office-state.private.json';original.write_text(json.dumps(state),encoding='utf8');original.chmod(0o600)
            original_bytes=original.read_bytes()
            with patch.object(P,'build_opener',return_value=Transport()),patch.object(P,'OPERATOR_STATE',operator), \
                    patch.object(self.budget.BudgetAdminClient,'_request',budget_request), \
                    patch.dict(os.environ,{'STAGING_TERMINAL_API_KEY':key}), \
                    __import__('contextlib').ExitStack() as stack:
                if os.name=='nt':
                    stack.enter_context(patch.object(private_owner,'private_parent'))
                    stack.enter_context(patch.object(private_owner.stat,'S_IMODE',return_value=0o600))
                with redirect_stdout(StringIO()) as stdout:
                    try:
                        if cli:
                            argv=['provision_webui.py','--phase','terminal-setup','--private-state',str(original),
                                '--terminal-state',str(world.target),'--terminal-tool-source',str(source),
                                '--receipt',str(root/'terminal.safe.json')]
                            with patch.object(sys,'argv',argv):code=P.main()
                            result=json.loads(stdout.getvalue());self.assertEqual(code,0,result)
                        else:result=P.terminal_setup(P.WebUI(),state,world.target,tool_source=source)
                    except Exception as caught:error=caught
                if not cli:self.assertEqual(stdout.getvalue(),'')
                self.assertEqual(state,frozen);self.assertEqual(original.read_bytes(),original_bytes)
            packet=json.loads(world.target.read_text(encoding='utf8')) if world.target.exists() else None
            return world,result,packet,error

    def test_native_setup_preserves_full_context_prefix_and_only_new_actor_resources(self):
        world,result,packet,error=self.exercise()
        self.assertIsNone(error);self.assertEqual(packet['stage'],'readback_ready')
        self.assertTrue(result['terminal_setup']['daemon_proxy_verified'])
        self.assertFalse(result['terminal_setup']['native_terminal_accepted'])
        self.assertEqual(packet['model']['params'],world.state['office_delegation_setup']['models']['corporate-documents']['params'])
        self.assertEqual(packet['model']['meta']['toolIds'][:-1],world.state['office_delegation_setup']['models']['corporate-documents']['meta']['toolIds'])
        self.assertEqual(packet['registry_after']['TERMINAL_SERVER_CONNECTIONS'][:-1],packet['registry_before']['TERMINAL_SERVER_CONNECTIONS'])
        self.assertTrue(all(entry['returned'] for entry in packet['journal']))
        self.assertEqual([route for method,route,_,_ in world.calls if method=='POST'],[
            '/api/v1/configs/terminal_servers','/api/v1/tools/create','/api/v1/tools/id/terminal_file_transfer/valves/update','/api/v1/models/create'])
        self.assertTrue(all(method=='GET' for method,_ in world.budget_calls))
        for value in (world.key,'actual complete root Skill','old-private-sentinel'):
            self.assertNotIn(value,json.dumps(result))

    def test_prewrite_absence_registry_and_foreign_auth_drift_are_fatal_without_posts(self):
        cases=(lambda w:setattr(w,'model_absence',401),
            lambda w:setattr(w,'source_fault',True),
            lambda w:w.tools.update({P.TERMINAL_TOOL_ID:{'id':P.TERMINAL_TOOL_ID}}),
            lambda w:w.registry['TERMINAL_SERVER_CONNECTIONS'][0].pop('name'),
            lambda w:w.registry['TERMINAL_SERVER_CONNECTIONS'][0].update(id=P.TERMINAL_ID),
            lambda w:setattr(w,'foreign_session',{'id':w.actor['id'],'role':'user'}))
        for change in cases:
            with self.subTest(change=change):
                world,result,packet,error=self.exercise(change)
                self.assertIsNone(result);self.assertIsNotNone(error);self.assertIsNone(packet)
                self.assertFalse(any(method=='POST' for method,_,_,_ in world.calls))

    def test_explicit_cli_phase_writes_separate_journal_without_replacing_office_state(self):
        world,result,packet,error=self.exercise(cli=True)
        self.assertIsNone(error);self.assertTrue(result['passed']);self.assertEqual(result['phase'],'terminal-setup')
        self.assertFalse(result['inference_issued']);self.assertEqual(packet['stage'],'readback_ready')

    def test_native_null_registry_is_known_empty_without_fabricating_old_rows(self):
        _,result,packet,error=self.exercise(lambda w:w.registry.update(TERMINAL_SERVER_CONNECTIONS=None))
        self.assertIsNone(error);self.assertIsNone(packet['registry_before']['TERMINAL_SERVER_CONNECTIONS'])
        self.assertEqual(len(packet['registry_after']['TERMINAL_SERVER_CONNECTIONS']),1)

    def test_real_native_readiness_is_mandatory_and_partial_config_is_journalled(self):
        for change in (lambda w:w.health.update(status=False),lambda w:w.schema['paths']['/execute']['post'].update(operationId='fake_command'),
                       lambda w:w.schema['components']['schemas']['ExecRequest']['properties'].pop('command')):
            with self.subTest(change=change):
                world,result,packet,error=self.exercise(change)
                self.assertIsNone(result);self.assertIsNotNone(error)
                self.assertEqual(packet['stage'],'failed');self.assertFalse(packet['daemon_proxy_verified'])
                self.assertEqual(len(packet['journal']),1);self.assertTrue(packet['journal'][0]['returned'])
                self.assertFalse(world.tools)

    def test_post_failure_keeps_exact_unreturned_intent_without_rollback_retry(self):
        world,result,packet,error=self.exercise(lambda w:setattr(w,'failed_post','/api/v1/tools/create'))
        self.assertIsNotNone(error);self.assertIsNone(result);self.assertEqual(packet['stage'],'failed')
        self.assertTrue(packet['daemon_proxy_verified']);self.assertFalse(packet['journal'][-1]['returned'])
        self.assertEqual(packet['journal'][-1]['route'],'/api/v1/tools/create')
        self.assertEqual(sum(method=='POST' and route=='/api/v1/tools/create' for method,route,_,_ in world.calls),1)

    def test_context_budget_or_foreign_permission_drift_cannot_complete(self):
        for mutate in (lambda w:w.rows['corporate-documents']['params'].update(system='changed'),
                       lambda w:w.budget_user.update(spend=1),
                       lambda w:w.rows[P.TERMINAL_MODEL_ID]['access_grants'].append({'principal_type':'user','principal_id':'*','permission':'read'})):
            with self.subTest(mutate=mutate):
                world,result,packet,error=self.exercise(lambda w:setattr(w,'mutate_after_model',mutate))
                self.assertIsNone(result);self.assertIsNotNone(error);self.assertEqual(packet['stage'],'failed')


class TerminalNativeContractTests(unittest.IsolatedAsyncioTestCase):
    """Pinned native DTO and access bodies; config/group IO leaves only."""
    @classmethod
    def setUpClass(cls):
        import ast, hashlib, __future__
        from pydantic import BaseModel, ConfigDict
        cls.root=Path(os.environ.get('GOAL584_NATIVE_SOURCE_ROOT',str(HERE.parents[1]/
            'local/goal584/cost-display/open-webui/backend/open_webui')))
        cls.ns={'BaseModel':BaseModel,'ConfigDict':ConfigDict}
        pins={'routers/configs.py':'e417a2c7bff5c839f2f134e21f9d1901353999aa408f1cafcda014f66c62ca1e',
              'utils/access_control/__init__.py':'aed18ea3b7788597a8b4eaf741d32e07b0244bc390ab792e44bda611d324b568'}
        for path,names in (('routers/configs.py',{'TerminalServerConnection','TerminalServersConfigForm'}),
                           ('utils/access_control/__init__.py',{'has_access','has_connection_access'})):
            if not (cls.root/path).is_file():
                if 'GOAL584_NATIVE_SOURCE_ROOT' in os.environ:raise AssertionError('Pinned Terminal native source unavailable')
                raise unittest.SkipTest('Set GOAL584_NATIVE_SOURCE_ROOT for pinned native Terminal contract checks')
            raw=(cls.root/path).read_bytes().replace(b'\r\n',b'\n')
            assert hashlib.sha256(raw).hexdigest()==pins[path],path
            nodes=[node for node in ast.parse(raw).body if getattr(node,'name',None) in names]
            assert len(nodes)==len(names)
            exec(compile(ast.Module(body=nodes,type_ignores=[]),path,'exec',flags=__future__.annotations.compiler_flag),cls.ns)
        cls.ns['TerminalServersConfigForm'].model_rebuild(_types_namespace=cls.ns)

    async def test_actual_native_registry_dto_preserves_canonical_prefix_and_exposes_legacy_normalization(self):
        connection=dict(id='old',name='Old',enabled=False,url='http://old:8000',path='/openapi.json',key='private-old',
            auth_type='bearer',forward_cookies=False,config={'access_grants':[]},server_type=None,policy_id=None,vendor={'keep':[1]})
        form=self.ns['TerminalServersConfigForm'].model_validate({'TERMINAL_SERVER_CONNECTIONS':[connection]})
        self.assertEqual(form.model_dump()['TERMINAL_SERVER_CONNECTIONS'],[connection])
        legacy=copy.deepcopy(connection);legacy.pop('name')
        self.assertNotEqual(self.ns['TerminalServerConnection'].model_validate(legacy).model_dump(),legacy)
        # This exact native default insertion is why the provisioner rejects an
        # incomplete old prefix before POST rather than silently rewriting it.

    async def test_actual_native_connection_acl_accepts_actor_and_rejects_foreign_and_top_level_grants(self):
        from types import ModuleType,SimpleNamespace
        config=ModuleType('open_webui.config');config.BYPASS_ADMIN_ACCESS_CONTROL=True
        actor,foreign=SimpleNamespace(id=OWNER,role='user'),SimpleNamespace(id=CONTROL,role='user')
        connection={'config':{'access_grants':[{'principal_type':'user','principal_id':OWNER,'permission':'read'}]}}
        with patch.dict(sys.modules,{'open_webui.config':config}):
            check=self.ns['has_connection_access']
            self.assertTrue(await check(actor,connection,set()))
            self.assertFalse(await check(foreign,connection,set()))
            self.assertFalse(await check(actor,{'access_grants':connection['config']['access_grants']},set()))
            wrong=copy.deepcopy(connection);wrong['config']['access_grants'][0]['permission']='write'
            self.assertFalse(await check(actor,wrong,set()))
            self.assertTrue(await check(SimpleNamespace(id=CONTROL,role='admin'),connection,set()))

    def test_optin_proxy_mount_is_readonly_and_uses_the_same_private_daemon_key(self):
        import yaml
        tree=yaml.compose((HERE.parents[1]/'compose/goal584.office-terminal-proof.yml').read_text(encoding='utf8'))
        root={key.value:value for key,value in tree.value}
        services={key.value:value for key,value in root['services'].value}
        proxy=yaml.safe_load(yaml.serialize(services['proxy']))
        self.assertEqual(proxy['environment'],{'STAGING_TERMINAL_API_KEY':'${STAGING_TERMINAL_API_KEY:?Set a separate staging Terminal key}'})
        self.assertEqual(proxy['volumes'],[{'type':'bind','source':'../deploy/openwebui-tools/terminal_file_transfer.py',
            'target':'/proof/terminal_file_transfer.py','read_only':True,'bind':{'create_host_path':False}}])


if __name__ == "__main__":
    unittest.main()
