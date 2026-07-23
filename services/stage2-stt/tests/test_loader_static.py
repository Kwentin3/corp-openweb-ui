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


def test_loader_routes_broker_documents_to_server_authoritative_private_intake():
    source = LOADER_PATH.read_text(encoding="utf-8")
    start = source.index("function patchFetch")
    end = source.index("function queueScan", start)
    patch_block = source[start:end]

    assert "brokerGate1UploadFile = uploadFile && isBrokerGate1Document(uploadFile.name, uploadFile.type) ? uploadFile : null;" in patch_block
    assert "if (sttUploadFile) {" in patch_block
    assert "nextInput = withProcessFalse(input);" in patch_block
    assert "brokerPrivateIntakeRequest(input, init, brokerGate1UploadFile)" in patch_block
    assert "nextInit = routed.init;" in patch_block
    assert "state.originalFetch(nextInput, nextInit)" in patch_block
    assert "normalizeBrokerPrivateIntakeResponse" in patch_block
    assert "normalizeBrokerGate1UploadedFile(" in patch_block


def test_loader_binds_only_gate2_completion_to_active_persistent_chat():
    source = LOADER_PATH.read_text(encoding="utf-8")
    start = source.index("async function bindBrokerGate2RequestToActiveChat")
    end = source.index("function withProcessFalse", start)
    binding_block = source[start:end]
    patch_start = source.index("function patchFetch")
    patch_end = source.index("function queueScan", patch_start)
    patch_block = source[patch_start:patch_end]

    assert (
        "const BROKER_GATE2_SOURCE_MODEL_ID = "
        "'broker_reports_gate2_source_fact_pipe';"
    ) in source
    assert "payload.model !== BROKER_GATE2_SOURCE_MODEL_ID" in binding_block
    assert "const chatId = persistentChatIdFromLocation();" in binding_block
    assert "chat_id: chatId" in binding_block
    assert "metadata:" in binding_block
    assert (
        "await bindBrokerGate2RequestToActiveChat(input, init)" in patch_block
    )
    assert "state.originalFetch(nextInput, nextInit)" in patch_block


def test_loader_private_intake_request_has_server_route_and_idempotency():
    source = LOADER_PATH.read_text(encoding="utf-8")
    start = source.index("function brokerIntakeIdempotencyKey")
    end = source.index("function normalizeUploadedFile", start)
    intake_block = source[start:end]

    assert "const BROKER_PRIVATE_INTAKE_PATH = '/api/v1/broker-reports/intake';" in source
    assert "state.brokerIntakeIdempotencyKeys.get(file)" in intake_block
    assert "state.brokerIntakeIdempotencyKeys.set(file, key)" in intake_block
    assert "headers.set('Idempotency-Key', brokerIntakeIdempotencyKey(file));" in intake_block
    assert "input: BROKER_PRIVATE_INTAKE_PATH" in intake_block
    assert "id: String(sourceId)" in intake_block
    assert "source_id: String(sourceId)" in intake_block
    assert "broker_reports_private_intake: true" in intake_block


def test_loader_broker_action_uses_only_protected_private_intake_action():
    source = LOADER_PATH.read_text(encoding="utf-8")

    assert (
        "const BROKER_GATE1_ACTION_ID = 'broker_reports_private_intake_action';"
        in source
    )
    assert "broker_reports_gate1_normalizer_action" not in source
    assert "Broker Reports private intake accepted. Ready to verify." in source
    assert "Verifying Broker Reports private intake..." in source
    assert (
        "Broker Reports source verified. Send the message to start processing."
        in source
    )


def test_loader_installs_broker_gate1_action_on_document_cards():
    source = LOADER_PATH.read_text(encoding="utf-8")
    start = source.index("function scanAttachmentCards")
    end = source.index("function installCardAction", start)
    scan_block = source[start:end]

    assert "isCandidateMedia(file.filename, file.mime_type)" in scan_block
    assert "isBrokerGate1Document(file.filename, file.mime_type)" in scan_block
    assert "installBrokerGate1CardAction(card, file);" in scan_block
    assert "card.dataset.brokerGate1Card !== '1'" in scan_block


def test_loader_broker_gate1_recovers_file_refs_from_files_api():
    source = LOADER_PATH.read_text(encoding="utf-8")
    start = source.index("async function refreshBrokerGate1Files")
    end = source.index("async function selectedModelId", start)
    refresh_block = source[start:end]

    assert "fetcher('/api/v1/files/', { cache: 'no-store' })" in refresh_block
    assert "rememberFilesFromListPayload(payload)" in refresh_block
    assert "normalizeBrokerGate1FileRecord(item)" in source
    assert "payload && Array.isArray(payload.items)" in source


def test_loader_broker_gate1_matches_truncated_visible_attachment_text():
    source = LOADER_PATH.read_text(encoding="utf-8")
    start = source.index("function fileMatchesElementText")
    end = source.index("function findCardFile", start)
    match_block = source[start:end]

    assert "haystack.includes(filename)" in match_block
    assert "const base = filename.replace" in match_block
    assert "const prefixLength = Math.min(18, Math.max(8, base.length));" in match_block
    assert "haystack.includes(prefix)" in match_block


def test_loader_broker_gate1_has_composer_panel_fallback():
    source = LOADER_PATH.read_text(encoding="utf-8")
    start = source.index("function scanBrokerGate1ComposerPanel")
    end = source.index("function scheduleBrokerGate1FileRefresh", start)
    panel_block = source[start:end]

    assert '[data-broker-gate1-composer-panel="1"]' in panel_block
    assert "root.appendChild(panel)" in panel_block
    assert "runBrokerGate1(files[0], button, status)" in panel_block
    assert "Files: ${files.length}" in panel_block


def test_loader_broker_gate1_action_posts_explicit_file_refs_to_action():
    source = LOADER_PATH.read_text(encoding="utf-8")
    start = source.index("async function callBrokerGate1Action")
    end = source.index("function extractTranscriptRef", start)
    action_block = source[start:end]

    assert "fetch(BROKER_GATE1_ACTION_URL" in action_block
    assert "files: files.map((file) => ({" in action_block
    assert "id: file.id" in action_block
    assert "filename: file.filename" in action_block
    assert "mime_type: file.mime_type" in action_block
    assert "appendToComposer(content)" in action_block
    assert "submitComposer" not in action_block
    assert "No uploaded file refs were visible" in action_block


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
    assert "const markdown = await fetchCanonicalMessageMarkdown(chatId, messageId);" in request_block
    assert "const html = extractScopedMessageHtml(content);" in request_block
    assert "message_markdown: markdown" in request_block
    assert "message_html: html" in request_block
    assert "source: markdown ? 'openwebui_chat_api' : 'dom'" in request_block
    assert "formatting_profile: hasStructuredSource ? 'semantic_chat_v1' : 'simple_mvp'" in request_block
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
    assert "collectCanonicalMessages(candidates, chat.history && chat.history.messages)" in fetch_block
    assert "collectCanonicalMessages(candidates, payload.messages)" in fetch_block
    assert "collectCanonicalMessages(candidates, payload.history && payload.history.messages)" in fetch_block
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
