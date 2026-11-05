"""Host-only strict-six topology, not image/profile or native Office acceptance.

Import this fixture only from a host coordinator. Pure worker validators must
not import it: the inherited browser host owns the Playwright dependency.
"""
import ipaddress
import hashlib
import json
import os
from pathlib import PurePosixPath
import re
import subprocess
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, build_opener

from prove_pricing_browser import CONFIG_LIMIT, MAX_BYTES, ROOT, PricingFixture, no_credentials, require
from build_office_profile import WEBUI_FILES, OFFICE_FILES
from prove_office_compatibility import MODEL, VALVES, WEBUI_MODULES, built_images, digest, verify_profile


OFFICE_MODELS = ''.join(f'''  - model_name: {name}
    litellm_params:
      model: openai/{wire}
      api_base: http://provider:8000/v1
      api_key: synthetic-provider-only-not-a-credential
    model_info:
      id: {deployment}
      mode: responses
      supports_reasoning: true
      supports_function_calling: true
      max_input_tokens: 10000
      max_output_tokens: 1024
      max_tokens: 11024
      input_cost_per_token: 0.01
      output_cost_per_token: 0.02
      # Declared synthetic terms; no external source fetch or activation.
      owui_pricing:
        schema: 1
        deployment_id: {deployment}
        currency: USD
        source_ref: goal584-office-synthetic-v1
        source_url: https://pricing.example.invalid/goal584/office
        source_checked_at_utc: "2026-11-05T00:00:00Z"
        declared_effective_from_utc: "2026-11-05T00:00:00Z"
        declared_effective_until_utc: null
        activation_ref: goal584-office-stand-v1
        qualified_usage: flat_input_output
''' for name, wire, deployment in (
    (MODEL, 'goal584-fake-office', 'goal584-office-primary'),
    ('gpt-6-luna', 'goal584-fake-office-service', 'goal584-office-service')))


def prepare_native_tokenizers(directory):
    """Prefill the native cache before the stand's internal network is started."""
    require(directory.is_absolute() and not directory.exists() and not directory.is_symlink(),
            'Office tokenizer cache must be fresh')
    directory.mkdir(mode=0o700)
    opener = build_opener(ProxyHandler({})); receipt = []
    for name, expected in (
        ('cl100k_base', '223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7'),
        ('o200k_base', '446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d')):
        url = 'https://openaipublic.blob.core.windows.net/encodings/' + name + '.tiktoken'
        with opener.open(url, timeout=30) as response: raw = response.read(5 * 1024 * 1024 + 1)
        require(0 < len(raw) <= 5 * 1024 * 1024 and hashlib.sha256(raw).hexdigest() == expected,
                'Office native tokenizer asset hash differs')
        # This filename is tiktoken.load.read_file_cached's native URL key.
        target = directory / hashlib.sha1(url.encode(), usedforsecurity=False).hexdigest()
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as handle: handle.write(raw)
        require(target.read_bytes() == raw, 'Office native tokenizer cache readback differs')
        receipt.append({'url': url, 'sha256': expected, 'bytes': len(raw)})
    return {'schema': 1, 'assets': receipt, 'model_calls': 0}


def prepare_office_config(original):
    """Return private host config bytes before boot; no write or stand operation.

    Preserve the complete caller-owned A/B config; only add the two fixed native
    aliases. Provider support and actual /model/info still require worker proof.
    """
    import yaml
    require(isinstance(original, bytes) and 0 < len(original) <= CONFIG_LIMIT,
            'Office YAML input exceeded bound')

    class UniqueKeys(yaml.SafeLoader):
        def construct_mapping(self, node, deep=False):
            keys = [self.construct_object(k, deep=deep) for k, _ in node.value
                    if k.tag != 'tag:yaml.org,2002:merge']
            require(len(keys) == len(set(keys)), 'Office YAML has duplicate mapping keys')
            return super().construct_mapping(node, deep=deep)

    try:
        text = original.decode('utf-8')
        before = yaml.load(text, Loader=UniqueKeys)
        require(isinstance(before, dict) and isinstance(before.get('model_list'), list)
                and len(before['model_list']) == 2 and isinstance(before.get('general_settings'), dict),
                'Office requires the original A/B configuration')
        for row, suffix in zip(before['model_list'], ('a', 'b')):
            require(isinstance(row, dict) and row.get('model_name') == 'goal584-' + suffix
                    and isinstance(row.get('litellm_params'), dict) and isinstance(row.get('model_info'), dict),
                    'Office prior model identity differs')
            params = row['litellm_params']
            require(params.get('model') == 'openai/goal584-fake-' + suffix
                    and params.get('api_base') == 'http://provider:8000/v1'
                    and params.get('api_key') == 'synthetic-provider-only-not-a-credential'
                    and row['model_info'].get('id') == 'goal584-deployment-' + suffix,
                    'Office prior model must use the original synthetic provider')
        markers = list(re.finditer(r'(?m)^general_settings:[ \t]*(?:#[^\r\n]*)?\r?$', text))
        require(len(markers) == 1, 'Office requires one unambiguous general_settings marker')
        tree = yaml.compose(text)
        models = next(value for key, value in tree.value if key.value == 'model_list')
        # Usually this is the general_settings marker itself. Earlier unknown
        # root settings stay in the suffix, outside the appended model list.
        at = models.end_mark.index
        require(at <= markers[0].start() and (at == 0 or text[at - 1] == '\n'),
                'Office model list does not precede general_settings')
        block = OFFICE_MODELS.replace('\n', '\r\n') if '\r\n' in text else OFFICE_MODELS
        result = (text[:at] + block + text[at:]).encode('utf-8')
        after = yaml.load(result, Loader=UniqueKeys)
        require(len(result) <= CONFIG_LIMIT and set(after) == set(before)
                and after['model_list'] == before['model_list'] + yaml.safe_load(block)
                and all(after[key] == value for key, value in before.items() if key != 'model_list'),
                'Office changed existing native configuration')
        return result
    except (UnicodeError, yaml.YAMLError, TypeError, ValueError, RecursionError):
        raise AssertionError('Office YAML is malformed or ambiguous') from None


def topology_row(raw):
    """Project native inspect JSON in memory; never export Config.Env."""
    config, state, host, network = (raw[k] for k in ('Config', 'State', 'HostConfig', 'NetworkSettings'))
    health = state.get('Health')
    require(health is None or isinstance(health, dict), 'Office Docker health shape differs')
    return {'id': raw['Id'], 'labels': config['Labels'], 'running': state['Running'],
        'health': health.get('Status') if health is not None else None,
        'networks': network['Networks'], 'ports': network['Ports'], 'mounts': raw['Mounts'],
        'readonly': host['ReadonlyRootfs'], 'init': host.get('Init'), 'tmpfs': host.get('Tmpfs'),
        'capdrop': host.get('CapDrop'), 'privileged': host['Privileged'],
        'security': host.get('SecurityOpt'), 'networkmode': host['NetworkMode']}


class OfficeFixture(PricingFixture):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.command += ['-f', 'compose/goal584.office-proof.yml']

    def _docker_json(self, arguments, *, project=None):
        try:
            result = subprocess.run(['docker', *arguments], cwd=ROOT, capture_output=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            raise AssertionError('Office Docker topology unavailable') from None
        operation = arguments[0] if arguments[0] in ('inspect', 'exec', 'image', 'network') else 'operation'
        require(result.returncode == 0 and len(result.stdout) <= MAX_BYTES,
                'Office Docker topology unavailable (' + operation + '; exit=' + str(result.returncode)
                + '; stdout_bytes=' + str(len(result.stdout)) + ')')
        try:
            value = json.loads(result.stdout)
        except (ValueError, UnicodeError):
            raise AssertionError('Office Docker topology JSON differs') from None
        if project is not None:
            try:
                value = project(value)
            except (KeyError, TypeError, AttributeError):
                raise AssertionError('Office Docker native projection differs') from None
        no_credentials(value, self.secrets)
        return value

    def bind(self, base_url):
        self._office_binding = None
        services = {'proxy', 'postgres', 'provider', 'redis', 'webui', 'office'}
        config = self._bind_services(base_url, services)
        project = config.get('name'); network = config['networks']['proof'].get('name')
        require(isinstance(project, str) and project and isinstance(network, str) and network
                and set(config['networks']) == {'proof'} and not config['networks']['proof'].get('external')
                and all(set(s.get('networks', {})) == {'proof'} and not s.get('network_mode')
                        for s in config['services'].values()), 'Office requires only the internal proof network')
        office = config['services']['office']
        require(office.get('read_only') is True and office.get('init') is True and not office.get('volumes')
                and office.get('tmpfs') == ['/tmp:rw,noexec,nosuid,size=128m'] and office.get('cap_drop') == ['ALL']
                and office.get('security_opt') == ['no-new-privileges:true']
                and office.get('environment', {}).get('OPENWEBUI_BASE_URL') == 'http://webui:8080',
                'Office Compose security/session owner differs')
        result = subprocess.run(self.command + ['ps', '--all', '--quiet'], cwd=ROOT, capture_output=True, timeout=15)
        ids = result.stdout.decode('ascii').split()
        require(result.returncode == 0 and len(ids) == len(set(ids)) == 6
                and all(re.fullmatch('[a-f0-9]{64}', value) for value in ids), 'Office requires six unique containers')
        rows = [self._docker_json(['inspect', '--format', '{{json .}}', value], project=topology_row) for value in ids]
        require({r['id'] for r in rows} == set(ids) and all(r['running'] is True
                and r['labels'].get('com.docker.compose.project') == project for r in rows)
                and {r['labels'].get('com.docker.compose.service') for r in rows} == services,
                'Office container service/project/running identity differs')
        actual_network = self._docker_json(['network', 'inspect', network])
        require(len(actual_network) == 1 and actual_network[0]['Name'] == network and actual_network[0]['Internal'] is True
                and actual_network[0]['Labels'].get('com.docker.compose.project') == project
                and actual_network[0]['Labels'].get('com.docker.compose.network') == 'proof',
                'Office actual proof network differs')
        require(all(set(r['networks']) == {network} and r['networks'][network]['NetworkID'] == actual_network[0]['Id']
                and r['networkmode'] == network and all(v is None or v == [] for v in (r['ports'] or {}).values())
                for r in rows), 'Office actual network/ports differ')
        by_service = {r['labels']['com.docker.compose.service']: r for r in rows}
        url = urlsplit(base_url)
        require(url.scheme == 'http' and url.port == 8080 and url.path in ('', '/') and not url.username and not url.password
                and not url.query and not url.fragment and isinstance(ipaddress.ip_address(url.hostname), ipaddress.IPv4Address)
                and ipaddress.ip_address(url.hostname).is_private
                and by_service['webui']['networks'][network]['IPAddress'] == url.hostname, 'Office native WebUI target differs')
        row = by_service['office']
        require(row['readonly'] is True and row['init'] is True and row['privileged'] is False and row['health'] == 'healthy'
                and row['tmpfs'] == {'/tmp': 'rw,noexec,nosuid,size=128m'} and row['capdrop'] == ['ALL']
                and row['security'] in (['no-new-privileges'], ['no-new-privileges:true'])
                and all(m['Type'] == 'tmpfs' and m['Destination'] == '/tmp' for m in row['mounts']),
                'Office actual security/storage differs')
        environment = self._docker_json(['inspect', '--format', '{{json .Config.Env}}', row['id']])
        callback = [value for value in environment if value.startswith('OPENWEBUI_BASE_URL=')]
        require(callback == ['OPENWEBUI_BASE_URL=http://webui:8080'], 'Office actual native WebUI callback differs')
        self._office_binding = {'project': project, 'services': {name: {'id': by_service[name]['id'],
            'image': config['services'][name].get('image')} for name in ('webui', 'office')}}

    def running_readback(self, base_url, build_receipt, expected_revision):
        """Collect actual same-job artifacts; not persisted profile/Office acceptance.

        Caller supplies trusted clean GITHUB_SHA and successful builder output.
        Strict-six binding is repeated immediately before target selection.
        """
        require(isinstance(expected_revision, str) and re.fullmatch('[0-9a-f]{40}', expected_revision)
                and isinstance(build_receipt, dict) and build_receipt.get('source_commit') == expected_revision,
                'Office readback source revision differs')
        self.bind(base_url)
        binding = self._office_binding
        verifier = '/usr/local/lib/openwebui-media-upload/verify_frontend_artifact.py'
        try:
            trusted = subprocess.run(['git', '-c', 'gc.auto=0', 'show', expected_revision +
                ':deploy/openwebui-upgrade-0122/verify_frontend_artifact.py'], cwd=ROOT, capture_output=True,
                timeout=15, env=os.environ | {'GIT_NO_LAZY_FETCH': '1'})
        except (OSError, subprocess.SubprocessError):
            raise AssertionError('Office trusted frontend source unavailable') from None
        require(trusted.returncode == 0 and 0 < len(trusted.stdout) <= MAX_BYTES, 'Office trusted frontend source unavailable')
        verifier_sha = hashlib.sha256(trusted.stdout).hexdigest()
        images = build_receipt.get('images', {})
        require(isinstance(images, dict), 'Office declared build image differs')
        protected = {'webui': ('/app/backend/open_webui', '/app/build', '/usr/local/lib/openwebui-media-upload'),
            'office': ('/app/officecli_openapi_proof', '/usr/local/bin/officecli')}
        rows, platforms = {}, {}
        for name, target in binding['services'].items():
            item = images.get(name)
            require(isinstance(item, dict), 'Office declared build image differs')
            expected = item.get('id')
            require(isinstance(expected, str) and re.fullmatch('sha256:[0-9a-f]{64}', expected)
                    and target['image'] == expected, 'Office declared build image differs')
            template = '{"id":{{json .Id}},"image_ref":{{json .Config.Image}},"image_id":{{json .Image}},"mounts":{{json .Mounts}},"labels":{{json .Config.Labels}},"running":{{json .State.Running}}}'
            row = self._docker_json(['inspect', '--format', template, target['id']])
            require(row['id'] == target['id'] and row['running'] is True
                    and row['labels'].get('com.docker.compose.project') == binding['project']
                    and row['labels'].get('com.docker.compose.service') == name
                    and row['image_ref'] == row['image_id'] == expected, 'Office actual build image differs')
            require(isinstance(row['mounts'], list) and all(isinstance(m, dict) for m in row['mounts']), 'Office actual mounts differ')
            for mount in row['mounts']:
                raw = mount.get('Destination'); path = PurePosixPath(raw) if isinstance(raw, str) else None
                require(path is not None and path.is_absolute() and str(path) == raw and '..' not in path.parts
                        and all(path != PurePosixPath(p) and path not in PurePosixPath(p).parents
                            and PurePosixPath(p) not in path.parents for p in protected[name]), 'Office mount shadows checked artifact')
            platform = self._docker_json(['image', 'inspect', '--format',
                '{"id":{{json .Id}},"os":{{json .Os}},"architecture":{{json .Architecture}}}', expected])
            require(platform == {'id': expected, 'os': 'linux', 'architecture': 'amd64'}, 'Office build platform differs')
            rows[name], platforms[name] = row, platform
        # All target IDs/mounts/platforms have passed before any container exec.
        common = 'import hashlib,json,pathlib; sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest(); '
        webui = self._docker_json(['exec', rows['webui']['id'], 'python', '-B', '-c', common +
            'import os; r=pathlib.Path("/app/backend/open_webui"); p=pathlib.Path("/usr/local/lib/openwebui-media-upload"); '
            'print(json.dumps({"modules":{n:sha(r/n) for n in ' + repr(WEBUI_FILES) + '},'
            '"build_hash":os.environ["WEBUI_BUILD_HASH"],"version":json.loads(pathlib.Path("/app/build/_app/version.json").read_text())["version"],'
            '"responses_stateful_env":os.getenv("ENABLE_RESPONSES_API_STATEFUL"),'
            '"frontend_receipt":json.loads((p/"frontend-receipt.json").read_text()),"frontend_manifest_sha256":sha(p/"frontend-files.json"),'
            '"verifier_sha256":sha(p/"verify_frontend_artifact.py")}))'])
        require(webui.pop('verifier_sha256') == verifier_sha, 'Office running frontend verifier source differs')
        webui['frontend_result'] = self._docker_json(['exec', rows['webui']['id'], 'python', '-B', '-c',
            'import hashlib,pathlib; p=pathlib.Path(' + repr(verifier) + '); raw=p.read_bytes(); '
            'assert hashlib.sha256(raw).hexdigest()==' + repr(verifier_sha) + '; exec(compile(raw,str(p),"exec"))'])
        binary_sha = build_receipt['office']['binary_sha256']
        office = self._docker_json(['exec', rows['office']['id'], 'python', '-B', '-c', common +
            'import subprocess; r=pathlib.Path("/app/officecli_openapi_proof"); b=pathlib.Path("/usr/local/bin/officecli"); '
            'binary=sha(b); assert binary==' + repr(binary_sha) + '; print(json.dumps({"modules":{n:sha(r/n) for n in ' + repr(OFFICE_FILES) + '},'
            '"binary_sha256":binary,"version":subprocess.check_output([str(b),"--version"],text=True,timeout=10).strip()}))'])
        running = {'webui': webui, 'office': office}
        for name in running:
            running[name].update(image_ref=rows[name]['image_ref'], image_id=rows[name]['image_id'],
                os=platforms[name]['os'], architecture=platforms[name]['architecture'])
        built_images(build_receipt, expected_revision, running)
        return running

    def _office_private(self, name):
        path = self.private / name
        require(path.is_file() and not path.is_symlink() and path.resolve().parent == self.private.resolve()
                and 0 < path.stat().st_size <= MAX_BYTES, 'Office private handoff unavailable or outside bound')
        if os.name != 'nt':
            require(path.stat().st_mode & 0o077 == 0, 'Office private handoff permissions differ')
        raw = path.read_bytes()
        require(len(raw) <= MAX_BYTES, 'Office private handoff exceeded bound')
        value = json.loads(raw)
        require(isinstance(value, dict) and type(value.get('schema')) is int and value['schema'] == 1,
                'Office private handoff schema differs')
        return raw, value

    def native_context(self, base_url, build_receipt, expected_revision, reasoning_cases):
        """Execute native schema/Responses owners in the actual built WebUI.

        The host's strict artifact binding attests the producer; fields in the
        returned packet are observations, never independent origin evidence.
        """
        running = self.running_readback(base_url, build_receipt, expected_revision)
        _, handoff = self._office_private('office-state.private.json')
        require(handoff.get('office_service_setup', {}).get('stage') == 'readback_ready',
                'Office native context requires prepared service state')
        require(isinstance(reasoning_cases, list) and 0 < len(reasoning_cases) <= 4
                and all(isinstance(case, list) and all(isinstance(item, dict)
                    and item.get('type') == 'reasoning' for item in case) for case in reasoning_cases),
                'Office native reasoning observation differs')
        cases = {digest(case): case for case in reasoning_cases}
        modules = {name: running['webui']['modules'][name] for name in ('utils/tools.py', 'routers/openai.py')}
        schema = handoff['office_setup']['openapi']
        payload = json.dumps({'module_sha256': modules, 'openapi': schema,
            'reasoning_cases': list(cases.values())}, ensure_ascii=True, allow_nan=False)
        require(len(payload.encode('ascii')) <= 96 * 1024, 'Office native context argument exceeded bound')
        code = '''import contextlib,hashlib,io,json,pathlib,sys
p=json.loads(sys.argv[1]);r=pathlib.Path('/app/backend/open_webui')
def modules():
    return {n:hashlib.sha256((r/n).read_bytes()).hexdigest() for n in ('utils/tools.py','routers/openai.py')}
assert modules()==p['module_sha256']
with contextlib.redirect_stdout(io.StringIO()):
    from open_webui.utils.tools import convert_openapi_to_tool_payload,clean_openai_tool_schema
    from open_webui.routers.openai import convert_to_responses_payload
    specs=[clean_openai_tool_schema(s) for s in convert_openapi_to_tool_payload(p['openapi'])]
    cases=[{'input_reasoning':v,'native_input':convert_to_responses_payload(
        {'messages':[{'role':'assistant','output':v}]})['input']} for v in p['reasoning_cases']]
assert modules()==p['module_sha256']
body=hashlib.sha256(json.dumps(p['openapi'],sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
print(json.dumps({'schema':1,'module_sha256':modules(),'source_body_sha256':body,
    'native_specs':specs,'reasoning_cases':cases},allow_nan=False))
'''
        packet = self._docker_json(['exec', self._office_binding['services']['webui']['id'],
            'python', '-B', '-c', code, payload])
        require(isinstance(packet, dict) and type(packet.get('schema')) is int and packet['schema'] == 1
                and packet.get('module_sha256') == modules and packet.get('source_body_sha256') == digest(schema)
                and isinstance(packet.get('native_specs'), list) and len(packet['native_specs']) > 2
                and isinstance(packet.get('reasoning_cases'), list) and len(packet['reasoning_cases']) == len(cases)
                and all(isinstance(item, dict) and set(item) == {'input_reasoning', 'native_input'}
                    and isinstance(item['native_input'], list) for item in packet['reasoning_cases'])
                and {digest(item['input_reasoning']): item['input_reasoning'] for item in packet['reasoning_cases']} == cases,
                'Office native context producer readback differs')
        return packet

    def prepare(self, base_url, build_receipt, expected_revision):
        """Coordinate existing workers; return safe readiness, never Office acceptance."""
        running = self.running_readback(base_url, build_receipt, expected_revision)
        try:
            common, _ = self._office_private('webui-state.private.json')
            provider_code = ('import hashlib,json,urllib.request; '
                'r=urllib.request.urlopen("http://127.0.0.1:8000/__proof/requests",timeout=3).read(' + str(MAX_BYTES + 1) + '); '
                'assert len(r)<=' + str(MAX_BYTES) + '; d=json.loads(r); '
                'print(json.dumps({"count":len(d["requests"]),"sha256":hashlib.sha256(json.dumps(d,sort_keys=True,allow_nan=False).encode()).hexdigest()}))')
            before = self.command_json(['exec', '-T', 'provider', 'python', '-B', '-c', provider_code], 'office_provider_before')
            user = ['--user', f'{os.getuid()}:{os.getgid()}'] if hasattr(os, 'getuid') and hasattr(os, 'getgid') else []
            for phase, state in (('office-setup', 'webui-state.private.json'), ('office-service-setup', 'office-state.private.json')):
                command = ['exec', '-T'] + user + ['proxy', 'python', '-B', '/proof/provision_webui.py', '--phase', phase,
                    '--private-state', '/proof-private/' + state, '--receipt', '/proof-private/' + phase + '.safe.json']
                if phase == 'office-setup': command += ['--office-state', '/proof-private/office-state.private.json']
                receipt = self.command_json(command, phase, timeout=180)
                require(receipt.get('passed') is True and receipt.get('phase') == phase
                        and receipt.get('inference_issued') is False and receipt.get('native_office_accepted') is False,
                        'Office preparation worker did not complete')
                require(self._office_private(phase + '.safe.json')[1] == receipt, 'Office private worker receipt differs')
            raw, handoff = self._office_private('office-state.private.json')
            require(self._office_private('webui-state.private.json')[0] == common
                    and handoff['stage'] == 'setup_complete'
                    and handoff['office_service_setup']['stage'] == 'readback_ready', 'Office private preparation incomplete')
            setup = handoff['office_setup']; model = setup['models'][MODEL]
            catalogs = [row for row in setup['actor_catalog'] if row['id'] == MODEL]
            servers = [row for row in setup['tool_servers']['TOOL_SERVER_CONNECTIONS']
                if isinstance(row.get('info'), dict) and row['info'].get('id') == 'officecli']
            require(len(catalogs) == len(servers) == 1, 'Office raw profile identity is ambiguous')
            catalog, server = catalogs[0], servers[0]; index = catalog['urlIdx']
            config = setup['connections']['OPENAI_API_CONFIGS'][str(index)]
            current = handoff['office_service_readback']['current']; baseline = handoff['office_service_readback']['baseline']
            tasks = current['task_config']; params = tasks['TASK_MODEL_PARAMS']
            profile = {'webui_image': running['webui']['image_id'], 'office_image': running['office']['image_id'],
                'webui_modules': {key: running['webui']['modules'][key] for key in WEBUI_MODULES},
                'office_modules': running['office']['modules'], 'office_binary_sha256': running['office']['binary_sha256'],
                'office_valves': {key: setup['valves'][key] for key in VALVES}, 'model': model['id'],
                'active': model['is_active'], 'function_calling': model['params']['function_calling'],
                'connection_index': index, 'api_type': config['api_type'],
                'session_tool_server': {'id': server['info']['id'], 'enabled': server['config']['enable'],
                    'auth_type': server['auth_type'], 'access_grants': server['config']['access_grants'],
                    'custom_header_names': list(server['headers']), 'function_name_filter_list': server['config']['function_name_filter_list']},
                'reasoning_settings': {'context_compaction_enabled': setup['before']['chat_config']['ENABLE_CONTEXT_COMPACTION'],
                    'responses_stateful_env': running['webui']['responses_stateful_env'], 'task_model_default': tasks['TASK_MODEL'],
                    'task_model_external': tasks['TASK_MODEL_EXTERNAL'], 'task_model_reasoning_effort': params['reasoning_effort'],
                    'task_custom_reasoning_effort': params['custom_params']['reasoning']['effort']}}
            trusted = subprocess.run(['git', '-c', 'gc.auto=0', 'show', expected_revision + ':deploy/openwebui-budgets/service_pipe.py'],
                cwd=ROOT, capture_output=True, timeout=15, env=os.environ | {'GIT_NO_LAZY_FETCH': '1'})
            require(trusted.returncode == 0 and 0 < len(trusted.stdout) <= 128 * 1024, 'Office trusted service source unavailable')
            service_source = trusted.stdout.decode('utf8')
            verify_profile(profile, build_receipt=build_receipt, expected_revision=expected_revision, running=running,
                service_tasks=current, service_baseline=baseline, service_source=service_source)
            after = self.command_json(['exec', '-T', 'provider', 'python', '-B', '-c', provider_code], 'office_provider_after')
            require(before == after and type(before['count']) is int and before['count'] >= 0
                    and re.fullmatch('[0-9a-f]{64}', before['sha256']), 'Office preparation changed provider inference')
            result = {'schema': 1, 'status': 'prepared', 'native_office_accepted': False, 'inference_issued': False,
                'inference_calls': 0, 'profile_sha256': digest(profile), 'private_handoff_sha256': hashlib.sha256(raw).hexdigest(),
                'service_source_sha256': hashlib.sha256(trusted.stdout).hexdigest(), 'provider_sha256': before['sha256']}
            no_credentials(result, self.secrets)
            return result
        except (OSError, subprocess.SubprocessError, ValueError, UnicodeError, KeyError, TypeError, IndexError):
            raise AssertionError('Office preparation readback unavailable or malformed') from None
