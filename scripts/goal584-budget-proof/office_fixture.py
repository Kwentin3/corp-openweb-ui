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


class OfficeFixture(PricingFixture):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.command += ['-f', 'compose/goal584.office-proof.yml']

    def _docker_json(self, arguments):
        try:
            result = subprocess.run(['docker', *arguments], cwd=ROOT, capture_output=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            raise AssertionError('Office Docker topology unavailable') from None
        require(result.returncode == 0 and len(result.stdout) <= MAX_BYTES, 'Office Docker topology unavailable')
        try:
            value = json.loads(result.stdout)
        except (ValueError, UnicodeError):
            raise AssertionError('Office Docker topology JSON differs') from None
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
        template = '{"id":{{json .Id}},"labels":{{json .Config.Labels}},"running":{{json .State.Running}},"health":{{if .State.Health}}{{json .State.Health.Status}}{{else}}null{{end}},"networks":{{json .NetworkSettings.Networks}},"ports":{{json .NetworkSettings.Ports}},"mounts":{{json .Mounts}},"readonly":{{json .HostConfig.ReadonlyRootfs}},"init":{{json .HostConfig.Init}},"tmpfs":{{json .HostConfig.Tmpfs}},"capdrop":{{json .HostConfig.CapDrop}},"privileged":{{json .HostConfig.Privileged}},"security":{{json .HostConfig.SecurityOpt}},"networkmode":{{json .HostConfig.NetworkMode}}}'
        rows = [self._docker_json(['inspect', '--format', template, value]) for value in ids]
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
