"""Action contract checks; actual native ACL, CLI and UI are qualified separately."""
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest


@pytest.fixture
def action(monkeypatch):
    path = Path(__file__).resolve().parents[3] / 'deploy/openwebui-functions/officecli_word_export_action.py'
    spec = importlib.util.spec_from_file_location('word_export_action', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name in ('open_webui', 'open_webui.models', 'open_webui.models.users',
                 'open_webui.utils', 'open_webui.utils.tools'):
        monkeypatch.setitem(sys.modules, name, ModuleType(name))
    sys.modules['open_webui.models.users'].UserModel = SimpleNamespace
    return module.Action()


def test_toolbar_translates_native_identity_and_ignores_supplied_message_text(action):
    import asyncio
    observed, events = {}, []

    async def create(**kwargs):
        observed['operation'] = kwargs
        return {'result_file_id':'native-file', 'result_sha256':'artifact-hash',
                'source_message_id':'selected', 'source_content_sha256':'native-source-hash',
                'source_text_preserved':True}, {}

    async def get_tools(request, tool_ids, user, extra_params):
        observed['native'] = (request, tool_ids, user.id, extra_params)
        return {'export_answer_to_word':{'callable':create}}

    async def emit(event):
        events.append(event)

    sys.modules['open_webui.utils.tools'].get_tools = get_tools
    request = object()
    receipt = asyncio.run(action.action({'chat_id':'chat', 'id':'selected',
                                         'messages':[{'content':'Forged caller content'}]},
                                        __user__={'id':'caller'}, __request__=request,
                                        __event_emitter__=emit, __id__='word_fields'))
    assert observed['native'] == (request, ['server:officecli'], 'caller',
                                  {'__user__':{'id':'caller'}, '__metadata__':{'chat_id':'chat', 'message_id':'selected'}})
    assert observed['operation']['source_message'] == 'selected_assistant'
    assert 'Forged caller content' not in str(observed['operation'])
    assert receipt['source_content_sha256'] == 'native-source-hash'
    assert events[-1]['data']['done'] is True


def test_unavailable_native_tool_does_not_fall_back_to_another_exporter(action):
    import asyncio

    async def get_tools(*args, **kwargs):
        return {}

    sys.modules['open_webui.utils.tools'].get_tools = get_tools
    with pytest.raises(ValueError, match='unavailable'):
        asyncio.run(action.action({'chat_id':'chat', 'id':'selected'}, __user__={'id':'caller'},
                                 __request__=object(), __id__='word'))
