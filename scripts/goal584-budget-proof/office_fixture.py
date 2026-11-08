"""Host-only strict-six (explicit Terminal: seven) topology, not native acceptance.

Import this fixture only from a host coordinator. Pure worker validators must
not import it: the inherited browser host owns the Playwright dependency.
"""
import copy
import ipaddress
import hashlib
import json
import os
from pathlib import PurePosixPath
import re
import stat
import subprocess
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, build_opener

from prove_pricing_browser import CONFIG_LIMIT, MAX_BYTES, ROOT, PricingFixture, no_credentials, require
from build_office_profile import WEBUI_FILES, OFFICE_FILES
from prove_office_compatibility import MODEL, VALVES, WEBUI_MODULES, built_images, digest, verify_profile


# Native resolver owners from the existing pinned WebUI image source closure.
# Internal checks leave the default packet and four-module saved packet intact.
NATIVE_RESOLUTION_SOURCES = {
    'utils/files.py': '4183622e47f152a0becd6cc2397e009750d14a30444c03ed50cd2c5f0d91711c',
    'utils/access_control/files.py': '87d406ca2b5e4846e0d8ddc9403d42ee3dda33cc6f52e6919ce0352ef3202f18',
    'models/users.py': '143e949b172252c45ae1cbe7d5f7bfc3460375fa49b203f4dbc36c6128d68bc3',
    'models/files.py': 'e0770c88528e5f95f64ee56fd11f1e662065ba269a7bf44688fa6d5ce224cb6d',
    'storage/provider.py': '59e43c4d64577e2e908583cf7cb8f7057d1f6be644d1781a0e754858b75f1da5'}

TERMINAL_SERVICE = 'open-terminal-office'
TERMINAL_IMAGE = 'ghcr.io/open-webui/open-terminal@sha256:81a5394b3cd4ae32adb600f2135f09ee124de37f26b0a780e2f5692472c0fc5c'
# Public OCI config of that index's linux/amd64 child, not a mutable tag.
TERMINAL_IMAGE_ID = 'sha256:6e8d19cc8196d501a875b1eea0e0b1bd43e2ee37b30d7952a219e699af21f3fb'
TERMINAL_OVERLAY = 'compose/goal584.office-terminal-proof.yml'


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
{streaming}      max_input_tokens: 10000
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
''' for name, wire, deployment, streaming in (
    (MODEL, 'goal584-fake-office', 'goal584-office-primary', '      supports_native_streaming: false\n'),
    ('gpt-6-luna', 'goal584-fake-office-service', 'goal584-office-service', '')))


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


def prepare_usage_guard_config(original):
    """Compose the existing Office and Usage fixtures before their first boot."""
    import yaml
    from prove_pricing_usage import configuration
    office = yaml.safe_load(prepare_office_config(original))
    base = yaml.safe_load(original)
    usage = configuration(base, 'v1')
    require(usage['model_list'][:2] == base['model_list']
            and all(usage[k] == v for k, v in base.items() if k != 'model_list'),
            'Usage fixture changed the original native configuration')
    usage_models = copy.deepcopy(usage['model_list'][2:])
    for model in usage_models:
        model['model_info']['supports_native_streaming'] = False
    office['model_list'].extend(usage_models)
    callbacks = office['litellm_settings']['callbacks']
    require(callbacks == base['litellm_settings']['callbacks']
            and 'usage_guard_fixture.handler' not in callbacks,
            'Usage guard callback registration differs')
    callbacks.append('usage_guard_fixture.handler')
    raw = yaml.safe_dump(office, sort_keys=False).encode('utf-8')
    require(len(raw) <= CONFIG_LIMIT, 'Usage guard YAML input exceeded bound')
    return raw


def prepare_delegated_office_config(original):
    """Explicit new scenario; never change the legacy Mini or service descriptor."""
    import yaml
    config = yaml.safe_load(prepare_usage_guard_config(original))
    for alias, wire, deployment, output, input_rate, output_rate in (
            ('gpt-6.1-sol', 'goal584-fake-delegated-parent', 'goal584-delegated-parent', 12000, .01, .02),
            ('gpt-6.1-terra', 'goal584-fake-delegated-worker', 'goal584-delegated-worker', 6000, .001, .002)):
        require(not any(row['model_name'] == alias for row in config['model_list']),
                'Delegated scenario alias already exists')
        config['model_list'].append({'model_name': alias, 'litellm_params': {
            'model': 'openai/' + wire, 'api_base': 'http://provider:8000/v1',
            'api_key': 'synthetic-provider-only-not-a-credential'}, 'model_info': {
                'id': deployment, 'mode': 'responses', 'supports_reasoning': True,
                'supports_function_calling': True, 'supports_native_streaming': False,
                'max_input_tokens': 32768, 'max_output_tokens': output, 'max_tokens': 32768 + output,
                'input_cost_per_token': input_rate, 'output_cost_per_token': output_rate,
                'owui_pricing': {'schema': 1, 'deployment_id': deployment, 'currency': 'USD',
                    'source_ref': 'goal584-delegated-synthetic-v1',
                    'source_url': 'https://pricing.example.invalid/goal584/delegated',
                    'source_checked_at_utc': '2026-11-06T00:00:00Z',
                    'declared_effective_from_utc': '2026-11-06T00:00:00Z',
                    'declared_effective_until_utc': None, 'activation_ref': 'goal584-delegated-stand-v1',
                    'qualified_usage': 'flat_input_output'}}})
    raw = yaml.safe_dump(config, sort_keys=False).encode('utf-8')
    require(len(raw) <= CONFIG_LIMIT, 'Delegated scenario YAML exceeded existing bound')
    return raw


def topology_row(raw, *, terminal=False):
    """Project native inspect JSON in memory; never export Config.Env."""
    config, state, host, network = (raw[k] for k in ('Config', 'State', 'HostConfig', 'NetworkSettings'))
    health = state.get('Health')
    require(health is None or isinstance(health, dict), 'Office Docker health shape differs')
    row = {'id': raw['Id'], 'labels': config['Labels'], 'running': state['Running'],
        'health': health.get('Status') if health is not None else None,
        'networks': network['Networks'], 'ports': network['Ports'], 'mounts': raw['Mounts'],
        'readonly': host['ReadonlyRootfs'], 'init': host.get('Init'), 'tmpfs': host.get('Tmpfs'),
        'capdrop': host.get('CapDrop'), 'privileged': host['Privileged'],
        'security': host.get('SecurityOpt'), 'networkmode': host['NetworkMode']}
    if terminal:
        environment = config['Env']
        require(isinstance(environment, list) and all(isinstance(value, str) for value in environment),
                'Terminal native environment shape differs')
        keys = [value.partition('=')[2] for value in environment if value.startswith('OPEN_TERMINAL_API_KEY=')]
        row['terminal'] = {'image_ref': config['Image'], 'image_id': raw['Image'], 'user': config['User'],
            'entrypoint': config['Entrypoint'], 'command': config['Cmd'], 'workdir': config['WorkingDir'],
            'key_sha256': [hashlib.sha256(value.encode()).hexdigest() for value in keys],
            'multi_user': [value for value in environment if value.startswith('OPEN_TERMINAL_MULTI_USER=')]
                == ['OPEN_TERMINAL_MULTI_USER=true'],
            'memory': host['Memory'], 'memory_swap': host['MemorySwap'], 'nano_cpus': host['NanoCpus'],
            'pids_limit': host['PidsLimit'], 'restart': host['RestartPolicy']['Name'],
            'capadd': host.get('CapAdd'), 'devices': host.get('Devices')}
    return row


class OfficeFixture(PricingFixture):
    def __init__(self, env_file, output, config, private, secrets, *, terminal=False):
        require(type(terminal) is bool, 'Terminal topology mode must be explicit boolean')
        super().__init__(env_file, output, config, private, secrets)
        self.terminal, self._terminal_env_file = terminal, env_file
        self.command += ['-f', 'compose/goal584.office-proof.yml']
        if terminal:
            self.command += ['-f', TERMINAL_OVERLAY]

    def _terminal_key(self):
        """One protected fixture assignment; not another general dotenv loader."""
        path = self._terminal_env_file
        require(path.is_file() and not path.is_symlink() and 0 < path.stat().st_size <= 65536,
                'Terminal private fixture env unavailable')
        if os.name != 'nt':
            require(stat.S_IMODE(path.stat().st_mode) & 0o077 == 0,
                    'Terminal private fixture env permissions differ')
        raw = path.read_bytes()
        require(len(raw) <= 65536, 'Terminal private fixture env exceeded bound')
        try:
            lines = [line for line in raw.decode('utf-8').splitlines() if line and not line.startswith('#')]
        except UnicodeError:
            raise AssertionError('Terminal private fixture env encoding differs') from None
        entries = [line.partition('=') for line in lines]
        names = [key for key, _, _ in entries]
        require(all(separator and re.fullmatch('[A-Za-z_][A-Za-z0-9_]*', key)
                    for key, separator, _ in entries) and len(names) == len(set(names)),
                'Terminal private fixture env is ambiguous')
        selected = [value for key, _, value in entries if key == 'STAGING_TERMINAL_API_KEY']
        require(len(selected) == 1 and re.fullmatch('[A-Za-z0-9_-]{32,128}', selected[0])
                and selected[0] in self.secrets
                and all(value != selected[0] for key, _, value in entries if key != 'STAGING_TERMINAL_API_KEY'),
                'Terminal requires its separate protected synthetic key')
        return selected[0]

    def _terminal_prerequisites(self):
        key = self._terminal_key()
        try:
            result = subprocess.run(['docker', 'compose', 'version', '--short'], cwd=ROOT,
                                    capture_output=True, timeout=15)
        except (OSError, subprocess.SubprocessError):
            raise AssertionError('Terminal requires Docker Compose >=2.24.4') from None
        version = re.fullmatch(rb'v?(\d+)\.(\d+)\.(\d+)(?:-desktop\.\d+)?\s*', result.stdout) \
            if result.returncode == 0 and len(result.stdout) <= 128 else None
        require(version is not None and tuple(int(value) for value in version.groups()) >= (2, 24, 4),
                'Terminal requires Docker Compose >=2.24.4')
        return key

    def _check_terminal(self, config, row, key, webui_id):
        """Check the inherited service in this binding; no daemon exec/API call."""
        service = config['services'][TERMINAL_SERVICE]
        volume = config.get('volumes', {}).get('terminal_home', {})
        volume_name = config['name'] + '_terminal_home'
        require(volume.get('name') == volume_name and not volume.get('external')
                and not volume.get('driver_opts') and volume.get('driver', 'local') == 'local',
                'Terminal requires its project-owned local home volume')
        mounts = service.get('volumes', [])
        require(len(mounts) == 1 and mounts[0].get('type') == 'volume'
                and mounts[0].get('source') == 'terminal_home' and mounts[0].get('target') == '/home'
                and not mounts[0].get('read_only') and not mounts[0].get('volume'),
                'Terminal declared home mount differs')
        require(service.get('image') == TERMINAL_IMAGE and 'build' not in service
                and service.get('restart') == 'no' and not service.get('privileged')
                and not service.get('read_only') and not service.get('cap_add') and not service.get('devices')
                and not service.get('cap_drop') and not service.get('security_opt') and not service.get('init')
                and not service.get('user') and not service.get('command') and not service.get('entrypoint')
                and service.get('mem_limit') == 768 * 1024**2 and service.get('memswap_limit') == 1024**3
                and service.get('cpus') == .5 and service.get('pids_limit') == 256
                and service.get('environment', {}).get('OPEN_TERMINAL_API_KEY') == key
                and service['environment'].get('OPEN_TERMINAL_MULTI_USER') == 'true',
                'Terminal inherited image/resources/security/key differ')
        bypass = 'localhost,127.0.0.1,webui,proxy,provider,postgres,redis,office,open-terminal-office,open-terminal-office:8000'
        require(all(config['services']['webui'].get('environment', {}).get(name) == bypass
                    for name in ('NO_PROXY', 'no_proxy')), 'Terminal native WebUI proxy bypass differs')
        actual_proxy = self._docker_json(['inspect', '--format', '{{json .Config.Env}}', webui_id],
            project=lambda values: [value for value in values if value.partition('=')[0] in ('NO_PROXY', 'no_proxy')])
        require(sorted(actual_proxy) == sorted([name + '=' + bypass for name in ('NO_PROXY', 'no_proxy')]),
                'Terminal actual native WebUI proxy bypass differs')
        actual = row.get('terminal', {})
        require(row['health'] == 'healthy' and row['privileged'] is False and row['readonly'] is False
                and not row['init'] and not row['capdrop'] and not row['security']
                and actual.get('image_ref') == TERMINAL_IMAGE and actual.get('image_id') == TERMINAL_IMAGE_ID
                and actual.get('user') == 'user' and actual.get('workdir') == '/home/user'
                and actual.get('entrypoint') == ['/usr/bin/tini', '--', '/app/entrypoint.sh']
                and actual.get('command') == ['run'] and not actual.get('capadd') and not actual.get('devices')
                and actual.get('memory') == 768 * 1024**2 and actual.get('memory_swap') == 1024**3
                and actual.get('nano_cpus') == 500000000 and actual.get('pids_limit') == 256
                and actual.get('restart') == 'no' and actual.get('multi_user') is True
                and actual.get('key_sha256') == [hashlib.sha256(key.encode()).hexdigest()],
                'Terminal actual image/resources/security/key differ')
        mounts = row['mounts']
        require(len(mounts) == 1 and mounts[0].get('Type') == 'volume' and mounts[0].get('Name') == volume_name
                and mounts[0].get('Destination') == '/home' and mounts[0].get('RW') is True,
                'Terminal actual home mount differs')
        volumes = self._docker_json(['volume', 'inspect', volume_name])
        require(isinstance(volumes, list) and len(volumes) == 1 and volumes[0].get('Name') == volume_name
                and volumes[0].get('Driver') == 'local' and not volumes[0].get('Options')
                and volumes[0].get('Labels', {}).get('com.docker.compose.project') == config['name']
                and volumes[0]['Labels'].get('com.docker.compose.volume') == 'terminal_home'
                and isinstance(volumes[0].get('Mountpoint'), str) and volumes[0]['Mountpoint'].startswith('/')
                and mounts[0].get('Source') == volumes[0].get('Mountpoint'),
                'Terminal actual project home volume differs')
        platform = self._docker_json(['image', 'inspect', '--format',
            '{"id":{{json .Id}},"os":{{json .Os}},"architecture":{{json .Architecture}}}', TERMINAL_IMAGE_ID])
        require(platform == {'id': TERMINAL_IMAGE_ID, 'os': 'linux', 'architecture': 'amd64'},
                'Terminal pinned platform differs')
        self._terminal_binding = {'id': row['id'], 'image': TERMINAL_IMAGE, 'image_id': TERMINAL_IMAGE_ID,
                                  'volume': volume_name, 'os': 'linux', 'architecture': 'amd64'}

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
        self._terminal_binding = None
        terminal_key = self._terminal_prerequisites() if self.terminal else None
        services = {'proxy', 'postgres', 'provider', 'redis', 'webui', 'office'}
        if self.terminal:
            services.add(TERMINAL_SERVICE)
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
        require(result.returncode == 0 and len(ids) == len(set(ids)) == len(services)
                and all(re.fullmatch('[a-f0-9]{64}', value) for value in ids),
                'Office requires seven unique containers' if self.terminal else 'Office requires six unique containers')
        rows = [self._docker_json(['inspect', '--format', '{{json .}}', value], project=lambda raw: topology_row(raw,
            terminal=self.terminal and raw['Config']['Labels'].get('com.docker.compose.service') == TERMINAL_SERVICE)) for value in ids]
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
        if self.terminal:
            self._check_terminal(config, by_service[TERMINAL_SERVICE], terminal_key, by_service['webui']['id'])
        self._office_binding = {'project': project, 'services': {name: {'id': by_service[name]['id'],
            'image': config['services'][name].get('image')} for name in ('webui', 'office')}}

    def running_readback(self, base_url, build_receipt, expected_revision):
        """Collect actual same-job artifacts; not persisted profile/Office acceptance.

        Caller supplies trusted clean GITHUB_SHA and successful builder output.
        The explicit six/seven binding repeats immediately before selection.
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

    def native_context(self, base_url, build_receipt, expected_revision, reasoning_cases, *, saved_output=None):
        """Execute native schema/Responses owners in the actual built WebUI.

        The host's strict artifact binding attests the producer; fields in the
        returned packet are observations, never independent origin evidence.
        Optional saved_output is one caller-supplied assistant output list;
        native owners convert only that output, without assembling chat history.
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
        if saved_output is not None:
            require(isinstance(saved_output, list) and saved_output and all(isinstance(item, dict)
                    and item.get('type') in ('reasoning', 'message', 'function_call', 'function_call_output')
                    and (item['type'] != 'message' or item.get('role') == 'assistant') for item in saved_output),
                    'Office native saved output observation differs')
            no_credentials(saved_output, self.secrets)
            modules.update({name: running['webui']['modules'][name] for name in ('utils/misc.py', 'utils/middleware.py')})
        schema = handoff['office_setup']['openapi']
        inputs = {'module_sha256': modules, 'openapi': schema, 'reasoning_cases': list(cases.values())}
        if saved_output is not None:
            users = handoff.get('users')
            require(isinstance(users, list) and len(users) == 1 and isinstance(users[0], dict)
                    and isinstance(users[0].get('id'), str) and bool(users[0]['id'])
                    and isinstance(handoff.get('admin'), dict) and bool(handoff['admin'].get('id'))
                    and users[0]['id'] != handoff['admin']['id'], 'Office native context ordinary principal differs')
            inputs.update(saved_output=saved_output, user_id=users[0]['id'])
        payload = json.dumps(inputs, ensure_ascii=True, allow_nan=False)
        require(len(payload.encode('ascii')) <= 96 * 1024, 'Office native context argument exceeded bound')
        code = '''import contextlib,hashlib,io,json,pathlib,sys
p=json.loads(sys.argv[1]);r=pathlib.Path('/app/backend/open_webui')
assert isinstance(p,dict) and set(p) in ({'module_sha256','openapi','reasoning_cases'},
    {'module_sha256','openapi','reasoning_cases','saved_output','user_id'})
names=('utils/tools.py','routers/openai.py')+(('utils/misc.py','utils/middleware.py') if 'saved_output' in p else ())
original=json.dumps(p,sort_keys=True,ensure_ascii=True,allow_nan=False)
def modules():
    return {n:hashlib.sha256((r/n).read_bytes()).hexdigest() for n in names}
assert modules()==p['module_sha256']
resolution_sources=RESOLUTION_SOURCES
def resolution_modules():
    return {n:hashlib.sha256((r/n).read_bytes()).hexdigest() for n in resolution_sources}
if 'saved_output' in p: assert resolution_modules()==resolution_sources
with contextlib.redirect_stdout(io.StringIO()):
    from open_webui.utils.tools import convert_openapi_to_tool_payload,clean_openai_tool_schema
    from open_webui.routers.openai import convert_to_responses_payload
    specs=[clean_openai_tool_schema(s) for s in convert_openapi_to_tool_payload(p['openapi'])]
    cases=[{'input_reasoning':v,'native_input':convert_to_responses_payload(
        {'messages':[{'role':'assistant','output':v}]})['input']} for v in p['reasoning_cases']]
    if 'saved_output' in p:
        assert p['user_id']==EXPECTED_USER_ID
        saved=p['saved_output']
        assert isinstance(saved,list) and saved and all(isinstance(v,dict)
            and v.get('type') in ('reasoning','message','function_call','function_call_output')
            and (v['type']!='message' or v.get('role')=='assistant') for v in saved)
        from open_webui.utils.misc import convert_output_to_messages
        import asyncio
        from open_webui.models.users import Users
        from open_webui.utils.files import FILE_CONTENT_URL_PATTERN
        from open_webui.utils.middleware import (process_messages_with_output,sanitize_tool_pairs,
            convert_url_images_to_base64,normalize_messages_for_model)
        messages=convert_output_to_messages(saved,raw=True,reasoning_format='responses',flatten_tool_images=False)
        messages=process_messages_with_output(messages,reasoning_format='responses',flatten_tool_images=False)
        messages=sanitize_tool_pairs(messages)
        def image_urls(messages):
            for message in messages:
                content=message.get('content')
                if isinstance(content,list):
                    for item in content:
                        if isinstance(item,dict) and item.get('type') in ('input_image','image_url'):
                            url=item.get('image_url')
                            yield url.get('url') if isinstance(url,dict) else url
        assert all(isinstance(url,str) and (url.startswith('data:image/')
            or FILE_CONTENT_URL_PATTERN.match(url)) for url in image_urls(messages))
        async def resolve():
            user=await Users.get_user_by_id(p['user_id'])
            assert user is not None and user.id==p['user_id'] and user.role=='user'
            form=await convert_url_images_to_base64({'messages':messages},user=user)
            assert all(isinstance(url,str) and url.startswith('data:image/') for url in image_urls(form['messages']))
            return normalize_messages_for_model(form)
        form=asyncio.run(resolve())
        observed={'input_saved_output':saved,'native_input':convert_to_responses_payload(form)['input']}
assert json.dumps(p,sort_keys=True,ensure_ascii=True,allow_nan=False)==original
assert modules()==p['module_sha256']
if 'saved_output' in p: assert resolution_modules()==resolution_sources
body=hashlib.sha256(json.dumps(p['openapi'],sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
packet={'schema':1,'module_sha256':modules(),'source_body_sha256':body,'native_specs':specs,'reasoning_cases':cases}
if 'saved_output' in p: packet['saved_output_case']=observed
print(json.dumps(packet,allow_nan=False))
'''
        code = code.replace('RESOLUTION_SOURCES', repr(NATIVE_RESOLUTION_SOURCES))
        code = code.replace('EXPECTED_USER_ID', repr(inputs.get('user_id')))
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
        if saved_output is None:
            require('saved_output_case' not in packet, 'Office unexpected native saved output observation')
        else:
            observed = packet.get('saved_output_case')
            require(set(packet) == {'schema', 'module_sha256', 'source_body_sha256', 'native_specs',
                    'reasoning_cases', 'saved_output_case'} and isinstance(observed, dict)
                    and set(observed) == {'input_saved_output', 'native_input'}
                    and digest(observed['input_saved_output']) == digest(saved_output)
                    and isinstance(observed['native_input'], list), 'Office native saved output producer readback differs')
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
