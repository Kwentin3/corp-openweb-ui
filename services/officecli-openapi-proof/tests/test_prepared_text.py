from hashlib import sha256
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import httpx
import pytest

from officecli_openapi_proof.docx_text import WORD, body_paragraphs, require_preserved_text
from officecli_openapi_proof.officecli import OfficeCliFailure
from officecli_openapi_proof.openwebui_client import HttpOpenWebUiClient, OpenWebUiFailure


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
