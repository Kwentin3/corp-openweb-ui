# GOAL G5.39Y — Human Visual Reasoning Reverse Engineering

Date: 2026-08-12

Mode: exploratory research only

Product HEAD: `02659a9b0bdfb2f19171d2a070a660af85119d59`

Product tree: `0a696522eb37eca13bb9224a41f7227823c8ce8c`

Research journal: <https://github.com/Kwentin3/corp-openweb-ui/issues/278>

## Outcome

G5.39Y terminates at:

**VISUAL_SIGNAL_NOT_SUFFICIENT**

The rendered channel restored a human-readable table/page view, but it did not
close distributed event identity. Two independently frozen visual experiments
produced the same failure shape as the preceding text-only baselines:

- DEV remained atomic or row-local and never became the complete distributed
  purchase/charge fact;
- LARGE produced one plausible dividend/tax group, but it covered only 5 of 9
  reviewed roles;
- NEGATIVE A/B remained safely separate;
- zero refs, literals, or cross-event groups were invented.

The human trace explains why. In the distributed cases, a person does not join
the event because values occupy one visual block. The decisive act is semantic
and arithmetic reconciliation across different sections: aggregate
quantity/value/charge for DEV and instrument/date/rate/quantity plus
gross-tax-net consistency for LARGE. The rendered image makes the operands and
their column meanings legible; it does not source-author the relation.

The narrower secondary finding is:

**SEMANTIC_RECONCILIATION_CAPABILITY_UNRESOLVED**

This report does not claim that vision is useless or that no stronger VLM could
do better. It proves only that the frozen rendered regions plus a complete
neutral ref legend were not the missing relation signal for this corpus and
published model. Exploration did not converge, so confirmatory proof did not
open and no candidate contract is selected.

## Frozen scope and authority

The product checkout already contained extensive user-owned Gate 5 changes.
They were preserved. Experimental code and exact outputs stayed under ignored
`local/`; this GOAL adds only privacy-safe report artifacts.

| Authority | Identity |
|---|---|
| G5.39X report | `4e20dedef46a5170dec15b3a1e800cc9e7250bc67bb186cf2d14d42c4ee0fc58` |
| G5.39W prepared rich evidence | `8c2cc837a89af0de91a6755d877c91ea403a49ca4d591e90a00a11e68aeb1aa3` |
| G5.39V trace | `18407e17a19b50568950bc93c21dc0be5fc7b7ed8172218355854910c86f5766` |
| Frozen oracle | `d76ade254cfe2c323e0ab73daf0fcf83d598034022e096dba6c86173a65e6c85` |
| Published Role Pack | `43e98dcbef4637506d79927ef19ae1790f9bcfcb69b0045f97c2af9648cd5ba6` |

The source corpus remained byte-identical to G5.39V/X. Exact customer values,
images, prompts, source paths, raw provider responses, and oracle content are
not published in Git.

## Phase 1 — human reasoning reverse engineering

The rendered source was reviewed before any G5.39Y model call. `YES` below is
an agent visual-review baseline, not independent human sign-off. An independent
human reviewer was not run and this is a stated limitation.

### DEV_PUBLIC_TBANK

Human analyst can identify the event: **YES**.

The person sees a wide executed-trades table on one page and cash operations,
security movement, and security-directory sections on the next. The source
visual facts are the section titles, headers, column alignment, row boundaries,
page order, and exact values. These facts explain what each operand means.

The join itself is semantic: the person recognizes transaction, charge, and
holding meanings, then reconciles the individual trade quantities and values
to the cash and holding totals. No border, merged cell, whitespace band, or
same-page block directly asserts that all components are one economic event.

- cue lost in plain text: physical geometry, color, borders, typography;
- cue surviving Stage C/Text IB: titles, rows/cells, column meaning, exact
  operands, source order;
- rendered-only decisive cue: none observed;
- semantic cue: aggregate quantity/value/charge reconciliation.

### HOLDOUT_REAL_001

Human analyst can identify the event: **YES**.

The fact is row-local. A table title and header assign meaning to cells in one
bounded row. Row boundary, column binding, and the explicit cell values are
sufficient. The same information survives Stage C, current text IB, Canonical,
and Gate 3 on this control.

- cue lost in plain text: cosmetic grid geometry;
- cue surviving Stage C/Text IB/Gate3: table, header, row, cells, source refs;
- rendered-only decisive cue: none observed;
- semantic cue: minimal row interpretation only.

### LARGE_REAL_001

Human analyst can identify the event: **YES** within the frozen three-page
diagnostic region.

The person sees separate withholding, dividend, and dividend-accrual tables.
Section titles and headers establish the meaning of each table. Repeated
instrument/security, date, rate, quantity, and amount signals narrow the
candidate, but none is identity by itself. The decisive human step is checking
the gross amount, withholding, and net amount as one coherent economic
calculation across the three sections.

- cue lost in plain text: raw column geometry, visual page simultaneity,
  typography and borders;
- cue surviving Stage C/Text IB: section titles, row/cell identity, exact
  operands, source order and page refs;
- rendered-only decisive cue: none observed;
- semantic cue: instrument/date/rate/quantity plus gross-tax-net
  reconciliation;
- Gate 3 loss: the three required pages are separate chunks.

### NEGATIVE_AB_001

Human analyst can identify two events: **YES**.

The synthetic rendered control contains both transactions and both charges
with equal visual treatment. The explicit order key repeats between the trade
and charge tables and separates A from B. This is a genuine source-authored
relation signal and survives both image and text representations. No target
row, role, or event was highlighted.

## Source-verifiable vs semantic cues

| Cue | Classification | Role in human decision |
|---|---|---|
| section/table title | source-verifiable | assigns local table meaning |
| header and column alignment | source-verifiable | binds literals to column semantics |
| row/cell boundary | source-verifiable | closes row-local facts |
| page/section order | source-verifiable | navigation only; not identity |
| repeated instrument/date/rate | source-verifiable values | narrows candidates; insufficient alone |
| explicit order key in NEGATIVE | source-verifiable relation | proves A/A and B/B separation |
| aggregate equality | semantic interpretation over source operands | decisive for DEV |
| gross-tax-net consistency | semantic interpretation over source operands | decisive for LARGE |
| transaction/charge/holding or dividend/tax ontology | semantic/domain reasoning | needed to choose reconciliation |
| typography, borders, whitespace | source visual fact | not decisive on the frozen targets |
| broker-template convention | outside knowledge | not used and forbidden |

## Phase 2 — cue preservation matrix

`Operands only` means that exact source values survive, but their economic
relation is not published as a source object.

| Human cue | Rendered | Visual extraction | Stage C | Text IB | Current Gate 3 |
|---|---|---|---|---|---|
| table/section title | YES | pixels/readable | YES | YES | HOLDOUT yes; DEV/LARGE lost |
| header and column binding | YES | pixels, no stable semantic ref bridge | YES | YES | HOLDOUT yes; DEV/LARGE lost |
| row/cell boundary | YES | pixels | YES | YES | HOLDOUT yes; DEV/LARGE lost |
| raw geometry/borders/whitespace | YES | YES | partial/not authoritative | NO | NO |
| page/section order | YES | YES | YES | YES | YES, but LARGE fragmented |
| repeated candidate keys | YES | readable | YES | YES | partial/fragmented |
| explicit cross-table order key | YES | readable | YES | YES | control only |
| aggregate arithmetic relation | operands only | operands readable | operands only | operands only | partial/lost |
| gross-tax-net relation | operands only | operands readable | operands only | operands only | fragmented |
| same economic event assertion | NO | NO | NO | NO | NO |

The visual-exclusive losses are real, but they are not the cues that make the
distributed target one event. Stage C and the compact text IB already preserve
the headers, rows/cells, source order, and exact operands a human uses. The
remaining step is semantic reconciliation, not recovery of border geometry.

## Provider and representation freeze

The locally published and approved profile was frozen before semantic output:

- provider/profile: `google_gemini`;
- requested/resolved model: `models/gemini-3.5-flash` exact match;
- provider-profile revision:
  `f0c2fd84daeee8cb33d907435dd843d70eb2db7b0f88b66bc49533f3fb9ac4e3`;
- image input and structured output: qualification passed;
- temperature 0, candidate count 1, thinking level `minimal`;
- maximum counted input: 60,000 tokens;
- maximum output: 16,384 tokens;
- retry, repair, best-of-N, merge, provider failover: all zero/false.

Google's official model page lists Gemini 3.5 Flash as accepting image input
and structured output with a 1,048,576-token input limit. The official image
guide documents inline PNG input and multi-image support. Verification date:
2026-08-12.

The experiment used the existing
`PdfGridExperimentProviderFactory.create_for_openwebui` route, which resolves
the published OpenWebUI provider connection and performs native Gemini
count/generate calls. No provider payload or credential path was added to the
product tree.

Each case supplied one composite PNG containing every page in the frozen
bounded region plus the complete Stage C-derived structural locator legend.
Every visible row/cell in the region remained available. Region selection was
the already-frozen post-oracle G5.39V diagnostic boundary; no discovery claim
is made.

## Phase 3 — research loop

### H1 — rendered region plus neutral locators, direct atoms and groups

Observation: human-readable schema might be the missing signal obscured by
flattened text.

Hypothesis: a rendered bounded region plus a complete neutral ref legend lets
the VLM produce exact atoms and complete distributed groups directly.

Prediction: complete DEV and LARGE groups appear without an A+B mixed group.

Freeze:
`913b834a5a937d6ae47d5f4afa56de631088d594f9e98674cd7df796d7bcf6e5`.

Result:

| Case | Counted input | Output | Facts | Groups | Best reviewed coverage |
|---|---:|---:|---:|---:|---:|
| DEV | 15,686 | 2,254 | 6 | 0 | 2/6 |
| HOLDOUT | 52,687 | 1,600 | 4 | 2 | 0/9 |
| LARGE | 27,836 | 700 | 2 | 1 | 5/9 |
| NEGATIVE A/B | 2,329 | 1,067 | 4 | 2 | 6/6 for A; no A+B mix |

Verdict: **FALSIFIED**.

What was learned: vision preserved safety and handled the explicit order key,
but distributed cases retained the text-only failure shape. Atom extraction
may still have competed with relation reasoning.

Safe audit SHA-256:
`6286f790d00716f9266ba4788272401c3746e8a92fb79ebb8975496f60d62fca`.

### H2 — frozen H2 atoms plus rendered relation-only pass

Observation: H1 could have failed because direct atom extraction and relation
grouping competed in one response.

Hypothesis: with the exact frozen H2 Role Pack atoms supplied immutably, the
rendered page channel lets a relation-only pass close distributed identity.

Prediction: DEV and LARGE reviewed coverage improves to completeness while
the negative case remains non-mixed.

Freeze:
`4ba43eb55cefbe95e9dd7911823bed047d6bbd643fed3ec1e410de0df03ff0a1`.

Result:

| Case | Counted input | Output | Frozen atoms | Groups | Best reviewed coverage |
|---|---:|---:|---:|---:|---:|
| DEV | 17,496 | 376 | 8 | 3 | 2/6 |
| HOLDOUT | 54,618 | 319 | 8 | 2 | 5/9 |
| LARGE | 28,073 | 214 | 2 | 1 | 5/9 |
| NEGATIVE A/B | 2,221 | 42 | 0 | 0 | 0/6; abstained |

Verdict: **FALSIFIED**.

What was learned: decomposition was not the blocker. DEV again produced only
row-local groups and LARGE repeated the same incomplete dividend/tax group.
The visual delta did not change the distributed event boundary.

Safe audit SHA-256:
`218d5606d4da9a137394245de0eff7fa3c62cbe09242d6982bff577009c27112`.

## Machine-adjudication boundary

All eight provider outputs copied the model-view `schema_version` instead of
the canonical output-schema const. They are therefore schema-invalid and
accepted outputs are **zero**. No output was normalized, repaired, retried, or
replayed.

The semantic proposals remain useful only as frozen diagnostics. This schema
failure does not conceal a winner: before applying the schema hard failure,
neither H1 nor H2 contained a complete DEV or LARGE candidate. It is an
additional fail-closed defect, not the cause of incomplete grouping.

H1 NEGATIVE also contained two Role-Pack-invalid atoms, so its otherwise
correct A/B separation is not a machine-valid proposal. H2 used the prior
frozen valid atoms and abstained because the H2 negative atom set was empty.

## Multimodal and context ledger

| Iteration | Calls | Source-page/control images | Input tokens | Output tokens | Max input |
|---|---:|---:|---:|---:|---:|
| H1 | 4 | 7 | 98,538 | 5,621 | 52,687 |
| H2 | 4 | 7 | 102,408 | 951 | 54,618 |
| Total | 8 | 14 supplied across calls | 200,946 | 6,572 | 54,618 |

Four unique composite PNGs occupied 1,818,502 bytes. DEV supplied two full
pages, HOLDOUT one, LARGE three, and NEGATIVE one complete synthetic rendered
control. The 65-page LARGE document was never supplied.

All eight semantic slots produced exactly one provider submission and one
provider response. Token-count calls were preflight accounting, not semantic
retries. No result selection or consensus occurred.

## Safety ledger

| Invariant | Result |
|---|---:|
| invented refs | 0 |
| invented literals | 0 |
| A+B mixed groups | 0 |
| invalid witness refs | 0 |
| missing group members | 0 |
| oracle rows/roles in model input | 0 |
| highlighted target rows/events | 0 |
| semantic retry / repair / merge | 0 / 0 / 0 |
| schema-invalid outputs | 8 |
| accepted outputs | 0 |

## Human vs model comparison

| Case | Human grouping | Model grouping | Difference |
|---|---|---|---|
| DEV | reconciles multiple trades, cash charge, and holding change | atoms or row-local groups only | model did not perform the aggregate cross-table reconciliation |
| HOLDOUT | closes one row under its header | enumerated/grouped other row-local candidates | bounded region contains many valid rows; visual schema does not select the reviewed event |
| LARGE | reconciles dividend, withholding, and accrual across three sections | one 5/9 dividend/tax group | model omitted the accrual/quantity/net closure despite seeing all pages |
| NEGATIVE | joins trade A→fee A and trade B→fee B by explicit order key | two disjoint H1 groups | source-authored key was usable; no cross-event mix |

This is not a subjective similarity claim. The gap is specific: the model used
explicit local/key relations but did not reproduce the human arithmetic closure
for distributed cases.

## Current knowledge

### PROVEN

- Human distributed-event reading on this corpus uses source-visible table
  semantics plus semantic/arithmetic reconciliation.
- Rendered regions with a complete neutral locator legend can preserve exact
  provenance and A/B separation.
- Adding that rendered channel to both direct and relation-only tasks did not
  improve complete DEV/LARGE recovery over the frozen text baselines.
- Visual geometry, typography, borders, and whitespace are not the decisive
  missing cues on these targets.

### FALSIFIED

- Rendered region + neutral source locator legend is sufficient for complete
  distributed event recovery.
- Rendered region makes a relation-only pass over frozen exact atoms sufficient.

### UNKNOWN

- A broker-neutral source-verifiable authoring method for semantic arithmetic
  reconciliation.
- Sensitivity to a separately preregistered stronger multimodal model.
- How to discover the bounded region without oracle after an interpreter
  contract is proven.
- Generalization beyond the frozen corpus/provider/model.

## Candidate, confirmation, and stopper

No candidate contract is selected. Confirmation was not run because neither
exploratory hypothesis recovered complete DEV and LARGE targets. A third prompt
over the same images would add no information signal and would violate the
research contract.

The strategic stopper applies: the next meaningful capability would need
source-verifiable semantic reconciliation evidence or a separately frozen
model-sensitivity question. Neither is authorized or implemented here. This
GOAL does not redesign CanonicalArtifact, add a parser, create a relation DB,
change provider abstraction, or open G5.40/dependent work.

## Verification, privacy, cleanup, and KISS

- Isolated adjudicator tests: `4 passed in 0.95s`.
- Existing model-client, bounded-labeling, visual-provider, CSV/HTML/XLSX, and
  related-event regressions: `57 passed in 7.04s` under PowerShell with no test
  ENV override.
- The irreversible boundary in the experiment is the single provider
  submission; tests and ledgers assert immutable one-attempt outcomes after it.
- Factory/anti-drift owner remains
  `PdfGridExperimentProviderFactory.create_for_openwebui`; product Gate 2
  `FACTORY_REQUIRED`/`FORBIDDEN` anchors remain unchanged.
- Exact outputs, images, customer values, prompts, oracle, and provider traces
  remain ignored outside Git; reports contain aggregates and hashes only.
- Experimental production code: none.
- KISS: existing rendered artifacts, one neutral ref legend, one existing
  provider factory, one VLM call per case, and at most two research stages.
- No graph, relation DB, broker rule, retry, consensus, product integration,
  staging, commit, push, PR, or activation was introduced.

## Official provider sources checked on 2026-08-12

- <https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash>
- <https://ai.google.dev/gemini-api/docs/image-understanding>
