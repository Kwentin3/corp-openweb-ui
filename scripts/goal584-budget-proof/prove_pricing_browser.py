#!/usr/bin/env python3
"""Future disposable pricing rehearsal: one visible call, exact YAML rollback.

Callback/config/mount activation belongs to the parent candidate. This host
coordinator reuses native observations and the existing rate snapshot verifier.
No provider reset, direct inference, database write or tariff calculation.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import time
from urllib.parse import urlsplit

from capture_webui_auth import FIELDS
from prove_pricing_snapshots import MAX_BYTES, no_credentials
from prove_webui_browser import Fixture, chat, login, require, same_money, verify_context_row, write_json
from verify_admin_calls import compare_provider


ROOT = Path(__file__).resolve().parents[2]
MODEL = "goal584-a"
CONFIG_LIMIT = 128 * 1024
OBSERVE = '''import json, sys
sys.path.insert(0, '/proof')
from decimal import Decimal
from prove_background_tasks import snapshot
from prove_service_tasks import task_config_evidence
from provision_webui import WebUI, native_client, read_private, TASK_FLAGS, require
from prove_pricing_snapshots import fixture_scope
from verify_admin_calls import accounting_totals_ready
s = read_private(__import__('pathlib').Path('/proof-private/webui-state.private.json'))
b = s['background_fixture']
require(b['stage'] == 'qualified_automatic_background' and b['task_config_restored'] is True
        and b['provider_controls_restored'] is True, 'Pricing requires completed restored background proof')
w = WebUI()
w.session(s['admin'], 'admin')
w.session(s['users'][0], 'user')
tasks = w.ok('GET', '/api/v1/tasks/config', token=s['admin']['token'])
require(all(tasks.get(flag) is False for flag in TASK_FLAGS), 'Pricing requires disabled automatic tasks')
native_client(s).schema()
for name in ('baseline_chat', 'service_chat'):
    active = w.ok('GET', '/api/tasks/chat/' + b[name]['chat_id'], token=s['users'][0]['token'])
    require(active.get('task_ids') == [], 'Earlier background Chat still has active tasks')
n = snapshot(w, s)
scope = fixture_scope(s)
personal = [v for v in n['budgets'] if v['user_id'] in scope['personal_payers']]
users = [{'user_id': v['user_id'], 'spend_usd': v['spend']} for v in personal]
keys = [{'user_id': v['user_id'], 'model': k['model'], 'spend_usd': k['spend']}
        for v in personal for k in v['models']]
rows = [{'request_id': v['request_id'], 'user_id': v['user_id'], 'model_group': v['model'],
         'spend_usd': v['spend_usd']} for v in n['rows'] if v['user_id'] in scope['personal_payers']]
target = sys.argv[1]
complete = target == 'baseline' or target != 'readiness' and any(v['request_id'] == target for v in rows)
ready = accounting_totals_ready(users, keys, rows, scope['personal_payers'], history_complete=complete)
# This is observed-ledger reconciliation only, never price/token arithmetic.
from prove_native_budgets import close_amount
service = next(v for v in n['budgets'] if v['user_id'] == scope['service_payer'])
for entry in [service, *service['models']]:
    own = [v for v in n['rows'] if v['user_id'] == scope['service_payer']
           and ('model' not in entry or v['model'] == entry['model'])]
    expected = sum((Decimal(v['spend_usd']) for v in own), Decimal(0))
    observed = Decimal(entry['spend'])
    require(observed <= expected or close_amount(observed, expected), 'Service counter exceeds persisted history')
    ready = ready and (observed == 0 if expected == 0 else close_amount(observed, expected))
print(json.dumps({'actor_id': s['users'][0]['id'], 'scope': scope, 'native': n, 'schema_ready': True,
                  'accounting_ready': ready, 'task_config': task_config_evidence(tasks)}))
'''
CONFIG_OBSERVATION = '''import hashlib, json, os, sys
from pathlib import Path
import yaml
raw = Path('/proof/config.yaml').read_bytes()
assert 0 < len(raw) <= 131072
c = yaml.safe_load(raw)
assert isinstance(c, dict) and len(c['model_list']) == 2
models = {m['model_name']: m for m in c['model_list']}
assert set(models) == {'goal584-a', 'goal584-b'}
for name, m in models.items():
    p, info = m['litellm_params'], m['model_info']
    assert p['api_base'] == 'http://provider:8000/v1' and p['model'] == 'openai/goal584-fake-' + name[-1]
    assert p['api_key'] == 'synthetic-provider-only-not-a-credential'
    assert info['id'] == 'goal584-deployment-' + name[-1]
    assert not info.get('configurable_clientside_auth_params')
    assert [info[k] for k in ('max_tokens','max_input_tokens','max_output_tokens')] == [15,10,5]
    expected = [float(sys.argv[1]), float(sys.argv[2])] if name == 'goal584-a' else [.01,.02]
    assert [info['input_cost_per_token'], info['output_cost_per_token']] == expected
g = c['general_settings']
assert g['custom_auth'] == 'capture_webui_auth.gateway_auth' and g['custom_auth_run_common_checks'] is True
assert g['fail_closed_budget_enforcement'] is True and g['store_prompts_in_spend_logs'] is False
assert g.get('allow_client_side_credentials') is not True and g['missing_session_id'] == 'omit'
assert os.environ['STORE_PROMPTS_IN_SPEND_LOGS'].lower() == 'false'
assert c['litellm_settings']['block_requests_for_models_without_pricing'] is True
callbacks = c['litellm_settings']['callbacks']
assert isinstance(callbacks,list) and callbacks.count('pricing_snapshot.handler') == 1
assert 'budget_errors.handler' in callbacks
print(json.dumps({'sha256': hashlib.sha256(raw).hexdigest(),
 'callback_sha256': hashlib.sha256(Path('/proof/pricing_snapshot.py').read_bytes()).hexdigest(),
 'verifier_sha256': hashlib.sha256(Path('/proof/prove_pricing_snapshots.py').read_bytes()).hexdigest(),
 'fixture_routes_and_rates_validated': True}))
'''


def changed_config(raw):
    """Change exactly two literal model-A values, preserving every other byte."""
    require(0 < len(raw) <= CONFIG_LIMIT, "Private native YAML exceeds fixture bound")
    text = raw.decode("utf8")
    starts = list(re.finditer(r"(?m)^  - model_name: (goal584-[ab])\r?$", text))
    require(len(starts) == 2 and {m[1] for m in starts} == {MODEL, "goal584-b"}, "Expected exactly the two native YAML model blocks")
    at = next(i for i, item in enumerate(starts) if item[1] == MODEL)
    begin, end = starts[at].start(), starts[at + 1].start() if at + 1 < len(starts) else len(text)
    block = text[begin:end]
    for field, old, new in (("input_cost_per_token", "0.01", "0.02"), ("output_cost_per_token", "0.02", "0.04")):
        pattern = r"(?m)^(      " + field + r": )" + re.escape(old) + r"(\r?)$"
        block, count = re.subn(pattern, lambda m: m[1] + new + m[2], block)
        require(count == 1, "Model-A native fixture rate has an unexpected representation")
    return (text[:begin] + block + text[end:]).encode("utf8")


def private_fixture(env_file, accounts, output):
    require(env_file.is_file() and env_file.stat().st_size <= 65536, "Private fixture env unavailable")
    values = {}
    for line in env_file.read_text(encoding="utf8").splitlines():
        if line and not line.startswith("#"):
            key, separator, value = line.partition("=")
            require(separator and key not in values, "Ambiguous fixture env")
            values[key] = value
    root, config = Path(values.get("PROOF_PRIVATE_DIR", "")), Path(values.get("PROOF_CONFIG_FILE", ""))
    require(root.is_absolute() and root.is_dir() and config.is_absolute() and config.is_file(), "Existing private native config required")
    require(not root.is_symlink() and not config.is_symlink(), "Private native config/root must not be symlinks")
    root, config, public, handoff = root.resolve(), config.resolve(), output.resolve(), accounts.resolve()
    require(config == root / "config.yaml" and handoff.is_relative_to(root) and accounts.is_file(), "Private config/accounts escaped fixture root")
    require(not public.is_relative_to(root) and not root.is_relative_to(public) and not env_file.resolve().is_relative_to(public),
            "Private fixture overlaps uploaded pricing output")
    require(not (output / "pricing-browser.json").exists(), "Pricing requires fresh output")
    if os.name == "posix":
        require(stat.S_IMODE(root.stat().st_mode) & 0o077 == 0
                and all(stat.S_IMODE(p.stat().st_mode) & 0o077 == 0 for p in (config, accounts, env_file)),
                "Pricing private fixture permissions differ")
    data = json.loads(accounts.read_text(encoding="utf8"))['users']
    require(len(data) == 2 and len({v['id'] for v in data}) == 2
            and all(v['email'].endswith('@example.com') and v['password'] for v in data), "Existing synthetic staff handoff required")
    return root, config, data, [v for k, v in values.items() if any(word in k for word in ('KEY', 'SECRET', 'PASSWORD'))]


def overwrite_config(path, value):
    # Keep the file inode: /proof/config.yaml is an existing read-only file bind.
    with path.open("r+b") as handle:
        handle.seek(0); handle.write(value); handle.truncate(); handle.flush(); os.fsync(handle.fileno())
    require(path.read_bytes() == value, "Private native YAML write/readback differs")


class PricingFixture(Fixture):
    def __init__(self, env_file, output, config, private, secrets):
        super().__init__(env_file.resolve(), output)
        self.config, self.private, self.secrets = config, private, secrets

    def command_json(self, arguments, label, timeout=75):
        try:
            result = subprocess.run(self.command + arguments, cwd=ROOT, capture_output=True, timeout=timeout)
        except (OSError, subprocess.SubprocessError):
            raise AssertionError("Pricing fixture command unavailable: " + label) from None
        require(result.returncode == 0 and len(result.stdout) <= MAX_BYTES, "Pricing fixture command failed: " + label)
        try:
            data = json.loads(result.stdout)
        except (ValueError, UnicodeError):
            raise AssertionError("Pricing fixture returned invalid safe JSON: " + label) from None
        no_credentials(data, self.secrets)
        return data

    def bind(self, base_url):
        # Compose config can contain secrets: capture only in memory, never export.
        result = subprocess.run(self.command + ['config', '--format', 'json'], cwd=ROOT, capture_output=True, timeout=30)
        require(result.returncode == 0 and len(result.stdout) <= MAX_BYTES, "Pricing Compose owner unavailable")
        config = json.loads(result.stdout)
        require(set(config['services']) == {'proxy', 'postgres', 'provider', 'redis', 'webui'}
                and config['networks']['proof']['internal'] is True
                and all(not s.get('ports') for s in config['services'].values()), "Pricing requires the isolated native fixture topology")
        mounts = {v['target']: v for v in config['services']['proxy']['volumes'] if v['type'] == 'bind'}
        expected = {'/proof/config.yaml': self.config, '/proof-private': self.private,
                    '/proof/pricing_snapshot.py': ROOT / 'deploy/openwebui-budgets/pricing_snapshot.py',
                    '/proof/prove_pricing_snapshots.py': ROOT / 'scripts/goal584-budget-proof/prove_pricing_snapshots.py'}
        require(all(target in mounts and Path(mounts[target]['source']).resolve() == path.resolve()
                    and (target == '/proof-private' or mounts[target].get('read_only') is True)
                    for target, path in expected.items()), "Pricing native config/callback/verifier mounts differ")
        result = subprocess.run(self.command + ['ps', '-q', 'webui'], cwd=ROOT, capture_output=True, timeout=15)
        container = result.stdout.decode('ascii').strip()
        require(result.returncode == 0 and re.fullmatch('[a-f0-9]{64}', container), "Pricing requires one native WebUI container")
        inspected = subprocess.run(['docker', 'inspect', '--format', '{{json .NetworkSettings.Networks}}', container],
                                   cwd=ROOT, capture_output=True, timeout=15)
        require(inspected.returncode == 0 and urlsplit(base_url).hostname in
                {v['IPAddress'] for v in json.loads(inspected.stdout).values()}, "Pricing target is outside this Compose owner")

    def config_observation(self, new=False):
        data = self.command_json(['exec', '-T', 'proxy', 'python', '-B', '-c', CONFIG_OBSERVATION,
                                  *(['0.02', '0.04'] if new else ['0.01', '0.02'])], 'native_config')
        for field, path in [('sha256', self.config), ('callback_sha256', ROOT / 'deploy/openwebui-budgets/pricing_snapshot.py'),
                            ('verifier_sha256', ROOT / 'scripts/goal584-budget-proof/prove_pricing_snapshots.py')]:
            require(data[field] == hashlib.sha256(path.read_bytes()).hexdigest(), "Pricing mounted source/config fingerprint differs")
        return data

    def restart(self):
        for arguments, timeout in [(['restart', 'proxy'], 75), (['up', '-d', '--no-deps', '--wait', '--wait-timeout', '180', 'proxy'], 210)]:
            try:
                result = subprocess.run(self.command + arguments, cwd=ROOT, capture_output=True, timeout=timeout)
            except (OSError, subprocess.SubprocessError):
                raise AssertionError("Native pricing proxy restart/readiness unavailable") from None
            require(result.returncode == 0, "Native pricing proxy restart/readiness failed")

    def observe(self, target='baseline'):
        data = self.command_json(['exec', '-T', 'proxy', 'python', '-B', '-c', OBSERVE, target], 'native_observation')
        self.sequence += 1
        write_json(self.output / ('pricing-native-%02d.json' % self.sequence), data)
        return data

    def pricing(self, mode, witness):
        command = ['exec', '-T', 'proxy', 'python', '-B', '/proof/prove_pricing_snapshots.py', '--mode', mode,
            '--private-state', '/proof-private/webui-state.private.json', '--receipt', '/proof-private/pricing-' + mode + '.safe.json',
            '--expected-input-rate', '0.01' if mode == 'record' else '0.02',
            '--expected-output-rate', '0.02' if mode == 'record' else '0.04',
            '--expected-cost', '0.20' if mode == 'record' else '0.40', '--witness-model', MODEL, '--witness-request-id', witness]
        if mode == 'compare': command += ['--prior-receipt', '/proof-private/pricing-record.safe.json']
        data = self.command_json(command, 'pricing_' + mode)
        require(data.get('passed') is True and data.get('mode') == mode, "Native pricing verifier did not qualify")
        write_json(self.output / ('pricing-' + mode + '.json'), data)
        return data

    def captures(self, label):
        physical, context = super().provider(), super().context()
        no_credentials(physical, self.secrets); no_credentials(context, self.secrets)
        write_json(self.output / ('pricing-provider-' + label + '.json'), physical)
        write_json(self.output / ('pricing-context-' + label + '.json'), context)
        return physical, context


def finance_ready(before, after, call, actor, request_id, expected_scope):
    require(before['models'] == after['models'] and before['unqualified_zero_request_ids'] == after['unqualified_zero_request_ids'],
            "Pricing call changed model profiles or unrelated zero-cost history")
    old, current = ({v['request_id']: v for v in value['rows']} for value in (before, after))
    require(len(old) == len(before['rows']) and len(current) == len(after['rows'])
            and old.keys() <= current.keys() and all(current[k] == v for k, v in old.items()), "Pricing call changed prior financial rows")
    added = [v for k, v in current.items() if k not in old]
    require(len(added) <= 1, "Pricing ordinary call created extra financial rows")
    if not added: return False
    row = added[0]; scope = row['scope']
    require(row['request_id'] == request_id and row['user_id'] == actor and row['model'] == MODEL
            and row['spend_usd'] in ('0.4', '0.40') and row['usage'] == {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}
            and scope == expected_scope and scope['category'] == 'personal' and scope['user_id'] == actor and scope['model'] == MODEL
            and scope['chat_id'] == scope['root_chat_id'] == call['chat_id']
            and scope['answer_id'] == scope['root_answer_id'] == call['message_id'], "Pricing witness is not the actual ordinary personal reply")
    previous, updated = ({v['user_id']: v for v in value['budgets']} for value in (before, after))
    require(len(previous) == len(updated) == 5 and previous.keys() == updated.keys(), "Pricing payer set changed")
    ready = True
    for uid, old_budget in previous.items():
        new_budget = copy.deepcopy(updated[uid])
        for old_value, new_value, delta in [(old_budget, new_budget, Decimal('.4') if uid == actor else Decimal(0)),
                *[(a, b, Decimal('.4') if uid == actor and a['model'] == MODEL else Decimal(0))
                  for a, b in zip(old_budget['models'], new_budget['models'])]]:
            expected = Decimal(old_value['spend']) + delta
            actual = Decimal(new_value['spend'])
            if delta and not same_money(actual, expected):
                require(actual < expected, "Pricing native counter exceeds the one explicit fixture call")
                ready = False
            else:
                require(same_money(actual, expected) if delta else actual == expected, "Pricing call changed an unrelated counter")
            new_value['spend'] = old_value['spend']
        require(new_budget == old_budget, "Pricing call changed native key/cap/reset/identity")
    return ready


def causal_request(before, after, context_before, context_after, call, actor):
    require(before['synthetic'] is after['synthetic'] is True and before['control'] == after['control'], "Pricing provider owner/control changed")
    require(after['requests'][:len(before['requests'])] == before['requests'] and len(after['requests']) == len(before['requests']) + 1,
            "Pricing browser did not cause exactly one new physical request")
    require(context_after['requests'][:len(context_before['requests'])] == context_before['requests']
            and len(context_after['requests']) == len(context_before['requests']) + 1, "Pricing browser did not cause exactly one new gateway request")
    captured, physical = context_after['requests'][-1], after['requests'][-1]
    verify_context_row(captured, {**call, 'user_id': actor}, builtin_tools=False)
    compare_provider(captured, physical, MODEL)
    patch = captured['native_stream_usage_patch']
    # compare_provider owns the allowed native patch and stream_options shape.
    # This known SDK flag is internal-only, not an inference/provider field.
    marker = '_litellm_strip_stream_usage'
    require(marker not in patch or patch[marker] is True, "Pricing native internal usage flag must be exactly true")
    require(set(captured['body']) <= set(FIELDS), "Unknown pricing gateway semantic field")
    merged = {**captured['body'], **patch, 'model': 'goal584-fake-a'}
    expected = {field: merged[field] for field in FIELDS if field in merged}
    require(physical['body'] == expected, "Pricing full provider body changed")
    scope = captured['verified_cost_scope']
    require(captured['native_auth_user_id'] == scope['user_id'] == actor and scope['category'] == 'personal' and scope['model'] == MODEL
            and scope['chat_id'] == scope['root_chat_id'] == call['chat_id']
            and scope['answer_id'] == scope['root_answer_id'] == call['message_id'], "Pricing capture lost ordinary personal scope")
    return physical['id']


def rehearse(fixture, config, private, actor, visible_call, receipt):
    require(all(not (private / name).exists() for name in ('pricing-config-original.private.yaml',
            'pricing-record.safe.json', 'pricing-compare.safe.json')), "Pricing private evidence must be fresh")
    receipt['initial_config_observation'] = fixture.config_observation()
    before = fixture.observe()
    require(before['accounting_ready'] is True and before['actor_id'] == actor, "Pricing baseline has unsettled accounting/foreign actor")
    old = [v for v in before['native']['rows'] if v['user_id'] == actor and v['model'] == MODEL and Decimal(v['spend_usd']) == Decimal('.20')]
    require(old, "Existing ordinary old-rate native witness unavailable")
    recorded = fixture.pricing('record', old[0]['request_id'])
    require(recorded['fixture_scope'] == before['scope'], "Pricing record changed fixture identity")
    physical_before, context_before = fixture.captures('before')
    original = config.read_bytes()
    require(hashlib.sha256(original).hexdigest() == receipt['initial_config_observation']['sha256'],
            "Private native YAML changed before the controlled pricing step")
    changed = changed_config(original)
    backup = private / 'pricing-config-original.private.yaml'
    fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    with os.fdopen(fd, 'wb') as handle:
        handle.write(original); handle.flush(); os.fsync(handle.fileno())
    receipt.update(original_config_sha256=hashlib.sha256(original).hexdigest(), changed_config_sha256=hashlib.sha256(changed).hexdigest())
    attempted = qualified = False
    try:
        attempted = True
        overwrite_config(config, changed)
        fixture.restart()
        receipt['changed_config_observation'] = fixture.config_observation(new=True)
        call = visible_call()
        receipt['call'] = call
        physical_after, context_after = fixture.captures('after')
        request_id = causal_request(physical_before, physical_after, context_before, context_after, call, actor)
        deadline = time.monotonic() + 60
        while True:
            after = fixture.observe(request_id)
            require(after['actor_id'] == actor and after['scope'] == before['scope'] and after['task_config'] == before['task_config'],
                    "Pricing call changed fixture/native TaskConfig")
            ready = finance_ready(before['native'], after['native'], call, actor, request_id,
                                  context_after['requests'][-1]['verified_cost_scope'])
            if ready and after['accounting_ready']: break
            require(time.monotonic() < deadline, "Pricing row/counters did not settle before deadline")
            time.sleep(.25)
        compared = fixture.pricing('compare', request_id)
        require(compared['witness_request_ids'] == [request_id] and compared['row_counts']['new'] == 1,
                "Pricing comparison included extra new native rows")
        quoted = next(v for v in compared['rows'] if v['request_id'] == request_id)
        financial = next(v for v in after['native']['rows'] if v['request_id'] == request_id)
        require(quoted['user_id'] == actor and quoted['api_key_hash'] == financial['key_hash']
                and quoted['usage'] == financial['usage'] and quoted['model_group'] == financial['model'],
                "Native pricing snapshot and personal financial row do not identify the same call")
        receipt.update(witness_request_id=request_id, old_witness_request_id=old[0]['request_id'],
                       old_immutable_rows=compared['row_counts']['old_immutable'], native_cost_usd='0.40', service_unchanged=True)
        qualified = True
        return after
    finally:
        if attempted:
            # Even partial config writes/restart/browser failures must attempt all
            # rollback steps. Never turn a restoration failure into a PASS.
            try:
                overwrite_config(config, original)
                receipt['config_bytes_restored'] = config.read_bytes() == backup.read_bytes() == original
            finally:
                fixture.restart()
                receipt['restored_config_observation'] = fixture.config_observation()
                restored = fixture.observe('readiness')
                receipt['restored_native_readiness'] = restored['schema_ready'] is True
                if qualified:
                    require(restored['scope'] == after['scope'] and restored['native'] == after['native']
                            and restored['task_config'] == after['task_config'], "Pricing restoration changed observed native financial/task state")
            require(receipt.get('config_bytes_restored') is True and receipt.get('restored_native_readiness') is True,
                    "Pricing original native config/readiness restoration failed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('base-url', 'accounts', 'env-file', 'output'):
        parser.add_argument('--' + name, type=str if name == 'base-url' else Path, required=True)
    args = parser.parse_args()
    u = urlsplit(args.base_url)
    require(u.scheme == 'http' and u.port == 8080 and u.path in ('', '/') and not u.username and not u.password
            and not u.query and not u.fragment and isinstance(ipaddress.ip_address(u.hostname), ipaddress.IPv4Address)
            and ipaddress.ip_address(u.hostname).is_private, "Pricing browser target must be disposable private IPv4:8080")
    private, config, accounts, secrets = private_fixture(args.env_file, args.accounts, args.output)
    secrets += [v['password'] for v in accounts]
    args.output.mkdir(exist_ok=True)
    fixture = PricingFixture(args.env_file, args.output, config, private, secrets)
    receipt = {'schema': 1, 'proof': 'goal584-native-pricing-browser', 'passed': False,
        'started_at_utc': datetime.now(timezone.utc).isoformat(),
        'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'not_qualified': ['tariff source/version/effective interval', 'atomic total/rate version binding', 'other routes/tariffs',
                          'global DB privacy', 'failure/cancel lifecycle', 'production', 'paid provider']}
    playwright = browser = None
    try:
        fixture.bind(args.base_url)
        def visible_call():
            nonlocal playwright, browser
            from playwright.sync_api import sync_playwright
            playwright = sync_playwright().start()
            browser = playwright.chromium.launch(channel='chrome', headless=True)
            receipt['browser_version'] = browser.version
            _, page, token = login(browser, args.base_url, accounts[0])
            return chat(page, args.base_url, token, accounts[0]['id'], MODEL, 'success',
                        'pricing-new-rate', args.output, expected_costs=('0.40', '0.40'))
        rehearse(fixture, config, private, accounts[0]['id'], visible_call, receipt)
        receipt['passed'] = True
    except Exception:
        # Provider/Compose/browser error strings may contain private values.
        receipt['failure'] = 'Pricing browser or exact native restoration failed'
    finally:
        try:
            if browser is not None: browser.close()
            if playwright is not None: playwright.stop()
        except Exception:
            receipt.update(passed=False, failure='Pricing browser cleanup failed')
    receipt['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
    no_credentials(receipt, secrets)
    write_json(args.output / 'pricing-browser.json', receipt)
    print(json.dumps(receipt, indent=2, allow_nan=False))
    return 0 if receipt['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
