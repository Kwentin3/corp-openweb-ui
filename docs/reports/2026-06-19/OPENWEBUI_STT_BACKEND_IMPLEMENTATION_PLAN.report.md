# OpenWebUI STT Backend Implementation Plan Report

Date: 2026-06-19

## 1. Summary

Created a compact implementation plan for the first backend slice of Stage 2
STT. The plan is a developer start package, not implementation.

No backend code, frontend code, provider setup, API keys, `.env`, compose,
scripts or production configuration were changed for this task.

## 2. Files reviewed

Required reading used:

- `docs/stage2/decisions/ADR-0004-stt-proxy-boundary.md`
- `docs/stage2/config/STT_ENV_CONTRACT.md`
- `docs/stage2/CONTRACT_BOUNDARIES.md`
- `docs/stage2/blueprints/TRANSCRIPTION_STT.blueprint.md`
- `docs/stage2/research/LEMONFOX_STT_RESEARCH.md`
- `docs/stage2/research/FFMPEG_WORKFLOW_ARTIFACT_INSPECTION.md`
- `docs/stage2/IMPLEMENTATION_GATES.md`
- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`

Optional broad PRD/research docs were not needed.

## 3. Implementation plan created

Created:

- `docs/stage2/implementation/STT_BACKEND_IMPLEMENTATION_PLAN.md`

The document stays under the requested 500-line target and is structured for an
agent/developer starting backend discovery and first implementation slices.

## 4. Key scope

Included in the first backend slice:

- STT env/config loading;
- provider capability profile;
- STT Provider Adapter Factory;
- `LemonfoxSttAdapter` proof-oriented plan;
- runtime capabilities endpoint;
- output profile validation;
- prepared-audio size validation;
- storage mode path `auto|s3|none`;
- transcription job model;
- cancel state model;
- usage event draft;
- backend validation/error model.

Excluded:

- final UI;
- OpenWebUI fork;
- browser ffmpeg implementation;
- OCR;
- web-search;
- manager visibility;
- hard billing/gateway;
- data masking;
- production-ready retention/audit archive.

## 5. Implementation slices

The plan defines seven backend slices:

1. Config and capability model.
2. Lemonfox adapter proof.
3. Output profile validation.
4. Storage mode logic.
5. Job model and cancel states.
6. Runtime capabilities endpoint.
7. Minimal smoke / tests.

Each slice includes acceptance notes and keeps real Lemonfox API calls optional
until an operator supplies a key outside Git.

## 6. Stop conditions

The plan requires the agent to stop if:

- no backend/domain-service location is available without deep fork;
- auth/session propagation is unclear;
- env cannot be read safely server-side;
- there is no safe place for provider secrets;
- Lemonfox key is required but not provided;
- `s3` is selected but bucket/config/health is unavailable;
- frontend changes are required before backend contract;
- production/compose/env/scripts changes are required without a separate
  command;
- any path would put provider key in browser, `NEXT_PUBLIC_*`, logs or tests;
- wasm/core binaries would need to be vendored.

## 7. Navigation updates

Updated:

- `docs/stage2/README.md`
- `docs/stage2/CONTEXT_INDEX.md`
- `docs/stage2/ENGINEERING_BACKLOG.md`
- `README.md`

The root README received a single link in the existing Stage 2 navigation block.

## 8. Non-goals preserved

Preserved:

- no backend implementation;
- no frontend implementation;
- no provider setup;
- no API keys;
- no `.env`;
- no compose/env/scripts changes;
- no production changes;
- no broad PRD repetition;
- no new architecture replacing ADR-0004.

## 9. Final status

STT backend implementation plan is ready for review. No implementation was
started.
