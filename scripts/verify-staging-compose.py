"""Validate the resolved clean-staging contours without starting containers."""
import json
import os
import pathlib
import subprocess
import tempfile

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
            assert web_env['SEARXNG_QUERY_URL'] == 'http://searxng:8080/search'
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
