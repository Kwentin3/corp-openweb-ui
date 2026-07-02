# STT v2 Gate 5 Prompt Access And Version Proof

Status: Gate 5 proof report.

Date: 2026-07-02.

## 1. Verdict

```text
Gate 5: Pass
Target runtime: root@178.72.138.169:/opt/openwebui-prd0
Server branch/base commit: main @ e89b97e
Runtime image id: sha256:44e81ffc1eeb676ae3f4bbfe018627d518dd19a80940d42db8089e4998a0f60e
```

Prompt access, missing/deleted prompt behavior, prompt version/hash changes,
loader-visible reference denial and old-result hash preservation are proven on
target runtime.

## 2. Runtime Prompt Proof Setup

OpenWebUI DB backup before temporary Gate 5 access proof prompts:

```text
/app/backend/data/runtime-backups/webui-before-stt-v2-gate5-prompt-proof-20260702T120000Z.db
```

OpenWebUI DB backup before temporary Gate 5 successful version proof prompt:

```text
/app/backend/data/runtime-backups/webui-before-stt-v2-gate5-success-proof-20260702T1225Z.db
```

Temporary access proof prompt ids:

```json
[
  "stage2-gate5-public-proof-20260702",
  "stage2-gate5-private-proof-20260702",
  "stage2-gate5-deleted-proof-20260702"
]
```

Temporary successful version proof prompt id:

```text
stage2-gate5-version-success-proof-20260702
```

All temporary proof prompts were removed after the proof:

```json
{
  "cleanup_prompt_ids": [
    "stage2-gate5-public-proof-20260702",
    "stage2-gate5-private-proof-20260702",
    "stage2-gate5-deleted-proof-20260702"
  ],
  "remaining": 0
}
```

```json
{
  "prompt_id": "stage2-gate5-version-success-proof-20260702",
  "remaining": 0
}
```

Temporary successful version proof result artifacts were expired:

```json
[
  {
    "artifact_ref_prefix": "art_",
    "expires_at_set": true,
    "expired_now": true,
    "deleted_at_set": false
  },
  {
    "artifact_ref_prefix": "art_",
    "expires_at_set": true,
    "expired_now": true,
    "deleted_at_set": false
  }
]
```

## 3. Target Runtime Access Proof

Sidecar proof:

```json
{
  "deleted_code": "prompt_not_found",
  "deleted_status": 404,
  "missing_code": "prompt_not_found",
  "missing_status": 404,
  "private_code": "prompt_access_denied",
  "private_execute_code": "prompt_access_denied",
  "private_execute_status": 403,
  "private_status": 403,
  "public_body_leaked": false,
  "public_has_prompt_body_field": false,
  "public_hash": "c3ae2e34f18cb63197402d2c6bcf938c2bf9a312d285c980c12b173114177667",
  "public_status": 200,
  "public_version": "gate5-v1",
  "ref_only_execute_code": "artifact_scope_unverified",
  "ref_only_execute_status": 403,
  "secret_markers_found": false
}
```

This proves:

- unauthorized users cannot read restricted prompts;
- unauthorized users cannot execute restricted prompts at the sidecar boundary;
- loader-visible `transcript_ref` without full artifact context is rejected;
- deleted and missing prompts return typed `prompt_not_found`;
- prompt body is not returned in metadata responses;
- no secret markers were printed.

## 4. Metadata Version And Change Proof

The temporary public proof prompt was updated from `gate5-v1` to `gate5-v2`.
The sidecar saw the new version/hash immediately, using the same adapter path:

```json
{
  "body_leaked": false,
  "has_prompt_body_field": false,
  "hash": "635d3bbff032311aa02de683a0cb140ce925d31ecdc49f690e7ab0a01053e132",
  "hash_len": 64,
  "secret_markers_found": false,
  "status": 200,
  "version": "gate5-v2"
}
```

No long-lived prompt body cache is used in loader or sidecar config.

## 5. Successful Old-Result Version Proof

The temporary successful version proof prompt was executed once as
`gate5-success-v1`, then changed to `gate5-success-v2` and executed again. The
first stored `PostProcessingResultV1` preserved its original prompt version and
hash.

First execution:

```json
{
  "first_status": 200,
  "first_hash": "88fc2aa0207dd12c0db79e5dd6545dae25b67122dc139b32fa9569a308727b50",
  "first_version": "gate5-success-v1",
  "first_text_len": 135,
  "secret_markers_found": false
}
```

Second execution and stored-first-result verification:

```json
{
  "first_kept_old_hash": true,
  "first_kept_old_version": true,
  "first_meta_hash": "88fc2aa0207dd12c0db79e5dd6545dae25b67122dc139b32fa9569a308727b50",
  "first_stored_hash": "88fc2aa0207dd12c0db79e5dd6545dae25b67122dc139b32fa9569a308727b50",
  "first_stored_version": "gate5-success-v1",
  "second_hash": "4a3b4c72452aba0759a584128bc452e318399ca298b021a1996502302ca3ebc2",
  "second_status": 200,
  "second_text_len": 111,
  "second_version": "gate5-success-v2",
  "secret_markers_found": false
}
```

## 6. Tests

Focused tests:

```text
python -m pytest -q services/stage2-stt/tests/test_prompt_catalog.py services/stage2-stt/tests/test_post_processing.py services/stage2-stt/tests/test_post_processing_routes.py
result: 16 passed in 2.04s
```

Full sidecar suite:

```text
python -m pytest -q services/stage2-stt/tests
result: 64 passed in 3.46s
```

## 7. Acceptance Status

| Requirement | Status | Evidence |
| --- | --- | --- |
| unauthorized user cannot see restricted prompt | Pass | target private prompt returned 403 `prompt_access_denied` |
| unauthorized user cannot execute restricted prompt | Pass | target execute returned 403 `prompt_access_denied` before LLM |
| loader-visible ref cannot bypass sidecar checks | Pass | target execute returned 403 `artifact_scope_unverified` |
| access checked on execution boundary | Pass | target proof and focused tests |
| missing/deleted prompt typed safe error | Pass | target returned 404 `prompt_not_found` |
| changed prompt changes version/hash | Pass | target `gate5-v1` -> `gate5-v2`, hash changed |
| old processed result keeps old hash | Pass | target successful v1/v2 execution proof |
| renamed prompt does not break stable routing | Pass | focused test |
| cache invalidation/TTL strategy clear | Pass | no body cache in loader/sidecar; adapter reads OpenWebUI DB per request |
| prompt body not stored long-lived in loader/config | Pass | no prompt body in metadata; code uses prompt ref/body hash |
| full rendered prompt not stored by default | Pass | tests and artifact storage code store result fields, not rendered prompt |
| access failure fail closed | Pass | typed 403s |
| errors chat-safe | Pass | Action formats safe error content |
| OpenWebUI core not patched | Pass | prompt rows and Action function only |

## 8. Known Limitations

- Prompt catalog still uses read-only SQLite access to OpenWebUI `webui.db`
  behind `PromptCatalogAdapter`; an HTTP adapter can replace it later without
  changing route contracts.

## 9. Final Gate 5 Verdict

```text
Gate 5: Pass
```
