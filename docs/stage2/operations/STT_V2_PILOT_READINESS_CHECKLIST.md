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
[ ] DOCX отсутствует by design
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
- Closing the issue requires DOCX, chunking, API adapter or OpenWebUI core patch.

Known non-blocking MVP limitations:

- DOCX is deferred.
- Chunking is deferred.
- OpenWebUI Prompt API Adapter is deferred.
- SQLite PromptCatalogAdapter remains accepted MVP/default.
- Only two MVP prompt templates are included.
- Authenticated browser-click proof can be replaced by this manual browser
  program plus runtime bridge proof when an agent cannot safely use a real
  browser session.
