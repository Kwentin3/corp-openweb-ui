# STT v2 Gate 3 Prompt Catalog Proof

Status: Gate 3 proof report.

Date: 2026-07-02.

## 1. Verdict

```text
Gate 3: Pass
Target runtime: root@178.72.138.169:/opt/openwebui-prd0
Server branch/base commit: main @ e89b97e
Deployment source archive SHA256: fdb1f3f2c8ef5d87c089dbbe4f5956727a8c13be0f7d29642963fb2eea73ffd0
Runtime image id: sha256:c7ea98fdc6fb3bbe3988403b0205ba61c5d86ada38bf10da2eef5b40759fdc5d
```

Two native OpenWebUI Prompts now exist as the post-processing template source
of truth. The sidecar resolves them through `PromptCatalogAdapter` and exposes
only UI-safe metadata.

## 2. Runtime Wiring

Safe env/status values:

```text
IMPORT_PROMPT_CATALOG=OK
STAGE2_STT_PROMPT_CATALOG_MODE=openwebui_sqlite
STAGE2_STT_OPENWEBUI_PROMPT_DB_PATH=/openwebui-data/webui.db
STAGE2_STT_POSTPROCESSING_EXECUTOR_MODE=disabled
STAGE2_STT_POSTPROCESSING_OPENAI_MODEL=gpt-5.4-mini
STAGE2_STT_POSTPROCESSING_OPENAI_API_KEY=SET_NONEMPTY
```

The executor remains disabled for Gate 3. The API key status is present because
compose maps the existing server-local `OPENAI_API_KEY` into the sidecar for
Gate 4, but no secret value was printed.

Mount proof:

```text
stage2_stt_data /data/stage2-stt true
openwebui_data /openwebui-data false
```

`openwebui_data` is mounted read-only into the sidecar.

## 3. Seeded OpenWebUI Prompts

OpenWebUI DB backup before Gate 3 seed:

```text
/app/backend/data/runtime-backups/webui-before-stt-v2-gate3-20260702T1143.db
```

The first seed showed mojibake in prompt names through the remote transport, so
it was corrected with an ASCII/Unicode-escape seed. Backup before the correction:

```text
/app/backend/data/runtime-backups/webui-before-stt-v2-gate3-encoding-fix-20260702T1145.db
```

Active prompt metadata:

| Template | Command | OpenWebUI prompt id | Version id | Tags |
| --- | --- | --- | --- | --- |
| `stage2.stt.summary.v1` | `stt-summary` | `bee65fbb-c9ba-428e-b1e2-c1fdf8ee03b4` | `2900f208-806b-4517-be21-959995bf6b75` | `stage2-stt-v2`, `stt-post-processing`, `summary` |
| `stage2.stt.meeting_protocol.v1` | `stt-meeting-protocol` | `33fa981d-7342-4b70-a206-9aaa670b037b` | `64afd51f-9a54-4070-9470-74c75ae6d681` | `stage2-stt-v2`, `stt-post-processing`, `meeting-protocol` |

Both prompts have:

```json
{
  "template_kind": "post_processing",
  "requires_speakers": false,
  "chunkable": false
}
```

Prompt bodies are intentionally not copied into this report.

## 4. Sidecar Resolution Proof

Target runtime probe:

```json
{
  "by_command_prompt_hash_len": 64,
  "by_command_status": 200,
  "by_command_template_id": "stage2.stt.meeting_protocol.v1",
  "by_id_prompt_hash_len": 64,
  "by_id_status": 200,
  "by_id_template_id": "stage2.stt.summary.v1",
  "commands": [
    "stt-meeting-protocol",
    "stt-summary"
  ],
  "labels": [
    "\u041a\u0440\u0430\u0442\u043a\u0438\u0439 \u043f\u0435\u0440\u0435\u0441\u043a\u0430\u0437",
    "\u041f\u0440\u043e\u0442\u043e\u043a\u043e\u043b \u0432\u0441\u0442\u0440\u0435\u0447\u0438"
  ],
  "list_status": 200,
  "missing_code": "prompt_not_found",
  "missing_status": 404,
  "prompt_body_leaked": false,
  "secrets_printed": false,
  "status": "ok",
  "template_count": 2,
  "template_ids": [
    "stage2.stt.meeting_protocol.v1",
    "stage2.stt.summary.v1"
  ]
}
```

The sidecar proved:

- list templates;
- resolve by `template_id`;
- resolve by OpenWebUI `command`;
- missing prompt returns typed `prompt_not_found`;
- prompt body is not returned in metadata responses.

## 5. Version And History Proof

OpenWebUI prompt DB query without content:

```json
[
  {
    "command": "stt-meeting-protocol",
    "history_count": 2,
    "template_id": "stage2.stt.meeting_protocol.v1",
    "template_kind": "post_processing",
    "version_id": "64afd51f-9a54-4070-9470-74c75ae6d681"
  },
  {
    "command": "stt-summary",
    "history_count": 2,
    "template_id": "stage2.stt.summary.v1",
    "template_kind": "post_processing",
    "version_id": "2900f208-806b-4517-be21-959995bf6b75"
  }
]
```

`history_count=2` is expected because the encoding-fix seed created a new active
version after the initial mojibake seed.

## 6. Tests

```text
cd services/stage2-stt
python -m pytest -q
result: 57 passed in 2.52s
```

New focused tests:

- `tests/test_prompt_catalog.py`
- `tests/test_post_processing.py`
- `tests/test_post_processing_routes.py`

## 7. Acceptance Status

| Requirement | Status | Evidence |
| --- | --- | --- |
| Two OpenWebUI Prompts exist on target runtime | Pass | DB query, prompt ids and commands |
| OpenWebUI Prompt body is source of truth | Pass | body stored only in OpenWebUI prompt table/history |
| Prompt body not duplicated in loader/Action/sidecar config | Pass | sidecar stores ids/hash only; metadata probe has `prompt_body_leaked=false` |
| Stable routing key exists | Pass | `template_id`, `command`, `openwebui_prompt_id` |
| Tags/meta exist | Pass | `stage2-stt-v2`, `stt-post-processing`, `template_kind=post_processing` |
| Sidecar resolves both prompts | Pass | list/by-id/by-command probes |
| Quick action can reference prompt metadata | Pass | `PostProcessingTemplateV1` response contains ids/hash, not body |
| UI-safe template metadata only | Pass | metadata response has no prompt body |
| Access checked to current runtime extent | Pass | sidecar checks owner/admin/access grants; MVP prompts are public-read |
| Missing prompt typed error | Pass | `prompt_not_found`, HTTP 404 |
| Version/hash captured | Pass | `version_id`, 64-char `prompt_body_hash` |
| OpenWebUI core not patched | Pass | seed changed runtime prompt rows only |

## 8. Known Limitations

- Prompt catalog integration uses read-only SQLite access to OpenWebUI `webui.db`
  because no safe sidecar API token path is available yet. This is isolated
  behind `PromptCatalogAdapter` and can be replaced by an HTTP adapter later.
- The two MVP prompts are public-read for the pilot. Restricted prompt behavior
  is covered in Gate 5.
- Gate 3 does not execute prompts; executor remains disabled until Gate 4.

## 9. Final Gate 3 Verdict

```text
Gate 3: Pass
Next gate allowed: Gate 4 Two MVP Quick Actions With Auto-run
```
