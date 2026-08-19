# G5.39 Structural Evidence Binding Tournament — preregistration

Status: `FROZEN_BEFORE_COMPARATIVE_INFERENCE`
Date: `2026-08-11`
Mode: research only; no production implementation.

## Frozen baseline

- G5.38C safe receipt SHA-256: `0c73e4ae741b15dc1c177aac4ddaf104b3afc5d6e06856a303f3639c594c5044`.
- Public development PDF SHA-256: `25c3b0606ce86852f6ac8fdf6feccbefedb609bcffc5c1581dc95b9b81c5da67`.
- G5.38C implementation bundle SHA-256: `7718c36492f2d8ebe5306af4e896336cb4143c5c062def0b5081c8f6836d7305`.
- Baseline behavior: two accepted page-region targets; diagnostic exposure of 4 structural projections / 16 rows / 274 cells recovered literals, but purchase and charge did not converge on one row and exact financial-event provenance remained unproved.
- Clean G5.38C call shape: one semantic call plus one role call; retry / merge / repair total `0`.
- G5.38C bounded sizes: source context `8,036` chars; clean role context `5,467` chars; diagnostic role context `5,228` chars.
- Ephemeral research baseline commit: `7558a7a11d6270d412017ee05a6ae5658c32c76d`.
- Ephemeral research baseline tree: `50ab726267e689d7b9feae318807080342b80c24`.
- Frozen harness config SHA-256: `a2f3e610fd570c4bf7075a6cb0441632417a3e716801ac51f8e33f3574ddcad1`.

All H1–H4 branches start from that same research commit. The nested research repository is ignored by the product repository and will be removed after safe evidence is retained.

## Frozen corpus

Authority: `BROKER_REPORTS_GATE5_STRUCTURAL_EVIDENCE_BINDING_G5_39.corpus.v2.safe.json`, SHA-256 `26615ec1f3aa148cf19d4b642d73a3df948b48f975bfeb98d1c47a141488145e`.

The pre-inference origin audit invalidated corpus v1: its proposed holdout was a public fee schedule, not a customer broker report. No model inference had occurred. V2 restarted the tournament with:

- `DEV_PUBLIC_TBANK`: official public development PDF;
- `HOLDOUT_REAL_001`: a distinct real six-page customer broker PDF, not used to design hypothesis mechanics;
- `LARGE_REAL_001`: a distinct real 65-page customer broker PDF; its `217,842`-character text projection exceeds the context budget;
- `NEGATIVE_AB_001`: frozen controlled A/B cross-event ambiguity fixture;
- existing CSV, HTML and XLSX disposal regressions.

Private adjudication/oracle SHA-256: `c90340ce7d8ff29b0f21635b84f4258531f4c641a598a08bdb7a4f4d319d7ac5`. It contains exact customer literals only under ignored `local/`; no private values or paths are copied into this report.

## Frozen hypotheses

| ID | Competing contract | Retrieval |
|---|---|---:|
| H1 | One first-class canonical row plus its exact cells; a fact must close row-locally. | 0 rounds |
| H2 | One closed set of exact structural refs, possibly across rows/tables, selected in one bounded model pass. | 0 rounds |
| H3 | Accepted anchor → deterministic containment/proximity/explicit-relation neighborhood → one pass → closed refs. | 0 rounds |
| H4 | Compact page/table map → exact page/table refs → deterministic row index → exact row refs → deterministic get-by-ref → final closed multi-target bundle. | at most 2 rounds |

H4 is the required frozen composition experiment: H4 supplies bounded discovery and H2 supplies the final proof contract. No H5 is preregistered; it will not be added merely to fill a slot.

## Model and fair budget

- Model/profile: `gpt-5.4-mini-2026-03-17` through the already configured OpenAI-compatible provider.
- Temperature: `0`; JSON object response mode.
- Per case, every hypothesis has at most `16,000` total provider input characters and `1,800` total output tokens.
- H1/H2/H3: at most one provider call and zero retrieval rounds per case.
- H4: at most three provider calls and two deterministic retrieval rounds per case.
- H4 total retrieved structural content: at most `10,000` characters per case.
- Whole-document content is forbidden for `LARGE_REAL_001`.
- Provider input/output, calls, retrieval rounds and retrieved characters are counted in total, not per call.
- Retry `0`; repair `0`; best-of-N `false`; multi-answer merge `false`.
- A transport failure before inference may be attributed and replayed only as a transport event; a semantic failure is final.

H4 receives more call boundaries but not a larger total input/output budget. Additional calls and implementation concepts count against it after correctness/generalization/completeness.

## Frozen evaluator and hard invariants

Every `PROVEN` fact must satisfy all of the following; otherwise it is an invalid proof:

1. every required role has an exact source structural ref;
2. the role literal exactly equals a literal at that ref;
3. every used ref is inside the strategy's allowed evidence space;
4. the final evidence bundle includes the full frozen evidence witness;
5. all used evidence belongs to the same adjudicated economic event;
6. the forged Transaction A / Transaction B mixture is rejected terminally;
7. ambiguity returns `FAIL_CLOSED`, never a guessed fact;
8. no broker-specific rule, prior-case reuse, retry, repair, best-of-N or weakened validator is allowed;
9. Gate 4 and all later owners remain unchanged.

The evaluator tests are frozen in the baseline. Before inference they prove that an A/B mixed fact is rejected and that an ambiguous answer terminates fail-closed.

## Metrics and evaluation order

For every hypothesis and sample record:

- expected and correctly proven facts;
- role-complete facts;
- false joins and unresolved facts;
- exact-provenance and hard-invariant result;
- provider calls, total input characters/tokens, total output tokens;
- retrieval rounds and retrieved structural characters;
- experiment LOC, runtime concepts and schema/persistence surface.

Decision order is lexicographic:

1. correctness/provenance;
2. DEV and HOLDOUT generalization;
3. financial completeness;
4. context/provider cost;
5. implementation complexity.

No weighted score is authoritative. KISS breaks a tie only after equal correctness and generalization.

## Winner and stop rules

A strategy is selectable only if hard invariants, holdout, large-context pressure and downstream compatibility pass; it must add no broker-specific logic and materially improve on G5.38C. Equivalent survivors are resolved in favor of the simpler contract.

If no strategy passes those conditions, the terminal is `NO_STRATEGY_PROVEN`. A strategic stop is reserved for evidence that bounded exact-ref work is impossible without whole-document reasoning, semantic search, a fundamental representation redesign, persistent graph/service, broker templates or best-of-N.

The selected experiment remains research code. No winner or rejected code is merged into production; only a minimal contract and safe evidence may remain. A clean production implementation is deferred to `G5.40 — Clean Structural Evidence Implementation`.
