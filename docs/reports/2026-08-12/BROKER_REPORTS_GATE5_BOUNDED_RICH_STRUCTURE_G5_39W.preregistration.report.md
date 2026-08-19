# GOAL G5.39W — Bounded Rich-Structure Research Loop preregistration

Status: **FROZEN_BEFORE_PHASE_A_INFERENCE**
Date: 2026-08-12
Mode: research and experiments only

## Baseline

- Product repository HEAD:
  02659a9b0bdfb2f19171d2a070a660af85119d59.
- Product repository tree:
  0a696522eb37eca13bb9224a41f7227823c8ce8c.
- Current origin/main after fetch:
  a55abe5d08a1cc2a47a679287bba0f479185595b.
- G5.39V safe report SHA-256:
  8f0bea630781f895e1903d2004934fc070048988f327191ca5f57b41c4281585.
- G5.39V exact private trace SHA-256:
  18407e17a19b50568950bc93c21dc0be5fc7b7ed8172218355854910c86f5766.
- G5.39V exact private evaluation SHA-256:
  8936763a5d5dcf666cc331801d806a70bbd277e353dd5e9fe7c398430b245587.

The product checkout is pre-existing dirty. All experimental code and exact
inputs/outputs will live in one ignored nested research repository. Product
source, production schemas, factories, and pre-existing changes are frozen.

## Corpus and assignments

The byte-identical G5.39/G5.39V corpus is frozen:

| Case | Source SHA-256 | Assignment |
|---|---|---|
| DEV_PUBLIC_TBANK | 25c3b0606ce86852f6ac8fdf6feccbefedb609bcffc5c1581dc95b9b81c5da67 | distributed real/public fact |
| HOLDOUT_REAL_001 | 79af73d5be78df446f768f516ed6eaebd5a9d4bfc6f98c98a4a53a5b5131f37d | independent row-local real holdout |
| LARGE_REAL_001 | 7cfd297786cc91cbccbe0c2ae5bce905a2a11ac6b35e5b0a795cf9c6d41bd015 | distributed large-real fact |
| NEGATIVE_AB_001 | frozen synthetic control | two similar events that must not be mixed |

The evaluator knows the private oracle. Runtime and model input do not receive:

- expected financial type;
- correct role names for the target;
- correct rows or refs;
- correct literals;
- event-group membership;
- broker identity or templates.

## Phase separation

Phase A tests interpretation only. The full reviewed rich region is supplied
directly; region selection is not scored or implied.

Phase B is forbidden unless one Phase A representation passes the frozen
Phase A threshold. Phase C is forbidden unless both A and B have frozen
winners.

## Provider and factory route

- Factory route:
  Gate2StructuredModelClientFactory.create.label_gate3_once.
- Provider profile: google_gemini.
- Model: models/gemini-3.5-flash.
- Structured-output mode: the existing Gemini Gate 3 schema seam.
- Temperature parameter: absent, as required by the sealed route.
- Semantic retry: 0.
- Repair: 0.
- Follow-up correction: 0.
- Answer merge: 0.
- Best-of-N: false.
- Prior-case output reuse: forbidden.

Every slot is claimed before its single submission. A transport failure before
inference remains a terminal result for the frozen experiment version; a
corrected transport experiment requires a new preregistration version and new
slot IDs.

## Phase A hypotheses

### IA — Existing Stage C rich projection

Canonical UTF-8 JSON serialization of the existing complete reviewed Stage C
region, preserving its current table objects, titles, page/table/row/cell refs,
column names, literals, row order, and explicit source relations where already
present. No semantic transformation is added.

### IB — Compact structure-preserving serialization

A deterministic line-oriented serialization of exactly the same tables and
rows, in original order:

table identity and title → page refs → row ref → ordered
column/ref/literal cells.

IB may remove JSON punctuation and repeated field names, but may not remove,
reorder, normalize, summarize, highlight, or add any table, row, cell, ref, or
literal. Existing explicit source relations remain explicitly marked and
unchanged.

### IC — Bounded visual/multimodal representation

Not applicable in this frozen round. The production-equivalent
label_gate3_once route accepts text messages plus structured response schema
and exposes no natural bounded image-input contract. A separate provider
pipeline would violate the task.

### ID — Hybrid

Not preregistered. It may be introduced only by a new frozen experiment
version if IA/IB expose one concrete missing geometry or hierarchy channel. It
will not be added merely to fill the hypothesis budget.

## Model-visible task

The same neutral instructions are used for every slot:

1. use only the supplied representation;
2. propose at most one coherent financial fact;
3. bind every proposed role to one exact visible structural ref and literal;
4. do not combine separate events;
5. return UNRESOLVED with no roles when grouping or required evidence is
   uncertain.

The output contract is:

- status: PROPOSED or UNRESOLVED;
- financial_type: model-proposed string, empty when unresolved;
- roles: role, target_alias, literal.

No explanation, confidence, copied evidence bundle, or hidden selector is
accepted.

## Repetition and slot count

Two independent calls are frozen for every representation/case pair:

| Representation | DEV | HOLDOUT | LARGE | NEGATIVE | Calls |
|---|---:|---:|---:|---:|---:|
| IA | 2 | 2 | 2 | 2 | 8 |
| IB | 2 | 2 | 2 | 2 | 8 |
| Total | 4 | 4 | 4 | 4 | 16 |

All 16 results count. No winner is selected from repeated calls.

## Context budget

- Reviewed region maximum: 125,000 characters.
- Provider input maximum: 55,000 reported input tokens per call.
- Provider output maximum: 2,048 tokens per call.
- Whole LARGE rich projection greater than one million characters is
  forbidden from model context.
- Exact input characters, bytes, tokens, output tokens, region/whole fraction,
  and call count are recorded per slot.

Any representation over a budget fails that case before provider submission.

## Deterministic validation

Before oracle adjudication:

- response conforms to the frozen closed schema;
- every target_alias exists in the allowed region;
- every literal equals the literal at that ref;
- every ref belongs to the supplied region;
- no duplicate contradictory role;
- UNRESOLVED contains no fact type or roles.

The private oracle is applied only after all outputs for the frozen hypothesis
are immutable. It classifies:

- role-complete expected fact;
- incomplete same-event fact;
- coherent other event;
- cross-event fact;
- wrong-event fact;
- invalid ref or literal;
- unresolved.

For NEGATIVE_AB, a proposal is safe only if every selected role belongs wholly
to one explicit event. Mixing A and B is a hard failure.

## Metrics

For every hypothesis and repetition:

- expected facts;
- correct facts;
- role-complete correct facts;
- incomplete same-event facts;
- coherent other-event facts;
- cross-event facts;
- wrong-event facts;
- invalid refs/literals;
- unresolved/abstained;
- region characters and bytes;
- region/whole-document fraction;
- input/output tokens;
- provider submissions and duration.

## Hard failures

A representation is disqualified by any accepted:

- cross-event fact;
- wrong-event fact;
- invented ref;
- invented literal;
- ref outside the region;
- broker-specific hint;
- oracle-filtered row set;
- manual or model repair;
- prior-case output reuse.

Provider/schema invalidity is a semantic result unless inference was never
submitted.

## Phase A success threshold

The decision order is safety → HOLDOUT → LARGE → DEV → completeness → context
cost → KISS.

A representation passes Phase A only when all are true:

1. zero hard failures across all eight calls;
2. HOLDOUT is the role-complete expected fact in 2/2 calls;
3. LARGE is the role-complete expected fact in 2/2 calls;
4. DEV is the role-complete expected fact in 2/2 calls;
5. NEGATIVE_AB is either UNRESOLVED or wholly one explicit event in 2/2 calls,
   with zero mixed roles;
6. all calls remain within the frozen context budgets.

An incomplete same-event proposal is retained as knowledge but does not pass.
No merely best numerical strategy becomes a winner.

If neither IA nor IB passes, the terminal is:
RICH_STRUCTURE_INTERPRETATION_NOT_PROVEN.
Phase B and Phase C will not run.

## Later-phase freeze

If Phase A passes, the exact winning representation contract and all Phase B
selection hypotheses, budgets, calls, and thresholds must be frozen in a new
preregistration before any Phase B inference.

If Phase B passes, the combined pipeline must likewise be frozen before Phase
C. No downstream owner may be changed to make the experiment pass.

## Publication and cleanup

Safe aggregate reports and hashes go under docs/reports/2026-08-12. Exact
customer values, Stage C regions, prompts containing private evidence, images,
oracle data, and provider traces remain ignored outside Git.

Issue #278 is the single GitHub journal. Rejected and winning experimental code
is removed after evidence publication. No experiment is merged automatically.
