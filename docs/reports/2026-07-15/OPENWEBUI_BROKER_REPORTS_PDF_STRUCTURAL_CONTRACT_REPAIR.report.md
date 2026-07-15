# OpenWebUI Broker Reports: PDF Structural Contract Repair

Date: 2026-07-15
Repository: `D:\Users\Roman\Desktop\Проекты\corp-openweb ui`
Mode: default-disabled Gate 1 research; production Gate 2 authority unchanged.

## Verdict

All five named structural contract defects are repaired and covered by repository tests plus a read-only controlled/sealed replay of `holdout_001`, `holdout_002` and `holdout_003`.

This is a contract-repair proof, not a new live-provider accuracy pass. The replay made zero provider calls and did not read the human reference. `holdout_001` and `holdout_002` prove that the repaired contract can represent both plausible borderless structures and preserve ambiguity; they do not prove that a live VLM will now emit both alternatives.

## Evidence boundary

The replay read only:

- `fresh_v4_2026-07-14_prereg1/private/holdout.preregistration.private.json`;
- `fresh_v4_2026-07-14_run1/private/holdout.terminal.private.json`.

The pre-registration SHA-256 was `48f3f31d32091bebec37e4a0b6f1c78fd1f488e99b3c7e97a51981c4f583e491`, exactly matching the SHA recorded by the terminal. The terminal SHA-256 was `2a9eaed161cd3fcc390dbade29aac9b130bcc9b1dfef634b2a910aa30e0c82e9`; its sealed `reference_process_started` value remained `false`.

The proof rebuilt the v5 visual package from the sealed parser observation and verified PNG bytes/hash. The original full raster-manifest payload was not persisted, so the sealed manifest hash was preserved as opaque identity rather than claimed as a byte-for-byte manifest reconstruction. No replacement terminal or new proof serialization was written.

## Contract before and after

| Goal | Before | Repaired contract |
|---|---|---|
| Borderless topology | Prompt/rules privileged drawn separators and could turn their absence into `unsupported`. | Boundaries may use stable whitespace gutters, repeated horizontal/vertical alignment, consistent atom bands, and visible separators when present. No drawn grid is required. The model view remains one crop/window, anonymous ids, bbox/order only, with no source values. |
| Span/header semantics | Equivalent geometry could be labelled `merged` or `spanning_header` and compared as different structure. | `merged` is the sole emitted canonical relation. Legacy `spanning_header` is accepted only at the response boundary and canonicalized before assembly. Header depth/hierarchy carries header meaning; scorer equality uses span geometry. |
| Geometry polarity | Missing or incomplete vector-line sets could act as negative evidence. | Every geometry subject reports `confirmed`, `contradicted`, `insufficient_evidence`, or `not_applicable`. Partial/missing evidence abstains and leaves visual boundaries intact; positive certified crossings still fail closed. |
| Multi-line span membership | Membership depended on global source-order contiguity and a common narrow x/y overlap band. | Membership depends on selected grid region, exact ownership, certified-separator non-crossing, non-overlap, and anchor/covered-cell consistency. Source order is retained only within materialized cells. |
| Consensus completeness | `accepted_unique_consensus`, `solver_search_complete` and `uniqueness_proven=true` overstated a supplied-hypothesis evaluator as a global search. | The accepted terminal is `accepted_supplied_consensus`. Results expose `supplied_hypotheses_exhausted`, `structural_domain_complete`, `uniqueness_proven`, `ambiguity_proven`, `domain_incomplete`, `search_not_certifiable`, `search_scope`, and a safe explanation. The current runtime never claims global structural completeness or uniqueness. |

## Evidence by goal

### 1. Borderless visual topology

`pdf_visual_topology_policy_v5` and its provider schema now state the non-line evidence contract explicitly and retain the existing input/output caps. A controlled replay derived row/column mid-gutters only from the anonymous sealed atom bboxes:

- `holdout_001`: both `3 x 2` and `3 x 3` bound exactly; terminal `ambiguous_multiple_consensus` with two distinct valid grids;
- `holdout_002`: both `2 x 2` and `2 x 3` bound exactly; the same honest ambiguous terminal.

Each target produced four exact-ownership bindings across two controlled attempts, with zero rejected hypotheses. Neither ambiguous target was materialized or promoted to acceptance.

### 2. Canonical spans and headers

The provider schema emits only `merged`; the parser accepts the legacy alias and returns canonical `merged`. Assembly and scorer tests compare `(start_row, end_row, start_column, end_column)` rather than provider wording.

Both sealed raw responses for `holdout_003` survived this boundary and produced the same canonical binding checksum. The result retained five canonical `merged` spans and one header-hierarchy relation without broker-specific or reference-specific mapping.

### 3. Geometry evidence polarity

Assembly result v5 records polarity separately for row boundaries, column boundaries, candidate separators and span separators. Incomplete boundary clusters and partial span-separator observations return `insufficient_evidence` without rejecting the visual proposal. No applicable check returns `not_applicable`; complete matching line sets may return `confirmed`.

The sealed incomplete vector coverage for `holdout_003` no longer rejects either attempt. Dedicated regressions also prove that an atom bbox crossing a certified separator is `contradicted` and blocks the hypothesis. Geometry remains a calibrator/auditor, never automatic table authority.

### 4. Multi-line span membership

The global source-order/common-band gates were removed. Dedicated tests cover non-contiguous multi-line atoms inside one selected region, exact ownership, span overlap, separator crossing and anchor consistency.

For `holdout_003`, both sealed attempts produced:

- shape `3 x 6`;
- five spans;
- one header-hierarchy relation;
- `51/51` atoms owned exactly once;
- one shared canonical binding candidate;
- materialization with `model_invented_values_total=0` and no source-value mutation.

### 5. Honest consensus completeness

Consensus result/policy v2 evaluates every supplied valid hypothesis but fixes the structural-domain fields to the honest boundary:

- accepted `holdout_003`: `supplied_hypotheses_exhausted=true`, `structural_domain_complete=false`, `uniqueness_proven=false`, `ambiguity_proven=false`, `domain_incomplete=true`, `search_not_certifiable=false`, `search_scope=supplied_vlm_hypotheses_only`;
- ambiguous `holdout_001/002`: the same bounded scope, with `ambiguity_proven=true` because two distinct supplied grids passed;
- invalid/rejected evidence maps to `incomplete_evidence`; no supported bounded hypothesis maps to `unsupported`; multiple passing grids remain `ambiguous_multiple_consensus`.

Materialization and continuation now require the full supplied-scope acceptance predicate and still set production authority to `false`. Legacy `accepted_unique_consensus` is readable only in append-only repeat history; new runtime events do not emit it.

## Per-table outcome

| Target | Proof mode | Exact ownership | Valid shapes | Terminal | Repeatability | Materialization |
|---|---|---:|---|---|---:|---|
| `holdout_001` | controlled anonymous bbox over sealed crop/atoms | `14/14` for every binding | `3 x 2`, `3 x 3` | `ambiguous_multiple_consensus` | `false` | forbidden; no values emitted |
| `holdout_002` | controlled anonymous bbox over sealed crop/atoms | `14/14` for every binding | `2 x 2`, `2 x 3` | `ambiguous_multiple_consensus` | `false` | forbidden; no values emitted |
| `holdout_003` | both sealed raw VLM responses, package identity rebound to v5 | `51/51` for both bindings | `3 x 6` | `accepted_supplied_consensus` | `true` | zero invented/mutated values |

Controlled repeatability for `holdout_001/002` is intentionally `false`: every attempt contains two valid grids, and the controlled fixture reports zero provider calls/context attestation. This does not weaken the ambiguity proof and is not upgraded to a successful provider repeatability claim.

## Context-budget impact

| Target | v4 static estimate | v5 static estimate | Delta | Image bytes | Sealed v4 input/output baseline |
|---|---:|---:|---:|---:|---:|
| `holdout_001` | 1744 | 1657 | -87 | 13241 | 2744 / 124 |
| `holdout_002` | 1735 | 1647 | -88 | 9287 | 2671 / 107 |
| `holdout_003` | 2544 | 2457 | -87 | 35077 | 5070 / 584 |

The image payloads and maximum budgets are unchanged. The sealed token counts are historical v4 baselines only; no exact v5 provider `countTokens` value is claimed because no provider call was made.

## Verification

- Pre-change targeted baseline: `102 passed`.
- Post-change key PDF/consensus/runtime set: `145 passed`.
- Full service regression: `534 passed`, five third-party SWIG deprecation warnings, zero failures.
- Gate 1 bundle/stub/delivery tests: `25 passed`; Gate 1 and unchanged Gate 2 bundle tests: `10 passed`.
- Scoped Ruff over the repaired production modules, scripts and dedicated PDF tests: clean.
- `compileall` over `broker_reports_gate1`, `openwebui_actions` and `scripts`: exit `0`.
- `git diff --check`: clean apart from Git's Windows LF/CRLF notices.
- Repository-wide Ruff is not a clean repository gate in the current tree (`182` findings, largely export/generated-bundle/test import-order patterns); it was not used to overstate this slice's scoped lint result.

The Gate 1 bundle was rebuilt through the existing bundle factory only. A second rebuild was byte-identical at SHA-256 `b9bc87b181b0df157fb44c64bacbaab2db071f5e6b6a2a7178176e385fff7131`. No task diff was produced in either Gate 2 bundle, and no new external dependency, workspace-only runtime import or filesystem path hack was added.

## Global invariants

- Parser values, source refs and candidate ids remain immutable.
- Every accepted atom is owned exactly once; ambiguous tables are not materialized.
- `holdout_003` materialization invents and mutates zero values.
- Replay provider calls, hidden retries and provider failovers are all zero.
- Runtime decisions used no human reference.
- Structural adjustments remain explicit in the adjustment journal; certified separator crossings are not silently ignored.
- Gate 2 selection and production authority remain unchanged and false for this research path.
- No OpenWebUI core patch, Knowledge/RAG/vector path, OCR, or whole-PDF authoritative extraction was introduced.

## Deliberately not implemented

- no new parser, provider, solver framework or serialization format;
- no SAT/SMT/CP-SAT or universal structural-domain enumeration;
- no reference-specific or broker-specific topology mapping;
- no hidden retry, best-looking-attempt selection, majority vote or provider failover;
- no live provider rerun, deployment, production Gate 2 promotion or authority change;
- no OCR, full-PDF authority, OpenWebUI core patch, Knowledge/RAG/vector work;
- no claim that the controlled borderless alternatives predict live-provider behaviour.

## Remaining ambiguity and next slice

The physical two-versus-three-column ambiguity in `holdout_001` and `holdout_002` is real under the available anonymous visual evidence and is therefore preserved. The runtime also correctly leaves the global structural domain incomplete. An empty geometry-certified merged region still uses the existing explicit empty-cell projection and remains a documented contract limitation.

One further minimal slice is justified only as validation: run the repaired v5 contract against a new source-frozen, previously unseen provider holdout with exact `countTokens` accounting and the same no-reference-until-terminal boundary. No architecture, parser or solver redesign is justified unless that run exposes a concrete unrepresentable alternative or evaluator defect.

## Final statuses

- `BROKER_REPORTS_BORDERLESS_VISUAL_CONTRACT_REPAIRED`
- `BROKER_REPORTS_SPAN_SEMANTICS_CANONICALIZED`
- `BROKER_REPORTS_GEOMETRY_EVIDENCE_POLARITY_REPAIRED`
- `BROKER_REPORTS_MULTILINE_SPAN_MEMBERSHIP_REPAIRED`
- `BROKER_REPORTS_CONSENSUS_COMPLETENESS_SEMANTICS_REPAIRED`
- `BROKER_REPORTS_STRUCTURAL_CONTRACT_REPAIR_PROVEN`
