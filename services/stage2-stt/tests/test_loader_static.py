from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
LOADER_PATH = ROOT / "deploy" / "openwebui-static" / "loader.js"


def test_loader_leaves_transcription_to_native_openwebui_filter():
    source = LOADER_PATH.read_text(encoding="utf-8")
    start = source.index("function queueScan")
    end = source.index("function findCardFile", start)
    queue_scan = source[start:end]

    assert "sttUploadFile" not in source
    assert "withProcessFalse(input)" not in source
    assert "installCardAction(card, file);" not in source
    assert "scanAttachmentCards();" not in queue_scan
    assert "scanMessageDocxButtons();" in queue_scan


def test_loader_leaves_broker_pdf_routing_to_native_message_input():
    source = LOADER_PATH.read_text(encoding="utf-8")
    start = source.index("function patchFetch")
    end = source.index("function queueScan", start)
    patch_block = source[start:end]

    assert "sttUploadFile" not in patch_block
    assert "withProcessFalse(input)" not in patch_block
    assert "state.originalFetch(nextInput, nextInit)" in patch_block
    assert "broker-reports/intake" not in patch_block
    assert "normalizeBroker" not in patch_block
    assert "brokerGate1UploadFile" not in patch_block
    assert "return response;" in patch_block


def test_loader_does_not_own_broker_gate1_pdf_routing():
    source = LOADER_PATH.read_text(encoding="utf-8")

    assert "BROKER_GATE1_PIPE_MODEL_ID" not in source
    assert "isBrokerGate1Pdf" not in source
    assert "isBrokerGate1ModelActive" not in source
    assert "brokerGate1UploadFile" not in source


def test_loader_action_payload_uses_the_current_native_model_selection():
    source = LOADER_PATH.read_text(encoding="utf-8")
    start = source.index("async function selectedModelId")
    end = source.index("function currentChatId", start)
    selected_model_block = source[start:end]

    assert "const selectedIds = currentSelectedModelIds();" in selected_model_block
    assert "selectedIds.length !== 1" in selected_model_block
    assert "return selectedIds[0];" in selected_model_block
    assert "payload.data[0]" not in selected_model_block


def test_loader_binds_only_gate2_completions_to_active_persistent_chat():
    source = LOADER_PATH.read_text(encoding="utf-8")
    start = source.index("async function bindBrokerGate2RequestToActiveChat")
    end = source.index("function normalizeUploadedFile", start)
    binding_block = source[start:end]
    patch_start = source.index("function patchFetch")
    patch_end = source.index("function queueScan", patch_start)
    patch_block = source[patch_start:patch_end]

    assert "const BROKER_GATE2_MODEL_IDS = new Set([" in source
    assert "'broker_reports_gate2_source_fact_pipe'" in source
    assert "'broker_reports_gate2_domain_source_fact_pipe'" in source
    assert "!BROKER_GATE2_MODEL_IDS.has(payload.model)" in binding_block
    assert "const chatId = persistentChatIdFromLocation();" in binding_block
    assert "chat_id: chatId" in binding_block
    assert "metadata:" in binding_block
    assert "await bindBrokerGate2RequestToActiveChat(input, init)" in patch_block
    assert "state.originalFetch(nextInput, nextInit)" in patch_block


def test_loader_has_no_broker_private_intake_route_or_dom_action():
    source = LOADER_PATH.read_text(encoding="utf-8")

    assert "/api/v1/broker-reports/intake" not in source
    assert "broker_reports_private_intake_action" not in source
    assert "brokerPrivateIntakeRequest" not in source
    assert "normalizeBrokerPrivateIntakeResponse" not in source
    assert "scanBrokerGate1ComposerPanel" not in source
    assert "installBrokerGate1CardAction" not in source
    assert "callBrokerGate1Action" not in source
    assert "data-broker-gate1" not in source


def test_loader_docx_button_is_assistant_scoped_and_deduplicated():
    source = LOADER_PATH.read_text(encoding="utf-8")
    start = source.index("function scanMessageDocxButtons")
    end = source.index("function loadScript", start)
    docx_block = source[start:end]

    assert 'div[id^="message-"]' in docx_block
    assert "root.querySelector('.chat-assistant.markdown-prose')" in docx_block
    assert "root.querySelector('.buttons')" in docx_block
    assert "root.querySelector('.copy-response-button')" in docx_block
    assert '[data-stage2-docx-export="1"]' in docx_block
    assert "button.dataset.stage2DocxExport = '1'" in docx_block
    assert "operation: 'export_message_docx'" in docx_block


def test_loader_docx_action_payload_includes_openwebui_action_envelope():
    source = LOADER_PATH.read_text(encoding="utf-8")
    start = source.index("async function callMessageDocxAction")
    end = source.index("async function saveMessageDocxResult", start)
    action_block = source[start:end]

    assert "const model = await selectedModelId();" in action_block
    assert "id: request.message_id || `stage2-docx-${Date.now()}`" in action_block
    assert "chat_id: request.chat_id || currentChatId()" in action_block
    assert "session_id: currentSessionId()" in action_block
    assert "model," in action_block
    assert "messages: []" in action_block
    assert "stage2_message_docx" in action_block
    assert "operation: 'export_message_docx'" in action_block


def test_loader_docx_request_uses_canonical_markdown_before_dom_html_fallback():
    source = LOADER_PATH.read_text(encoding="utf-8")
    start = source.index("async function buildMessageDocxRequest")
    end = source.index("function extractScopedMessageText", start)
    request_block = source[start:end]

    assert "const chatId = currentChatId();" in request_block
    assert "const messageId = messageIdFromRoot(root);" in request_block
    assert (
        "const markdown = await fetchCanonicalMessageMarkdown(chatId, messageId);"
        in request_block
    )
    assert "const html = extractScopedMessageHtml(content);" in request_block
    assert "message_markdown: markdown" in request_block
    assert "message_html: html" in request_block
    assert "source: markdown ? 'openwebui_chat_api' : 'dom'" in request_block
    assert (
        "formatting_profile: hasStructuredSource ? 'semantic_chat_v1' : 'simple_mvp'"
        in request_block
    )
    assert "message_markdown: null" not in request_block
    assert "message_markdown: text" not in request_block


def test_loader_docx_fetches_openwebui_chat_markdown_safely():
    source = LOADER_PATH.read_text(encoding="utf-8")
    start = source.index("async function fetchCanonicalMessageMarkdown")
    end = source.index("function extractScopedMessageText", start)
    fetch_block = source[start:end]

    assert "String(chatId).startsWith('local:')" in fetch_block
    assert "`/api/v1/chats/${encodeURIComponent(chatId)}`" in fetch_block
    assert "cache: 'no-store'" in fetch_block
    assert "findCanonicalChatMessage(payload, messageId)" in fetch_block
    assert "collectCanonicalMessages(candidates, chat.messages)" in fetch_block
    assert (
        "collectCanonicalMessages(candidates, chat.history && chat.history.messages)"
        in fetch_block
    )
    assert "collectCanonicalMessages(candidates, payload.messages)" in fetch_block
    assert (
        "collectCanonicalMessages(candidates, payload.history && payload.history.messages)"
        in fetch_block
    )
    assert "message.content ?? message.text ?? message.message" in fetch_block
    assert "value.text ?? value.content ?? value.message ?? ''" in fetch_block


def test_loader_docx_extraction_avoids_global_response_content_container():
    source = LOADER_PATH.read_text(encoding="utf-8")
    start = source.index("function extractScopedMessageText")
    end = source.index("function normalizeDocxText", start)
    extract_block = source[start:end]

    assert "content.cloneNode(true)" in extract_block
    assert "cleanDocxClone(clone)" in extract_block
    assert "function extractScopedMessageHtml" in extract_block
    assert "sanitizeDocxHtml(clone)" in extract_block
    assert "DOCX_REMOVE_SELECTOR" in source
    assert "node.removeAttribute(attribute.name)" in extract_block
    assert "safeDocxHref(attribute.value)" in extract_block
    assert "document.querySelector('#response-content-container')" not in source


def test_loader_docx_download_has_save_picker_and_blob_fallback():
    source = LOADER_PATH.read_text(encoding="utf-8")
    start = source.index("async function saveMessageDocxResult")
    end = source.index("function safeDownloadFilename", start)
    save_block = source[start:end]

    assert "window.showSaveFilePicker" in save_block
    assert "URL.createObjectURL(blob)" in save_block
    assert "anchor.download = filename" in save_block
    assert "URL.revokeObjectURL(url)" in save_block
