"""Prepare the existing gateway for native CC interoperability; never apply it.

Run as the deployment owner with explicit --root after native admin sign-in.
Only native local GETs and Docker identity reads precede protected file writes.

Optional managed preparation (never applies native config): pass both
--managed-config /protected/phase/private/approved-litellm.json and
--managed-env /protected/phase/private/approved-litellm.env. The JSON is the
operator-approved native LiteLLM config (JSON is YAML-compatible); prices and
provider credentials remain caller-owned. The env must supply distinct
LITELLM_MASTER_KEY and OWUI_BUDGET_GATEWAY_SECRET. Outputs use the existing
new-phase files/Compose selectors; an existing gateway is never overwritten.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import urllib.error
import urllib.request

BASE_ROOT = Path('/opt/openwebui-upgrade-0122')
WEBUI_URL = 'http://127.0.0.1:18122'
WEBUI_CONTAINER = 'openwebui-0122-openwebui-0122-1'
GOOGLE_INDEX = 4
GOOGLE_URL = 'https://generativelanguage.googleapis.com/v1beta/openai'
GATEWAY_URL = 'http://google-gateway-0122:4000/v1'
REQUIRED_GOOGLE_MODELS = frozenset({
    'models/gemini-3.5-flash', 'models/gemini-3.6-flash',
    'models/gemini-3.1-flash-lite', 'models/gemini-3.5-flash-lite',
})
# Admission constraints for the existing native connections, not model catalogs.
CC_CONNECTIONS = (
    (1, 'https://api.openai.com/v1', 'OPENAI_API_KEY', r'gpt-[A-Za-z0-9][A-Za-z0-9._-]*'),
    (2, 'https://api.anthropic.com/v1', 'ANTHROPIC_API_KEY', r'claude-[A-Za-z0-9][A-Za-z0-9._-]*'),
    (GOOGLE_INDEX, GOOGLE_URL, 'GEMINI_API_KEY', r'models/[A-Za-z0-9][A-Za-z0-9._-]*'),
)
PROXY_KEYS = frozenset({
    'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY',
    'http_proxy', 'https_proxy', 'all_proxy', 'no_proxy',
})
CONFIG = '''model_list:
  - model_name: "models/*"
    litellm_params:
      model: "gemini/*"
      api_key: os.environ/GEMINI_API_KEY
  - model_name: "gpt-*"
    litellm_params:
      model: "openai/gpt-*"
      api_key: os.environ/OPENAI_API_KEY
  - model_name: "claude-*"
    litellm_params:
      model: "anthropic/claude-*"
      api_key: os.environ/ANTHROPIC_API_KEY
litellm_settings:
  num_retries: 0
  cache: false
router_settings:
  num_retries: 0
  fallbacks: []
general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY
  store_model_in_db: false
  background_health_checks: false
'''


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def protected(path, *, directory=False):
    require(not path.is_symlink(), 'Protected input must not be a symlink: ' + path.name)
    metadata = path.stat()
    require(stat.S_ISDIR(metadata.st_mode) if directory else stat.S_ISREG(metadata.st_mode),
            'Unexpected protected input type: ' + path.name)
    require(stat.S_IMODE(metadata.st_mode) == (0o700 if directory else 0o600),
            'Protected input has unexpected permissions: ' + path.name)
    require(metadata.st_uid == os.geteuid(), 'Protected input has a different owner: ' + path.name)


def phase_root(value):
    root = Path(value)
    require(root.is_absolute() and '..' not in root.parts, 'Use an absolute task phase root')
    require(root.resolve(strict=True) == root, 'Phase root must not traverse symlinks')
    require(BASE_ROOT.resolve(strict=True) == BASE_ROOT, 'Task base must not traverse symlinks')
    require(root == BASE_ROOT or root.is_relative_to(BASE_ROOT), 'Phase root is outside the task base')
    require(all(re.fullmatch(r'[a-z0-9][a-z0-9-]*', part)
                for part in root.relative_to(BASE_ROOT).parts), 'Use simple task phase directory names')
    protected(root, directory=True)
    if (root / 'private').exists() or (root / 'private').is_symlink():
        protected(root / 'private', directory=True)
    return root


def read_env(path):
    protected(path)
    raw = path.read_bytes()
    result = {}
    for line in raw.decode('utf-8').splitlines():
        if not line or line.startswith('#'):
            continue
        key, separator, value = line.partition('=')
        require(separator and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', key), 'Unexpected raw env syntax')
        require(key not in result, 'Duplicate env key: ' + key)
        result[key] = value
    return raw, result


def encoded(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + '\n').encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def write_new(path, value, mode=0o600):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(value)


def native_get(path, token):
    request = urllib.request.Request(WEBUI_URL + path, headers={'Authorization': 'Bearer ' + token})
    # Session credentials must not follow a redirect or use a host-wide proxy.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.URLError:
        raise RuntimeError('Native local GET failed: ' + path) from None


def docker_read(args):
    try:
        return subprocess.check_output(['docker', *args], text=True, timeout=30,
                                       stderr=subprocess.DEVNULL)
    except (subprocess.SubprocessError, OSError):
        raise RuntimeError('Docker identity read failed') from None


def candidate_identity(root, compose):
    inspection = json.loads(docker_read(['inspect', WEBUI_CONTAINER]))[0]
    image = compose.get('RELEASE_WEBUI_IMAGE', '')
    require(re.fullmatch(r'sha256:[0-9a-f]{64}', image), 'Expected an immutable candidate image ID')
    require(inspection['Image'] == image and inspection['State']['Running'] is True,
            'Candidate image/running identity changed')
    labels = inspection['Config']['Labels']
    require(labels.get('com.docker.compose.project') == 'openwebui-0122'
            and labels.get('com.docker.compose.service') == 'openwebui-0122', 'Foreign candidate owner')
    require(inspection['HostConfig']['PortBindings'].get('8080/tcp') ==
            [{'HostIp': '127.0.0.1', 'HostPort': '18122'}], 'Candidate must use the private loopback route')
    require(compose.get('RELEASE_WEBUI_ENV_FILE') == str(root / 'webui.env'),
            'Candidate environment belongs to a different phase root')
    protected(root / 'prepared.private.json')
    prepared = json.loads((root / 'prepared.private.json').read_text(encoding='utf-8'))
    if 'phase_root' in prepared:
        require(prepared['phase_root'] == str(root), 'Snapshot belongs to a different phase root')
        volume = compose.get('RELEASE_DATA_VOLUME')
    else:
        # The inspected first snapshot predates explicit phase/volume selectors.
        # Its immutable boot image and all three native default volume names bind it.
        legacy_volumes = {name: 'openwebui-0122_' + name
                          for name in ('data', 'stt_data', 'terminal_home')}
        require(root == BASE_ROOT and prepared.get('volumes') == legacy_volumes
                and prepared.get('boot_image_id') == image
                and not any(key in compose for key in
                            ('RELEASE_DATA_VOLUME', 'RELEASE_STT_DATA_VOLUME', 'RELEASE_TERMINAL_HOME_VOLUME')),
                'Only the original verified snapshot may omit phase/volume selectors')
        volume = legacy_volumes['data']
    require(volume == prepared['volumes']['data'] and any(
        mount.get('Name') == volume and mount.get('Destination') == '/app/backend/data'
        for mount in inspection['Mounts']), 'Candidate data volume differs from the prepared snapshot')
    containers = docker_read(['container', 'ls', '-a', '--format', '{{json .}}', '--no-trunc'])
    for line in containers.splitlines():
        item = json.loads(line)
        require('google-gateway-0122' not in item['Names']
                and 'com.docker.compose.service=google-gateway-0122' not in item['Labels'],
                'A Google gateway container already exists; do not overwrite an active or stopped trial')
    return inspection['Id'], image


def project(source, models, master_key):
    expected = {'ENABLE_OPENAI_API', 'OPENAI_API_BASE_URLS', 'OPENAI_API_KEYS', 'OPENAI_API_CONFIGS'}
    require(isinstance(source, dict) and set(source) == expected and source['ENABLE_OPENAI_API'] is True,
            'Unexpected native OpenAI configuration contract')
    urls, keys, configs = (source[key] for key in
                          ('OPENAI_API_BASE_URLS', 'OPENAI_API_KEYS', 'OPENAI_API_CONFIGS'))
    require(isinstance(urls, list) and isinstance(keys, list) and len(urls) == len(keys)
            and len(urls) > GOOGLE_INDEX and isinstance(configs, dict), 'Invalid native connection arrays')
    require(set(configs).issubset(map(str, range(len(urls)))),
            'Native connection configs must use normalized index keys before projection')
    require(sum(
        isinstance(url, str) and 'generativelanguage.googleapis.com' in url for url in urls) == 1,
        'Expected one existing direct Google CC connection')
    require(isinstance(models, dict) and isinstance(models.get('data'), list)
            and all(isinstance(item, dict) for item in models['data']), 'Unexpected native model catalog')
    responses = configs.get('0')
    require(isinstance(responses, dict) and responses.get('api_type') == 'responses'
            and any(item.get('id') == 'gpt-6.1-sol' and item.get('urlIdx') == 0 for item in models['data'])
            and not any(item.get('id') == 'gpt-6.1-sol' and item.get('urlIdx') != 0 for item in models['data']),
            'Complete the native gpt-6.1-sol move to the existing Responses connection first')
    pending = copy.deepcopy(source)
    catalogs, upstream_keys = {}, {}
    for index, expected_url, env_key, pattern in CC_CONNECTIONS:
        label = 'CC connection ' + str(index)
        require(isinstance(urls[index], str) and urls[index].rstrip('/') == expected_url,
                label + ' must use its existing direct provider URL')
        connection = configs.get(str(index))
        require(isinstance(connection, dict) and connection.get('enable', True) is True,
                label + ' must be enabled in the native configuration')
        providers = (None, '', 'openai', 'anthropic') if index == 2 else (None, '', 'openai')
        require(connection.get('api_type') in (None, '') and not connection.get('azure')
                and connection.get('provider') in providers
                and connection.get('auth_type') in (None, '', 'bearer')
                and not connection.get('prefix_id'), label + ' must retain unprefixed CC semantics')
        require(isinstance(keys[index], str) and keys[index].strip(), label + ' has no native provider key')
        ids = [item.get('id') for item in models['data'] if item.get('urlIdx') == index]
        require(ids and all(isinstance(item, str) and re.fullmatch(pattern, item) for item in ids)
                and len(ids) == len(set(ids)), label + ' has invalid or duplicate native model IDs')
        require(not any(item.get('id') in ids and item.get('urlIdx') != index for item in models['data']),
                label + ' model ID has another connection owner')
        configured = connection.get('model_ids', [])
        require(isinstance(configured, list) and (not configured or set(configured) == set(ids)),
                label + ' configured catalog differs from the native source catalog')
        catalogs[index] = ids
        upstream_keys[env_key] = keys[index]
        pending['OPENAI_API_BASE_URLS'][index] = GATEWAY_URL
        pending['OPENAI_API_KEYS'][index] = master_key
        pending['OPENAI_API_CONFIGS'][str(index)]['model_ids'] = ids
    require('gpt-5.6-luna' in catalogs[1], 'The current OpenAI CC model is missing from its native catalog')
    require(REQUIRED_GOOGLE_MODELS.issubset(catalogs[GOOGLE_INDEX]),
            'Current Google OfficeCLI models are missing from the native catalog')
    restored = copy.deepcopy(pending)
    for index in catalogs:
        restored['OPENAI_API_BASE_URLS'][index] = urls[index]
        restored['OPENAI_API_KEYS'][index] = keys[index]
        restored['OPENAI_API_CONFIGS'][str(index)] = copy.deepcopy(configs[str(index)])
    require(restored == source, 'Projection changed another native connection')
    return pending, catalogs, upstream_keys


def project_managed(source, models, inference_bearer, gateway_config):
    """Project native /openai/models, not the mixed /api/models workspace catalog."""
    expected = {'ENABLE_OPENAI_API', 'OPENAI_API_BASE_URLS', 'OPENAI_API_KEYS', 'OPENAI_API_CONFIGS'}
    require(isinstance(source, dict) and set(source) == expected and source['ENABLE_OPENAI_API'] is True,
            'Unexpected native OpenAI configuration contract')
    urls, keys, configs = (source[key] for key in
                          ('OPENAI_API_BASE_URLS', 'OPENAI_API_KEYS', 'OPENAI_API_CONFIGS'))
    require(isinstance(urls, list) and bool(urls) and isinstance(keys, list) and len(urls) == len(keys)
            and isinstance(configs, dict) and set(configs).issubset(map(str, range(len(urls)))),
            'Invalid native connection arrays or non-normalized config keys')
    require(isinstance(inference_bearer, str) and inference_bearer.startswith('sk-') and len(inference_bearer) > 3
            and not any(char.isspace() or ord(char) < 32 for char in inference_bearer),
            'Explicit shared inference bearer required')
    require(all(key != inference_bearer or url.rstrip('/') == GATEWAY_URL
                for url, key in zip(urls, keys) if isinstance(url, str)),
            'Shared inference bearer must not reuse a direct provider credential')
    require(isinstance(gateway_config, dict) and isinstance(gateway_config.get('model_list'), list)
            and bool(gateway_config['model_list']), 'Approved native LiteLLM model_list required')
    for settings_name in ('litellm_settings', 'router_settings'):
        settings = gateway_config.get(settings_name, {})
        require(isinstance(settings, dict), 'Invalid native LiteLLM settings')
        require(not any(settings.get(name) for name in
                        ('fallbacks', 'default_fallbacks', 'context_window_fallbacks', 'content_policy_fallbacks')),
                'Managed preparation forbids provider fallbacks')
    require(gateway_config.get('litellm_settings', {}).get('block_requests_for_models_without_pricing') is True,
            'Approved native fail-closed pricing flag required')
    general = gateway_config.get('general_settings', {})
    required_profile = {'master_key': 'os.environ/LITELLM_MASTER_KEY', 'database_url': 'os.environ/DATABASE_URL',
                        'custom_auth': 'litellm_auth.gateway_auth', 'custom_auth_run_common_checks': True,
                        'fail_closed_budget_enforcement': True, 'disable_spend_logs': False,
                        'missing_session_id': 'omit'}
    require(isinstance(general, dict) and all(type(general.get(key)) is type(value)
            and general[key] == value for key, value in required_profile.items())
            and general.get('disable_budget_reservation') is not True,
            'Approved native budget authentication/database/enforcement/SpendLogs profile required')
    settings = gateway_config['litellm_settings']
    callbacks = settings.get('callbacks', [])
    require(isinstance(callbacks, list) and all(isinstance(value, str) for value in callbacks)
            and {'budget_errors.handler', 'pricing_snapshot.handler'}.issubset(callbacks)
            and {'budget_runtime.responses_handler', 'budget_runtime.cc_stream_handler'}.issubset(callbacks)
            and 'budget_runtime.handler' not in callbacks and len(callbacks) == len(set(callbacks))
            and settings.get('enable_post_custom_auth_checks') is not True,
            'Approved native budget callback/common-check profile required')
    approved = {}
    for row in gateway_config['model_list']:
        require(isinstance(row, dict), 'Invalid approved native model row')
        name, info, params = row.get('model_name'), row.get('model_info'), row.get('litellm_params')
        require(isinstance(name, str) and bool(name) and name == name.strip() and '*' not in name
                and name not in approved and isinstance(params, dict)
                and isinstance(params.get('model'), str) and bool(params['model'])
                and '*' not in params['model'], 'Approved native model aliases must be explicit and unique')
        approved[name] = (info, params)
    require(isinstance(models, dict) and isinstance(models.get('data'), list)
            and all(isinstance(item, dict) for item in models['data']), 'Unexpected native model catalog')
    catalogs, owners, wire_owners = {}, set(), set()
    for item in models['data']:
        index, name = item.get('urlIdx'), item.get('id')
        require(type(index) is int and 0 <= index < len(urls) and isinstance(name, str)
                and bool(name) and name == name.strip() and name not in owners
                and not item.get('pipe') and not item.get('pipeline'),
                'Native catalog requires unambiguous connection-owned model IDs')
        owners.add(name)
        catalogs.setdefault(index, []).append(name)
    pending = copy.deepcopy(source)
    for index in range(len(urls)):
        label = 'Managed connection ' + str(index)
        config = configs.get(str(index), {})
        require(isinstance(config, dict) and type(config.get('enable', True)) is bool,
                label + ' has invalid enable state')
        if not config.get('enable', True):
            require(not catalogs.get(index), label + ' is disabled but has catalog models')
            pending['OPENAI_API_KEYS'][index] = ''
            pending['OPENAI_API_BASE_URLS'][index] = ''
            # Keep the protected source for rollback; inactive headers may still
            # contain provider credentials and must not remain in WebUI.
            pending['OPENAI_API_CONFIGS'][str(index)] = {'enable': False}
            continue
        require(catalogs.get(index), label + ' requires explicit classification and catalog models')
        require(config.get('api_type') in (None, '', 'chat_completions', 'responses')
                and config.get('auth_type') in (None, 'bearer')
                and config.get('provider') in (None, '', 'openai')
                and not config.get('azure') and not config.get('forward_cookies'),
                label + ' has unsupported API/auth/provider/cookie configuration')
        prefix = config.get('prefix_id')
        require(prefix is None or isinstance(prefix, str), label + ' has an invalid model prefix')
        configured = config.get('model_ids', [])
        # Native model_ids are wire IDs; native catalog IDs include prefix_id.
        wires = [name[len(prefix) + 1:] if prefix and name.startswith(prefix + '.') else name
                 for name in catalogs[index]]
        require(isinstance(configured, list) and len(configured) == len(set(configured))
                and (not configured or set(configured) == set(wires)), label + ' configured catalog differs')
        mode = 'responses' if config.get('api_type') == 'responses' else 'chat'
        for wire in wires:
            require(wire and wire not in wire_owners and wire in approved,
                    label + ' has duplicate, unpriced or protocol-incompatible wire models')
            info, params = approved[wire]
            require(isinstance(info, dict) and info.get('mode') == mode,
                    label + ' has duplicate, unpriced or protocol-incompatible wire models')
            require(all(type(info.get(field)) in (int, float)
                        and math.isfinite(info[field]) and info[field] >= 0
                        for field in ('input_cost_per_token', 'output_cost_per_token')),
                    label + ' requires approved native input/output token pricing')
            if mode == 'responses':
                require(info.get('supports_native_streaming') is False
                        and params['model'].startswith('openai/')
                        and params.get('custom_llm_provider') in (None, 'openai'),
                        label + ' requires the qualified buffered OpenAI Responses profile')
            wire_owners.add(wire)
        headers = config.get('headers', {})
        require(isinstance(headers, dict) and all(isinstance(key, str) and isinstance(value, str)
                and not any(char in key + value for char in '\r\n\0') for key, value in headers.items()),
                label + ' has invalid native metadata headers')
        lowered = [key.lower() for key in headers]
        require(len(set(lowered)) == len(lowered) and not any(
            key in ('host', 'cookie') or any(part in key.replace('_', '-') for part in ('authorization', 'api-key', 'token', 'secret'))
            for key in lowered), label + ' headers may not override gateway credentials')
        projected = copy.deepcopy(config)
        projected['headers'] = dict(headers)
        for name, template in (('X-OpenWebUI-User-Id', '{{USER_ID}}'), ('X-OpenWebUI-Task', '{{TASK}}')):
            present = next((key for key in headers if key.lower() == name.lower()), name)
            require(present not in headers or headers[present] == template,
                    label + ' has conflicting native identity headers')
            projected['headers'][present] = template
        projected['model_ids'] = wires
        pending['OPENAI_API_CONFIGS'][str(index)] = projected
        pending['OPENAI_API_BASE_URLS'][index] = GATEWAY_URL
        pending['OPENAI_API_KEYS'][index] = inference_bearer
    return pending, catalogs


def main(root, *, managed_config=None, managed_env=None):
    root = phase_root(root)
    compose_path = root / 'compose.env'
    original_compose, compose = read_env(compose_path)
    require(not any(key.startswith('RELEASE_GOOGLE_') for key in compose), 'Gateway selectors already exist')
    protected(root / 'webui.env')
    session_path = root / 'admin-native-session.private.json'
    protected(session_path)
    outputs = {
        'config': root / 'google-gateway/config.yaml',
        'env': root / 'private/google-gateway.env',
        'source': root / 'private/google-openai-source.private.json',
        'pending': root / 'private/google-openai-pending.private.json',
        'receipt': root / 'private/google-gateway-prepared.private.json',
    }
    require(not (root / 'google-gateway').exists() and not (root / 'google-gateway').is_symlink()
            and all(not path.exists() and not path.is_symlink()
            for path in outputs.values()), 'Gateway inputs already exist; do not overwrite staging data')
    container_id, image = candidate_identity(root, compose)
    session = json.loads(session_path.read_text(encoding='utf-8'))
    require(session.get('role') == 'admin' and isinstance(session.get('token'), str)
            and session['token'], 'Expected the existing native admin sign-in response')
    require(bool(managed_config) == bool(managed_env), 'Managed config and env must be provided together')
    source = native_get('/openai/config', session['token'])
    models = native_get('/openai/models' if managed_config else '/api/models', session['token'])
    managed_inputs = {}
    if managed_config:
        for path in (managed_config, managed_env):
            require(path.is_absolute() and path.is_relative_to(root / 'private')
                    and path.resolve(strict=True) == path, 'Managed inputs must be inside the protected phase private directory')
            protected(path)
            managed_inputs[path] = path.read_bytes()
        try:
            gateway_config = json.loads(managed_inputs[managed_config].decode('utf-8'))
        except (json.JSONDecodeError, UnicodeError):
            raise RuntimeError('Managed config must be UTF-8 JSON; explicitly export native YAML as JSON first') from None
        _, gateway_env = read_env(managed_env)
        inference_bearer = gateway_env.get('OWUI_BUDGET_GATEWAY_SECRET')
        master_key = gateway_env.get('LITELLM_MASTER_KEY')
        operator_key = gateway_env.get('OWUI_BUDGET_OPERATOR_KEY', '')
        require(isinstance(master_key, str) and bool(master_key) and master_key != inference_bearer
                and operator_key.startswith('sk-') and len(operator_key) > 3
                and not any(char.isspace() for char in operator_key)
                and operator_key not in (master_key, inference_bearer)
                and bool(gateway_env.get('DATABASE_URL'))
                and inference_bearer not in (value for key, value in gateway_env.items()
                                           if key != 'OWUI_BUDGET_GATEWAY_SECRET'),
                'Separate master/operator/provider and shared inference credentials plus native database required')
        pending, catalogs = project_managed(source, models, inference_bearer, gateway_config)
        config_bytes = managed_inputs[managed_config]
    else:
        master_key = 'sk-' + secrets.token_urlsafe(48)
        pending, catalogs, upstream_keys = project(source, models, master_key)
        _, webui_env = read_env(root / 'webui.env')
        gateway_env = {key: value for key, value in webui_env.items() if key in PROXY_KEYS}
        gateway_env.update(upstream_keys, LITELLM_MASTER_KEY=master_key)
        config_bytes = CONFIG.encode()
    require(all(not any(char in value for char in '\r\n\0') for value in gateway_env.values()),
            'Unexpected multiline gateway environment')
    # Re-read the native owner before creating files; fail if an operator changed it.
    require(native_get('/openai/config', session['token']) == source, 'Native config changed during preparation')
    require(candidate_identity(root, compose) == (container_id, image), 'Candidate identity changed during preparation')
    require(compose_path.read_bytes() == original_compose, 'Compose selectors changed during preparation')
    require(all(path.read_bytes() == raw for path, raw in managed_inputs.items()),
            'Approved managed inputs changed during preparation')
    if not (root / 'private').exists():
        (root / 'private').mkdir(mode=0o700)
    protected(root / 'private', directory=True)
    (root / 'google-gateway').mkdir(mode=0o700)
    write_new(outputs['config'], config_bytes, 0o600 if managed_config else 0o644)
    write_new(outputs['env'], ''.join(key + '=' + value + '\n'
              for key, value in sorted(gateway_env.items())).encode())
    write_new(outputs['source'], encoded(source))
    write_new(outputs['pending'], encoded(pending))
    selectors = ('RELEASE_GOOGLE_CONFIG_FILE=' + str(outputs['config']) + '\n'
                 'RELEASE_GOOGLE_ENV_FILE=' + str(outputs['env']) + '\n').encode()
    fd = os.open(compose_path, os.O_RDWR | os.O_NOFOLLOW)
    with os.fdopen(fd, 'r+b') as stream:
        metadata = os.fstat(stream.fileno())
        require(stat.S_IMODE(metadata.st_mode) == 0o600 and metadata.st_uid == os.geteuid(),
                'Compose selector permissions or owner changed')
        require(stream.read() == original_compose, 'Compose selectors changed before append')
        if original_compose and not original_compose.endswith(b'\n'):
            stream.write(b'\n')
        stream.write(selectors)
    receipt = {'phase_root': str(root), 'candidate_id': container_id, 'candidate_image': image,
               'connection_indices': sorted(catalogs),
               'catalog_counts': {str(index): len(ids) for index, ids in catalogs.items()},
               'native_source_sha256': digest(encoded(source)), 'native_catalog_sha256': digest(encoded(models)),
               'proxy_env_names': sorted(set(gateway_env) & PROXY_KEYS),
               'files_sha256': {name: digest(path.read_bytes()) for name, path in outputs.items()
                                if name != 'receipt'},
               'native_config_applied': False, 'containers_started': False, 'model_inference_requested': False}
    write_new(outputs['receipt'], encoded(receipt))
    print(json.dumps({'phase_root': str(root), 'catalog_counts': receipt['catalog_counts'],
                      'native_config_applied': False, 'containers_started': False, 'model_inference_requested': False}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True, help='Existing protected phase under the task base')
    parser.add_argument('--managed-config', type=Path, help='Protected approved native LiteLLM JSON config')
    parser.add_argument('--managed-env', type=Path, help='Protected native gateway env with separate inference/master keys')
    args = parser.parse_args()
    try:
        main(args.root, managed_config=args.managed_config, managed_env=args.managed_env)
    except (RuntimeError, OSError, ValueError, KeyError, TypeError, IndexError) as error:
        raise SystemExit(str(error)) from None
