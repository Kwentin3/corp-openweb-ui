# OpenWebUI STT Docs Implementation Drift Audit

Date: 2026-06-19

Scope: documentation-only audit after the Stage 2 STT backend, OpenWebUI media
attachment Action and browser ffmpeg.wasm normalization implementation reports.
No runtime, compose, env, frontend, backend, media or historical report files
were changed by this audit except living documentation and this report.

## 1. Summary

Living Stage 2 STT docs had drift from the latest implementation evidence:
several plan/probe docs still described backend routes, the OpenWebUI Action
path or broad browser normalization as future work. The docs now mark the
initial MVP implementation as implemented/proven while keeping ADR-0004
`Proposed` and preserving real production-hardening blockers.

Final verdict: `docs_actualized_no_material_drift_remaining`.

## 2. Implementation baseline used

Reports read:

- `OPENWEBUI_STT_FFMPEG_BROWSER_NORMALIZATION_IMPLEMENTATION.report.md`
- `OPENWEBUI_STT_FRONTEND_MEDIA_ACTION_PATCH.report.md`
- `OPENWEBUI_STT_RUNTIME_COMPLETION.report.md`
- `OPENWEBUI_STT_PLAYWRIGHT_UI_PROOF.report.md`
- `OPENWEBUI_STT_FFMPEG_INPUT_FORMAT_CONTRACT_REFINE.report.md`
- `OPENWEBUI_MEDIA_ATTACHMENT_STT_ACTION_REFINE.report.md`
- `OPENWEBUI_NATIVE_STT_UX_INTEGRATION_RESEARCH.report.md`
- `OPENWEBUI_STT_BACKEND_IMPLEMENTATION.report.md`
- `OPENWEBUI_ADR0004_LEMONFOX_CAPABILITIES_AND_RUNTIME_LIMITS.report.md`

Code/config/test surface inspected:

- `deploy/openwebui-static/loader.js`
- `deploy/openwebui-static/stage2-stt-normalization.json`
- `scripts/fetch-ffmpeg-wasm-assets.sh`
- `compose/openwebui.compose.yml`
- `services/stage2-stt/stage2_stt/config.py`
- `services/stage2-stt/stage2_stt/contracts.py`
- `services/stage2-stt/stage2_stt/runtime.py`
- `services/stage2-stt/stage2_stt/app.py`
- `services/stage2-stt/stage2_stt/lemonfox.py`
- `services/stage2-stt/tests/`

Key baseline facts:

- Static browser config selects `mp3_high_compat` and self-hosted ffmpeg.wasm
  assets.
- Sidecar config still defaults to `opus_webm_compact` with
  `mp3_high_compat` fallback.
- Sidecar job routes are private/internal and require internal auth.
- OpenWebUI public capabilities route is not exposed as sidecar JSON.
- No browser Lemonfox/provider key is part of the static config path.

## 3. Drift found

- ADR and boundary docs lacked a sticky implementation note, so future agents
  could treat already-built MVP routes/UI/browser normalization as still
  unstarted.
- `STT_BACKEND_IMPLEMENTATION_PLAN.md` still said no implementation had
  started.
- `STT_OPENWEBUI_MEDIA_ACTION_PROBE_PLAN.md` and
  `STT_FRONTEND_MEDIA_ACTION_PATCH_PLAN.md` still read as active probe/patch
  plans instead of historical baselines.
- Acceptance/gates/backlog mixed completed proof with blockers, especially
  OpenWebUI Action path and browser normalization.
- Runtime capabilities contract wording drifted from the implemented
  `declared_input_mime_prefixes` field.
- Stage 2 navigation did not put the latest runtime/ffmpeg implementation
  reports ahead of older research/probe reports.

## 4. Docs updated

- `README.md`
- `docs/stage2/README.md`
- `docs/stage2/CONTEXT_INDEX.md`
- `docs/stage2/CONTRACT_BOUNDARIES.md`
- `docs/stage2/IMPLEMENTATION_GATES.md`
- `docs/stage2/ENGINEERING_BACKLOG.md`
- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`
- `docs/stage2/blueprints/TRANSCRIPTION_STT.blueprint.md`
- `docs/stage2/config/STT_ENV_CONTRACT.md`
- `docs/stage2/contracts/STT_MEDIA_INPUT_NORMALIZATION_CONTRACT.md`
- `docs/stage2/decisions/ADR-0004-stt-proxy-boundary.md`
- `docs/stage2/implementation/STT_BACKEND_IMPLEMENTATION_PLAN.md`
- `docs/stage2/implementation/STT_FRONTEND_MEDIA_ACTION_PATCH_PLAN.md`
- `docs/stage2/implementation/STT_OPENWEBUI_MEDIA_ACTION_PROBE_PLAN.md`

Historical implementation/research reports were intentionally not edited.

## 5. Completed items now marked implemented/proven

- Prepared MP3 OpenWebUI Action path.
- OpenWebUI media attachment `Transcribe` static loader patch.
- Private `stage2-stt` sidecar job routes and internal auth boundary.
- Lemonfox live smoke through the sidecar path.
- Browser ffmpeg.wasm probe/normalization.
- Generated MP4 with audio proof.
- Generated WebM audio/video proof.
- Unsupported/decode-failed input safe visible error.
- No-audio media safe visible error.
- Self-hosted ffmpeg.wasm asset mode through OpenWebUI static assets.
- Private sidecar/no public sidecar JSON route.
- No browser-exposed Lemonfox/provider key.

## 6. Remaining pending items

- Mobile browser acceptance.
- Large/customer media, including practical 1 GB behavior.
- Low-memory browser behavior.
- Cancel during ffmpeg preprocessing.
- Final browser/internal duration-limit policy.
- Opus WebM/OGG provider proof if Opus is promoted to default.
- Production storage mode, retention and cleanup policy.
- Persistence beyond the current in-memory job store.
- Transcript history/export/workflow.
- Dedicated meeting workflow.
- Source media retention policy.
- Multi-user/group permission hardening.
- Richer progress/cancel UX and provider-side cancellation proof.
- Licensing/ops/cache/rollback hardening for ffmpeg assets.

## 7. Sticky comments added

Sticky implementation notes were added to the ADR, env contract, input
normalization contract, boundary map, blueprint and implementation plans. The
notes explicitly say which MVP slices are implemented/proven and which
production-hardening items remain pending.

## 8. Stale phrases checked

The user-provided stale phrase set was checked against living docs under
`docs/stage2` and root `README.md`. After edits, there were no hits in those
living docs. Historical reports may still contain old blocker/status phrases
and were left intact by design.

Additional active-plan stale checks found no living-doc hits for uncontextualized
phrases such as an unstarted backend implementation, future-only broad
normalization, or deferred private capabilities implementation.

## 9. Tests/checks run

- `git status --short`
- `git diff --stat`
- `rg` stale-phrase checks against `docs/stage2` and root `README.md`

Final `git diff --check`, final stale-phrase grep, docs-only staged scope check,
commit and push were run after this report was created.

No runtime services, provider calls or media tests were run in this docs-only
audit.

## 10. Final documentation status

Living Stage 2 STT docs now reflect the implemented MVP path and preserve the
real production gaps. ADR-0004 remains `Proposed`; the docs do not mark Stage 2
STT as production-accepted. The next work should start from the updated
hardening backlog rather than re-planning the closed backend route, Action path
or browser normalization slices.
