# OpenWebUI ADR-0004 STT Proxy Boundary Review Report

Date: 2026-06-18
Repo: `corp-openweb ui`
Scope: ADR-0004 STT proxy boundary review preparation

## 1. Summary

Prepared `ADR-0004 STT Proxy Boundary` for human review.

The ADR now states the browser / Stage 2 backend / STT provider boundary,
compares five options, recommends `Option B. Server-side STT proxy/job service`,
rejects direct browser-to-provider calls, keeps API keys server-side only and
lists draft internal contracts plus endpoint boundaries.

No implementation was started. No backend code, frontend code, provider setup,
compose/env/scripts, production runtime or `.env` files were read or changed.

Important blocker:

- the actual existing ffmpeg workflow artifact is not present in this repo;
- ADR-0004 is reviewable as a boundary decision, but implementation readiness is
  blocked by artifact inspection.

## 2. Files Reviewed

Required files reviewed:

- `README.md`
- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md`
- `docs/stage2/README.md`
- `docs/stage2/CONTRACT_BOUNDARIES.md`
- `docs/stage2/IMPLEMENTATION_GATES.md`
- `docs/stage2/decisions/README.md`
- `docs/stage2/decisions/ADR-0004-stt-proxy-boundary.md`
- `docs/stage2/blueprints/TRANSCRIPTION_STT.blueprint.md`
- `docs/stage2/research/TRANSCRIPTION_STT_RESEARCH.md`
- `docs/stage2/research/FFMPEG_BROWSER_WORKFLOW_RESEARCH.md`
- `docs/stage2/research/LEMONFOX_STT_RESEARCH.md`
- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`
- `docs/stage2/acceptance/TEST_DATA_REQUIREMENTS.md`
- `docs/reports/2026-06-18/OPENWEBUI_STAGE2_RESEARCH_ACTUALIZATION.report.md`
- `docs/reports/2026-06-18/OPENWEBUI_STAGE2_DOMAIN_BOUNDARIES_AND_FORMAT_REFINE.report.md`
- `docs/reports/2026-06-18/OPENWEBUI_STAGE2_RAW_MARKDOWN_PHYSICAL_FORMAT_PROOF.report.md`

Additional related files reviewed for sync:

- `docs/stage2/CONTEXT_INDEX.md`
- `docs/stage2/ENGINEERING_BACKLOG.md`
- `docs/stage2/ROADMAP.md`

No required file was missing.

## 3. Existing Research Reused

Reused Stage 2 research from 2026-06-18:

- `TRANSCRIPTION_STT_RESEARCH`:
  native OpenWebUI STT exists, Lemonfox can be a priority candidate, but PRD-1
  transcription needs server-side proxy/adapter boundaries.
- `FFMPEG_BROWSER_WORKFLOW_RESEARCH`:
  ffmpeg.wasm is viable as browser media preprocessing, but the actual existing
  workflow artifact was not present in this repository.
- `LEMONFOX_STT_RESEARCH`:
  Lemonfox has an OpenAI-compatible transcription endpoint, Russian support,
  audio/video formats, diarization-related parameters, callbacks and EU endpoint
  option, but it still needs a server-side proxy for keys, usage and policy.
- `CONTRACT_BOUNDARIES`:
  Stage 2 custom capabilities must stay behind explicit backend contracts.
- `IMPLEMENTATION_GATES`:
  STT proxy boundary approval and artifact inspection are required before
  implementation planning.

No broad new market/provider research was performed. The existing research was
already current for this Stage 2 pass and the task explicitly asked to avoid
starting research from zero.

## 4. Additional Verification Performed

Local verification performed:

- checked the git working tree before edits;
- listed repository files with `rg --files`;
- searched for ffmpeg/STT/transcription/Lemonfox references across repo docs;
- searched outside docs and markdown for implementation files related to
  `ffmpeg`, `ffmpeg.wasm`, `transcription`, `transcript`, `stt`,
  `speech-to-text` and `Lemonfox`;
- checked file-name matches for ffmpeg/transcription/STT terms;
- confirmed the prior raw-markdown proof report exists locally but was not yet
  tracked by git.

External verification was not performed in this pass because the ADR uses the
already collected 2026-06-18 Stage 2 research and does not add new provider
claims beyond that research.

## 5. FFMPEG Workflow Artifact Inspection

Result:

- actual ffmpeg workflow artifact not present in this repo.

Evidence:

- non-doc search found no implementation code or package/example files for
  ffmpeg/STT/transcription;
- filename search found only documentation paths;
- existing Stage 2 research already stated that the customer/executor ffmpeg
  workflow was not present in this repository and was not inspected.

Contract extraction:

- not possible from this repo.

ADR-0004 now records `blocked by artifact inspection` and lists the contract
fields required from the real artifact:

- supported input formats;
- output format and output MIME/content type;
- whether output is mp3, wav, m4a, webm or another format;
- browser and mobile support;
- max observed file size and duration;
- ffmpeg core version and asset hosting model;
- worker model;
- progress event shape;
- cancellation behavior;
- error and timeout behavior;
- licensing and core asset hosting notes.

## 6. ADR Changes

Updated:

- `docs/stage2/decisions/ADR-0004-stt-proxy-boundary.md`

Major changes:

- kept `Status: Proposed`;
- added full context/problem/decision-needed framing;
- compared five options:
  - native OpenWebUI STT only;
  - server-side STT proxy/job service;
  - direct browser-to-provider call;
  - external standalone transcription tool;
  - deep OpenWebUI fork;
- recommended server-side STT proxy/job service;
- rejected direct browser-to-provider calls;
- defined browser / Stage 2 backend / STT provider ownership;
- stated missing ffmpeg artifact and `blocked by artifact inspection`;
- added draft internal contracts;
- added draft endpoint boundary;
- added runtime proof checklist;
- added customer/operator input checklist;
- preserved non-goals and implementation stop rules.

Synced related docs:

- `README.md`
- `docs/stage2/CONTRACT_BOUNDARIES.md`
- `docs/stage2/IMPLEMENTATION_GATES.md`
- `docs/stage2/ENGINEERING_BACKLOG.md`
- `docs/stage2/CONTEXT_INDEX.md`
- `docs/stage2/README.md`
- `docs/stage2/blueprints/TRANSCRIPTION_STT.blueprint.md`

## 7. Recommended Option

Recommended option:

`Option B. Server-side STT proxy/job service`.

Rationale:

- keeps STT provider keys server-side;
- centralizes auth/session, permissions, data policy, limits and retention;
- normalizes transcript output before UI/templates see it;
- normalizes provider errors into stable reason codes;
- supports progress, cancel, retry and long-running jobs;
- supports usage events and future cost visibility;
- keeps Lemonfox/OpenAI/future STT provider details behind adapters;
- matches Stage 2 domain isolation and backend-first delivery.

Caveats:

- native OpenWebUI STT can still be tested as a baseline;
- proxy scope can be reduced only if native STT proves all PRD-1 acceptance
  criteria;
- direct browser-to-provider remains rejected;
- deep OpenWebUI fork is not the first path;
- final UI implementation waits for backend contract and runtime proof.

## 8. Open Questions

Open questions carried into ADR-0004:

- How will OpenWebUI session/auth be propagated to the Stage 2 backend?
- Where are prepared audio blobs temporarily stored?
- What are max file size and duration limits?
- What is cancellation behavior for local ffmpeg work and server/provider work?
- Which transcript fields are mandatory for first acceptance?
- How are speaker labels and timestamps normalized?
- How are provider errors mapped into stable reason codes?
- How are usage events emitted and reviewed?
- What retention applies to source media, prepared audio and transcript?
- Is callback/async provider flow required in Practical Stage 2 or deferred?
- Can native OpenWebUI STT reduce proxy scope after baseline proof?

## 9. Runtime Proofs Needed

Runtime proofs required before implementation:

- deployed/staging OpenWebUI version and native STT baseline;
- auth/session propagation option to Stage 2 backend;
- user/group permission check source;
- Lemonfox smoke with approved test key and audio;
- existing ffmpeg workflow output contract;
- desktop and mobile prepared-audio output;
- practical max file size and duration limits;
- unsupported/large-file error behavior;
- transcript result returned/stored without leaking raw provider details;
- sample `UsageEventV1` emission;
- no STT API key in browser bundle, browser storage or browser network logs.

## 10. Customer/Operator Inputs Needed

Required inputs:

- existing ffmpeg workflow repo/path/artifact;
- minimal demo or runnable instructions;
- short audio sample;
- short video sample;
- large audio/video sample;
- expected templates for summary, protocol, tasks, decisions and follow-up;
- retention preference for source media, prepared audio and transcript;
- approved STT provider/account path;
- speaker labels and timestamps requirement;
- maximum acceptable processing time;
- whether EU processing is required.

## 11. Non-Goals Preserved

Preserved non-goals:

- no implementation;
- no backend code;
- no frontend code;
- no Lemonfox setup;
- no real API keys;
- no `.env` read;
- no production changes;
- no compose/env/scripts changes;
- no OpenWebUI fork;
- no ADR acceptance without human review;
- no claim that ffmpeg artifact was inspected.

## 12. Final Status

Final status:

`ADR-0004 blocked by missing ffmpeg artifact`

Interpretation:

- ADR-0004 is now suitable for human review as a Proposed boundary decision;
- implementation readiness and final approval are blocked until the actual
  ffmpeg workflow artifact is provided and inspected, or a replacement
  preprocessing contract is approved.
