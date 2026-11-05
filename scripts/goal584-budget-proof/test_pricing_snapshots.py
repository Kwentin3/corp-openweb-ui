"""Native published snapshot/GET projection mutations; no runtime or inference."""
import ast
import asyncio
from collections.abc import Callable, Sequence
from contextlib import redirect_stdout
import copy
from dataclasses import dataclass, fields
from datetime import datetime, timedelta, timezone
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType
from typing import Final, TypedDict
import unittest
from unittest.mock import Mock, patch

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import prove_pricing_snapshots as p
from prove_native_budgets import NativeProof

UPSTREAM = REPO / "local/goal584/litellm/upstream/litellm"
ADAPTER = REPO / "deploy/openwebui-budgets/pricing_snapshot.py"
IDS = [f"{n:08d}-1111-4111-8111-111111111111" for n in range(1, 6)]


def execute(nodes, namespace):
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), "actual_native_pricing_ast", "exec",
                 flags=__import__("__future__").annotations.compiler_flag), namespace)


def nodes(path, names):
    result = [node for node in ast.parse(path.read_text(encoding="utf8")).body if getattr(node, "name", None) in names]
    if {node.name for node in result} != set(names):
        raise AssertionError("Native pricing source changed")
    return result


class PricingProofTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not ADAPTER.exists() or not (UPSTREAM / "litellm_core_utils/litellm_logging.py").exists():
            raise unittest.SkipTest("Native/callback source unavailable; no runtime acceptance implied")
        cls.native_module = ModuleType("pricing_proof_native_ast")
        cls.ns = cls.native_module.__dict__
        sys.modules[cls.native_module.__name__] = cls.native_module
        base = type("CustomLogger", (), {})  # Only external extension base is doubled.
        cls.ns.update(dataclass=dataclass, Final=Final, Callable=Callable, Sequence=Sequence,
                      TypedDict=TypedDict, CustomLogger=base)
        execute(nodes(UPSTREAM / "litellm_core_utils/llm_cost_calc/utils.py", {"BilledTokenRates", "_custom_pricing_rates"}), cls.ns)
        execute(nodes(UPSTREAM / "types/utils.py", {"CostBreakdown"}), cls.ns)
        execute(nodes(UPSTREAM / "litellm_core_utils/core_helpers.py",
                      {"get_litellm_metadata_from_kwargs", "add_missing_spend_metadata_to_litellm_metadata"}), cls.ns)
        logging_class = nodes(UPSTREAM / "litellm_core_utils/litellm_logging.py", {"Logging"})[0]
        methods = {"add_dynamic_callback", "_with_dynamic_callback", "set_cost_breakdown"}
        execute([ast.ClassDef(name="Logging", bases=[], keywords=[], decorator_list=[],
                body=[node for node in logging_class.body if getattr(node, "name", None) in methods])], cls.ns)
        writer = nodes(UPSTREAM / "proxy/spend_tracking/spend_tracking_utils.py", {"get_logging_payload"})[0]
        payload = next(node for node in ast.walk(writer) if isinstance(node, ast.Call)
                       and isinstance(node.func, ast.Name) and node.func.id == "SpendLogsPayload")
        expressions = {keyword.arg: keyword.value for keyword in payload.keywords}
        cls.row_expression = compile(ast.fix_missing_locations(ast.Expression(ast.Dict(
            keys=[ast.Constant("spend"), ast.Constant("metadata")],
            values=[expressions["spend"], expressions["metadata"]]))), "native_row_expressions", "eval")
        # These tests qualify rate copying without native proxy auth. The
        # descriptor helpers must remain unused; their behavior is exercised
        # against real native owners in test_pricing_snapshot.py.
        unused_descriptor_helper = Mock(side_effect=AssertionError("Unqualified descriptor inspected billing usage"))
        cls.addClassCleanup(unused_descriptor_helper.assert_not_called)
        modules = {}
        for name, values in {
            "litellm.integrations.custom_logger": {"CustomLogger": base},
            "litellm.litellm_core_utils.core_helpers": {"get_litellm_metadata_from_kwargs": cls.ns["get_litellm_metadata_from_kwargs"]},
            "litellm.litellm_core_utils.litellm_logging": {"Logging": cls.ns["Logging"]},
            "litellm.litellm_core_utils.llm_cost_calc.utils": {"BilledTokenRates": cls.ns["BilledTokenRates"],
                "_cache_token_counts": unused_descriptor_helper, "_reasoning_token_count": unused_descriptor_helper},
            "litellm.litellm_core_utils.llm_cost_calc.guardrail_cost": {"guardrail_information_cost": unused_descriptor_helper},
            "litellm.types.utils": {"Usage": type("UnusedUsage", (), {})},
        }.items():
            module = ModuleType(name); module.__dict__.update(values); modules[name] = module
        spec = importlib.util.spec_from_file_location("pricing_snapshot", ADAPTER)
        cls.adapter = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, modules):
            spec.loader.exec_module(cls.adapter)
        cls.patch = patch.dict(sys.modules, {"pricing_snapshot": cls.adapter})
        cls.patch.start()

    @classmethod
    def tearDownClass(cls):
        cls.patch.stop()
        sys.modules.pop(cls.native_module.__name__, None)

    def state(self):
        return {"schema": 1, "stage": "setup_complete", "run_id": "goal584-pricing-fixture",
                "users": [{"id": IDS[0]}, {"id": IDS[1]}], "admin": {"id": IDS[2], "password": "private-plain-password"},
                "bootstrap_fixture": {"employee": {"id": IDS[3]}}, "service_fixture": {"payer_id": IDS[4]}}

    def raw(self, index=1, version=1, payer=IDS[0]):
        # Actual native rate factory -> Logging owner -> actual callback -> same raw row metadata.
        owner = self.ns["Logging"]()
        for key in ("dynamic_input_callbacks", "dynamic_success_callbacks", "dynamic_async_success_callbacks",
                    "dynamic_failure_callbacks", "dynamic_async_failure_callbacks"):
            setattr(owner, key, None)
        owner.stream = False
        owner.model_call_details = {"response_cost": .2 if version == 1 else .4,
            "litellm_params": {"metadata": {"spend_logs_metadata": {"owui_budget": {"private": "discard"}}}}}
        rate = .01 if version == 1 else .02
        rates = self.ns["_custom_pricing_rates"]({"input_cost_per_token": rate, "output_cost_per_token": rate * 2})
        costs = (.1, .1, .2) if version == 1 else (.2, .2, .4)
        owner.set_cost_breakdown(*costs, 0., billed_token_rates=rates)
        asyncio.run(self.adapter.handler.async_pre_call_hook(None, None, {"litellm_logging_obj": owner}, "acompletion"))
        asyncio.run(owner.dynamic_async_success_callbacks[0].async_logging_hook(owner.model_call_details, None, "acompletion"))
        metadata = owner.model_call_details["litellm_params"]["metadata"]
        published = eval(self.row_expression, {"kwargs": owner.model_call_details,
                         "clean_metadata": metadata, "safe_dumps": json.dumps})
        return {"request_id": "chatcmpl-goal584-" + f"{index:032x}", "user": payer, "api_key": f"{index:064x}",
                "model": "goal584-fake-a", "model_group": "goal584-a", "model_id": "goal584-deployment-a",
                "status": "success", "spend": published["spend"],
                "prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15,
                "metadata": published["metadata"], "messages": {"private": "do not export"},
                "response": {"headers": {"Authorization": "sk-" + "x" * 32}}}

    def native(self, rows):
        # Execute actual NativeProof.logs pagination; double only native HTTP GET.
        native = NativeProof.__new__(NativeProof)
        native.started_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        def get(method, path, query):
            self.assertEqual((method, path, query["page"], query["page_size"]), ("GET", "/spend/logs/v2", 1, 100))
            return {"data": [copy.deepcopy(row) for row in rows if row["user"] == query["user_id"]], "total_pages": 1}
        native.ok = Mock(side_effect=get)
        return native

    def observed(self, rows):
        native = self.native(rows)
        result = p.observe(self.state(), native)
        self.assertEqual(native.ok.call_count, 5)
        self.assertEqual({call.kwargs["query"]["user_id"] for call in native.ok.call_args_list}, set(IDS))
        return result

    def expected(self, version=1):
        return p.fixture_expectation("0.01" if version == 1 else "0.02", "0.02" if version == 1 else "0.04",
                                     "0.20" if version == 1 else "0.40", "goal584-a")

    def receipt(self, rows):
        scope, projected, reads = self.observed(rows)
        return {"schema": 1, "proof": p.PROOF, "passed": True, **p.qualify(scope, projected, reads, self.expected())}

    def test_actual_native_published_snapshot_survives_exact_same_row_projection(self):
        raw = self.raw()
        original = copy.deepcopy(raw)
        scope, rows, reads = self.observed([raw])
        result = p.qualify(scope, rows, reads, self.expected(), raw["request_id"])
        published = json.loads(raw["metadata"])["spend_logs_metadata"][p.SNAPSHOT_KEY]
        self.assertEqual(rows[0]["metadata"]["spend_logs_metadata"][p.SNAPSHOT_KEY], published)
        self.assertEqual(set(rows[0]), p.ROW_FIELDS | {"api_key_hash"})
        self.assertEqual(rows[0]["api_key_hash"], raw["api_key"])
        self.assertEqual(rows[0]["model_id"], "goal584-deployment-a")
        self.assertEqual(result["row_counts"]["qualified_witnesses"], 1)
        self.assertNotIn("private", json.dumps(result)); self.assertNotIn("Authorization", json.dumps(result))
        rows[0]["metadata"]["spend_logs_metadata"][p.SNAPSHOT_KEY]["rates"][p.rate_fields()[0]] = 99
        self.assertEqual(raw, original)

    def test_public_callback_fields_match_actual_native_frozen_definition(self):
        self.assertEqual(tuple(field.name for field in fields(self.ns["BilledTokenRates"])), p.rate_fields())
        self.assertEqual(len(p.rate_fields()), 7)

    def test_compare_requires_new_actual_witness_and_keeps_all_old_rows(self):
        old = self.raw()
        zero = self.raw(3, payer=IDS[4]); zero.update(spend=0., prompt_tokens=0, completion_tokens=0, total_tokens=0, status="failure", metadata={})
        prior = self.receipt([old, zero])
        new = self.raw(2, version=2, payer=IDS[2])
        scope, rows, reads = self.observed([old, new, zero])
        result = p.qualify(scope, rows, reads, self.expected(2), new["request_id"], prior)
        self.assertEqual(result["row_counts"]["old_immutable"], 2)
        self.assertEqual(result["row_counts"]["new"], 1)
        self.assertEqual((result["row_counts"]["positive"], result["row_counts"]["zero"]), (2, 1))
        self.assertEqual(result["row_counts"]["snapshot_availability"]["missing"], 1)
        with self.assertRaises(p.ProofError): p.qualify(scope, prior["rows"], reads, self.expected(2), prior=prior)
        with self.assertRaises(p.ProofError): p.qualify(scope, rows, reads, self.expected(2), old["request_id"], prior)
        without_zero = [row for row in rows if row["spend"] > 0]
        with self.assertRaises(p.ProofError): p.qualify(scope, without_zero, reads, self.expected(2), prior=prior)

    def test_comparison_cannot_substitute_another_model_for_a_fixture_price_change(self):
        prior = self.receipt([self.raw()])
        scope, rows, reads = self.observed([self.raw(), self.raw(2, version=2)])
        changed = {**self.expected(2), "model": "goal584-b"}
        with self.assertRaises(p.ProofError): p.qualify(scope, rows, reads, changed, prior=prior)
        with self.assertRaises(p.ProofError): p.fixture_expectation("0.01", "0.04", "0.20", "goal584-a")

    def test_changed_old_cost_usage_snapshot_identity_or_missing_row_fails(self):
        old, new = self.raw(), self.raw(2, version=2)
        prior = self.receipt([old])
        mutations = [lambda row: row.update(spend=.4), lambda row: row["usage"].update(prompt_tokens=11, total_tokens=16),
                     lambda row: row.update(model_id="changed-native-deployment"), lambda row: row.update(api_key_hash="f" * 64),
                     lambda row: row["metadata"]["spend_logs_metadata"][p.SNAPSHOT_KEY].update(observed_at_utc="2026-01-01T00:00:00Z")]
        for mutate in mutations:
            scope, rows, reads = self.observed([old, new]); mutate(rows[0])
            with self.subTest(mutate=mutate), self.assertRaises(p.ProofError):
                p.qualify(scope, rows, reads, self.expected(2), new["request_id"], prior)
        scope, rows, reads = self.observed([new])
        with self.assertRaises(p.ProofError): p.qualify(scope, rows, reads, self.expected(2), prior=prior)

    def test_missing_or_unknown_required_snapshot_fails_without_zero_fallback(self):
        with patch.dict(sys.modules, {"pricing_snapshot": None}), self.assertRaisesRegex(p.ProofError, "module is unavailable"):
            p.rate_fields()
        for missing in (True, False):
            raw = self.raw()
            if missing: raw["metadata"] = {}
            else:
                meta = json.loads(raw["metadata"]); snapshot = meta["spend_logs_metadata"][p.SNAPSHOT_KEY]
                snapshot.update(availability="unknown", rates=dict.fromkeys(p.rate_fields())); raw["metadata"] = meta
            scope, rows, reads = self.observed([raw])
            for witness in (None, raw["request_id"]):
                with self.subTest(missing=missing, witness=witness), self.assertRaises(p.ProofError):
                    p.qualify(scope, rows, reads, self.expected(), witness)

    def test_wrong_witness_model_status_usage_and_native_cost_are_rejected(self):
        for values in ({"model_group": "goal584-b"}, {"model": "foreign-physical-model"}, {"status": "failure"},
                       {"prompt_tokens": 11, "total_tokens": 16}, {"spend": .4}):
            raw = self.raw(); raw.update(values)
            scope, rows, reads = self.observed([raw])
            with self.subTest(values=values), self.assertRaises(p.ProofError):
                p.qualify(scope, rows, reads, self.expected(), raw["request_id"])

    def test_partial_preserves_other_five_values_and_honest_availability(self):
        raw = self.raw(); meta = json.loads(raw["metadata"]); snapshot = meta["spend_logs_metadata"][p.SNAPSHOT_KEY]
        extras = [0., .123, None, .456, None]
        for name, value in zip(p.rate_fields()[2:], extras): snapshot["rates"][name] = value
        snapshot["availability"] = "partial"; raw["metadata"] = meta
        scope, rows, reads = self.observed([raw]); result = p.qualify(scope, rows, reads, self.expected())
        self.assertEqual(result["rows"][0]["metadata"]["spend_logs_metadata"][p.SNAPSHOT_KEY], snapshot)

    def test_invalid_rate_primitives_schema_availability_or_utc_are_rejected(self):
        template = json.loads(self.raw()["metadata"])["spend_logs_metadata"][p.SNAPSHOT_KEY]
        mutations = [lambda s: s["rates"].pop(p.rate_fields()[-1]), lambda s: s["rates"].update(input_cost_per_token=True),
                     lambda s: s["rates"].update(input_cost_per_token=float("inf")), lambda s: s["rates"].update(input_cost_per_token="0.01"),
                     lambda s: s.update(availability="unknown"), lambda s: s.update(tariff_version="invented"),
                     lambda s: s.update(schema=True), lambda s: s.update(observed_at_utc="2026-02-30T00:00:00Z"),
                     lambda s: s.update(observed_at_utc="2026-01-01T03:00:00+03:00")]
        for mutate in mutations:
            snapshot = copy.deepcopy(template); mutate(snapshot)
            with self.subTest(mutate=mutate), self.assertRaises(p.ProofError): p.validate_snapshot(snapshot)

    def test_duplicate_foreign_or_secret_bearing_rows_are_rejected(self):
        with self.assertRaises(p.ProofError): self.observed([self.raw(), self.raw()])
        raw = self.raw(); raw["user"] = "ffffffff-1111-4111-8111-111111111111"
        with self.assertRaises(p.ProofError): p.project_row(raw, set(IDS))
        for changes in ({"api_key": "sk-" + "x" * 32}, {"model": "sk-" + "x" * 32},
                        {"model_id": "eyJaaa.bbb.ccc"}):
            raw = self.raw(); raw.update(changes)
            with self.subTest(changes=list(changes)), self.assertRaises(p.ProofError): self.observed([raw])
        raw = self.raw(); raw["model_id"] = "private-plain-password"
        scope, rows, reads = self.observed([raw])
        with self.assertRaises(p.ProofError):
            p.qualify(scope, rows, reads, self.expected(), secrets=p.private_credentials(self.state()))

    def test_prior_receipt_is_bounded_and_cannot_add_unapproved_metadata(self):
        prior = self.receipt([self.raw()])
        prior["rows"][0]["metadata"]["raw_headers"] = {"Authorization": "secret"}
        scope, rows, reads = self.observed([self.raw(), self.raw(2, version=2)])
        with self.assertRaises(p.ProofError): p.qualify(scope, rows, reads, self.expected(2), prior=prior)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prior.json"; path.write_text('{"bad":NaN}', encoding="utf8")
            with self.assertRaises(p.ProofError): p.read_prior(path)
            path.write_text(" " * (p.MAX_BYTES + 1), encoding="utf8")
            with self.assertRaises(p.ProofError): p.read_prior(path)

    def test_cli_record_uses_existing_client_and_writes_only_safe_receipt(self):
        raw = self.raw(); native = self.native([raw]); state = self.state()
        external = ModuleType("provision_webui")
        external.OPERATOR_STATE = Path("/proof-private/gateway-state.private.json")
        external.read_private = Mock(return_value=state)
        external.native_client = Mock(return_value=native)
        external.write_private = Mock()
        arguments = [str(HERE / "prove_pricing_snapshots.py"), "--mode", "record", "--private-state", str(p.STATE),
                     "--receipt", "/proof-private/pricing.safe.json", "--expected-input-rate", "0.01",
                     "--expected-output-rate", "0.02", "--expected-cost", "0.20", "--witness-request-id", raw["request_id"]]
        with patch.dict(sys.modules, {"provision_webui": external}), patch.object(sys, "argv", arguments), redirect_stdout(io.StringIO()):
            self.assertEqual(p.main(), 0)
        external.native_client.assert_called_once_with(state)
        receipt = external.write_private.call_args.args[1]
        self.assertTrue(receipt["passed"])
        self.assertEqual(receipt["rows"][0]["request_id"], raw["request_id"])
        self.assertNotIn("password", json.dumps(receipt))


if __name__ == "__main__": unittest.main()
