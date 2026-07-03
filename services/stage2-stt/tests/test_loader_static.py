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


def test_loader_docx_extraction_avoids_global_response_content_container():
    source = LOADER_PATH.read_text(encoding="utf-8")
    start = source.index("function extractScopedMessageText")
    end = source.index("function normalizeDocxText", start)
    extract_block = source[start:end]

    assert "content.cloneNode(true)" in extract_block
    assert "button, svg, textarea, input, select, script, style, noscript" in extract_block
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
