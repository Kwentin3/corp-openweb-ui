# OfficeCLI OpenAPI DOCX proof

Revision: `568a0dc50ed535428c77d3976ad1e27827014bf4`

## Observed native path

- A least-privileged `test` user used the temporary native Global Tool Server `officecli` in a normal OpenWebUI chat.  It remains a Session-authenticated, internal-only sidecar connection.
- Initial failures used the default non-native function-call path.  Static inspection shows that it builds one tool-planning request and does not perform a fresh selection round after `inspect`; actual upstream provider request bodies are deliberately not logged or intercepted, so their exact payload is `NOT_VERIFIED`.
- One fresh chat used `Claude Opus 5`, OpenWebUI's per-chat **Native** function-calling setting, and a short adapter-use instruction.  It did not add Word authoring rules: OfficeCLI's official skill/help remained the reference.
- Two ordinary user requests (neither named a tool) completed sequentially.  On each turn the model loaded/read the official material as needed, inspected the native attachment, invoked `apply_office_batch`, and OpenWebUI attached the returned DOCX to that assistant message.
- The second turn resolved the first assistant attachment and produced `officecli-451-updated-v2.docx`; the user did not upload a file again.

## Artifact checks

- The original fixture was `officecli-451-anonymized-source.docx`; the two native assistant attachments had distinct native file identities and SHA-256 values.  The final file hash is `2b7a0e46be712b5923b9a87708e0e92f089e1d55955b18b943dbff8b022c1065`.
- Word opened both source and final DOCX read-only.  Both have 21 Word paragraphs.
- At body indexes 5 and 6 only, the final text is respectively `3.2. Практическая часть — продолжение` and `Провести демонстрацию обновлённого сценария редактирования документа.`
- All other body paragraphs, the table, header, footer, and run-format signatures are equal to the source.  The target runs retained their formatting (including the bold 13pt heading and 12pt body run).
- OfficeCLI rewrote several normal DOCX package XML parts while saving.  Byte equality of non-target ZIP members is therefore not claimed; the preservation conclusion is document-structure/text/format evidence above.
- The sidecar has `OFFICECLI_SKIP_UPDATE=1` and `OFFICECLI_NO_AUTO_RESIDENT=1`; bounded execution was reported by both successful `apply_office_batch` calls.

## Acceptance limit

R5's filename-collision regression and R6's internal-only/session-authenticated sidecar checks remain covered by the code and targeted tests.  R6 authentication is still a known proof limitation, not a user/passport/audit subsystem.

R7 is accepted for this narrow configured native-chat scenario: a user can make two natural-language edits with no re-upload and receive the real second DOCX.  This is not a claim that every model, default function-calling mode, or arbitrary chat configuration will autonomously select the tool.  No OpenWebUI core change, provider proxy/interceptor, model roulette, forced tool loop, or extra architecture was added.
