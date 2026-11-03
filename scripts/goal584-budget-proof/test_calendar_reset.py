"""Pinned native helper AST and isolation contracts; no DB/services/inference."""
import ast
import copy
from datetime import datetime, time, timedelta, timezone, tzinfo
import hashlib
import importlib.util
import io
import json
import operator
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from typing import Final, Iterable
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import prove_calendar_reset as P
UPSTREAM=HERE.parents[1]/"local/goal584/litellm/upstream"


def native_tree(relative):
    path=UPSTREAM/"litellm"/relative
    if not path.is_file():raise unittest.SkipTest("Pinned native source fixture unavailable")
    return ast.parse(path.read_text(encoding="utf-8"))


def native_duration():
    tree=native_tree("litellm_core_utils/duration_parser.py")
    nodes=[node for node in tree.body if isinstance(node,(ast.FunctionDef,ast.AnnAssign))]
    namespace={"datetime":datetime,"time":time,"timedelta":timedelta,"timezone":timezone,"tzinfo":tzinfo,
               "Final":Final,"ZoneInfo":ZoneInfo,"re":re,"verbose_logger":SimpleNamespace(warning=lambda *a:None)}
    exec(compile(ast.Module(body=nodes,type_ignores=[]),"<actual native duration_parser>","exec"),namespace)
    return namespace["get_next_standardized_reset_time"]


def packet():
    boundary="2026-11-30T21:00:00+00:00"
    before={"users":[{"user_id":"own","max_budget":.20,"spend":.20,"budget_duration":"1mo",
                       "budget_reset_at":boundary,"teams":[],"updated_at":"old"}],
            "keys":[{"user_id":"own","token":"a"*64,"max_budget":.20,"spend":.20,"total_spend":.20,
                      "budget_duration":"1mo","budget_reset_at":boundary,"updated_at":"old"}],
            "journal":[{"request_id":"actual-owner-shaped-test-row","spend":.20,"future_column":{"unchanged":True}}]}
    after=copy.deepcopy(before)
    for row in after["users"]+after["keys"]:
        row.update(spend=0,budget_reset_at="2026-12-31T21:00:00+00:00",updated_at="new")
    return before,after


class NativeSourceTests(unittest.TestCase):
    def test_native_source_fingerprints_are_the_exact_pinned_git_objects(self):
        if not (UPSTREAM/".git").exists():self.skipTest("Pinned native source repository unavailable")
        revision=subprocess.check_output(["git","-C",str(UPSTREAM),"rev-parse","HEAD"],text=True).strip()
        self.assertEqual(revision,P.REVISION)
        for path,digest in P.NATIVE_HASHES.items():
            content=subprocess.check_output(["git","-C",str(UPSTREAM),"show",P.REVISION+":litellm/"+path])
            self.assertEqual(hashlib.sha256(content).hexdigest(),digest,path)

    def test_actual_native_month_math_uses_moscow_midnight_strictly_next_month_at_boundary(self):
        compute=native_duration()
        cases=(("2026-11-30T20:59:59+00:00","2026-11-30T21:00:00+00:00"),
               ("2026-11-30T21:00:00+00:00","2026-12-31T21:00:00+00:00"),
               ("2026-11-30T21:00:01+00:00","2026-12-31T21:00:00+00:00"),
               ("2027-12-31T21:00:00+00:00","2028-01-31T21:00:00+00:00"),
               ("2028-02-28T21:00:00+00:00","2028-02-29T21:00:00+00:00"))
        for current,expected in cases:
            with self.subTest(current=current):
                result=compute("1mo",P.timestamp(current),"Europe/Moscow",time(0,0))
                self.assertEqual(result.astimezone(timezone.utc),P.timestamp(expected))
                self.assertEqual((result.day,result.hour,result.minute),(1,0,0))

    def test_actual_prisma_scalar_filter_is_lt_so_exact_boundary_is_not_due(self):
        tree=native_tree("proxy/utils.py")
        filters=[]
        for node in ast.walk(tree):
            if isinstance(node,ast.Dict):
                for key,value in zip(node.keys,node.values):
                    if isinstance(key,ast.Constant) and key.value=="budget_reset_at" and isinstance(value,ast.Dict):
                        if any(isinstance(child,ast.Name) and child.id=="reset_at" for child in value.values):filters.append(value)
        self.assertGreaterEqual(len(filters),2)
        boundary=P.timestamp("2026-11-30T21:00:00+00:00")
        for value in filters:
            for offset,expected in ((-1,False),(0,False),(1,True)):
                where=eval(compile(ast.Expression(value),"<actual native Prisma cutoff>","eval"),{"reset_at":boundary+timedelta(seconds=offset)})
                self.assertEqual(set(where),{"lt"})
                self.assertEqual(operator.lt(boundary,where["lt"]),expected)

    def test_actual_native_advanced_counter_recognizes_real_prisma_datetimes_under_local_clock(self):
        tree=native_tree("proxy/common_utils/reset_budget_job.py")
        nodes=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in ("_as_utc","_count_advanced")]
        self.assertEqual(len(nodes),2)
        boundary=P.timestamp("2026-11-30T21:00:00+00:00")
        clock=P.clock_at(boundary+timedelta(seconds=1))
        namespace={"datetime":clock,"timezone":timezone,"Final":Final,"Iterable":Iterable}
        exec(compile(ast.Module(body=nodes,type_ignores=[]),"<actual native advanced count>","exec"),namespace)
        next_date=P.timestamp("2026-12-31T21:00:00+00:00")
        self.assertIsInstance(next_date,clock)
        self.assertEqual(namespace["_count_advanced"]([next_date,boundary],clock.now(timezone.utc)),1)

    def test_only_two_native_clock_modules_are_patched_and_sql_is_readonly(self):
        source=ast.parse(Path(P.__file__).read_text(encoding="utf-8"))
        patches=[node for node in ast.walk(source) if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)
                 and isinstance(node.func.value,ast.Name) and node.func.value.id=="patch" and node.func.attr=="object"]
        self.assertEqual({(node.args[0].id,node.args[1].value) for node in patches},
                         {("job_module","datetime"),("tz_module","datetime")})
        try:from pglast import parse_sql
        except ImportError:self.skipTest("Optional pglast unavailable")
        for query in (P.COUNTS_SQL,P.ROWS_SQL):
            self.assertTrue(all(type(item.stmt).__name__=="SelectStmt" for item in parse_sql(query)))


class IsolationTests(unittest.TestCase):
    def fixture(self,directory):
        project="goal584-calendar-"+"a"*12
        args=SimpleNamespace(project=project,private_state=Path(directory)/"calendar-state.private.json")
        attest={"schema":1,"project":project,"proxy_container_id":"b"*64,"postgres_container_id":"c"*64,
                "redis_container_id":"d"*64,"redis_run_id":"e"*40}
        env={"PROOF_CALENDAR_PROJECT":project,"HOSTNAME":"b"*12,"DATABASE_URL":"postgresql://proof:private@postgres:5432/goal584_calendar"}
        config={"general_settings":{"database_url":env["DATABASE_URL"],"disable_reset_budget":True,
                    "coordination_redis":{"host":"redis","port":6379}},
                "litellm_settings":{"timezone":"Europe/Moscow","budget_reset_time":"00:00","budget_rollover":False,"num_retries":0},
                "model_list":[{"model_name":"goal584-"+letter,"litellm_params":{"model":"openai/goal584-fake-"+letter,
                                   "api_base":"http://provider:8000/v1"}} for letter in ("a","b")]}
        return args,attest,config,env

    def test_fresh_project_db_container_and_native_settings_are_required(self):
        with tempfile.TemporaryDirectory() as directory:
            values=self.fixture(directory);P.require_isolated(*values)
            for mutate in (lambda v:v[0].__setattr__("project","goal584-native-budget-proof"),
                           lambda v:v[3].update(HOSTNAME="other"),
                           lambda v:v[2]["general_settings"].update(database_url=v[3]["DATABASE_URL"].replace("goal584_calendar","goal584")),
                           lambda v:v[2]["general_settings"].update(custom_auth="litellm_auth.gateway_auth"),
                           lambda v:v[2]["general_settings"].update(disable_reset_budget=False),
                           lambda v:v[2]["litellm_settings"].update(budget_rollover=True),
                           lambda v:v[2]["litellm_settings"].update(timezone="UTC"),
                           lambda v:v[2]["model_list"][0]["litellm_params"].update(api_base="https://external.invalid/v1")):
                with self.subTest(mutation=mutate):
                    bad=self.fixture(directory);mutate(bad)
                    with self.assertRaises(P.ProofError):P.require_isolated(*bad)
            (Path(directory)/"webui-state.private.json").write_text("{}",encoding="utf-8")
            with self.assertRaisesRegex(P.ProofError,"refuses"):P.require_isolated(*self.fixture(directory))

    def test_global_sweep_population_cannot_include_extra_users_keys_or_other_budget_owners(self):
        empty={name:0 for name in P.TABLES}
        P.population(empty,{"users":[],"keys":[],"journal":[]})
        own=copy.deepcopy(empty);own[P.TABLES[0]]=own[P.TABLES[1]]=1;own[P.TABLES[2]]=1
        snapshot={"users":[{"user_id":"own","models":["goal584-a"]}],"keys":[{"user_id":"own","token":"a"*64,"models":["goal584-a"]}],
                  "journal":[{"user":"own","api_key":"a"*64}]}
        P.population(own,snapshot,"own","a"*64)
        for table in P.TABLES:
            bad=copy.deepcopy(own);bad[table]=3
            with self.subTest(table=table),self.assertRaises(P.ProofError):P.population(bad,snapshot,"own","a"*64)
        snapshot["keys"][0]["user_id"]="foreign"
        with self.assertRaises(P.ProofError):P.population(own,snapshot,"own","a"*64)

    def test_reset_verification_preserves_full_journal_unknown_fields_caps_identity_and_lifetime_total(self):
        before,after=packet();next_boundary=P.timestamp("2026-12-31T21:00:00+00:00")
        original=copy.deepcopy([before,after]);P.reset_delta(before,after,next_boundary)
        self.assertEqual([before,after],original)
        for mutate in (lambda s:s["keys"][0].update(total_spend=.4),lambda s:s["keys"][0].update(max_budget=.4),
                       lambda s:s["users"][0].update(user_id="foreign"),
                       lambda s:s["journal"][0]["future_column"].update(unchanged=False),
                       lambda s:s["users"][0].update(spend=.000000000001)):
            bad=copy.deepcopy(after);mutate(bad)
            with self.subTest(mutation=mutate),self.assertRaises(P.ProofError):P.reset_delta(before,bad,next_boundary)


class CalendarHTTP:
    """Replace only HTTP I/O; execute the real request/infer/readback methods."""

    def __init__(self):
        self.rows = []
        self.urls = []
        self.boundary = "2026-11-30T21:00:00+00:00"
        self.change = lambda path, payload: None

    def open(self, request, timeout):
        self.urls.append(request.full_url)
        route = urlsplit(request.full_url)
        if route.path == "/v1/chat/completions":
            body = json.loads(request.data)
            assert request.get_header("Authorization") == "Bearer sk-private-synthetic"
            assert body["model"] == "goal584-a"
            response_id = "chatcmpl-goal584-" + format(len(self.rows) + 1, "032x")
            usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
            self.rows.append({"request_id": response_id, "user": "own", "api_key": "a" * 64,
                              "model_group": "goal584-a", "metadata": body["metadata"], "spend": .20, **usage})
            payload = {"id": response_id, "usage": usage}
        elif route.path == "/spend/logs/v2":
            assert parse_qs(route.query)["user_id"] == ["own"]
            payload = {"data": copy.deepcopy(self.rows), "total_pages": 1}
        else:
            info = {"user_id": "own", "models": ["goal584-a"], "spend": .20, "max_budget": .20,
                    "budget_duration": "1mo", "budget_reset_at": self.boundary}
            if route.path == "/user/info":
                assert parse_qs(route.query)["user_id"] == ["own"]
                payload = {"user_info": {**info, "teams": []}, "keys": []}
            elif route.path == "/key/info":
                assert parse_qs(route.query) == {"key": ["a" * 64]}
                payload = {"info": {**info, "total_spend": len(self.rows) * .20}}
            else:
                raise AssertionError("Unexpected HTTP route: " + route.path)
        self.change(route.path, payload)
        response = io.BytesIO(json.dumps(payload).encode())
        response.code = 200
        response.headers = {}
        return response


class CalendarInferenceTests(unittest.TestCase):
    def fixture(self):
        proof = P.CalendarProof("http://127.0.0.1:4000", "synthetic-master", .01, {})
        proof.users = ["own"]
        proof.keys["own", "goal584-a"] = {"token": "sk-private-synthetic", "alias": "calendar",
                                          "hash": "a" * 64, "cap": P.CALL_COST}
        proof.opener = CalendarHTTP()
        proof.reset_at = P.timestamp(proof.opener.boundary)
        return proof

    def next_period(self, proof):
        # An external native reset is represented only by its readback; this
        # transport regression does not simulate or claim to execute the job.
        proof.opener.boundary = "2026-12-31T21:00:00+00:00"
        proof.reset_at = P.timestamp(proof.opener.boundary)

    def test_actual_inherited_infer_checks_calendar_period_and_lifetime_in_both_phases(self):
        proof = self.fixture()
        self.assertIs(P.CalendarProof.infer, P.NativeProof.infer)
        self.assertIs(P.CalendarProof.request, P.NativeProof.request)
        proof.infer("own", "goal584-a")
        proof.calendar_api_readback()
        first = copy.deepcopy(proof.receipt["calendar_inference_readback"])
        self.next_period(proof)
        proof.infer("own", "goal584-a")
        proof.calendar_api_readback()
        final = proof.receipt["calendar_inference_readback"]
        self.assertEqual((first["journal_count"], final["journal_count"]), (1, 2))
        self.assertEqual((first["period_spend_usd"], final["period_spend_usd"]), ("0.20", "0.20"))
        self.assertEqual((first["lifetime_spend_usd"], final["lifetime_spend_usd"]), ("0.20", "0.40"))
        self.assertEqual((first["budget_duration"], final["budget_duration"]), ("1mo", "1mo"))
        self.assertNotEqual(first["budget_reset_at"], final["budget_reset_at"])
        self.assertEqual(set(proof.keys), {("own", "goal584-a")})
        self.assertEqual(len(proof.expected), 2)
        self.assertEqual(len(proof.receipt["calls"]), 2)
        self.assertTrue(all("sk-private-synthetic" not in url for url in proof.opener.urls))

    def test_inherited_infer_rejects_bad_response_or_calendar_readback(self):
        mutations = (
            ("response_usage", "/v1/chat/completions", lambda p: p["usage"].update(total_tokens=14)),
            ("old_duration", "/user/info", lambda p: p["user_info"].update(budget_duration="30d")),
            ("foreign_model", "/key/info", lambda p: p["info"].update(models=["goal584-b"])),
            ("foreign_payer", "/key/info", lambda p: p["info"].update(user_id="foreign")),
            ("wrong_period", "/key/info", lambda p: p["info"].update(spend=.40)),
            ("lost_lifetime", "/key/info", lambda p: p["info"].update(total_spend=.20)),
            ("old_boundary", "/user/info", lambda p: p["user_info"].update(budget_reset_at="2026-11-30T21:00:00Z")),
            ("wrong_cap", "/key/info", lambda p: p["info"].update(max_budget=.40)),
            ("wrong_key", "/spend/logs/v2", lambda p: p["data"][-1].update(api_key="foreign")),
            ("wrong_id", "/spend/logs/v2", lambda p: p["data"][-1].update(request_id="foreign")),
            ("wrong_lineage", "/spend/logs/v2", lambda p: p["data"][-1]["metadata"]["spend_logs_metadata"].update(chat_id="foreign")),
            ("duplicate_root", "/spend/logs/v2", lambda p: p["data"].__setitem__(1, copy.deepcopy(p["data"][0]))),
        )
        for name, route, mutate in mutations:
            with self.subTest(name=name):
                proof = self.fixture()
                proof.infer("own", "goal584-a")
                proof.calendar_api_readback()
                self.next_period(proof)
                proof.opener.change = lambda path, payload: mutate(payload) if path == route else None
                with self.assertRaises(P.ProofError):
                    proof.infer("own", "goal584-a")
                    proof.calendar_api_readback()
                # A failed second phase cannot overwrite the verified first readback.
                self.assertEqual(proof.receipt["calendar_inference_readback"]["journal_count"], 1)

    def test_journal_ready_does_not_require_materialized_api_counters_yet(self):
        proof = self.fixture()
        def lagging_api(path, payload):
            if path in ("/user/info", "/key/info"):
                raise AssertionError("Inference cannot read unsettled API counters")
        proof.opener.change = lagging_api
        proof.infer("own", "goal584-a")
        self.assertEqual(proof.receipt["calendar_journal_count"], 1)
        self.assertFalse(any(urlsplit(url).path in ("/user/info", "/key/info") for url in proof.opener.urls))
        proof.opener.change = lambda path, payload: None
        proof.calendar_api_readback()
        self.next_period(proof)
        proof.opener.change = lagging_api
        proof.infer("own", "goal584-a")
        proof.opener.change = lambda path, payload: None
        proof.calendar_api_readback()
        self.assertEqual(proof.receipt["calendar_inference_readback"]["lifetime_spend_usd"], "0.40")

    def test_generated_secret_remains_registered_when_qualify_fails(self):
        async def failing_qualify(args, attest, receipt, secrets):
            secrets.append("sk-generated-before-error")
            raise P.ProofError("Synthetic failure with sk-generated-before-error")

        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            argv = ["calendar", "--project", "goal584-calendar-" + "a" * 12,
                    "--attestation", str(target / "attestation"), "--private-state", str(target / "state"),
                    "--receipt", str(target / "receipt")]
            output = io.StringIO()
            with patch.object(sys, "argv", argv), patch.object(P, "read_private", return_value={}), \
                 patch.object(P, "qualify", failing_qualify), patch.object(P, "write_private") as write, redirect_stdout(output):
                with self.assertRaisesRegex(P.ProofError, "Credential-bearing calendar receipt suppressed"):
                    P.main()
            write.assert_not_called()
            self.assertEqual(output.getvalue(), "")


if __name__=="__main__":unittest.main()
