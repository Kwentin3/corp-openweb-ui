from hashlib import sha256
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import httpx
import pytest
from fastapi.testclient import TestClient

from officecli_openapi_proof.docx_text import WORD, body_paragraphs, require_preserved_text
from officecli_openapi_proof.officecli import OfficeCliFailure
from officecli_openapi_proof.openwebui_client import HttpOpenWebUiClient, OpenWebUiFailure, OpenWebUiUnauthorized
from officecli_openapi_proof.app import CreateOfficeDocumentRequest, ExportOfficeAnswerRequest, create_app
from officecli_openapi_proof.config import Settings
from pydantic import ValidationError


def test_drafting_requires_content_and_export_defaults_to_the_native_answer():
    with pytest.raises(ValidationError, match='commands'):
        CreateOfficeDocumentRequest(output_name='result.docx')
    assert ExportOfficeAnswerRequest(output_name='result.docx').source_message == 'previous_assistant'
    ExportOfficeAnswerRequest(output_name='result.docx', source_message='selected_assistant')
    for value in (None, 'new_content'):
        with pytest.raises(ValidationError, match='source_message'):
            ExportOfficeAnswerRequest(output_name='result.docx', source_message=value)
    CreateOfficeDocumentRequest(output_name='result.docx', commands=[{'command':'add'}])
    with pytest.raises(ValidationError, match='extra_forbidden'):
        CreateOfficeDocumentRequest(output_name='result.docx', source_message='previous_assistant',
                                    commands=[{'command':'add','props':{'text':'Date: ____'}}])


def test_note_export_uses_one_explicit_native_source_without_retyped_content():
    request = ExportOfficeAnswerRequest(output_name='note.docx', source_note_id='native-note')
    assert request.commands == []
    assert request.source_note_id == 'native-note'
    for source in ('previous_assistant', 'selected_assistant'):
        with pytest.raises(ValidationError, match='not both'):
            ExportOfficeAnswerRequest(output_name='note.docx', source_note_id='native-note', source_message=source)
    for identifier in ('', '../foreign', 'https://foreign/note', 'note?user=other', 'a' * 129):
        with pytest.raises(ValidationError):
            ExportOfficeAnswerRequest(output_name='note.docx', source_note_id=identifier)


def test_native_note_markdown_is_read_verbatim_with_caller_authorization(monkeypatch):
    calls = []
    source = '## Fill-in template\n\n{{Client}}\n\n| Item | Price |\n| --- | --- |\n| {{Item}} | {{Price}} |\n'
    def request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        note = {'id':'native-note', 'data':{'content':{'md':source, 'json':{'display':'not the canonical source'}}}}
        return httpx.Response(200, json=note, request=httpx.Request(method,url))
    monkeypatch.setattr('officecli_openapi_proof.openwebui_client.httpx.request',request)
    result = HttpOpenWebUiClient('http://native',5).resolve_note_text('native-note','Bearer caller')
    assert result.note_id == 'native-note' and result.text == source
    assert calls[0][:2] == ('GET','http://native/api/v1/notes/native-note')
    assert calls[0][2]['headers'] == {'Authorization':'Bearer caller'}
    assert calls[0][2]['follow_redirects'] is False


@pytest.mark.parametrize('status',[401,403,404])
def test_denied_or_missing_native_note_is_not_replaced_by_another_source(monkeypatch,status):
    calls = []
    def request(method,url,**kwargs):
        calls.append(url)
        return httpx.Response(status,json={'detail':'unavailable'},request=httpx.Request(method,url))
    monkeypatch.setattr('officecli_openapi_proof.openwebui_client.httpx.request',request)
    with pytest.raises(OpenWebUiUnauthorized if status in (401,403) else OpenWebUiFailure):
        HttpOpenWebUiClient('http://native',5).resolve_note_text('native-note','Bearer caller')
    assert calls == ['http://native/api/v1/notes/native-note']


@pytest.mark.parametrize('note',[
    {'id':'foreign-note','data':{'content':{'md':'A valid but different source'}}},
    {'id':'native-note','data':{'content':{'json':{'text':'Do not infer Markdown from this'}}}},
    {'id':'native-note','data':{'content':{'md':'  '}}},
    {'id':'native-note','data':{'content':{'md':['Not text']}}},
])
def test_native_note_misbinding_and_missing_canonical_text_are_rejected(monkeypatch,note):
    monkeypatch.setattr('officecli_openapi_proof.openwebui_client.httpx.request',
        lambda method,url,**kwargs:httpx.Response(200,json=note,request=httpx.Request(method,url)))
    with pytest.raises(OpenWebUiFailure):
        HttpOpenWebUiClient('http://native',5).resolve_note_text('native-note','Bearer caller')


@pytest.mark.parametrize('status,note',[
    (403,{'detail':'unavailable'}),
    (200,{'id':'another-note','data':{'content':{'md':'A different valid source'}}}),
])
def test_export_does_not_start_cli_or_publish_before_note_owner_acceptance(monkeypatch,status,note):
    calls = []
    def request(method,url,**kwargs):
        calls.append((method,url,kwargs['headers']))
        auth = url.endswith('/api/v1/auths/')
        return httpx.Response(200 if auth else status,json={'id':'caller'} if auth else note,
                              request=httpx.Request(method,url))
    class UncalledExecutor:
        def run(self,*args,**kwargs):
            raise AssertionError('No Office operation before source owner acceptance')
    monkeypatch.setattr('officecli_openapi_proof.openwebui_client.httpx.request',request)
    client = TestClient(create_app(UncalledExecutor(),HttpOpenWebUiClient('http://native',5),
        Settings('officecli',5,'1.0.152','http://native')))
    response = client.post('/v1/officecli/documents/export-answer',
        headers={'Authorization':'Bearer caller','X-OpenWebUI-Chat-Id':'chat','X-OpenWebUI-Message-Id':'current'},
        json={'output_name':'note.docx','source_note_id':'native-note'})
    assert response.status_code == (401 if status == 403 else 502)
    assert calls == [('GET','http://native/api/v1/auths/',{'Authorization':'Bearer caller'}),
                     ('GET','http://native/api/v1/notes/native-note',{'Authorization':'Bearer caller'})]


def test_message_toolbar_source_uses_the_exact_completed_native_message(monkeypatch):
    data = native_history()
    monkeypatch.setattr('officecli_openapi_proof.openwebui_client.httpx.request',
                        lambda method, url, **kwargs: httpx.Response(200, json=data, request=httpx.Request(method, url)))
    client = HttpOpenWebUiClient('http://native', 5)
    assert client.resolve_completed_assistant_text('chat', 'selected', 'Bearer caller').message_id == 'selected'
    assert client.resolve_completed_assistant_text('chat', 'other-branch', 'Bearer caller').text == 'A different source.'
    with pytest.raises(OpenWebUiFailure):
        client.resolve_completed_assistant_text('chat', 'current', 'Bearer caller')


def native_history():
    return {'chat': {'history': {'messages': {
        'current': {'role': 'assistant', 'parentId': 'question'},
        'question': {'role': 'user', 'parentId': 'selected'},
        'selected': {'role': 'assistant', 'done': True, 'content': 'Approved source: keep all 17 items.'},
        'other-branch': {'role': 'assistant', 'done': True, 'content': 'A different source.'},
    }}}}


def test_source_is_bound_by_native_parent_ids_and_caller_authorization(monkeypatch):
    calls = []

    def request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return httpx.Response(200, json=native_history(), request=httpx.Request(method, url))

    monkeypatch.setattr('officecli_openapi_proof.openwebui_client.httpx.request', request)
    source = HttpOpenWebUiClient('http://native', 5).resolve_previous_assistant_text('chat', 'current', 'Bearer caller')
    assert source.message_id == 'selected'
    assert source.text == 'Approved source: keep all 17 items.'
    assert calls[0][0:2] == ('GET', 'http://native/api/v1/chats/chat')
    assert calls[0][2]['headers'] == {'Authorization': 'Bearer caller'}
    assert calls[0][2]['follow_redirects'] is False


@pytest.mark.parametrize('change', ['missing-current', 'missing-parent', 'wrong-role', 'unfinished', 'empty'])
def test_missing_or_unfinished_source_is_not_replaced_by_a_neighbour(monkeypatch, change):
    data = native_history()
    messages = data['chat']['history']['messages']
    if change == 'missing-current':
        messages.pop('current')
    elif change == 'missing-parent':
        messages['current']['parentId'] = ['not-an-id']
    elif change == 'wrong-role':
        messages['selected']['role'] = 'user'
    elif change == 'unfinished':
        messages['selected']['done'] = False
    else:
        messages['selected']['content'] = ''
    monkeypatch.setattr('officecli_openapi_proof.openwebui_client.httpx.request',
                        lambda method, url, **kwargs: httpx.Response(200, json=data, request=httpx.Request(method, url)))
    with pytest.raises(OpenWebUiFailure):
        HttpOpenWebUiClient('http://native', 5).resolve_previous_assistant_text('chat', 'current', 'Bearer caller')


def write_document(path: Path, paragraphs):
    root = ET.Element(WORD + 'document')
    body = ET.SubElement(root, WORD + 'body')
    for text in paragraphs:
        paragraph = ET.SubElement(body, WORD + 'p')
        for part in (text[:3], text[3:]):
            ET.SubElement(ET.SubElement(paragraph, WORD + 'r'), WORD + 't').text = part
    with ZipFile(path, 'w') as package:
        package.writestr('word/document.xml', ET.tostring(root))


def test_formatting_run_changes_and_added_fields_preserve_the_full_source(tmp_path):
    path = tmp_path / 'source.docx'
    write_document(path, ['Keep source one.', 'Keep source two.'])
    source = body_paragraphs(path)
    write_document(path, ['Date: ______', 'Keep source one.', 'Keep source two.', 'Signature: ______'])
    require_preserved_text(source, body_paragraphs(path))


@pytest.mark.parametrize('changed', [['Keep source one.'], ['Keep source two.', 'Keep source one.'],
                                  ['Rewritten source one.', 'Keep source two.'],
                                  ['Keep source one.', 'Keep source two.', 'Keep source one.']])
def test_changed_real_document_is_rejected_even_with_its_new_valid_hash(tmp_path, changed):
    path = tmp_path / 'result.docx'
    write_document(path, ['Keep source one.', 'Keep source two.'])
    source = body_paragraphs(path)
    before = sha256(path.read_bytes()).hexdigest()
    write_document(path, changed)
    assert sha256(path.read_bytes()).hexdigest() != before
    with pytest.raises(OfficeCliFailure, match='changed, removed, reordered or duplicated'):
        require_preserved_text(source, body_paragraphs(path))
