# STT v2 Diarization Proof Contract

Status: Gate 1 acceptance contract.

Date: 2026-07-02.

Scope: LemonFox speaker-label runtime proof and normalized transcript evidence
for STT v2 Gate 1.

## 1. Purpose

Prove that runtime diarization is real, normalized and safe before building
speaker-aware post-processing.

Gate 1 does not implement:

- prompt catalog;
- quick actions;
- post-processing;
- DOCX;
- chunking.

## 2. Source Basis

External:

- LemonFox STT API: https://www.lemonfox.ai/apis/speech-to-text

Provider facts to verify in runtime:

- `speaker_labels=true` enables diarization;
- `response_format=verbose_json` is required to access speaker labels;
- word timestamps require `timestamp_granularities[]=word` and `verbose_json`;
- direct upload is documented as limited to 100 MB;
- URL input is documented as up to 1 GB.

Local:

- `services/stage2-stt/stage2_stt/config.py`
- `services/stage2-stt/stage2_stt/lemonfox.py`
- `services/stage2-stt/stage2_stt/contracts.py`
- `services/stage2-stt/stage2_stt/runtime.py`
- `docs/stage2/blueprints/STT_V2_TRANSCRIPT_POSTPROCESSING.blueprint.md`

## 3. Runtime Configuration

Gate 1 test runtime must set:

```text
STAGE2_LEMONFOX_ENABLE_SPEAKER_LABELS=true
```

Provider request must include:

```text
speaker_labels=true
response_format=verbose_json
```

If word-level speaker proof is required and supported:

```text
timestamp_granularities[]=word
```

## 4. Capability Proof

Required capability evidence:

- capabilities endpoint returns `supports_speaker_labels=true`;
- provider capability profile reflects speaker-label support;
- capability response contains no provider secret or raw env value;
- if speaker labels are disabled, capability must show that state clearly.

Recommended endpoint:

```text
GET /stage2-api/transcription/capabilities
```

## 5. Synthetic Audio Fixture

Use synthetic two-speaker audio with deterministic content.

Requirements:

- at least two alternating speaker turns;
- clear separation between turns;
- short enough for direct upload and fast proof;
- no personal/sensitive content;
- stable transcript phrases suitable for test assertions.

Suggested content:

```text
Speaker A: Project alpha starts on Monday.
Speaker B: I will prepare the checklist.
Speaker A: Please confirm the deployment window.
Speaker B: The deployment window is Thursday morning.
```

The proof report must record:

- fixture generation method or fixture file path;
- duration;
- mime type;
- checksum;
- selected output profile.

## 6. Expected Normalized Output

`TranscriptResultV1` must preserve:

```text
text
segments[]
segments[].text
segments[].start_seconds
segments[].end_seconds
segments[].speaker
segments[].words[]
segments[].words[].text
segments[].words[].start_seconds
segments[].words[].end_seconds
segments[].words[].speaker
warnings[]
```

Required assertions:

- at least two distinct non-null speaker labels are present when provider returns
  speaker data;
- segment speakers are normalized into `segments[].speaker`;
- word speakers are normalized into `words[].speaker` when provider returns word
  speakers;
- absence of word speaker data does not fail segment-level proof;
- normalized speaker labels remain generic labels, not invented real names.

## 7. Speaker-labeled Projection

If Gate 1 proof creates `TranscriptProjectionV1`, it must:

- derive only from normalized `TranscriptResultV1`;
- use `segments[].speaker` and/or `words[].speaker`;
- not use raw provider JSON;
- not invent participant names;
- include warnings when speaker labels are absent or incomplete.

Projection is optional for Gate 1 unless used as proof that downstream inputs
can be speaker-labeled without provider payload access.

## 8. No Raw Provider Leak Proof

Proof must show raw LemonFox payload is absent from:

- OpenWebUI chat output;
- Action output;
- loader-visible data;
- ordinary sidecar logs;
- product artifact rows;
- `TranscriptProjectionV1`;
- proof report excerpts unless explicitly redacted.

Allowed evidence:

- grep/rg over logs/artifacts for known raw-payload markers;
- structured test asserting Action output only includes safe transcript content;
- database inspection showing no raw provider JSON in product artifact rows.

## 9. Failure Behavior

If provider does not return speaker labels:

- transcript remains valid;
- warning is recorded;
- Gate 1 speaker-label proof is Not Done;
- no raw provider fallback parsing outside the adapter is allowed.

If `STAGE2_LEMONFOX_ENABLE_SPEAKER_LABELS=false`:

- capability must report speaker labels disabled;
- Gate 1 cannot be marked Done.

## 10. Acceptance Criteria

Gate 1 is accepted when:

- test runtime has `STAGE2_LEMONFOX_ENABLE_SPEAKER_LABELS=true`;
- capabilities show speaker support;
- provider request uses `speaker_labels=true` and `verbose_json`;
- synthetic two-speaker audio proof exists;
- normalized `TranscriptResultV1` contains speaker labels;
- no raw provider leak proof passes;
- flat transcript output remains backward compatible.
