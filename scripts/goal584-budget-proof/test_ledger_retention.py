"""Mutation checks at raw DB/chat boundaries; no live fixture or inference."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
spec = importlib.util.spec_from_file_location("goal584_retention_under_test", HERE / "prove_ledger_retention.py")
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
IDS = [f"{n:08d}-1111-4111-8111-111111111111" for n in range(1, 10)]
ACTOR, CHAT, ANSWER, USER_MESSAGE = IDS[0], IDS[5], IDS[6], IDS[7]
SCOPE = dict(schema=1, category="personal", user_id=ACTOR, chat_id=CHAT, root_chat_id=CHAT,
             answer_id=ANSWER, root_answer_id=ANSWER, call_id=IDS[8], model="goal584-a")


def raw_snapshot():
    users = [dict(user_id=uid, spend=.2 if uid == ACTOR else 0, max_budget=20,
                  models=["goal584-a", "goal584-b"], budget_duration="1mo", budget_reset_at="2026-12-01T00:00:00Z") for uid in IDS[:5]]
    keys = [dict(token=f"{n:064x}", user_id=uid, spend=.2 if n == 1 else 0, max_budget=10,
                 models=["goal584-a" if n % 2 else "goal584-b"], budget_duration="1mo", budget_reset_at="2026-12-01T00:00:00Z")
            for n,uid in enumerate([uid for uid in IDS[:4] for _ in range(2)] + [IDS[4]], 1)]
    row = dict(request_id="chatcmpl-goal584-" + "a"*32, user=ACTOR, api_key=keys[0]["token"], spend=.2,
               metadata={"spend_logs_metadata":{"owui_budget":SCOPE}}, session_id=CHAT, model_group="goal584-a",
               messages={}, response="{}", proxy_server_request=None, arbitrary_future_column={"kind":"normal"})
    return dict(journal=[row], journal_count=1, users=users, users_count=5, keys=keys, keys_count=9)


def saved_chat():
    return dict(id=CHAT, user_id=ACTOR, meta={}, chat={"history":{"messages":{
        USER_MESSAGE:dict(id=USER_MESSAGE, role="user", content="Hi", user_id=ACTOR),
        ANSWER:dict(id=ANSWER, role="assistant", content="Proof", user_id=ACTOR, done=True),
    }}})


class RawContractTests(unittest.TestCase):
    def test_full_raw_snapshot_order_is_canonical_and_financial_mutations_fail(self):
        original = raw_snapshot()
        before = p.normalize_snapshot(original, set(IDS[:5]))
        ordered = copy.deepcopy(original)
        ordered["keys"].reverse()
        p.compare_snapshots(before, p.normalize_snapshot(ordered, set(IDS[:5])))
        for mutate in [lambda s:s["journal"].clear(), lambda s:s["journal"][0].update(spend=.1),
                       lambda s:s["journal"][0].update(request_id="different-native-request"),
                       lambda s:s["keys"][0].update(spend=.3), lambda s:s["users"][0].update(max_budget=30),
                       lambda s:s["journal"][0]["arbitrary_future_column"].update(kind="altered")]:
            changed = copy.deepcopy(original)
            mutate(changed)
            with self.subTest(mutation=mutate), self.assertRaises(p.ProofError):
                p.compare_snapshots(before, p.normalize_snapshot(changed, set(IDS[:5])))

    def test_query_reads_all_columns_in_readonly_transaction_and_rejects_non_uuid(self):
        sql = p.snapshot_sql(IDS[:5])
        self.assertIn("READ ONLY", sql)
        self.assertEqual(sql.count("SELECT * FROM"), 3)
        self.assertEqual(sql.count("to_jsonb(r)"), 3)
        for table in ["LiteLLM_SpendLogs","LiteLLM_UserTable","LiteLLM_VerificationToken"]:
            self.assertIn(table, sql)
        with self.assertRaises(p.ProofError):
            p.snapshot_sql(IDS[:4] + ["'; DELETE FROM x;--"])

    def test_truncated_rows_missing_body_columns_foreign_and_duplicate_ids_fail(self):
        for mutate in [lambda s:s.update(journal_count=2),lambda s:s["journal"][0].pop("messages"),
                       lambda s:s["journal"][0].update(user=IDS[8]),
                       lambda s:s["keys"][0].update(token=s["keys"][1]["token"])]:
            changed=raw_snapshot();mutate(changed)
            with self.subTest(mutation=mutate),self.assertRaises(p.ProofError):
                p.normalize_snapshot(changed,set(IDS[:5]))

    def test_privacy_scan_reads_unknown_columns_and_nested_json_without_short_substring_false_positive(self):
        rows=raw_snapshot()["journal"]
        rows[0]["arbitrary_future_column"]={"HeaderNameContainingHi": "This Hi substring is harmless"}
        p.privacy_check(rows,["Hi","Proof"])
        cases=[("messages",{"role":"user","content":"Hi"}),
               ("arbitrary_future_column",json.dumps({"payload":json.dumps({"text":"Hi"})})),
               ("arbitrary_future_column",{"output":"Proof"}),
               ("arbitrary_future_column","prefix " + "a long private chat string exceeding thirtytwo characters" + " suffix"),
               ("arbitrary_future_column","sk-"+"z"*40),
               ("arbitrary_future_column","eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJwcml2YXRlIn0.signatureabcdefgh")]
        for field,value in cases:
            changed=copy.deepcopy(rows);changed[0][field]=value
            with self.subTest(field=field,value=value),self.assertRaises(p.ProofError):
                p.privacy_check(changed,["Hi","Proof","a long private chat string exceeding thirtytwo characters"])

    def test_paid_root_comes_from_actual_row_and_owned_completed_native_history(self):
        normalized=p.normalize_snapshot(raw_snapshot(),set(IDS[:5]))
        self.assertEqual(p.candidate_roots(normalized,ACTOR),[{"request_id":normalized["journal"][0]["request_id"],"scope":SCOPE}])
        self.assertEqual(p.owned_chat(saved_chat(),SCOPE,ACTOR),["Hi","Proof"])
        for mutate in [lambda c:c.update(user_id=IDS[1]),lambda c:c.update(id=IDS[8]),
                       lambda c:c["chat"]["history"]["messages"][ANSWER].update(done=False),
                       lambda c:c.update(meta={"internal":True})]:
            chat=saved_chat();mutate(chat)
            with self.subTest(mutation=mutate),self.assertRaises(p.ProofError):
                p.owned_chat(chat,SCOPE,ACTOR)


class CoordinatorTests(unittest.TestCase):
    def environment(self,directory):
        base=Path(directory);private=base/"private";private.mkdir(mode=0o700)
        account=private/"staff.private.json"
        account.write_text(json.dumps({"users":[{"id":uid,"email":f"staff{i}@example.com","password":"private-synthetic-password"} for i,uid in enumerate(IDS[:2])]}), encoding="utf-8")
        account.chmod(0o600)
        env=base/"proof.env";env.write_text("PROOF_PRIVATE_DIR="+str(private.resolve())+"\n", encoding="utf-8");env.chmod(0o600)
        return SimpleNamespace(base_url="http://172.18.0.4:8080",env_file=env,accounts=account,output=base/"artifacts",private_output=private/"raw.private.json")

    def test_private_output_must_stay_inside_private_root_outside_artifact_tree(self):
        with tempfile.TemporaryDirectory() as directory:
            args=self.environment(directory)
            p.private_paths(args.env_file,args.accounts,args.output,args.private_output)
            for path in [Path(directory)/"outside.private.json",args.output/"raw.private.json"]:
                with self.assertRaises(p.ProofError):
                    p.private_paths(args.env_file,args.accounts,args.output,path)
            with self.assertRaises(p.ProofError):
                p.private_paths(args.env_file,args.accounts,args.accounts.parent/"public",args.private_output)

    def execute(self,args,*,foreign=False,drift=False,provider_delta=False):
        calls=[];snapshots=[raw_snapshot(),raw_snapshot()]
        if drift:snapshots[1]["users"][0]["spend"]+=.2
        class Fixture:
            def __init__(self,env):pass
            def target(self,url):calls.append("native_target")
            def projection(self):return dict(run_id="goal584-webui-"+"a"*12,staff_ids=IDS[:2],personal_ids=IDS[:4],service_id=IDS[4])
            def provider(self):
                calls.append("provider_read")
                return ["changed"] if provider_delta and calls.count("provider_read")==2 else []
            def snapshot(self,payers):calls.append("raw_db_read");return snapshots.pop(0)
            def validate_roots(self,roots):calls.append("native_scope_validation");return roots
        class Session:
            token="synthetic-fresh-session"
            def __init__(self,url):pass
            def login(self,actor):calls.append("fresh_login")
            def request(self,method,path):
                calls.append((method,path))
                if "/api/tasks/chat/" in path:return 200,{"task_ids":[]}
                if method=="DELETE":return 200,True
                if ("DELETE","/api/v1/chats/"+CHAT) in calls:return 404,{"detail":"not found"}
                chat=saved_chat()
                if foreign:chat["user_id"]=IDS[1]
                return 200,chat
        with patch.object(p,"Fixture",Fixture),patch.object(p,"Session",Session):
            if foreign or drift or provider_delta:
                with self.assertRaises(p.ProofError):p.run(args)
                return calls,None
            return calls,p.run(args)

    def test_only_selected_native_delete_after_private_raw_evidence_then_full_retention_comparison(self):
        with tempfile.TemporaryDirectory() as directory:
            args=self.environment(directory);calls,result=self.execute(args)
            self.assertTrue(result["passed"])
            self.assertEqual([call for call in calls if isinstance(call,tuple) and call[0]=="DELETE"],[("DELETE","/api/v1/chats/"+CHAT)])
            self.assertLess(calls.index("raw_db_read"),calls.index(("DELETE","/api/v1/chats/"+CHAT)))
            raw=json.loads(args.private_output.read_text(encoding="utf-8"))
            self.assertEqual(raw["before"],raw["after"])
            self.assertNotIn("private-synthetic-password",json.dumps(result))
            self.assertNotIn("synthetic-fresh-session",json.dumps(result))
            if os.name=="posix":self.assertEqual(stat.S_IMODE(args.private_output.stat().st_mode),0o600)

    def test_foreign_chat_never_deleted_and_financial_drift_or_provider_dispatch_fails(self):
        for flags in [dict(foreign=True),dict(drift=True),dict(provider_delta=True)]:
            with self.subTest(flags=flags),tempfile.TemporaryDirectory() as directory:
                args=self.environment(directory);calls,_=self.execute(args,**flags)
                if flags.get("foreign"):self.assertFalse(any(isinstance(call,tuple) and call[0]=="DELETE" for call in calls))

    def test_public_target_credentials_redirector_or_nonfixture_host_are_refused(self):
        for target in ["https://172.18.0.4:8080","http://8.8.8.8:8080","http://user:secret@172.18.0.4:8080","http://172.18.0.4:8080/api/chat"]:
            with self.subTest(target=target),self.assertRaises(p.ProofError):p.native_url(target)


if __name__=="__main__":unittest.main()
