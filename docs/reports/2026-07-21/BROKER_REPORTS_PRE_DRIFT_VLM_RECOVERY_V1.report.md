# Broker Reports Pre-Drift VLM Recovery v1

Status: `LOCATED_AND_CLASSIFIED`

Evidence date: `2026-07-21`

Verified implementation revision: `f94abcdeb94c0ae07ec09e137d646198c12d9018`

Machine map:
`BROKER_REPORTS_PRE_DRIFT_VLM_RECOVERY_MAP.v1.safe.json`.

## Plain answer

The earlier Gemini/OpenAI capability was not lost. Its provider foundation,
adapters, crop contracts, prompts, schemas, runners, validators, tests and
reports are ancestors of `origin/main` and therefore are also present on the
clean candidate. What never happened was production integration of the
dual-VLM research runner into the maintained Gate 1/2 Functions.

The recovery program misread this boundary as absence and added a second
contract scaffold in `d7cc52d`. That scaffold is not authoritative: it has a
large proposal schema and validator, but no OpenWebUI credential resolver, no
concrete live Gemini/OpenAI transport boundary, no dual-provider comparison,
no token-preflight lineage, and no live benchmark evidence. It is excluded
from the clean candidate.

## Exact history

| Commit | Recovered responsibility | State |
| --- | --- | --- |
| `296c814` | initial Gate 2 provider factory | production implemented |
| `d68d9ee` | Claude/Gemini provider-route qualification | live-verified foundation |
| `6924c18` | provider profiles and execution metadata | production implemented |
| `894c602` | native provider transport | production implemented |
| `cc095df` | OpenWebUI-owned credential reuse | production implemented |
| `7cae51e` | dual-VLM factory, Gemini/OpenAI adapters, crops, fact prompts/schemas, runner and tests | live-provider benchmark only |
| `146b04b`, `0c96977`, `47cf25c` | local review evolution and sealed benchmark report | private proof / benchmark evidence |
| `747c808` | explicit provider-schema comparability disclosure | benchmark evidence |
| `203d4ee` | canonical-table and literal dual-VLM implementations, tests and live reports | live-provider benchmark only |
| `2037084` | table-intake authority boundary | accepted documentation |

The compact recovery set is recorded in the machine map. The branch
`codex/pdf-dual-vlm-fact-benchmark` points at `203d4ee`, which is already an
ancestor of `origin/main`; no recovery cherry-pick is needed to preserve it.

## Provider implementation

The sole dual-fact entrypoint is
`PdfDualVlmFactProviderFactory.create_for_openwebui` in
`services/broker-reports-gate1-proof/scripts/pdf_dual_vlm_fact_providers.py`.
It constructs:

- a Gemini detector and extractor through
  `PdfGridExperimentProviderFactory` / `GeminiGridExperimentAdapter`;
- an OpenAI extractor through `OpenAIResponsesVisionAdapter`;
- one exact OpenWebUI provider connection per profile through
  `Gate2OpenWebUIProviderConnectionResolver`.

Authentication remains inside OpenWebUI configuration. The research runner
never reads environment secrets and never constructs an adapter directly.
Gemini uses native `generateContent` and `countTokens` requests with the
connection API key; OpenAI uses native Responses and input-token endpoints
with the same resolver boundary.

Frozen model configuration was:

| Role | Provider/model | Output budget |
| --- | --- | --- |
| page/table detector | Gemini `models/gemini-3.5-flash` | 4,096 |
| crop fact extractor | Gemini `models/gemini-3.5-flash` | 16,384 |
| crop fact extractor | OpenAI `gpt-5.4-mini-2026-03-17` | 16,384 |

All arms use temperature `0`, a 24,000 counted-input guard and a 240-second
transport deadline. Gemini uses `minimal` thinking; OpenAI image detail is
`high`. Each operation permits one preflight/count and one generation,
attempt number one, empty lineage, no hidden retry and no provider failover.

## Crops, prompts and schemas

The runner renders declared pages at 150 DPI, validates PNG dimensions and
hashes, derives immutable table crops, and verifies that both extractors see
the identical crop SHA. Whole-document visual upload is forbidden.

Recovered prompt versions are:

- `dual_vlm_detection_v1`;
- `dual_vlm_fact_extraction_v1`;
- `dual_vlm_canonical_table_normalizer_v4`;
- `dual_vlm_literal_table_detection_v2`;
- `dual_vlm_literal_table_extraction_v2`.

Recovered schema families cover detection, crop identity, physical cells,
financial facts, consensus, canonical tables, literal observations, reference
seals, diffs and scores. Gemini receives a provider projection whose keyword
transformation count and adapted-schema hash are recorded. OpenAI receives the
unchanged canonical strict JSON schema. The reports correctly describe the
comparison unit as `model + provider API + schema adapter`, not model alone.

## Parsing and terminal behavior

The adapters preserve HTTP class, model identity, response hash, usage,
duration, finish reason, parse result and terminal failure class. OpenAI
distinguishes incomplete, non-terminal, refusal, provider-error, invalid JSON,
wrong structured-text block count and resolved-model mismatch. Gemini records
the equivalent transport, parse and model checks. Malformed output is terminal;
neither a second LLM nor a deterministic semantic repair rewrites it.

Consensus validates both provider contracts and the shared crop identity,
pairs facts deterministically, checks source-region compatibility, and keeps
uncertain, missing or conflicting results review-only. Human references are
unavailable to detection, providers and comparison until after terminal seal.

## Evidence classification

The fact benchmark ran eight public broker cases and nine paired crop
extractions. Crop/model-view/canonical-schema identity was complete, but the
human reference fact type was incompatible with the provider enum. Its zero
precision/recall was therefore contract-limited; human review rate was 1.0.

The canonical-table research used real provider calls. Both providers produced
the correct same table on 5/5 controlled cases. On nine real PDF tables Gemini
returned a valid contract on 9/9 and OpenAI on 8/9, but full consensus was 0/9.
Repeated real runs were not deterministic. This is useful live-provider proof,
not production acceptance.

The literal benchmark had both responses contract-valid on 5/9 crops, five
exact raw agreements and only two agreements independently parser-verified in
both arms. Its literal human reference was not sealed. Fail-closed behavior
prevented false automatic acceptance; it did not prove useful recall.

No dual-VLM research runner was bundled into or deployed as a maintained stage
Function. Stage evidence therefore classifies this code as benchmark/live
provider proof only.

## Old implementation versus new scaffold

| Contract | Pre-drift implementation | `d7cc52d` scaffold |
| --- | --- | --- |
| bounded page/crop | implemented and benchmarked | implemented contract |
| Gemini/OpenAI payloads | concrete native adapters | payload builders behind abstract boundary |
| auth | OpenWebUI resolver | absent |
| dual-provider call/compare | implemented | absent; one configured provider per runtime |
| model qualification | exact model and capability checks | arbitrary non-empty model id |
| schema adaptation | measured canonical/adapted hashes and transform counts | provider projection without live proof |
| retry/deadline truth | one attempt, explicit 240 s deadline, no retry/failover | boundary timeout exists; downstream retry truth not proven |
| refusal/incomplete | provider-specific terminal handling | generic completion errors |
| evidence | sealed reports, live calls, controlled and public cases | unit tests only |
| stage integration | not integrated | explicitly not integrated |

The scaffold duplicates several ideas but is materially less complete. Its
large single-provider proposal schema may contain useful contract ideas, but it
must not replace the recovered provider path or enter the clean candidate.

## Restore, discard, still missing

Restore in the next goal by routing the already-present factory/adapters through
one maintained bounded runtime boundary; do not rewrite them. Reuse crop hash,
prompt/schema version, adapted-schema provenance, one-attempt policy and
terminal review behavior.

Discard the OCR-guided divergent branch as production architecture, the
duplicate `d7cc52d` runtime scaffold, whole-document upload assumptions,
provider-output canonical authority and mixed recovery bundles.

Genuinely missing are current-model requalification, a contract-compatible
human-reviewed table reference, a maintained dual-provider decision envelope,
closed-world bundle integration, candidate/live readback, and an explicit
stage delivery receipt.

Recommended next goal:
`Broker Reports Pre-Drift Dual-VLM Selective Runtime Integration And
Current-Model Requalification v1`.
