"""Validate clean staging and the staged release recipe without starting containers."""
import json
import os
import pathlib
import subprocess
import tempfile
from urllib.parse import parse_qs, urlsplit

repository = pathlib.Path(__file__).resolve().parents[1]
manifest = json.loads((repository / 'deploy/openwebui-patches/media-upload-v0.11.4/manifest.json').read_text(encoding='utf-8'))
overlays = ['terminal', 'office', 'search', 'stt', 'media']
expected_services = ['openwebui', 'open-terminal-office', 'officecli-openapi-proof', 'searxng', 'searxng-valkey', 'stage2-stt']
with tempfile.TemporaryDirectory(prefix='openwebui-staging-config-') as temporary:
    config_directory = pathlib.Path(temporary).resolve()
    environment = {
        **os.environ,
        'STAGING_WEBUI_SECRET_KEY': 'synthetic-ci-only-webui-secret',
        'STAGING_ADMIN_EMAIL': 'fixture@example.invalid',
        'STAGING_ADMIN_PASSWORD': 'synthetic-ci-only-password',
        'STAGING_TERMINAL_API_KEY': 'synthetic-ci-only-terminal-key',
        'STAGING_SEARXNG_SECRET': 'synthetic-ci-only-search-secret',
        'STAGING_SEARXNG_CONFIG_DIR': str(config_directory),
        'STAGING_OUTBOUND_PROXY': 'http://proxy.example.invalid:8118',
        'STAGING_STT_INTERNAL_API_KEY': 'synthetic-ci-only-stt-key',
        'STAGING_OFFICECLI_IMAGE': 'fixture/office@sha256:' + 'a' * 64,
        'STAGING_STT_IMAGE': 'fixture/stt@sha256:' + 'b' * 64,
        'STAGING_MEDIA_TRIAL_IMAGE': 'fixture/media@sha256:' + 'c' * 64,
    }
    for name in ['settings.yml', 'limiter.toml']:
        (config_directory / name).write_text('# Synthetic config-validation fixture\n', encoding='utf-8')
    command = ['docker', 'compose', '--env-file', os.devnull, '-f', str(repository / 'compose/openwebui.staging.compose.yml')]
    for count in range(len(overlays) + 1):
        if count:
            command += ['-f', str(repository / f'compose/openwebui.staging-{overlays[count - 1]}.compose.yml')]
        config = json.loads(subprocess.check_output(command + ['config', '--format', 'json'], env=environment, cwd=repository, text=True))
        services = config['services']
        # Search adds two services; the media selector adds no service.
        service_count = [1, 2, 3, 5, 6, 6][count]
        assert set(services) == set(expected_services[:service_count])
        assert config['name'] == 'openwebui-474'
        assert config['networks']['isolated']['internal'] is True
        for name, service in services.items():
            assert not service.get('ports'), f'{name}: published host port'
            assert not service.get('privileged') and not service.get('network_mode')
            assert service.get('restart') == 'no'
            # Compose 5 renders byte counts as strings; Compose 2 may use ints.
            assert int(service['mem_limit']) > 0 and service['pids_limit'] > 0
            assert 0 < service['cpus'] <= 0.5
            assert 'isolated' in service['networks']
            assert set(service['networks']) <= {'isolated', 'search-egress'}
            for mount in service.get('volumes', []):
                if mount['type'] == 'volume':
                    assert mount['source'] in config['volumes']
                else:
                    assert name == 'searxng' and mount['type'] == 'bind'
                    assert mount['read_only'] and pathlib.Path(mount['source']).resolve().parent == config_directory
        for volume in config.get('volumes', {}).values():
            assert not volume.get('external')
            assert volume['name'].startswith('openwebui-474_')
        webui = services['openwebui']
        web_env = webui['environment']
        assert web_env['ENABLE_OPENAI_API'] == web_env['ENABLE_OLLAMA_API'] == 'false'
        assert web_env['OPENAI_API_KEY'] == '' and web_env['ENABLE_SIGNUP'] == 'false'
        assert web_env['WEBUI_SECRET_KEY'] == environment['STAGING_WEBUI_SECRET_KEY']
        assert web_env['WHISPER_MODEL_AUTO_UPDATE'] == 'false'
        assert webui['labels']['traefik.enable'] == 'false'
        official = 'ghcr.io/open-webui/open-webui:v' + manifest['version'] + '@' + manifest['official_amd64_digest']
        assert webui['image'] == (environment['STAGING_MEDIA_TRIAL_IMAGE'] if count == 5 else official)
        if count >= 1:
            terminal = services['open-terminal-office']
            assert set(terminal['networks']) == {'isolated'}
            assert terminal['environment']['OPEN_TERMINAL_API_KEY'] == environment['STAGING_TERMINAL_API_KEY']
        if count >= 2:
            office = services['officecli-openapi-proof']
            assert set(office['networks']) == {'isolated'} and office['read_only'] is True
            assert office['environment']['OPENWEBUI_BASE_URL'] == 'http://openwebui:8080'
        if count >= 3:
            assert set(webui['networks']) == set(services['searxng']['networks']) == {'isolated', 'search-egress'}
            assert set(services['searxng-valkey']['networks']) == {'isolated'}
            search_url = urlsplit(web_env['SEARXNG_QUERY_URL'])
            assert search_url.scheme == 'http' and search_url.netloc == 'searxng:8080'
            assert search_url.path == '/search'
            assert parse_qs(search_url.query) == {'engines': ['duckduckgo web']}
            assert web_env['WEB_SEARCH_TRUST_ENV'] == 'false'
            assert web_env['http_proxy'] == environment['STAGING_OUTBOUND_PROXY']
        if count >= 4:
            stt = services['stage2-stt']
            stt_env = stt['environment']
            assert set(stt['networks']) == {'isolated'}
            assert stt_env['STAGE2_LEMONFOX_API_KEY'] == '' and stt_env['STAGE2_STT_ALLOW_STUB_TRANSCRIPT'] == 'false'
            assert stt_env['STAGE2_STT_PROMPT_CATALOG_MODE'] == stt_env['STAGE2_STT_POSTPROCESSING_EXECUTOR_MODE'] == 'disabled'
            assert stt_env['STAGE2_STT_INTERNAL_API_KEY'] == web_env['STAGE2_STT_INTERNAL_API_KEY'] == environment['STAGING_STT_INTERNAL_API_KEY']
            assert 'stage2-stt' in web_env['NO_PROXY'].split(',')
    print('Six resolved staging combinations passed: isolated storage/callbacks, no host ports or provider credentials; no containers started')

# Keep release checks in the existing Compose CI owner. Staged release recipe
# names match compose/openwebui.staging*.yml; changing this script also selects CI.
def verify_release_recipe():
    expected = {
        'openwebui-0114': 'sha256:c4ba3bda7e228f99a246f1d823dfe2a8830dbd8fad6966d2e1862350fb8be423',
        'stage2-stt-0114': 'sha256:ee7444dfc32f45ad620494e046d6c204468f06e6af55f4ca004b98bac3c8c205',
        'officecli-0114': 'sha256:3009ae1362e9896156028dbbdf39596682764a06fe1db2cd85775c5b93b82370',
        'open-terminal-0114': 'ghcr.io/open-webui/open-terminal@sha256:81a5394b3cd4ae32adb600f2135f09ee124de37f26b0a780e2f5692472c0fc5c',
    }
    with tempfile.TemporaryDirectory(prefix='openwebui-release-config-') as temporary:
        directory = pathlib.Path(temporary)
        fixtures = {
            'WEBUI': {'WEBUI_SECRET_KEY': 'synthetic-preserved-web-key-$literal', 'WEBUI_URL': 'https://chat.example.invalid', 'OPENAI_API_KEY': 'synthetic-preserved-provider-key', 'STAGE2_STT_INTERNAL_API_KEY': 'synthetic-preserved-stt-key'},
            'STT': {'STAGE2_STT_INTERNAL_API_KEY': 'synthetic-preserved-stt-key', 'STAGE2_LEMONFOX_API_KEY': 'synthetic-preserved-lemonfox-key', 'STAGE2_STT_TRANSCRIPT_TTL_DAYS': '14'},
            'TERMINAL': {'OPEN_TERMINAL_API_KEY': 'synthetic-preserved-terminal-key'},
        }
        environment = {
            **os.environ,
            'OPENWEBUI_HOST': 'chat.example.invalid',
            'RELEASE_WEBUI_NO_PROXY': 'localhost,existing.custom.internal,openwebui-0114,stage2-stt,stage2-stt-0114,officecli-0114,open-terminal-0114,searxng,searxng-valkey',
            'RELEASE_STT_NO_PROXY': 'localhost,existing.storage.internal,stage2-stt-0114,openwebui-0114',
        }
        for kind, values in fixtures.items():
            path = directory / f'{kind.lower()}.env'
            path.write_text(''.join(f'{key}={value}\n' for key, value in values.items()), encoding='utf-8')
            environment[f'RELEASE_{kind}_ENV_FILE'] = str(path)
        command = ['docker', 'compose', '--env-file', os.devnull, '-f', str(repository / 'compose/openwebui.staging-release-0114.compose.yml')]
        for routed in (False, True):
            if routed:
                command += ['-f', str(repository / 'compose/openwebui.staging-release-0114.route.compose.yml')]
            config = json.loads(subprocess.check_output(command + ['config', '--format', 'json'], env=environment, cwd=repository, text=True))
            assert config['name'] == 'openwebui-0114'
            assert set(config['services']) == set(expected)
            assert config['networks']['existing-web']['name'] == 'openwebui_web'
            assert config['networks']['existing-web']['external'] is True
            for name, service in config['services'].items():
                assert service['image'] == expected[name] and service['pull_policy'] == 'never'
                assert not service.get('build') and not service.get('ports') and not service.get('container_name')
                assert not service.get('privileged') and not service.get('network_mode')
                assert int(service['mem_limit']) > 0 and service['pids_limit'] > 0
                assert 'services' in service['networks']
                aliases = {key: (network or {}).get('aliases', []) for key, network in service['networks'].items()}
                assert aliases == {key: [] for key in service['networks']}
                for mount in service.get('volumes', []):
                    assert mount['type'] == 'volume' and mount['source'] in config['volumes']
                if name != 'openwebui-0114':
                    assert service['labels']['traefik.enable'] == 'false'
            assert {v['name'] for v in config['volumes'].values()} == {'openwebui-0114_data', 'openwebui-0114_stt_data', 'openwebui-0114_terminal_home'}
            assert not any(v.get('external') for v in config['volumes'].values())
            web = config['services']['openwebui-0114']
            # Config export may escape dollars for a second Compose parse. A separate
            # native create/inspect proof checks the literal runtime value (no start).
            key = fixtures['WEBUI']['WEBUI_SECRET_KEY']
            assert web['environment']['WEBUI_SECRET_KEY'] in (key, key.replace('$', '$$'))
            assert 'OAUTH_SESSION_TOKEN_ENCRYPTION_KEY' not in web['environment']
            assert 'OAUTH_CLIENT_INFO_ENCRYPTION_KEY' not in web['environment']
            assert web['environment']['OPENAI_API_KEY'] == fixtures['WEBUI']['OPENAI_API_KEY']
            assert web['environment']['NO_PROXY'] == web['environment']['no_proxy'] == environment['RELEASE_WEBUI_NO_PROXY']
            assert web['environment']['STAGE2_STT_BASE_URL'] == 'http://stage2-stt-0114:8080'
            assert not any(k in web['environment'] for k in ('ENABLE_PERSISTENT_CONFIG', 'DEFAULT_MODELS', 'WEBUI_ADMIN_PASSWORD'))
            assert web['labels']['traefik.enable'] == str(routed).lower()
            assert not any('loader' in key for key in web['labels'])
            if routed:
                assert web['labels']['traefik.docker.network'] == 'openwebui_web'
                assert web['labels']['traefik.http.routers.openwebui.rule'] == 'Host(`chat.example.invalid`)'
                assert web['labels']['traefik.http.routers.openwebui.service'] == 'openwebui'
            stt = config['services']['stage2-stt-0114']
            assert stt['environment']['STAGE2_STT_INTERNAL_API_KEY'] == web['environment']['STAGE2_STT_INTERNAL_API_KEY']
            assert stt['environment']['NO_PROXY'] == stt['environment']['no_proxy'] == environment['RELEASE_STT_NO_PROXY']
            for key, value in fixtures['STT'].items():
                assert stt['environment'][key] == value
            assert stt['environment']['STAGE2_STT_PROMPT_CATALOG_MODE'] == stt['environment']['STAGE2_STT_POSTPROCESSING_EXECUTOR_MODE'] == 'disabled'
            assert stt['environment']['STAGE2_STT_OPENWEBUI_PROMPT_DB_PATH'] == ''
            assert [m['target'] for m in stt['volumes']] == ['/data/stage2-stt']
            office = config['services']['officecli-0114']
            assert office['environment']['OPENWEBUI_BASE_URL'] == 'http://openwebui-0114:8080'
            assert set(office['networks']) == {'services'} and office['read_only'] is True
            terminal = config['services']['open-terminal-0114']
            assert terminal['environment']['OPEN_TERMINAL_API_KEY'] == fixtures['TERMINAL']['OPEN_TERMINAL_API_KEY']
            assert set(terminal['networks']) == {'services'}
        print('Release Compose and explicit route overlay resolved: pinned images, separate volumes, preserved environment, unique service names; no containers started')

verify_release_recipe()
