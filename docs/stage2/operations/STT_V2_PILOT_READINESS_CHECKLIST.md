# STT v2 Pilot Readiness Checklist

Status: controlled pilot checklist.

Date: 2026-07-02.

Use this checklist immediately before a controlled pilot run.

```text
[ ] OpenWebUI доступен
[ ] stage2-stt доступен
[ ] транскрибация работает
[ ] transcript_ref создаётся
[ ] ArtifactStore работает
[ ] два prompt-шаблона существуют
[ ] quick actions доступны
[ ] `Краткий пересказ` работает
[ ] `Протокол встречи` работает
[ ] long transcript получает safe refusal
[ ] message-level DOCX export доступен для completed assistant message
[ ] DOCX сохраняет markdown/table formatting через `semantic_chat_v1`
[ ] chunking отсутствует by design
[ ] SQLite PromptCatalogAdapter accepted as MVP/default
[ ] OpenWebUI API Adapter отложен
[ ] secrets не светятся
[ ] OpenWebUI core не патчился
[ ] known limitations записаны
```

Pilot blocker conditions:

- OpenWebUI unavailable.
- `stage2-stt` unavailable.
- Provider egress broken.
- ArtifactStore unavailable.
- No transcript reference after successful transcription.
- Prompt catalog returns zero templates.
- Both quick actions unavailable.
- Post-processing executor unavailable.
- Raw provider payload, prompt body or secrets visible to users.
- Message-level DOCX export is unavailable or fails browser save/open proof.
- Closing the issue requires chunking, API adapter or OpenWebUI core patch.

Known non-blocking MVP limitations:

- Specialized processed-result-only DOCX artifact path remains deferred; the
  generic message-level DOCX exporter is implemented.
- Chunking is deferred.
- OpenWebUI Prompt API Adapter is deferred.
- SQLite PromptCatalogAdapter remains accepted MVP/default.
- Only two MVP prompt templates are included.
- Authenticated browser-click proof can be replaced by this manual browser
  program plus runtime bridge proof when an agent cannot safely use a real
  browser session.
