from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
LOADER_PATH = ROOT / "deploy" / "openwebui-static" / "loader.js"


def test_loader_binds_postprocessing_actions_to_prepared_file_scope():
    source = LOADER_PATH.read_text(encoding="utf-8")
    start = source.index("async function runTranscription")
    end = source.index("async function callTranscriptionAction", start)
    run_transcription = source[start:end]

    assert "const preparedFile = isPreparedStage2Audio(file) ? file : await prepareMediaFile(file, status);" in run_transcription
    assert "const content = await callTranscriptionAction(preparedFile, status);" in run_transcription
    assert "loadPostprocessingActions(preparedFile, transcriptRef, button.parentElement, status)" in run_transcription
    assert "loadPostprocessingActions(file, transcriptRef, button.parentElement, status)" not in run_transcription


def test_loader_quick_action_drafts_native_chat_prompt_instead_of_processed_result():
    source = LOADER_PATH.read_text(encoding="utf-8")
    start = source.index("async function runPostprocessingAction")
    end = source.index("async function callPostprocessingPromptDraft", start)
    action_block = source[start:end]

    assert "const draft = await callPostprocessingPromptDraft(file, transcriptRef, template);" in action_block
    assert "submitPostprocessingPromptDraft(draft.prompt_text, transcriptRef)" in action_block
    assert "appendToComposer(content)" not in action_block


def test_loader_quick_action_uses_prompt_draft_operation():
    source = LOADER_PATH.read_text(encoding="utf-8")
    start = source.index("async function callPostprocessingPromptDraft")
    end = source.index("async function submitPostprocessingPromptDraft", start)
    draft_block = source[start:end]

    assert "operation: 'draft_postprocessing_prompt'" in draft_block
    assert "stage2_stt_prompt_draft" in draft_block
    assert "execute_postprocessing" not in draft_block


def test_loader_quick_action_submits_prompt_without_overwriting_unrelated_draft():
    source = LOADER_PATH.read_text(encoding="utf-8")
    start = source.index("async function submitPostprocessingPromptDraft")
    end = source.index("function findComposer", start)
    submit_block = source[start:end]

    assert "composerText && transcriptRef && !composerText.includes(transcriptRef)" in submit_block
    assert "postprocessing_prompt_blocked" in submit_block
    assert "replaceComposerText(composer, promptText)" in submit_block
    assert "submitComposer(composer)" in submit_block


def test_loader_scans_message_docx_buttons_without_replacing_stt_scan():
    source = LOADER_PATH.read_text(encoding="utf-8")
    start = source.index("function queueScan")
    end = source.index("function findCardFile", start)
    queue_scan = source[start:end]

    assert "scanAttachmentCards();" in queue_scan
    assert "scanMessageDocxButtons();" in queue_scan


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


def test_loader_docx_request_uses_semantic_html_without_fake_markdown():
    source = LOADER_PATH.read_text(encoding="utf-8")
    start = source.index("function buildMessageDocxRequest")
    end = source.index("function extractScopedMessageText", start)
    request_block = source[start:end]

    assert "const html = extractScopedMessageHtml(content);" in request_block
    assert "message_markdown: null" in request_block
    assert "message_html: html" in request_block
    assert "formatting_profile: html ? 'semantic_chat_v1' : 'simple_mvp'" in request_block
    assert "message_markdown: text" not in request_block


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
