# GOAL G5.39X — Autonomous Rich-Document Financial Fact Research Loop

Date: 2026-08-12

Mode: exploratory research only

Product HEAD: 02659a9b0bdfb2f19171d2a070a660af85119d59

Product HEAD tree: 0a696522eb37eca13bb9224a41f7227823c8ce8c

Research journal: https://github.com/Kwentin3/corp-openweb-ui/issues/278

## Outcome

G5.39X terminates at:

**NO_STRATEGY_PROVEN**

Four evidence-driven hypotheses narrowed the problem substantially, but none
produced a complete source-verifiable distributed financial fact on both DEV
and LARGE while satisfying the safety invariants.

One reusable building block was supported: the existing published Role Pack
plus bounded compact Stage C structure produced exact source-bound atomic
financial facts on DEV, independent HOLDOUT, and LARGE. It is not a winner.
The unresolved capability is a source-verifiable relation or aggregation
witness whose authoring method generalizes beyond row identity, proximity,
literal equality, and broker-specific layout rules.

Exploration did not reach the Exploration-to-Confirmation threshold.
Confirmatory proof, production implementation, downstream pressure, Gate 4+
changes, and any dependent GOAL were not run.

## Frozen baseline

The product checkout was already dirty with user-owned Gate 5 work. It was
preserved. Experimental code lived only in an ignored nested research
repository and exact private evidence stayed ignored under local/.

| Authority | Identity |
|---|---|
| Product HEAD | 02659a9b0bdfb2f19171d2a070a660af85119d59 |
| Product tree | 0a696522eb37eca13bb9224a41f7227823c8ce8c |
| G5.39W prepared rich evidence | 8c2cc837a89af0de91a6755d877c91ea403a49ca4d591e90a00a11e68aeb1aa3 |
| G5.39V trace | 18407e17a19b50568950bc93c21dc0be5fc7b7ed8172218355854910c86f5766 |
| Private oracle | d76ade254cfe2c323e0ab73daf0fcf83d598034022e096dba6c86173a65e6c85 |
| Published Role Pack | 43e98dcbef4637506d79927ef19ae1790f9bcfcb69b0045f97c2af9648cd5ba6 |
| Final isolated research commit | f2bbfc4085250728683f0437f8cdec1864a5185f |

The corpus remained byte-identical:

| Case | Source identity | Assignment |
|---|---|---|
| DEV_PUBLIC_TBANK | 25c3b0606ce86852f6ac8fdf6feccbefedb609bcffc5c1581dc95b9b81c5da67 | distributed public pressure |
| HOLDOUT_REAL_001 | 79af73d5be78df446f768f516ed6eaebd5a9d4bfc6f98c98a4a53a5b5131f37d | independent real row-local pressure |
| LARGE_REAL_001 | 7cfd297786cc91cbccbe0c2ae5bce905a2a11ac6b35e5b0a795cf9c6d41bd015 | distributed large-document pressure |
| NEGATIVE_AB_001 | frozen synthetic A/B control | similar operations must remain separate |

## Production-equivalent provider route

Every inference used:

Gate2StructuredModelClientFactory.create

→ label_gate3_once

→ repository-owned authenticated OpenWebUI completion boundary

→ google_gemini / models/gemini-3.5-flash

The factory sealed the exact three-part model context and canonical schema.
Provider context and canonical schema hashes passed preflight for every
executed slot. FACTORY_REQUIRED and FORBIDDEN remain at the canonical owner.
No provider SDK bypass or parallel model route was created.

## Research journal

### Observation from G5.39W

The model had been asked for any one coherent fact while the evaluator expected
one preselected oracle event. Compact IB often returned a real single-row
operation, so wrong-event classification did not establish that rich
interpretation itself was impossible.

### H1 — bounded enumeration

Hypothesis: replace arbitrary single selection with a bounded set of distinct
facts, leaving IB, corpus, model, and route unchanged.

Prediction: the reviewed event appears among the set without loss of precision.

Result:

- 4 calls, one per case;
- 23 schema-valid proposals after one deterministic fact-id correction;
- 0 invented refs, 0 invented literals, 0 A/B cross-event facts;
- all 23 proposals were one-row facts;
- 0 complete reviewed targets.

Verdict: **FALSIFIED**.

Observation: enumeration removed the task/evaluator confound but saturated on
row-local facts. The task had no shared financial role vocabulary.

Freeze commit: 16ccce6de30d7da892eece8c841711017926a4a5.

Corrected adjudicator commit: dfbd4a759d7088ac203bb43d2c9dbd01c35a84c0.

Safe audit SHA-256: 74001ac39dd27adf2dc376861e5e8e9083e3b9fa81c0e1db64ca68b5d5d2981b.

### H2 — published Role Pack atomic facts

Hypothesis: the smallest useful semantic unit is an atomic source-bound fact
under the existing published Role Pack.

Prediction: every positive real case yields exact Role-Pack-compatible facts,
while the A/B control fails closed.

Result:

- 4 calls;
- DEV 8, HOLDOUT 8, LARGE 2 Role-Pack-valid atomic facts;
- NEGATIVE_AB abstained;
- 18/18 proposals had exact refs/literals and valid Role Pack cardinality;
- no relation between atoms was claimed.

Verdict: **SUPPORTED AS A BUILDING BLOCK ONLY**.

Observation: atomic interpretation is workable. Distributed event identity is
the remaining gap.

Freeze commit: e60eba7c169765b67a31de1904ce0d688012dab6.

Safe audit SHA-256: 7107bc4c028f81c8aff8757565177289457f6f34d9e64dfad461753f1b9629a0.

### H3 — one pass atoms plus explicit groups

Hypothesis: one response containing Role-Pack atoms and groups with exact
source witness refs is the minimal distributed-fact contract.

Prediction: privately valid distributed groups appear on DEV and LARGE, while
NEGATIVE_AB remains two disjoint groups or abstains.

Result:

- 4 calls;
- 20 exact Role-Pack-valid atoms;
- HOLDOUT produced 3 groups;
- NEGATIVE_AB produced 2 disjoint groups;
- DEV produced 0 groups;
- LARGE produced 0 groups;
- 0 missing members, invented witnesses, or A/B mixed groups.

Verdict: **FALSIFIED**.

Observation: grouping occurred where an explicit or same-row witness was easy,
but relation authoring competed with atom extraction on the distributed cases.

Freeze commit: 199003881cad8887c00dd5aa3689c2810edf0101.

Final corrected adjudicator commit: 4ae237ce62a8f1dff3d715427fa7d355e2918dc2.

Safe audit SHA-256: 3091b8895c32b54f577a8503c2a11a4347b98f399e75ce76ad8774895815d4ca.

### H4 / H4V2 — relation-only second pass

Hypothesis: relation search needs its own pass over the complete immutable H2
atom set plus the same IB source structure.

H4 stopped in preflight with 0 submissions because the canonical Gemini
adapter required its unused target-alias schema anchor. H4V2 froze the same
semantic task and inputs with that execution-only anchor.

Result:

- 4 executed calls;
- DEV produced 3 groups, all row-local rather than distributed;
- HOLDOUT abstained;
- LARGE produced 1 dividend/tax group, but it covered only 5 of 9 reviewed
  roles and was not a complete distributed fact;
- NEGATIVE_AB abstained;
- 0 missing members, invented witnesses, or A/B mixed groups.

Verdict: **FALSIFIED**.

Observation: a second pass can turn omission into plausible grouping, but
exact refs do not make an incomplete group a complete distributed financial
fact.

H4 preflight freeze: d14e511f739576c4905263a9644a967fd6b6d869.

H4V2 freeze: 2df0fd054dcc73c2df8beec7a4c8fce04ab0a533.

Safe audit SHA-256: e3bb7307ece2c15ccbfa4e1427820a35a513c3d8120bee6f4803b515dff67671.

## Experiment ledger

| Iteration | Input contract | Calls | Input / output tokens | Max input | Verdict |
|---|---|---:|---:|---:|---|
| H1 | IB → enumerate up to 8 facts | 4 | 92,669 / 9,406 | 51,245 | FALSIFIED |
| H2 | IB → published Role Pack atoms | 4 | 93,221 / 6,576 | 51,383 | SUPPORTED building block |
| H3 | IB → atoms plus groups | 4 | 93,313 / 6,734 | 51,406 | FALSIFIED |
| H4V2 | complete H2 atoms + IB → relations only | 4 | 97,302 / 695 | 53,367 | FALSIFIED |
| Total | four frozen hypotheses | 16 | 376,505 / 23,411 | 53,367 | NO_STRATEGY_PROVEN |

All 16 claimed semantic slots produced exactly one provider submission and one
provider response. Semantic retries, repair calls, best-of-N, consensus,
output merging, and post-output prompt changes were zero.

H4 preflight v1 produced 0 submissions and 0 outputs. It is transport/schema
lineage, not an extra semantic call.

## Safety ledger

| Invariant | Result |
|---|---:|
| Invented refs | 0 |
| Invented literals | 0 |
| NEGATIVE_AB cross-event facts | 0 |
| NEGATIVE_AB mixed groups | 0 |
| Missing group members | 0 |
| Invalid witness refs | 0 |
| Accepted explicitly-targeted wrong events | 0 |
| Oracle leaks into prompt/selection/representation | 0 |
| Semantic retry / repair / merge | 0 / 0 / 0 |

H1 emitted 23 coherent non-target row facts under an enumeration task; they
were not relabeled as wrong target events because the model task had no
explicit target. None was promoted as a complete distributed target.

Two deterministic evaluator corrections were frozen after immutable outputs:
an opaque fact-id restriction in H1, and two Role-Pack/schema-witness
consistency defects in H3. The same output hashes were re-adjudicated; no
inference was replayed.

## Context ledger

| Case | Whole Stage C chars | Structural region fraction | H1–H3 IB chars | H4V2 combined chars |
|---|---:|---:|---:|---:|
| DEV_PUBLIC_TBANK | 29,336 | 99.6864% | 28,454 | 33,063 |
| HOLDOUT_REAL_001 | 224,775 | 47.8131% | 104,225 | 109,241 |
| LARGE_REAL_001 | 1,022,810 | 4.7545% | 43,826 | 44,645 |
| NEGATIVE_AB_001 | 2,243 | 96.8792% | 2,006 | 2,039 |

The whole large document never entered model context. Maximum observed input
was 53,367 tokens, below the frozen 55,000-token ceiling. H4V2 included all H2
atoms without oracle filtering.

## Current understanding

### PROVEN

- Task semantics and evaluator semantics must match.
- Compact Stage C structure plus the published Role Pack can yield exact
  source-bound atomic financial facts on all three positive real cases.
- Abstention and explicit A/B separation can prevent false cross-event joins.
- A relation-only pass can produce plausible groups, but plausibility and exact
  refs do not prove complete distributed identity.

### FALSIFIED

- Bounded enumeration alone solves distributed fact recovery.
- One-pass atom extraction plus relation grouping solves DEV and LARGE.
- A second relation-only pass over complete atomic candidates is sufficient
  for complete distributed fact recovery.

### UNKNOWN

- How a broker-neutral source-authored relation/aggregation witness should be
  produced.
- Whether a bounded multimodal representation supplies the missing witness
  without a separate production provider pipeline.
- Bounded-region discovery after an interpreter contract is proven.
- Generalization beyond this corpus and provider/model.

## Candidate contract and confirmation

No candidate contract is selected.

The Exploration-to-Confirmation gate did not open because no approach
recovered a complete distributed fact on more than one real pressure case.
No confirmatory calls were made.

## Verification, cleanup, and KISS

- Isolated research contract/adjudicator tests: 16 passed in 0.393 s.
- Existing model-client, bounded-labeling, CSV/HTML/XLSX, and related-event
  regressions: 48 passed in 6.47 s.
- Anti-drift anchors remain at gate2_model_clients.py lines 44–47; factory and
  one-attempt method remain at lines 80 and 383.
- Product HEAD/tree and production provider files are unchanged by G5.39X.
- Experimental code is removed after evidence hashes and this report are
  fixed; private outputs remain ignored outside Git.
- KISS: one existing representation, one published Role Pack, one existing
  factory/provider route, and at most two model stages. No graph, DB, rules
  engine, broker template, consensus, or downstream fork was introduced.

No staging, product commit, push, PR, production activation, G5.40, or clean
implementation GOAL is authorized by this outcome.

## Final scientific conclusion

The minimal proven contract stops at:

bounded compact rich structure

→ published Role Pack atomic facts

→ exact source validation

The next arrow remains unproven:

atomic facts

→ source-verifiable distributed financial identity

Additional prompt decomposition without a new evidence-bearing relation signal
would repeat the same failure. The current honest terminal is
**NO_STRATEGY_PROVEN**.
