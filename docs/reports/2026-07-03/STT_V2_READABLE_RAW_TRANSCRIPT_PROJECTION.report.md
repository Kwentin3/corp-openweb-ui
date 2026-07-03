# STT v2 Readable Raw Transcript Projection Report

Date: 2026-07-03

Status: implemented, pushed and deployed to PRD-0.

## Scope

This change makes the first raw STT response easier to read when LemonFox
returns diarized segments. It does not add post-processing, speaker-name
inference, DOCX changes or provider payload exposure.

## Problem

The LemonFox adapter can request and normalize speaker labels into
`TranscriptResultV1.segments[].speaker`, and artifact metadata already records
speaker-label counts. The OpenWebUI Action still rendered only
`result.text`, so multi-speaker meetings appeared as one flat paragraph.

## Contract Decisions

- Raw transcript chat display is a deterministic presentation projection.
- Source data is only normalized `TranscriptResultV1`.
- Provider labels such as `SPEAKER_00` are mapped to generic labels such as
  `Спикер 1` for the current transcript.
- Adjacent same-speaker segments may be merged for readability.
- If speaker labels are absent, the Action keeps the backward-compatible flat
  transcript output.
- Raw provider JSON, logs, secrets, prompt bodies and hidden config remain
  forbidden in chat output.

## Implementation

- `stage2_media_transcription_action.py` now formats the transcription result
  through `_format_transcript_result`.
- Speaker-aware formatting is used only when normalized segments contain
  speaker labels.
- The formatter renders timestamped speaker turns and merges adjacent segments
  with the same normalized speaker label.
- Flat fallback remains active for plain transcript results and for segment
  lists without speaker labels.

## Documentation Updates

- `STT_V2_ARTIFACT_CONTRACTS.md`: added raw transcript chat display projection
  rules and acceptance text.
- `STT_V2_TRANSCRIPT_POSTPROCESSING.blueprint.md`: clarified that raw chat
  output may use normalized projection rules but remains presentation-only.
- `STT_V2_GATE_1_2_ACCEPTANCE_MATRIX.md`: added `G1-DIA-011` and refined
  `BC-001`.
- `STT_V2_MANUAL_BROWSER_TEST_PROGRAM.md`: added browser check for readable
  generic speaker turns and flat fallback.

## Local Verification

```text
python -m pytest -q services/stage2-stt/tests/test_openwebui_action.py
11 passed in 0.64s

python -m pytest -q services/stage2-stt/tests
69 passed in 2.80s

python -m compileall -q services/stage2-stt
pass
```

## Server Deployment Proof

Implementation commit:

```text
c3ce6d1 feat: render diarized stt transcripts
```

Server git/deploy state:

```text
server_head=c3ce6d1
git status: ## main...origin/main
stage2-stt: rebuilt and recreated from compose-stage2-stt image
openwebui: restarted and healthy after Action DB update
public HTTPS: https://gpt.alpha-soft.ru returned HTTP 200
```

OpenWebUI Action deployment proof:

```text
function.id=stage2_media_transcription_action
rows_updated=1
db_sha256=6cbaba58ed566140185e46fe47d959b3453c8f7471698e0bd1e5ad4c3900be89
file_sha256=6cbaba58ed566140185e46fe47d959b3453c8f7471698e0bd1e5ad4c3900be89
has_formatter=True
has_generic_speaker_label=True
backup_dir=/opt/openwebui-prd0/backups/codex-stt-v2/20260703T084211Z-readable-raw-transcript
```

Runtime capability proof:

```text
supports_speaker_labels=True
provider_id=lemonfox
adapter_id=lemonfox
artifact_store_mode=sqlite
```

DB-executed formatter proof:

```text
[00:00-00:08] Спикер 1:
first fragment. continued.

[00:08-00:12] Спикер 2:
reply.
raw_provider_label_leaked=False
flat_fallback_leaked=False

flat_fallback=plain transcript
```

## Residual Notes

- The display still depends on provider diarization quality.
- Real speaker names remain out of scope for raw output; they can be handled by
  a separate prompt/action later.
- This change updates the OpenWebUI Action runtime surface, so deployment must
  update the Action content stored in OpenWebUI, not only the sidecar image.
