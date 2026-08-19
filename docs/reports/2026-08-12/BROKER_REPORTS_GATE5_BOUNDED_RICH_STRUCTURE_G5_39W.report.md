# GOAL G5.39W — Bounded Rich-Structure Research Loop

Date: 2026-08-12
Mode: research and experiments only
Product HEAD: 02659a9b0bdfb2f19171d2a070a660af85119d59
Product HEAD tree: 0a696522eb37eca13bb9224a41f7227823c8ce8c
Research journal: https://github.com/Kwentin3/corp-openweb-ui/issues/278

## Outcome

G5.39W terminates at:

**RICH_STRUCTURE_INTERPRETATION_NOT_PROVEN**

Neither tested rich representation met the frozen Phase A threshold:

- IA, the exact existing Stage C JSON, produced six noncanonical responses
  across the six positive real calls. The two negative-control calls were one
  safe abstention and one incomplete same-event proposal.
- IB, a deterministic compact serialization of the same structure, produced
  two noncanonical DEV responses, selected a different row-local event in both
  HOLDOUT calls and both LARGE calls, and safely abstained twice on the
  negative control.

Across all 16 calls there were zero invented refs, zero invented literals, and
zero accepted NEGATIVE_AB cross-event joins. That safety result does not offset
zero role-complete correct target facts and four schema-valid wrong-event
proposals.

The Phase A gate therefore failed. Phase B region selection, Phase C combined
proof, downstream pressure, and any winner contract were not run by the
predeclared stopper. G5.40 remains unauthorized.

No production code, CanonicalArtifact schema, Gate 3 owner, relation heuristic,
Gate 4+, Tax Model, declaration, package, projection, or XML behavior changed.

## Frozen baseline

The product checkout, pre-existing dirt, G5.39V evidence, corpus assignments,
provider/model, context budget, repetitions, retry policy, metrics, hard
failures, and phase-transition threshold were frozen before inference.

| Authority | Frozen identity |
|---|---|
| Product HEAD | 02659a9b0bdfb2f19171d2a070a660af85119d59 |
| Product tree | 0a696522eb37eca13bb9224a41f7227823c8ce8c |
| G5.39V report | 8f0bea630781f895e1903d2004934fc070048988f327191ca5f57b41c4281585 |
| G5.39V private trace | 18407e17a19b50568950bc93c21dc0be5fc7b7ed8172218355854910c86f5766 |
| G5.39V private evaluation | 8936763a5d5dcf666cc331801d806a70bbd277e353dd5e9fe7c398430b245587 |
| G5.39W v2 prepared input | 8c2cc837a89af0de91a6755d877c91ea403a49ca4d591e90a00a11e68aeb1aa3 |

The corpus remained byte-identical:

| Case | Source SHA-256 | Assignment |
|---|---|---|
| DEV_PUBLIC_TBANK | 25c3b0606ce86852f6ac8fdf6feccbefedb609bcffc5c1581dc95b9b81c5da67 | distributed real/public target |
| HOLDOUT_REAL_001 | 79af73d5be78df446f768f516ed6eaebd5a9d4bfc6f98c98a4a53a5b5131f37d | independent real row-local target |
| LARGE_REAL_001 | 7cfd297786cc91cbccbe0c2ae5bce905a2a11ac6b35e5b0a795cf9c6d41bd015 | distributed large-real target |
| NEGATIVE_AB_001 | frozen synthetic control | two similar events that must not be mixed |

The private oracle SHA-256 is
d76ade254cfe2c323e0ab73daf0fcf83d598034022e096dba6c86173a65e6c85.
It was applied only after each hypothesis output set was immutable.

## Production-equivalent route

Both representations used the same existing sealed route:

1. [Gate2StructuredModelClientFactory](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_model_clients.py)
   created the client.
2. label_gate3_once sealed the exact model-visible messages and canonical
   schema.
3. The repository-owned live completion boundary sent the sealed form through
   authenticated OpenWebUI to its configured provider.
4. Provider/model were fixed to
   google_gemini / models/gemini-3.5-flash.
5. The existing
   [Gemini response-format adapter](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_provider_adapters.py)
   performed ten recorded schema transformations per call.

The anti-drift anchors remain FACTORY_REQUIRED and FORBIDDEN in the
model-client owner. No experimental provider SDK or direct provider API path
was added.

## Transport lineage

The first 16 implicit-v1 slots were retired before inference:

- 15 local attempts could not import the in-process OpenWebUI completion module;
- the final attempt stopped at OpenWebUI sign-in rate limiting;
- claimed slots: 16;
- provider submissions: 0;
- provider responses: 0;
- model outputs: 0;
- retired aggregate SHA-256:
  fe96383e414ca3d1f77b69de464bf6ae1e82f287df18e08c76c031c7a729f350.

The retry contract explicitly permitted a new frozen experiment version after
attributed transport failure before inference. The v2 transport reused the
repository's existing authenticated OpenWebUI completion boundary. It did not
change corpus bytes, representations, prompts, schema, oracle, budgets,
metrics, or semantic rules.

V2 preflight proved for 16/16 new slots:

- frozen model published;
- exact factory request profile;
- final provider context byte-exact;
- canonical schema hash exact;
- ten Gemini schema transformations;
- zero claims and zero submissions before the final freeze.

## Phase A hypotheses

### IA — Existing Stage C rich projection

IA is the canonical compact JSON serialization of the exact existing complete
reviewed Stage C region. It retains every table identity/title, page/table/row/
cell ref, column, literal, source order, and existing explicit source relation.
No item was filtered by the oracle.

Experiment commit:
e77621008af6c573e3161cc353b3186998912fc0.

### IB — Compact structure-preserving serialization

IB is a deterministic line-oriented rendering of the exact same information:
table → row → ordered cell/structural-ref/literal. Tests proved that every
source item appears exactly once and in source order. No semantic relation,
normalization, highlighting, reordering, or candidate-row selection was added.

Experiment commit:
e77621008af6c573e3161cc353b3186998912fc0.

### IC — Visual/multimodal

NOT_APPLICABLE. The production-equivalent label_gate3_once route exposes text
messages plus a structured response schema, not a natural bounded-image
contract. Building a separate multimodal provider pipeline was prohibited.

### ID — Hybrid

NOT_RUN. IA/IB exposed canonical-status noncompliance and wrong event choice,
not one concrete missing geometry/hierarchy channel. Adding a hybrid merely to
fill the hypothesis budget would violate the research contract and KISS.

## Phase A comparison

Every row below contains both independent repetitions; no result was selected
or discarded.

| Hypothesis | DEV | HOLDOUT | LARGE | NEGATIVE_AB | Hard result | Verdict |
|---|---|---|---|---|---|---|
| IA | invalid, invalid | invalid, invalid | invalid, invalid | unresolved, incomplete same-event | 6 noncanonical positive outputs | REJECT |
| IB | invalid, invalid | wrong event, wrong event | wrong event, wrong event | unresolved, unresolved | 4 accepted wrong target events | REJECT |

Aggregate metrics:

| Hypothesis | Calls | Submissions | Role-complete correct | Invalid responses | Wrong events | Cross-event negative joins | Invalid refs | Invalid literals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| IA | 8 | 8 | 0 | 6 | 0 | 0 | 0 | 0 |
| IB | 8 | 8 | 0 | 2 | 4 | 0 | 0 | 0 |

IA's six invalid responses used statuses outside the frozen enum after provider
schema adaptation: variants of RESOLVED and SUCCESS. Their refs and literals
were visible, but canonical runtime validation fails them closed. They were not
repaired or semantically reclassified as accepted facts.

IB's four wrong-event results were canonical-schema-valid and passed the
deterministic ref/literal/region checks. Private-oracle adjudication showed that
each was internally one row in one table, but not the assigned target event.
They are wrong events, not invented evidence and not cross-row mixing. This is
still a hard safety failure because a valid-looking fact for the wrong event
would be accepted without the private oracle.

No positive call returned the role-complete assigned target fact.

## Context-window metrics

The complete reviewed region, not oracle-filtered rows, was sent. Both
repetitions used identical input bytes and reported identical input-token
counts per hypothesis/case.

| Case | Stage C whole chars | Region fraction | IA chars / input tokens | IB chars / input tokens |
|---|---:|---:|---:|---:|
| DEV_PUBLIC_TBANK | 29,336 | 99.6864% | 29,244 / 13,501 | 28,454 / 14,141 |
| HOLDOUT_REAL_001 | 224,775 | 47.8131% | 107,472 / 48,700 | 104,225 / 51,182 |
| LARGE_REAL_001 | 1,022,810 | 4.7545% | 48,630 / 26,981 | 43,826 / 26,210 |
| NEGATIVE_AB_001 | 2,243 | 96.8792% | 2,173 / 859 | 2,006 / 884 |

| Hypothesis | Total input tokens | Total output tokens | Total duration | Maximum input tokens |
|---|---:|---:|---:|---:|
| IA | 180,082 | 3,404 | 143.485 s | 48,700 |
| IB | 184,834 | 2,976 | 103.515 s | 51,182 |

All calls stayed below the 55,000-input-token and 2,048-output-token budgets.
The whole LARGE projection greater than one million characters never entered
model context.

Compact IB reduced characters for every case but increased tokens for DEV,
HOLDOUT, and NEGATIVE_AB. More importantly, it did not improve correctness.
Context compression therefore does not justify retaining it.

## False-join audit

NEGATIVE_AB contains two explicit, disjoint event components within one bounded
region.

- IA repetition 1: safe abstention.
- IA repetition 2: incomplete proposal wholly inside one expected component.
- IB repetitions 1 and 2: safe abstention.
- accepted A/B mixed facts: 0/4.
- invented refs/literals: 0/4.

This proves the negative control did not false-join in these four calls. It
does not prove interpretation because the positive real targets all failed.

## Phase B comparison

NOT_RUN_BY_FROZEN_STOPPER.

Phase B required a Phase A representation that produced the complete assigned
DEV, HOLDOUT, and LARGE facts in both repetitions with zero hard failures.
Neither IA nor IB did so. Running SB1–SB3 would test selection with no proven
interpreter and would repeat the closed-bundle-as-discovery mistake.

No claim is made about whether bounded region selection is possible.

## Combined proof

NOT_RUN_BY_FROZEN_STOPPER.

There is no Phase A winner and therefore no legal A+B composition. No
large-document selection → interpretation → validation result exists.

## Downstream pressure

NOT_RUN_BY_FROZEN_STOPPER.

The contract permits Gate 4, purchase/charge relation, controlled disposal, Tax
Model, declaration, and XML/XSD pressure only after combined structural/fact
correctness passes. No downstream behavior was changed to compensate.

## Research ledger

| Stage | Hypothesis / correction | Evidence identity | Result | Verdict / retained knowledge |
|---|---|---|---|---|
| Freeze | IA + IB, two calls/case | e4e5e2e1e672e4254818d70f23c3da461cd13ef7 | 5 contract tests pass | RETAIN freeze |
| Setup | implicit-v1 local completion | retired aggregate fe96383e… | 0 submissions, 0 outputs | RETIRE transport version |
| Transport v2 | existing OpenWebUI completion boundary | e77621008af6c573e3161cc353b3186998912fc0 | 16/16 preflight | RETAIN transport evidence |
| IA | exact Stage C JSON | 8 immutable result hashes | 0 complete; 6 invalid | REJECT |
| IB | compact exact structure | 8 immutable result hashes | 0 complete; 2 invalid; 4 wrong events | REJECT |
| Adjudication | refine wrong vs mixed taxonomy only | 04ba9e4e1fd1d099466c6602cd2fe14bc02d37c7 | same frozen outputs; 7 tests pass | RETAIN corrected taxonomy |
| Phase B | SB1–SB3 | none | not authorized by threshold | NOT RUN |
| Phase C | composition | none | no A/B winners | NOT RUN |

Final exact evaluation SHA-256:
479c5f91e2c04a2921c33a962311d10f5e5317b015dc4632980ab341d55bc556.

Final safe evaluation SHA-256:
88a29de43f5e37b8d5a0c1e5e755c549633fd5e94d47bb1ce85707b78f325c05.

## Minimal winner contract

None. No representation is selected and no experimental contract may be
promoted into production.

The evidence supports a narrower conclusion: exposing Stage C structure is
necessary to avoid the proven C → D flattening, but the two tested textual
representations plus the current production-equivalent provider/profile do not
reliably select and complete the assigned economic event in one clean pass.

## Verification, cleanup, and KISS

- Research contract tests before inference: 6 passed in 0.204 s.
- Final deterministic/adjudicator tests: 7 passed in 0.359 s.
- Existing model-client and bounded-labeling tests: 40 passed in 2.97 s.
- Factory anti-drift anchors remain present at the exact current owner.
- V2 claims/results: 16/16.
- V2 provider submissions/responses: 16/16.
- Semantic retries, repair, follow-up correction, answer merge: 0.
- Best-of-N: false.
- Exact private source, region, oracle, prompts containing evidence, and
  provider traces remain ignored outside Git.
- Experimental research repository is removed at closeout; safe reports and
  hashes remain.
- Product source and pre-existing worktree changes are untouched.
- KISS: two materially distinct serializations of one existing rich owner, one
  existing factory/provider route, one validator, and a frozen early stop.

No staging, product commit, push, PR, product activation, or dependent GOAL is
authorized by this report.

## Limitations

This is a bounded negative result for one provider/model profile, two textual
representations, four frozen cases, and two repetitions each. IC was not
applicable on the current route. The result does not prove that every
structure-preserving representation or multimodal architecture must fail.

It does prove that IA and IB are not acceptable strategies under the frozen
safety and correctness threshold. Choosing IB because it returns more
schema-valid outputs would knowingly select four wrong target events and is
therefore prohibited.
