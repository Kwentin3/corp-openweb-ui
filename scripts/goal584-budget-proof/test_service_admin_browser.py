"""Rehearse separate admin reporting costs against native-shaped artifacts."""
import copy
import ast
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from io import BytesIO
from unittest.mock import patch
from uuid import uuid4

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import prove_service_admin_browser as B


def admin_post_verify_tree(workflow):
    """Actual workflow tail/catch and existing trusted/public helpers, no native IO."""
    block=next(b for b in workflow.split('      - name: ')[1:] if b.startswith('Verify the native admin form'))
    embedded=block.split("<<'PY'\n",1)[1].rsplit('\n          PY',1)[0]
    tree=ast.parse('\n'.join(line[10:] for line in embedded.splitlines()))
    helpers=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('trusted','public')]
    guarded=next(n for n in tree.body if isinstance(n,ast.Try) and any(
        isinstance(v,ast.Constant) and v.value=='admin-unknown-host' for v in ast.walk(n)))
    start=next(i for i,n in enumerate(guarded.body) if isinstance(n,ast.Assign) and any(
        isinstance(t,ast.Name) and t.id=='stage' for t in n.targets) and isinstance(n.value,ast.Constant) and n.value.value=='verify')
    return ast.Module(body=[*helpers,ast.Try(body=guarded.body[start:],handlers=guarded.handlers,orelse=[],finalbody=[])],type_ignores=[])


def run_admin_post_verify(directory, png, *, workflow=None, verified=None, build=None, mutation=None):
    """Native receipt/browser screenshots are IO leaves; execute the actual host tail."""
    from prove_pricing_snapshots import no_credentials
    repository=HERE.parents[1]
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repository,text=True).strip()
    # A Linux workflow consumes Git LF bytes; materialize that exact source on Windows.
    root=(directory/'source').resolve();package=root/'services/officecli-openapi-proof/officecli_openapi_proof'
    package.mkdir(parents=True)
    for name in ('__init__.py','rendering.py','officecli.py','config.py'):
        relative='services/officecli-openapi-proof/officecli_openapi_proof/'+name
        (package/name).write_bytes(subprocess.check_output(['git','-c','gc.auto=0','show',revision+':'+relative],
            cwd=repository,timeout=15,env=__import__('os').environ|{'GIT_NO_LAZY_FETCH':'1'}))
    private,out=directory/'private',directory/'output';private.mkdir();out.mkdir()
    paths={key:private/(key+'.png') for key in ('page_screenshot','employee_screenshot')}
    for path in paths.values():path.write_bytes(png)
    packet={'paths':{key:str(path) for key,path in paths.items()},
        'screenshot_sha256':{key:hashlib.sha256(png).hexdigest() for key in paths}}
    build=copy.deepcopy(build) if build is not None else {'office':{'modules':{'rendering.py':hashlib.sha256(
        (root/'services/officecli-openapi-proof/officecli_openapi_proof/rendering.py').read_bytes()).hexdigest()}}}
    if mutation=='hash':packet['screenshot_sha256']['page_screenshot']='0'*64
    elif mutation=='path':
        outside=directory/'outside.png';outside.write_bytes(png);packet['paths']['page_screenshot']=str(outside)
    elif mutation=='owner_hash':build['office']['modules']['rendering.py']='0'*64
    fixture=type('HostTailIO',(),{'secrets':[]})()
    receipt=verified or {'passed':True,'status':'verified','personal_calls':2,'personal_cost_usd':'.332',
        'native_saved_embed_verified':True,'unknown_employee_verified':True,
        'whole_goal_accepted':False,'production_accepted':False,'unknown_cost_finality':False}
    def native(arguments,label,timeout=120,require_passed=True,host_owner=True):
        assert arguments==['/proof/prove_unknown_usage_gui.py','--phase','admin-verify']
        assert label=='admin-unknown-verify' and timeout==150 and host_owner is False
        assert receipt.get('passed') is True
        return copy.deepcopy(receipt)
    namespace=dict(root=root,private=private,out=out,packet=packet,build=build,native=native,fixture=fixture,
        source=repository/'scripts/goal584-budget-proof',revision=revision,
        closure={'source_sha256':{'reviewed.py':'a'*64}},credentials=lambda:None,no_credentials=no_credentials,
        Path=Path,json=json,hashlib=hashlib,subprocess=subprocess,os=__import__('os'),sys=sys,stage='verify')
    code=compile(ast.fix_missing_locations(admin_post_verify_tree(workflow or (
        repository/'.github/workflows/goal584-office-proof.yml').read_text(encoding='utf-8'))),'actual-admin-post-verify','exec')
    error=None
    old_path=sys.path[:]
    old_modules={key:value for key,value in sys.modules.items() if key.split('.')[0]=='officecli_openapi_proof'}
    for key in old_modules:del sys.modules[key]
    try:
        try:exec(code,namespace)
        except SystemExit as caught:error=caught.code
    finally:
        sys.path[:]=old_path
        for key in list(sys.modules):
            if key.split('.')[0]=='officecli_openapi_proof':del sys.modules[key]
        sys.modules.update(old_modules)
    result=json.loads((out/'admin-unknown-host.safe.json').read_text(encoding='utf-8'))
    return result,out,error


def packet():
    ids = [str(uuid4()) for _ in range(4)]
    admin, payer, chat, answer, parent = ids[0], *[str(uuid4()) for _ in range(4)]
    reset = "2026-12-01T00:00:00Z"
    users = [{"user_id": uid, "max_budget_usd": "1000" if uid == admin else "20",
              "spend_usd": "1.6" if uid == admin else ".2", "budget_duration": "1mo", "budget_reset_at": reset}
             for uid in ids]
    keys = [{"user_id": uid, "model": model, "key_alias": "fixture-" + uid + model,
             "max_budget_usd": "500" if uid == admin else "10", "spend_usd": "1.6" if uid == admin and model == "goal584-a"
              else ".2" if uid != admin and model == "goal584-a" else "0", "budget_duration": "1mo", "budget_reset_at": reset}
            for uid in ids for model in ("goal584-a", "goal584-b")]
    before = {"passed": True, "admin_id": admin, "service_payer_id": payer, "personal": {"users": users, "keys": keys},
              "service": {"users": [{"user_id": payer, "max_budget_usd": "20", "spend_usd": ".2",
                                     "budget_duration": "1mo", "budget_reset_at": reset}],
                          "keys": [{"user_id": payer, "model": "goal584-a", "key_alias": "service-assignment",
                                    "max_budget_usd": "20", "spend_usd": ".2", "budget_duration": "1mo", "budget_reset_at": reset}]},
              "positive_spend_logs": [{"request_id": "chatcmpl-goal584-" + uuid4().hex, "user_id": uid,
                                       "model_group": "goal584-a", "spend_usd": ".2"}
                                      for uid in ids for _ in range(8 if uid == admin else 1)]}
    after = copy.deepcopy(before)
    for collection in (after["personal"]["users"], after["personal"]["keys"]):
        for row in collection:
            if row["user_id"] == admin and row.get("model", "goal584-a") == "goal584-a":
                row["spend_usd"] = "2.0"
    opened = {"admin_id": admin, "parent_author_id": admin, "model_id": B.MODEL, "stored_parent_text": B.INTENT,
              "chat_id": chat, "assistant_id": answer, "parent_user_id": parent,
              "terminal_persisted": True, "exact_submitted_and_stored_strings": True, "sandbox_same_origin": False}
    context, provider = {"requests": []}, {"synthetic": True, "requests": []}
    skill, _, statuses = B.source_contract()
    schemas = [{"type": "function", "function": {"name": name, "description": "Native Tool",
                "parameters": {"type": "object", "properties": properties}}} for name, properties in (
        ("open_budget_form", {"view_json": {"type": "string", "default": "{}"}}), ("apply_budget_form", {}))]
    messages = [{"role": "system", "content": skill}, {"role": "user", "content": B.INTENT}]
    for index in range(2):
        if index:
            messages += [{"role": "assistant", "tool_calls": [{"id": "native-open", "type": "function",
                "function": {"name": "open_budget_form", "arguments": '{"view_json":"{}"}'}}]},
                {"role": "tool", "tool_call_id": "native-open", "content": json.dumps(statuses["opened"])}]
        body = {"model": "goal584-a", "messages": copy.deepcopy(messages), "stream": True, "max_tokens": 5,
                "tools": copy.deepcopy(schemas)}
        scope = {"schema": 1, "user_id": admin, "chat_id": chat, "answer_id": answer, "root_chat_id": chat,
                 "root_answer_id": answer, "model": "goal584-a", "call_id": str(uuid4()), "category": "personal"}
        captured = {"user_id": admin, "task": "", "verified_cost_scope": scope, "body": body,
                    "body_after_auth": copy.deepcopy(body), "attestation_present_before": True,
                    "provenance_removed_after": True, "native_stream_usage_patch": {
                        "stream_options": {"include_usage": True}, "_litellm_strip_stream_usage": True}}
        context["requests"].append(captured)
        request_id = "chatcmpl-goal584-" + uuid4().hex
        provider["requests"].append({"id": request_id, "body": {**copy.deepcopy(body), "model": "goal584-fake-a",
            "stream_options": {"include_usage": True}}, "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}})
        after["positive_spend_logs"].append({"request_id": request_id, "user_id": admin, "model_group": "goal584-a",
            "session_id": chat, "owui_budget": scope, "spend_usd": ".2", "prompt_tokens": 10,
            "completion_tokens": 5, "total_tokens": 15})
    return [before, after, opened, context, provider]


class ServiceAdminViewTests(unittest.TestCase):
    def snapshots(self, observations, expected_rows):
        with tempfile.TemporaryDirectory() as directory:
            fixture = object.__new__(B.ServiceAdminFixture)
            fixture.sequence, fixture.command, fixture.output = 0, ["native-compose"], Path(directory)
            responses = [subprocess.CompletedProcess([], 0, json.dumps(value), "") for value in observations]
            with patch.object(B.subprocess, "run", side_effect=responses) as run, patch.object(B.time, "sleep"):
                result = fixture.snapshot(expected_rows=expected_rows)
            retained = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(Path(directory).glob("service-admin-native-*.json"))]
            return result, retained, run.call_args_list

    def test_footer_snapshot_waits_for_counter_convergence_with_all_four_histories_retained(self):
        _, complete, *_ = packet()
        pending = copy.deepcopy(complete)
        admin = complete["admin_id"]
        for collection in (pending["personal"]["users"], pending["personal"]["keys"]):
            for row in collection:
                if row["user_id"] == admin and row.get("model", "goal584-a") == "goal584-a": row["spend_usd"] = "1.6"
        result, retained, calls = self.snapshots([pending, complete], len(complete["positive_spend_logs"]))
        self.assertEqual(result, complete)
        self.assertEqual(retained, [pending, complete])
        self.assertEqual({row["user_id"] for row in result["positive_spend_logs"]}, {row["user_id"] for row in complete["personal"]["users"]})
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(0 < call.kwargs["timeout"] <= 60 for call in calls))

    def test_footer_snapshot_waits_for_missing_journal_rows_before_classifying_surplus(self):
        _, complete, *_ = packet()
        pending = copy.deepcopy(complete); pending["positive_spend_logs"].pop()
        result, retained, _ = self.snapshots([pending, complete], len(complete["positive_spend_logs"]))
        self.assertEqual(result, complete); self.assertEqual(len(retained), 2)

    def test_footer_snapshot_does_not_wait_on_surplus_duplicate_or_missing_identity(self):
        _, complete, *_ = packet()
        for mutate in (lambda value: value["personal"]["users"][0].update(spend_usd="3"),
                       lambda value: value["positive_spend_logs"].append(copy.deepcopy(value["positive_spend_logs"][0])),
                       lambda value: value["personal"]["keys"].pop()):
            changed = copy.deepcopy(complete); mutate(changed)
            with self.subTest(mutation=mutate), self.assertRaises(AssertionError):
                self.snapshots([changed], len(complete["positive_spend_logs"]))

    def test_two_admin_calls_are_separate_from_unchanged_service_and_staff(self):
        result = B.verify_view(*packet())
        self.assertEqual(result["admin_reporting_cost_usd"], "0.40")
        self.assertEqual(result["service_spend_usd"], "0.20")
        self.assertTrue(result["reporting_billed_to_admin_personal_identity"])

    def reject(self, mutate):
        values = packet()
        mutate(values)
        with self.assertRaises((AssertionError, ValueError, KeyError)):
            B.verify_view(*values)

    def test_reject_service_or_staff_charge_caps_and_missing_admin_accounting(self):
        self.reject(lambda values: values[1]["service"]["users"][0].update(spend_usd=".4"))
        self.reject(lambda values: values[1]["personal"]["users"][1].update(spend_usd=".4"))
        self.reject(lambda values: values[1]["personal"]["keys"][0].update(max_budget_usd="999"))
        self.reject(lambda values: values[1]["personal"]["users"][0].update(spend_usd="1.6"))
        self.reject(lambda values: values[0]["personal"]["users"].pop())

    def test_reject_extra_provider_calls_or_wrong_identity_and_native_rows(self):
        self.reject(lambda values: values[4]["requests"].pop())
        self.reject(lambda values: values[1]["positive_spend_logs"].append(copy.deepcopy(values[1]["positive_spend_logs"][-1])))
        self.reject(lambda values: values[3]["requests"][0]["verified_cost_scope"].update(category="service"))
        self.reject(lambda values: values[3]["requests"][0]["verified_cost_scope"].update(root_chat_id=str(uuid4())))

    def test_reject_lost_skill_schema_instructions_or_business_arguments(self):
        self.reject(lambda values: values[4]["requests"][1]["body"].pop("tools"))
        def forge(values):
            for slot in ("body", "body_after_auth"):
                values[3]["requests"][1][slot]["messages"][-2]["tool_calls"][0]["function"]["arguments"] = '{"service_payer_id":"forged"}'
            values[4]["requests"][1]["body"]["messages"][-2]["tool_calls"][0]["function"]["arguments"] = '{"service_payer_id":"forged"}'
        self.reject(forge)


def unknown_packet():
    actor, admin = str(uuid4()), str(uuid4())
    from verify_admin_calls import literal
    aliases = literal(HERE / "prove_unknown_usage_policy.py", "ALIASES")
    accounts = {"schema": 1, "admin": {"id": admin}, "actor_id": actor, "employee_ids": [actor],
        "model_id": B.MODEL, "tool_id": "employee_budget_admin", "skill_id": "goal584-budget-admin-guide",
        "managed_model_ids": list(aliases)}
    actor_row = {"user_id": actor, "expense_status": "unknown", "spend_usd": ".332", "models": [
        {"id": alias, "spend_usd": ".332" if index == 0 else "0",
         "expense_status": "unavailable" if index == 0 else "unknown"} for index, alias in enumerate(aliases)]}
    def expense(value):
        primary = ("Расход неизвестен." if value["expense_status"] == "unknown" else
                   "Полнота данных о расходе не подтверждена.")
        return primary, primary + " В истории есть запросы без данных о расходе. " + (
            "По данным учёта: " + value["spend_usd"] + " USD. Эта сумма не подтверждает итоговый расход.")
    primary, summary = expense(actor_row)
    visible = {"employee_primary": primary, "employee_summary": summary + " Остаток не подтверждён.", "models": {}}
    keys = {}
    for index, model in enumerate(actor_row["models"]):
        primary, text = expense(model)
        visible["models"][model["id"]] = {"primary": primary, "expense": text,
            "blocked": "Заблокирована" if index else "Не заблокирована"}
        keys[model["id"]] = {"blocked": bool(index)}
    return [accounts, [actor_row], visible, keys]


class UnknownAdminRenderTests(unittest.TestCase):
    def reject(self, mutate):
        values = unknown_packet(); mutate(values)
        with self.assertRaises((AssertionError, ValueError, KeyError)): B.verify_unknown_render(*values)

    def test_unknown_primary_keeps_zero_native_counter_secondary_and_not_final(self):
        values = unknown_packet()
        result = B.verify_unknown_render(*values)
        self.assertTrue(result["employee_unknown_primary"])
        self.assertTrue(result["native_counters_not_final"])
        self.assertFalse(result["known_subtotal_present"])
        self.assertEqual(len(result["unknown_models"]), 2)
        self.assertNotIn("spend_usd", result)

    def test_actual_employee_model_and_source_roster_are_required(self):
        self.reject(lambda v: v[0].update(actor_id=str(uuid4())))
        self.reject(lambda v: v[0].update(employee_ids=[v[0]["admin"]["id"]]))
        self.reject(lambda v: v[0]["managed_model_ids"].reverse())
        self.reject(lambda v: v[1][0]["models"].pop())
        self.reject(lambda v: v[0].update(skill_id="another-skill"))

    def test_unknown_cannot_be_cleared_or_presented_as_confirmed_subtotal(self):
        self.reject(lambda v: v[1][0].update(expense_status="known"))
        self.reject(lambda v: v[1][0]["models"][1].update(expense_status="unavailable"))
        self.reject(lambda v: v[1][0].update(known_subtotal_usd="0"))
        self.reject(lambda v: v[1][0]["models"][1].update(known_subtotal_usd="0"))
        self.reject(lambda v: v[1][0]["models"][0].update(expense_status="known"))

    def test_primary_final_zero_and_missing_counter_caveats_are_rejected(self):
        self.reject(lambda v: v[2].update(employee_primary="0 USD"))
        self.reject(lambda v: v[2].update(employee_summary="Расход неизвестен. По данным учёта: .332 USD."))
        alias = unknown_packet()[0]["managed_model_ids"][1]
        self.reject(lambda v: v[2]["models"][alias].update(expense="Расход неизвестен. По данным учёта: 0 USD."))
        self.reject(lambda v: v[2]["models"][alias].update(primary="0"))

    def test_visible_counter_and_historical_qualification_must_match_saved_row(self):
        self.reject(lambda v: v[2].update(employee_summary=v[2]["employee_summary"].replace(".332", "9")))
        self.reject(lambda v: v[2].update(employee_summary=v[2]["employee_summary"].replace(
            "В истории есть запросы без данных о расходе.", "")))

    def test_block_label_requires_actual_boolean_native_readback(self):
        alias = unknown_packet()[0]["managed_model_ids"][1]
        self.reject(lambda v: v[3][alias].update(blocked=False))
        self.reject(lambda v: v[3][alias].update(blocked="true"))
        self.reject(lambda v: v[2]["models"][alias].update(blocked="Не заблокирована"))


class UnknownAdminFailureTests(unittest.TestCase):
    """Actual wait/catch owners at browser/HTTP/filesystem leaves; no browser claim."""
    def native_state(self):
        answer, chat = str(uuid4()), str(uuid4())
        stored = {'id':chat, 'chat':{'history':{'messages':{answer:{'id':answer,'role':'assistant','done':False,
            'error':{'type':'invalid_request_error','code':'400','message':B.UNKNOWN_PROVIDER_ERROR},
            'output':[{'type':'function_call','name':'employee_budget_admin_open_budget_form','call_id':'native-open'},
                      {'type':'function_call_output','call_id':'native-open','status':'completed','embeds':[]}]}}}}}
        return {'id':answer}, stored, {'task_ids':[str(uuid4())]}

    def private_io(self, stack):
        import os
        import stat
        import prove_gateway_auth as owner
        if os.name == 'nt':
            # POSIX mode metadata is an OS leaf on Windows; all existing native
            # private path/symlink/write/read checks continue to execute.
            stack.enter_context(patch.object(owner.stat,'S_IMODE',side_effect=lambda mode:0o700 if stat.S_ISDIR(mode) else 0o600))
        return owner

    def test_wait_editor_observer_receives_actual_references_and_preserves_pending(self):
        from types import SimpleNamespace
        import prove_admin_browser as A
        sent, stored, task_body = self.native_state(); observed=[]; gets=[]
        response = SimpleNamespace(status=200,json=lambda:task_body)
        page = SimpleNamespace(context=SimpleNamespace(request=SimpleNamespace(get=lambda *a,**k:gets.append((a,k)) or response)))
        with tempfile.TemporaryDirectory() as directory, patch.object(A,'chat_read',return_value=stored), \
                patch.object(A.time,'monotonic',side_effect=[0,61]):
            with self.assertRaisesRegex(AssertionError,'Native admin task/editor did not complete'):
                A.wait_editor(page,'http://stand','private-token',stored['id'],sent,'admin',B.MODEL,B.INTENT,
                    Path(directory),'observed',observer=lambda chat,tasks:observed.append((chat,tasks)))
            pending=json.loads((Path(directory)/'observed-pending.json').read_text())
        self.assertIs(observed[0][0],stored); self.assertIs(observed[0][1],task_body)
        self.assertEqual(len(gets),1)
        self.assertEqual(set(pending),{'assistant_id','message_fields','done','active_task_ids','top_embed_count','output'})
        self.assertEqual(pending['assistant_id'],sent['id']); self.assertEqual(pending['active_task_ids'],task_body['task_ids'])
        self.assertEqual(pending['done'],False)

    def test_wait_editor_default_and_invalid_tasks_keep_original_guards(self):
        from types import SimpleNamespace
        import prove_admin_browser as A
        sent,stored,task_body=self.native_state()
        for status,body,expected in ((200,task_body,'Native admin task/editor did not complete'),
                                     (503,{'task_ids':[]},'Native admin task owner unavailable')):
            observed=[];gets=[]
            response=SimpleNamespace(status=status,json=lambda:body)
            page=SimpleNamespace(context=SimpleNamespace(request=SimpleNamespace(get=lambda *a,**k:gets.append(a) or response)))
            with self.subTest(status=status),tempfile.TemporaryDirectory() as directory, \
                    patch.object(A,'chat_read',return_value=stored),patch.object(A.time,'monotonic',side_effect=[0,61]):
                kwargs={} if status==200 else {'observer':lambda *args:observed.append(args)}
                with self.assertRaisesRegex(AssertionError,expected):
                    A.wait_editor(page,'http://stand','private-token',stored['id'],sent,'admin',B.MODEL,B.INTENT,
                        Path(directory),'default',**kwargs)
            self.assertEqual(observed,[]);self.assertEqual(len(gets),1)

    def exercise(self, *, oversized=False, ack_status=200, write_failure=False, oversized_ack=False):
        import base64
        import contextlib
        import hashlib
        import os
        from types import SimpleNamespace
        import prove_admin_browser as A
        with tempfile.TemporaryDirectory() as directory,contextlib.ExitStack() as stack:
            private=Path(directory);owner=self.private_io(stack)
            sent,stored,tasks=self.native_state(); sent.update(model=B.MODEL,chat_id=stored['id'])
            raw_submission=json.dumps(sent);raw_ack=json.dumps({'chat_id':stored['id'],'task_id':'native-task'}).encode()
            if oversized_ack:raw_ack=b'x'*5000
            response=SimpleNamespace(status=ack_status,request=SimpleNamespace(post_data=raw_submission,post_data_json=sent),
                body=lambda:raw_ack,json=lambda:json.loads(raw_ack))
            class Pending:
                def __enter__(self): return SimpleNamespace(value=response)
                def __exit__(self,*args): return False
            class Control:
                @property
                def first(self): return self
                def click(self): pass
                def fill(self,value): pass
            gets=[]
            page=SimpleNamespace(locator=lambda selector:Control(),expect_response=lambda *a,**k:Pending(),
                context=SimpleNamespace(request=SimpleNamespace(get=lambda *a,**k:gets.append(a[0]) or
                    SimpleNamespace(status=200,json=lambda:tasks))))
            class Context:
                closed=False
                def close(self): self.closed=True
            inherited,created=Context(),Context();browser=SimpleNamespace(contexts=[inherited])
            def login(*args,**kwargs): browser.contexts.append(created);return page,'private-token'
            admin,actor=str(uuid4()),str(uuid4());revision='a'*40
            state={'schema':1,'stage':'setup_complete','observation':{'unknown':{'budget':{'user_id':actor}}}}
            fixture=SimpleNamespace(private=private,command=[],secrets=['private-token','private-password'],
                running_readback=lambda *args:{'bound':'actual-leaf'},
                command_json=lambda *a,**k:{'passed':True,'phase':'unknown-snapshot','admin_id':admin,'actor_id':actor},
                _office_private=lambda name:(b'',state))
            accounts={'schema':1,'model_id':B.MODEL,'employee_ids':[actor],'actor_id':actor,
                'admin':{'id':admin,'password':'private-password'}}
            stack.enter_context(patch.object(B,'admin_login',side_effect=login))
            stack.enter_context(patch.object(A,'chat_read',return_value=stored))
            stack.enter_context(patch.object(A.time,'monotonic',side_effect=[0,61]))
            stack.enter_context(patch.object(os,'getuid',return_value=1001,create=True))
            stack.enter_context(patch.object(os,'getgid',return_value=1001,create=True))
            if oversized:
                stored['private_padding']='private-secret-'+ 'x'*20_000
            if oversized or oversized_ack:
                stack.enter_context(patch.object(B,'MAX_BYTES',4096))
            checkpoint=B._unknown_checkpoint
            if write_failure:
                def writing(path,packet,**kwargs):
                    if kwargs.get('failure'):raise OSError('private diagnostic write failed')
                    return checkpoint(path,packet,**kwargs)
                stack.enter_context(patch.object(B,'_unknown_checkpoint',side_effect=writing))
            try:
                B.run_unknown_presence(browser,fixture,'http://stand',{},revision,accounts)
            except Exception as error:
                caught=error
            else:self.fail('Controlled native incomplete state must fail')
            path=private/'admin-unknown-browser.private.json'
            packet=json.loads(path.read_text(encoding='utf8'))
            self.assertTrue(created.closed);self.assertFalse(inherited.closed)
            self.assertEqual(packet['source_sha256'],hashlib.sha256(Path(B.__file__).read_bytes()).hexdigest())
            self.assertEqual(packet['binding']['source_commit'],revision)
            self.assertLessEqual(path.stat().st_size,B.MAX_BYTES)
            if not oversized and not oversized_ack:
                self.assertEqual(packet['raw_submission'],raw_submission)
                self.assertEqual(base64.b64decode(packet['raw_acknowledgement_base64']),raw_ack)
            return packet,caught,gets

    def test_actual_failure_packet_retains_raw_send_ack_last_native_state(self):
        packet,error,gets=self.exercise()
        self.assertEqual(str(error),'Native admin task/editor did not complete');self.assertEqual(len(gets),1)
        self.assertEqual(packet['failure_phase'],'wait_editor')
        self.assertEqual(len(packet['last_native_tasks']['task_ids']),1)
        safe=B.unknown_failure_projection(packet)
        self.assertTrue(safe['collected']);self.assertEqual(safe['answer_http_status'],400)
        self.assertEqual(safe['provider_error_hint'],'synthetic_responses_request_rejected')
        self.assertEqual(safe['tool_call_count'],1);self.assertEqual(safe['editor_embed_count'],0)

    def test_oversize_failure_omits_raw_explicitly_and_retains_real_summary_binding(self):
        packet,error,gets=self.exercise(oversized=True)
        self.assertEqual(str(error),'Native admin task/editor did not complete');self.assertEqual(len(gets),1)
        self.assertTrue(packet['raw_omitted']);self.assertGreater(packet['raw_bytes'],4096)
        self.assertNotIn('last_native_chat',packet);self.assertNotIn('raw_submission',packet)
        self.assertIn('id',packet['submitted']);self.assertIn('chat_id',packet['acknowledgement'])
        safe=B.unknown_failure_projection(packet)
        self.assertTrue(safe['collected']);self.assertTrue(safe['raw_omitted'])
        self.assertEqual(safe['native_task_ids_count'],1);self.assertIs(safe['answer_done'],False)

    def test_before_observer_missing_packet_and_write_failure_are_unavailable(self):
        packet,error,gets=self.exercise(ack_status=403)
        self.assertEqual(gets,[]);self.assertEqual(packet['failure_phase'],'ordinary_send')
        self.assertFalse(B.unknown_failure_projection(packet)['collected'])
        for value in (None,{},'private-secret'):
            safe=B.unknown_failure_projection(value);self.assertFalse(safe['collected'])
            self.assertIsNone(safe['answer_done']);self.assertIsNone(safe['native_task_ids_count'])
        packet,error,gets=self.exercise(write_failure=True)
        self.assertEqual(str(error),'Native admin task/editor did not complete')
        self.assertFalse(B.unknown_failure_projection(packet)['collected'])
        packet,error,gets=self.exercise(oversized_ack=True)
        self.assertEqual(gets,[]);self.assertTrue(packet['raw_omitted']);self.assertTrue(packet['raw_send_ack_omitted'])
        self.assertEqual(packet['raw_acknowledgement_bytes'],5000)
        self.assertFalse(B.unknown_failure_projection(packet)['collected'])

    def test_whitelist_drops_hostile_fields_and_unknown_or_conflicting_error_types(self):
        import ast
        sent,stored,tasks=self.native_state()
        packet={'submitted':sent,'last_native_chat':stored,'last_native_tasks':tasks,'failure':{'error_class':'private-secret'},
            'failure_phase':'private-secret','url':'https://private-secret','amount':'99.99','token':'private-secret'}
        answer=stored['chat']['history']['messages'][sent['id']]
        answer['error'].update(message='private-secret '+B.UNKNOWN_PROVIDER_ERROR+' private-secret',status_code=422)
        safe=B.unknown_failure_projection(packet)
        self.assertIsNone(safe['answer_http_status']);self.assertEqual(safe['phase'],'unavailable')
        encoded=json.dumps(safe);self.assertNotIn('private-secret',encoded);self.assertNotIn('99.99',encoded)
        self.assertNotIn(sent['id'],encoded);self.assertNotIn('http',encoded.replace('answer_http_status',''))
        self.assertLessEqual(len(encoded.encode()),4096)
        for field in ('native_accounting_accepted','provider_dispatch_accepted','whole_goal_accepted'):self.assertIs(safe[field],False)
        literals={n.value for n in ast.walk(ast.parse((HERE/'mock_provider.py').read_bytes())) if isinstance(n,ast.Constant) and isinstance(n.value,str)}
        self.assertIn(B.UNKNOWN_PROVIDER_ERROR,literals)
        answer['error']={'type':'private-secret','status_code':True,'message':'other'}
        safe=B.unknown_failure_projection(packet)
        self.assertEqual(safe['answer_error_type'],'unavailable');self.assertIsNone(safe['answer_http_status'])
        self.assertEqual(safe['provider_error_hint'],'unavailable')
        packet.update(raw_omitted=True,diagnostic_observation={k:'private-secret' for k in B._unknown_observation({})})
        safe=B.unknown_failure_projection(packet)
        self.assertFalse(safe['collected']);self.assertNotIn('private-secret',json.dumps(safe))

    def test_success_packet_cannot_be_silently_omitted_and_pending_identity_is_preserved(self):
        import contextlib
        with tempfile.TemporaryDirectory() as directory,contextlib.ExitStack() as stack:
            self.private_io(stack);path=Path(directory)/'private.json'
            with patch.object(B,'MAX_BYTES',512),self.assertRaisesRegex(AssertionError,'packet exceeded bound'):
                B._unknown_checkpoint(path,{'content':'x'*2048})
            self.assertFalse(path.exists())
        packet,_,_=self.exercise()
        sent=packet['submitted']['id'];answer=packet['last_native_chat']['chat']['history']['messages'][sent]
        self.assertEqual(answer['id'],sent)
        safe=B.unknown_failure_projection(packet)
        self.assertTrue(safe['answer_id_matches_submitted'])

    def test_actual_workflow_catch_requires_source_revision_and_remains_fatal(self):
        import ast
        import hashlib
        from types import SimpleNamespace
        from prove_pricing_snapshots import no_credentials
        workflow=(HERE.parents[1]/'.github/workflows/goal584-office-proof.yml').read_text(encoding='utf8')
        block=next(b for b in workflow.split('      - name: ')[1:] if b.startswith('Verify the native admin form'))
        embedded=block.split("<<'PY'\n",1)[1].rsplit('\n          PY',1)[0]
        tree=ast.parse('\n'.join(line[10:] for line in embedded.splitlines()))
        handlers=[h for n in ast.walk(tree) if isinstance(n,ast.Try) for h in n.handlers
            if any(isinstance(v,ast.Constant) and v.value=='admin-unknown-host' for v in ast.walk(h))]
        self.assertEqual(len(handlers),1)
        code=compile(ast.fix_missing_locations(ast.Module(body=[ast.Try(body=[ast.Raise(exc=ast.Name(id='error',ctx=ast.Load()),cause=None)],
            handlers=[handlers[0]],orelse=[],finalbody=[])],type_ignores=[])),'actual_workflow_admin_catch','exec')
        full,_,_=self.exercise();omitted,_,_=self.exercise(oversized=True)
        no_observation=copy.deepcopy(full);no_observation.pop('last_native_chat');no_observation.pop('last_native_tasks')
        badsource=copy.deepcopy(full);badsource['source_sha256']='0'*64
        badrevision=copy.deepcopy(full);badrevision['binding']['source_commit']='b'*40
        for packet,expected in ((full,True),(omitted,True),(None,False),(badsource,False),(badrevision,False),(no_observation,False)):
            public={}
            def private(name):
                if packet is None:raise FileNotFoundError(name)
                return b'',packet
            env={'error':AssertionError('private-secret'), 'stage':'browser','json':json,
                'unknown_failure_projection':B.unknown_failure_projection,'no_credentials':no_credentials,
                'fixture':SimpleNamespace(_office_private=private,secrets=['private-secret']),
                'browser_sha':hashlib.sha256(Path(B.__file__).read_bytes()).hexdigest(),'revision':'a'*40,
                'public':lambda name,value:public.update({name:value})}
            with self.subTest(expected=expected),self.assertRaises(SystemExit) as caught:exec(code,env)
            self.assertEqual(caught.exception.code,1)
            self.assertIs(public['admin-unknown-lifecycle']['collected'],expected)
            self.assertIs(public['admin-unknown-host']['lifecycle_diagnostic_collected'],expected)
            self.assertIs(public['admin-unknown-host']['passed'],False)
            self.assertNotIn('private-secret',json.dumps(public))


class UnknownAdminPostVerifyTests(unittest.TestCase):
    def png(self):
        from PIL import Image
        stream=BytesIO();Image.new('RGB',(16,16),'white').save(stream,format='PNG');return stream.getvalue()

    def test_actual_host_tail_uses_firstparty_png_owner_and_exports_both_verified_hashes(self):
        png=self.png()
        with tempfile.TemporaryDirectory() as directory:
            result,out,error=run_admin_post_verify(Path(directory),png)
            self.assertIsNone(error);self.assertIs(result['passed'],True)
            self.assertEqual(result['stage'],'complete');self.assertEqual(result['personal_cost_usd'],'.332')
            for label in ('page','employee'):
                self.assertEqual((out/('office-admin-unknown-'+label+'.png')).read_bytes(),png)
            self.assertFalse(result['whole_goal_accepted'] or result['production_accepted'] or result['unknown_cost_finality'])

    def test_actual_host_tail_keeps_png_hash_path_and_owner_guards_fatal(self):
        for mutation in ('malformed','hash','path','owner_hash'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as directory:
                png=b'\x89PNG\r\n\x1a\nheader-only' if mutation=='malformed' else self.png()
                result,out,error=run_admin_post_verify(Path(directory),png,mutation=mutation)
                self.assertEqual(error,1);self.assertIs(result['passed'],False)
                self.assertEqual(result['stage'],'verify')
                self.assertEqual(result['error_class'],'OfficeCliFailure' if mutation=='malformed' else 'AssertionError')
                self.assertFalse((out/'office-admin-unknown-page.png').exists())


if __name__ == "__main__":
    unittest.main()
