"""Dedicated one-worker native catalog-check coordinator; no inference or native imports.

Parent supplies an actual Docker/Git/private-mount attestation from a fresh stand.
The worker observes native APIs and uses the existing fixture controller only.
It does not execute a scheduler, rewrite configuration or erase native history.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
from importlib.metadata import version
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.request import Request

from prove_native_budgets import NativeProof, ProofError, require
from prove_gateway_auth import read_private, write_private

sys.path.append(str(Path(__file__).resolve().parent.parent.parent / 'deploy/litellm-patches/positive-floor-v1.105.1'))
import native_floor_identity as native_sdk

PROOF = 'goal584-native-pricing-catalog'
PRIVATE = Path('/proof-private')
CONFIG = Path('/proof/config.yaml')
CATALOG = 'http://provider:8000/__proof/catalog'
SOURCE = '/model/cost_map/source'
STATUS = '/schedule/model_cost_map_reload/status'
SCHEDULE = '/schedule/model_cost_map_reload'
RELOAD = '/reload/model_cost_map'
MAX_BYTES = 4 * 1024 * 1024
PROVIDER_SHA = '6a235e6e81c064ea711afc5331cffece458d6a9c6d25f1ffb34b0869bd0b28da'
HELPERS = {'prove_native_budgets.py': 'b31b13400683770aa5366d92e76e5dac8596a6a7f47ad104c001ed5f1689e331',
    'prove_gateway_auth.py': 'aec065251e8c5164ff4d10f33e4b27a76f7647a2f0e026aea0d0908a6e8f7f09',
    'native_floor_identity.py': '39d28b28e3d60fb6e5989cdd4b23a2a1341277bc569f2bf3ef0eb9e32deac839',
    'manifest.json': '1695ef5f07b8662e8c8a0bc031c01debb74266f92873bac12cc5f2edac93b99b'}
NATIVE = {'litellm_core_utils/get_model_cost_map.py': '66fe0c8a066efebd34cca8815ac23ebf09379b76f7b32525321503ef6d7db679',
    'proxy/common_utils/periodic_reload_schedule.py': 'db917c79f25dc931afa2d1dd5a5146b231b1aaf526621f9f01a3bbe7abdbd4d4',
    'constants.py': '89c44d97c1be1e90c6e2521589a9c0c931c153363e3b29255526ca9ce6737f67',
    'model_prices_and_context_window_backup.json': '329113e5820834dc2a206500db9ec7861a17c74b86fe79601dec05478c06327e'}
DOCUMENTS = {
    'S1': ('81b3a4c0e550eeb11a2499bc179809999e8c2c3a7eb680780e3f730812a71776', '630a3fcc1ead78474df82c7a1b3f5afa69867f86', 2250880),
    'S2': ('d7230431a767de7a2cbd6ad112b2e2bd04db8b0de04881f9524fa7dcca114d5f', '785f2714ae96b8657ec7759fd71161ab811ed6a9', 2250880),
    'invalid': ('4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945', '0637a088a01e8ddab3bf3fa98dbe804cbde1a0dc', 2),
    'truncated': ('02caa3159c6c57b8cd83702d02b6d5df3f3a87e30f6f3c2114ea3773d29c180c', '1d02a82334ce6c0601358e298510b6f054b47b9b', 18)}
BACKUP_BLOB = 'd42e66605d72e6b4270c7fff97cf9a28cb2b1ebd'
COMMAND = ['--config', '/proof/config.yaml', '--host', '0.0.0.0', '--port', '4000', '--num_workers', '1', '--telemetry', 'false']
IMAGES = {'provider': native_sdk.BASE_IMAGE,
    'postgres': 'docker.io/pgvector/pgvector:0.8.7-pg16-bookworm@sha256:0dd3149a06e4579a0d70d8fef9945636cd514005e7237deb27f9b67886f8dc4f',
    'redis': 'docker.io/library/redis:7-alpine@sha256:8da19c7399dca900c6822a1cf30f9d2285585e2c4b457ff4095b0f4500054d3f'}


def encoded(value):
    raw = json.dumps(value, sort_keys=True, allow_nan=False).encode()
    require(len(raw) <= MAX_BYTES, 'catalog_evidence_bytes')
    return raw


def utc(value):
    require(isinstance(value, str) and len(value) <= 64, 'catalog_timestamp')
    try:
        at = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        raise ProofError('catalog_timestamp') from None
    require(at.utcoffset() is not None, 'catalog_timestamp_timezone')
    return at


def source_projection(value):
    require(set(value) == {'source', 'url', 'is_env_forced', 'fallback_reason', 'loaded_at', 'source_revision', 'etag', 'model_count'}, 'catalog_source_shape')
    require(value['source'] in ('local', 'remote') and value['url'] in (None, CATALOG)
        and type(value['is_env_forced']) is bool and value['fallback_reason'] is None
        and type(value['model_count']) is int and 4458 <= value['model_count'] <= 100000, 'catalog_source_profile')
    utc(value['loaded_at'])
    require(value['source_revision'] in {BACKUP_BLOB, DOCUMENTS['S1'][1], DOCUMENTS['S2'][1]}
        and value['etag'] in (None, '"'+DOCUMENTS['S1'][0]+'"', '"'+DOCUMENTS['S2'][0]+'"'), 'catalog_source_revision')
    require((value['source'] == 'local' and value['url'] is None and value['source_revision'] == BACKUP_BLOB and value['etag'] is None)
        or (value['source'] == 'remote' and value['url'] == CATALOG and value['is_env_forced'] is False
            and any(value['source_revision'] == blob and value['etag'] == '"'+h+'"' for h, blob, _ in (DOCUMENTS['S1'], DOCUMENTS['S2']))), 'catalog_source_binding')
    return dict(value)


def status_projection(value):
    require(set(value) == {'scheduled', 'interval_hours', 'last_run', 'next_run', 'source_revision', 'etag'}, 'catalog_status_shape')
    require(type(value['scheduled']) is bool and (value['interval_hours'] is None or type(value['interval_hours']) is int and value['interval_hours'] == 1)
        and value['scheduled'] == (value['interval_hours'] == 1), 'catalog_status_interval')
    require(value['source_revision'] in {BACKUP_BLOB, DOCUMENTS['S1'][1], DOCUMENTS['S2'][1]}
        and value['etag'] in (None, '"'+DOCUMENTS['S1'][0]+'"', '"'+DOCUMENTS['S2'][0]+'"'), 'catalog_status_revision')
    if value['last_run'] is None:
        require(value['next_run'] is None, 'catalog_status_next_without_last')
    else:
        at = utc(value['last_run'])
        require(value['next_run'] is None if not value['scheduled'] else utc(value['next_run']) == at + timedelta(hours=1), 'catalog_status_next')
    return dict(value)


def catalog_projection(value):
    require(set(value) == {'synthetic', 'variant', 'native_revision', 'corpus_sha256', 'corpus_git_blob', 'corpus_entry_count', 'request_count', 'requests_by_variant', 'documents'}, 'catalog_fixture_shape')
    require(value['synthetic'] is True and value['native_revision'] == native_sdk.BASE_REVISION
        and value['corpus_sha256'] == NATIVE['model_prices_and_context_window_backup.json']
        and value['corpus_git_blob'] == BACKUP_BLOB and value['corpus_entry_count'] == 4460, 'catalog_fixture_origin')
    require(set(value['requests_by_variant']) == set(DOCUMENTS) and value['variant'] in DOCUMENTS
        and all(type(n) is int and 0 <= n <= 10000 for n in value['requests_by_variant'].values())
        and type(value['request_count']) is int and value['request_count'] == sum(value['requests_by_variant'].values()) <= 10000, 'catalog_fixture_count')
    require(value['documents'] == {k: {'sha256': h, 'native_git_blob': blob, 'bytes': size, 'etag': '"'+h+'"'}
        for k, (h, blob, size) in DOCUMENTS.items()}, 'catalog_fixture_documents')
    return value


def source_files():
    here = Path(__file__).resolve().parent
    paths = {name: here/name for name in HELPERS}
    if not paths['native_floor_identity.py'].is_file():
        paths['native_floor_identity.py'] = Path(native_sdk.__file__)
        paths['manifest.json'] = paths['native_floor_identity.py'].with_name('manifest.json')
    actual = {name: hashlib.sha256(p.read_bytes()).hexdigest() for name, p in paths.items()}
    require(actual == HELPERS, 'catalog_helper_binding')
    actual[Path(__file__).name] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    return actual


def profile(args, attest, config, env=os.environ):
    require(set(attest) == {'schema', 'proof', 'project', 'source_commit', 'containers', 'proxy_command', 'config_sha256', 'files_sha256', 'provider_sha256', 'native_artifact'}, 'catalog_attestation_shape')
    require(type(attest['schema']) is int and attest['schema'] == 1 and attest['proof'] == PROOF
        and re.fullmatch('goal584-pricing-[0-9a-f]{12}', args.project) and args.project == attest['project'] == env.get('PROOF_PRICING_PROJECT')
        and re.fullmatch('[0-9a-f]{40}', attest['source_commit']) and attest['source_commit'] == env.get('PROOF_SOURCE_COMMIT'), 'catalog_project_binding')
    require(not any(PRIVATE.glob('*webui*')) and not (PRIVATE/'gateway-state.private.json').exists(), 'catalog_refuses_shared_fixture')
    require(set(attest['containers']) == {'proxy', 'postgres', 'redis', 'provider'} and attest['proxy_command'] == COMMAND, 'catalog_four_service_topology')
    ids = []
    for service, item in attest['containers'].items():
        require(set(item) == {'id', 'number', 'image_ref', 'image_id', 'network', 'health'} and re.fullmatch('[0-9a-f]{64}', item['id'])
            and item['number'] == '1' and item['health'] == 'healthy' and item['network'] == args.project+'_proof'
            and re.fullmatch('sha256:[0-9a-f]{64}', item['image_id'])
            and item['image_ref'] == (native_sdk.image_ref() if service == 'proxy' else IMAGES[service]), 'catalog_container_binding')
        ids.append(item['id'])
    require(len(set(ids)) == 4 and env.get('HOSTNAME') == attest['containers']['proxy']['id'][:12], 'catalog_worker_binding')
    if native_sdk.variant() != 'stock':
        require(attest['containers']['proxy']['image_id'] == native_sdk.image_ref(), 'catalog_derivative_image')
    require(attest['native_artifact'] == native_sdk.identity(), 'catalog_native_variant')
    require(attest['config_sha256'] == hashlib.sha256(CONFIG.read_bytes()).hexdigest()
        and attest['files_sha256'] == source_files() and attest['provider_sha256'] == PROVIDER_SHA, 'catalog_attested_sources')
    require(env.get('LITELLM_MODEL_COST_MAP_URL') == CATALOG and env.get('LITELLM_LOCAL_MODEL_COST_MAP', '').lower() == 'false'
        and env.get('PROXY_CONFIG_RELOAD_INTERVAL_SECONDS', '30') == '30'
        and not any(env.get(k) for k in ('MODEL_COST_MAP_MIN_MODEL_COUNT', 'MODEL_COST_MAP_MAX_SHRINK_RATIO')), 'catalog_fetch_environment')
    general, settings = config['general_settings'], config['litellm_settings']
    require(general.get('database_url') == 'os.environ/DATABASE_URL' and re.fullmatch(r'postgresql://goal584:[A-Za-z0-9_-]+@postgres:5432/goal584_pricing', env.get('DATABASE_URL', ''))
        and general.get('master_key') == 'os.environ/PROOF_MASTER_KEY' and general.get('custom_auth') is None
        and general.get('store_model_in_db') in (None, False) and general.get('supported_db_objects') in (None, ['model_cost_map'])
        and general.get('proxy_config_reload_interval_seconds', 30) == 30
        and settings.get('num_retries') == 0, 'catalog_native_config')
    models = config['model_list']
    require(len(models) == 2 and {m['model_name'] for m in models} == {'goal584-a', 'goal584-b'}, 'catalog_model_set')
    for model in models:
        suffix = model['model_name'][-1];params, info = model['litellm_params'], model['model_info']
        require(params == {'model': 'openai/goal584-fake-'+suffix, 'api_base': 'http://provider:8000/v1', 'api_key': 'synthetic-provider-only-not-a-credential'}
            and info.get('id') == 'goal584-deployment-'+suffix and info.get('mode') == 'chat'
            and (info.get('max_input_tokens'), info.get('max_output_tokens'), info.get('max_tokens')) == (10,5,15)
            and info.get('input_cost_per_token') == .01 and info.get('output_cost_per_token') == .02, 'catalog_explicit_synthetic_route')
    spec = importlib.util.find_spec('litellm')
    require(spec is not None and spec.origin is not None and version('litellm') == '1.105.1', 'catalog_installed_sdk')
    package = Path(spec.origin).parent
    require({p: hashlib.sha256((package/p).read_bytes()).hexdigest() for p in NATIVE} == NATIVE, 'catalog_installed_sources')
    native_sdk.inspect_sources()  # package discovery/read only; never imports LiteLLM.


class Coordinator:
    def __init__(self, native, state_path, receipt):
        self.native, self.path, self.receipt = native, state_path, receipt
        self.private = {'schema': 1, 'proof': PROOF, 'observations': []}
        self.claimed = self.owns_schedule = self.owns_catalog = False

    def save(self):
        encoded(self.private);write_private(self.path, self.private)

    def native_request(self, method, path, **kwargs):
        require((method, path) in {('GET', '/openapi.json'), ('GET', SOURCE), ('GET', STATUS), ('POST', SCHEDULE), ('DELETE', SCHEDULE), ('POST', RELOAD)}, 'catalog_unexpected_native_api')
        require(not kwargs or method == 'POST' and path == SCHEDULE and kwargs == {'query': {'hours': 1}}, 'catalog_unexpected_native_arguments')
        status, payload, _ = self.native.request(method, path, **kwargs)
        self.private.setdefault('api', []).append({'method': method, 'path': path, 'status': status, 'payload': payload})
        require(type(status) is int and 100 <= status <= 599, 'catalog_native_http_status')
        self.receipt.setdefault('api', []).append({'stage': self.receipt['stage'], 'method': method, 'path': path,
            'status': status, 'payload_sha256': hashlib.sha256(encoded(payload)).hexdigest()})
        self.save()
        return status, payload

    def provider(self, path, body=None):
        require(path in ('/observations', '/control', '/requests'), 'catalog_unexpected_fixture_api')
        if path == '/control':
            require(isinstance(body, dict) and set(body) == {'variant'} and body['variant'] in DOCUMENTS, 'catalog_unexpected_fixture_arguments')
        else:
            require(body is None, 'catalog_unexpected_fixture_arguments')
        url = CATALOG+path if path != '/requests' else 'http://provider:8000/__proof/requests'
        remaining = self.native.timeout if self.native.poll_deadline is None else self.native.poll_deadline-time.monotonic()
        require(remaining > 0, 'catalog_observation_deadline')
        request = Request(url, data=None if body is None else encoded(body), headers={'Content-Type': 'application/json'})
        try:
            with self.native.opener.open(request, timeout=min(20, remaining)) as response:
                raw = response.read(MAX_BYTES+1);status = response.status
        except (OSError, ValueError):
            raise ProofError('catalog_fixture_http') from None
        require(status == 200 and len(raw) <= MAX_BYTES, 'catalog_fixture_http')
        value = json.loads(raw);require(isinstance(value, dict), 'catalog_fixture_json')
        self.private.setdefault('fixture_api', []).append({'path': path, 'payload': value});self.save()
        return value

    def capture(self, label):
        require(len(self.private['observations']) < 256, 'catalog_observation_count')
        a, source = self.native_request('GET', SOURCE);b, status = self.native_request('GET', STATUS)
        catalog = self.provider('/observations');physical = self.provider('/requests')
        raw = {'label': label, 'at': datetime.now(timezone.utc).isoformat(), 'source': source, 'status': status, 'catalog': catalog, 'physical': physical}
        self.private['observations'].append(raw);self.save()
        require(a == b == 200, 'catalog_native_read_status')
        require(set(physical) == {'synthetic', 'requests', 'control'} and physical['synthetic'] is True and physical['requests'] == [], 'catalog_unexpected_inference')
        projected = {k: raw[k] for k in ('label', 'at')}
        projected.update(source=source_projection(source), status=status_projection(status), catalog=catalog_projection(catalog), physical_count=0)
        if self.receipt['observations']:
            previous = self.receipt['observations'][-1]['catalog']['requests_by_variant']
            require(all(catalog['requests_by_variant'][v] >= previous[v] for v in DOCUMENTS), 'catalog_observation_history_decreased')
        self.receipt['observations'].append(projected)
        return projected

    def run(self):
        failure = None
        try:
            self.receipt['stage'] = 'baseline'
            code, spec = self.native_request('GET', '/openapi.json')
            require(code == 200 and spec.get('info', {}).get('version') == '1.105.1', 'catalog_native_openapi')
            # Native catalog routes are intentionally hidden from OpenAPI.
            # Version/source guards and actual native HTTP results own capability.
            baseline = self.capture('baseline')
            require(baseline['catalog']['variant'] == 'S1'
                and all(baseline['catalog']['requests_by_variant'][v] == 0 for v in ('S2', 'invalid', 'truncated'))
                and (baseline['source']['source'] == 'local' and baseline['catalog']['request_count'] == 0
                    or baseline['source']['source_revision'] == DOCUMENTS['S1'][1] and baseline['catalog']['request_count'] > 0)
                and baseline['status'] == {'scheduled': False, 'interval_hours': None, 'last_run': None, 'next_run': None,
                    'source_revision': baseline['source']['source_revision'], 'etag': baseline['source']['etag']}, 'catalog_not_fresh')
            self.claimed = True
            self.receipt['stage'] = 'first_native_poll';self.owns_schedule = True
            code, scheduled = self.native_request('POST', SCHEDULE, query={'hours': 1})
            require(code == 200 and scheduled.get('status') == 'success' and scheduled.get('interval_hours') == 1, 'catalog_schedule_rejected')
            def ready():
                observation = self.capture('first_poll')
                require(time.monotonic() < self.native.poll_deadline, 'catalog_late_poll_completion')
                require(observation['catalog']['variant'] == 'S1' and all(observation['catalog']['requests_by_variant'][v] == 0 for v in ('S2', 'invalid', 'truncated'))
                    and observation['status']['scheduled'], 'catalog_first_poll_profile')
                if (observation['catalog']['request_count'] > baseline['catalog']['request_count'] and observation['source']['source_revision'] == DOCUMENTS['S1'][1]
                    and observation['source']['source'] == 'remote' and observation['source']['url'] == CATALOG
                    and observation['source']['etag'] == observation['status']['etag'] == '"'+DOCUMENTS['S1'][0]+'"'
                    and observation['status']['source_revision'] == DOCUMENTS['S1'][1] and observation['status']['last_run'] is not None
                    and utc(observation['source']['loaded_at']) > utc(baseline['source']['loaded_at'])):
                    return observation
            first = self.native.poll('first catalog schedule execution', ready)
            self.receipt['stage'] = 'manual_S2';self.owns_catalog = True
            require(catalog_projection(self.provider('/control', {'variant': 'S2'}))['variant'] == 'S2', 'catalog_control_variant')
            code, result = self.native_request('POST', RELOAD)
            require(code == 200 and result.get('status') == 'success' and result.get('source_revision') == DOCUMENTS['S2'][1]
                and result.get('etag') == '"'+DOCUMENTS['S2'][0]+'"', 'catalog_manual_reload_failed')
            adopted = self.capture('manual_S2')
            require(adopted['source']['source_revision'] == adopted['status']['source_revision'] == DOCUMENTS['S2'][1]
                and adopted['source']['source'] == 'remote' and adopted['source']['url'] == CATALOG
                and adopted['source']['etag'] == adopted['status']['etag'] == '"'+DOCUMENTS['S2'][0]+'"'
                and adopted['catalog']['variant'] == 'S2'
                and utc(adopted['status']['last_run']) >= utc(first['status']['last_run'])
                and adopted['catalog']['requests_by_variant']['S2'] > first['catalog']['requests_by_variant']['S2'], 'catalog_manual_source_status')
            for variant in ('invalid', 'truncated'):
                self.receipt['stage'] = variant
                require(catalog_projection(self.provider('/control', {'variant': variant}))['variant'] == variant, 'catalog_control_variant')
                before = self.capture(variant+'_before')
                code, _ = self.native_request('POST', RELOAD)
                after = self.capture(variant+'_after')
                require(code == 502, 'catalog_expected_native_parse_failure')
                require(after['catalog']['variant'] == before['catalog']['variant'] == variant
                    and after['source'] == before['source'] and after['status'] == before['status']
                    and after['catalog']['requests_by_variant'][variant] > before['catalog']['requests_by_variant'][variant], 'catalog_invalid_fetch_changed_native_state')
            self.receipt['stage'] = 'observed'
        except Exception as error:
            failure = error
        finally:
            errors = []
            previous = self.receipt['observations'][-1] if self.receipt['observations'] else None
            if self.claimed and self.owns_schedule:
                try:
                    code, value = self.native_request('DELETE', SCHEDULE)
                    require(code == 200 and value.get('status') == 'success', 'catalog_cancel_failed')
                except Exception:
                    errors.append('cancel_failed')
            if self.claimed and self.owns_catalog:
                try:
                    require(catalog_projection(self.provider('/control', {'variant': 'S1'}))['variant'] == 'S1', 'catalog_restore_failed')
                except Exception:
                    errors.append('catalog_restore_failed')
            if self.claimed:
                try:
                    restored = self.capture('restored')
                    require(not restored['status']['scheduled'] and restored['catalog']['variant'] == 'S1', 'catalog_restore_readback')
                    if failure is None and previous is not None:
                        require(restored['source'] == previous['source'] and all(restored['status'][k] == previous['status'][k]
                            for k in ('last_run', 'source_revision', 'etag')), 'catalog_cancel_changed_success_history')
                except Exception:
                    errors.append('restore_readback_failed')
            self.receipt['restoration'] = {'attempted': self.claimed, 'failures': errors,
                'active_native_map_restored': False, 'scope': 'fixture variant and owned interval only; adopted native map remains until teardown'}
            if failure is None and errors:
                failure = ProofError('catalog_restoration_failed')
        if failure is not None:
            raise failure


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--attestation', type=Path, required=True)
    parser.add_argument('--private-state', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--base-url', default='http://127.0.0.1:4000')
    parser.add_argument('--timeout', type=float, default=120)
    args = parser.parse_args()
    receipt = {'schema': 1, 'proof': PROOF, 'passed': False, 'stage': 'preflight', 'observations': [],
        'not_qualified': ['elapsed-hour recurrence', 'HA source/time atomicity', 'status-write rollback', 'inference/tariff activation', 'production/whole GOAL']}
    receipt_authorized = False
    try:
        paths = (args.attestation, args.private_state, args.receipt)
        require(not PRIVATE.is_symlink() and all(p.parent.resolve() == PRIVATE.resolve() and not p.is_symlink() for p in paths) and len({p.resolve() for p in paths}) == 3
            and not args.private_state.exists() and not args.receipt.exists(), 'catalog_private_paths')
        receipt_authorized = True
        require(0 < args.timeout <= 120, 'catalog_timeout_bound')
        master = os.environ.get('PROOF_MASTER_KEY', '')
        require(master.startswith('sk-') and len(master) >= 20, 'catalog_private_master_missing')
        import yaml
        config = yaml.safe_load(CONFIG.read_bytes());attest = read_private(args.attestation)
        profile(args, attest, config)
        receipt.update(project=args.project, source_commit=attest['source_commit'], native_artifact=attest['native_artifact'])
        native = NativeProof(args.base_url, master, args.timeout, {})
        Coordinator(native, args.private_state, receipt).run()
        receipt['passed'] = True
    except Exception as e:
        receipt['failure_code'] = str(e) if isinstance(e, ProofError) and re.fullmatch('[a-z_]{1,80}', str(e)) else 'external_boundary_failure'
    try:
        raw = encoded(receipt)
        require(not re.search(rb'(?:sk-|gw-|Bearer\s)[A-Za-z0-9_-]{12,}|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+', raw), 'catalog_public_credential')
        if receipt_authorized:
            write_private(args.receipt, receipt)
    except Exception:
        receipt['passed'] = False
        receipt.setdefault('failure_code', 'catalog_receipt_write_failed')
        receipt['receipt_write_failure'] = 'catalog_receipt_write_failed'
    summary = {key: receipt[key] for key in ('proof', 'passed', 'stage', 'failure_code', 'receipt_write_failure') if key in receipt}
    print(json.dumps(summary))
    return 0 if receipt['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
