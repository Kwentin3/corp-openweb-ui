# Broker Reports Gate 2 package hot-path performance closure

Date: 2026-07-19
Status: passed
Measured implementation revision: `f117b702d7961c43b4426b25698b1814e13256d3`

## Verdict

The maintained `Gate2InputReadinessFactory` path was remeasured on the same
accepted actual Gate 1 graph and machine as the baseline audit. Wall time fell
from `3519.572 s` to `55.469930 s`, a `63.45x` speedup. The required `10x`
threshold is exceeded without timeout changes, truncation, concurrency,
resumable processing or weaker validation.

Provider/LLM participation remained exactly zero. The delay was deterministic
local validation and lookup work, not model inference.

## Comparable workload

| Property | Value |
| --- | --- |
| Workload fingerprint | `8bc80a70c4f228670dcf71acdd824389b63215308f377a9cfe8436c0fccdc9b7` |
| Accepted run label | `actual_gate1_20260718T182125Z` |
| Artifact records / document ids | `1531 / 104` |
| Artifact payload bytes | `1,458,630,551` |
| Python / SQLite | `3.11.9 / 3.45.1` |
| Host | Windows Server 2019, 8 logical CPUs, `34,039,119,872 B` RAM |
| Preparation provider calls / retries / tokens | `0 / 0 / 0` |

Raw customer data and raw measurement payloads remain outside Git.

## Before and after

| Metric | Accepted baseline | Optimized actual run | Change |
| --- | ---: | ---: | ---: |
| Wall time | `3519.572 s` | `55.469930 s` | `63.45x` faster |
| CPU user+system | `3509.563 s` | `55.328125 s` | `63.43x` faster |
| Incremental peak RSS | `4,282,335,232 B` | `3,933,814,784 B` | `-348,520,448 B` (`-8.14%`) |
| Private discovery/validation | baseline-equivalent `3505.49 s` | `40.464197 s` | `86.63x` faster |
| Unique / total full PDF parent validations | at most `162 / 822` | `45 / 45` | one per selected parent identity/checksum |
| PDF parent cache hits | not present | `518` | in-run only |
| Per-unit PDF structural/linkage checks | implicit in full validation | `563` | preserved for every selected unit |
| PDF checksum calls | approximately `6,812,794` | `219,654` | approximately `31.02x` fewer |
| Full table projection validations | `98` | `0` | correct for default full-unit strategy |
| Resolver calls | `1254` | `725` | `-42.19%` |
| Payload bytes read | `1,455,533,632` | `1,309,710,249` | `-10.02%` |
| SQLite queries | `1256` | `727` | `-42.12%` |
| Preparation provider calls | `0` | `0` | unchanged |

An instrumentation-heavy confirmation run completed in `108.508622 s`, still
`32.44x` faster than the uninstrumented baseline. It reproduced the same
package, error, cache, access and immutability outcomes and supplied the
checksum-call count above. The narrow run is the comparable product timing;
instrumentation time is not presented as product latency.

## Implemented hot-path changes

1. PDF validation is split into full parent validation and per-unit
   structure/linkage validation. `audit_and_build` caches only a successful
   validation keyed by immutable parent artifact identity plus payload checksum
   and only for that service invocation. Wrong parent, checksum, access or
   lifecycle context still fails closed.
2. Input strategy and readiness scope are selected before materializing or
   fully validating unused representations. Default table-projection full
   validations are zero but all `259` projections remain inventoried and
   accounted.
3. Source-value and PDF layout resolution use one-pass prepared indexes and
   batch lookup while preserving duplicate, missing, checksum and private-path
   errors.
4. Readiness is enforced per scope. Noncanonical PDF table candidates and
   visual units without a compatible consumer are explicit blocked outcomes;
   neutral XML structure is eligible without financial semantics.

The implementation points are
`gate2_input_readiness.py:576-915`,
`gate2_input_readiness.py:1899-1901`,
`pdf_text_layer.py:841-1013`,
`pdf_layout_units.py:1001-1017`, and
`source_provenance.py:736`.

## Fan-out and zero-loss accounting

The optimized actual run inventories `928` source units:

| Outcome | Count |
| --- | ---: |
| Built and validated packages | `667` |
| Noncanonical PDF table candidates blocked | `194` |
| Visual units blocked because no consumer exists | `67` |
| Total | `928` |

The equality `928 = 667 + 194 + 67` is exact. Package scopes are `602` text,
`41` canonical table and `24` neutral structure. The former baseline built
`837` packages because it incorrectly promoted `194` PDF table candidates and
did not package `24` ready neutral XML units. The changed count is therefore an
intentional contract correction, not truncation or silent loss.

All `667` built packages passed. The run reports `75` packageable and `28`
unpackageable source-ready documents. The remaining terminal errors preserve
the baseline fail-closed classes: `24` memory-blocked documents and `4`
documents with no eligible private slice, plus the aggregate error. No timeout
or partial-success label converted those errors into success.

ArtifactStore state was byte-for-byte unchanged by package preparation.
Knowledge/RAG/vector writes and package persistence were zero.

## Verification

- Expanded focused suite before bundle build: `78 passed`.
- Bundle and architecture suite: `16 passed`.
- Full service suite after bundle build: `911 passed`, `5 warnings`.
- Performance-probe regression suite after accounting refinement: `3 passed`.
- Ruff checks and `git diff --check`: passed.
- Controlled large-table regression proves one complete source-value inventory
  pass followed by indexed lookups; reference count no longer multiplies full
  index scans.
- Controlled three-document PDF probe: three full parent validations, three
  linkage checks, zero projection validations, zero provider calls.
- Access/lifecycle, wrong-parent, checksum, duplicate, missing and private-path
  negative tests remain terminal and fail closed.

## Remaining decisions

No timeout increase is justified. Concurrency and resumable processing are not
needed to close this performance gate. Lazy package generation and broader
payload batching may still reduce memory or secondary I/O, but the measured
RSS improvement and `63.45x` wall-speedup make them ordinary follow-up debt,
not acceptance blockers.
