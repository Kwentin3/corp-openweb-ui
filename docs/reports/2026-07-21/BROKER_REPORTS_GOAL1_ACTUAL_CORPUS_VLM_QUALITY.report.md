# Broker Reports Goal 1 — Actual-Corpus VLM Quality and Review Envelope

Date: 2026-07-21

Repository: `Kwentin3/corp-openweb-ui`

Accepted base: `9791f7828e6b83102450ac52a64386f804d0018e`

Delivery branch: `codex/broker-reports-actual-corpus-vlm-quality-v1`

Status: `COMPLETED`

## Verdict

The maintained Gemini/OpenAI visual-table runtime is useful only as a
conditional proposal generator inside a source-visible assisted-review flow.
It is not qualified for unattended extraction or automatic publication.

Across this bounded actual contour, only 5 of 36 provider outputs met the
strict assisted-review usefulness threshold, covering 2 of 9 crops. Zero
crops qualified across both providers and both repetitions. Exact literal
value agreement was 48.03%, omissions were 51.97%, and only 50% of
unit/provider pairs repeated exactly. Seven of 36 provider outputs failed the
deterministic table validator. These results make mandatory source review a
product invariant, not a temporary precaution.

The runtime preserved that boundary: all 18 decisions required review,
provider output had zero canonical authority, and zero canonical tables were
published.

## Authorized bounded contour

The task owner explicitly delegated source inspection and technical verdict
authority. The UTF-8 SHA-256 of that delegation statement is
`7a86287a36423dc3967f358b8a84e4b2670d3800a8024eb64753edc63c25540c`.
The reviewer is recorded as `delegated_agent`, never as a human reviewer or
customer.

The private contour contains six source PDFs and nine production-rendered
table crops. Every crop was regenerated from the sealed detector result with
the maintained `PdfTableRasterFactory`, at 150 DPI with the runtime's 8%
page-relative padding. All nine source table bounds are contained by the
evaluated crop bounds. Source PDFs, page numbers, crop SHA-256 values and
manifest hashes remain in sealed private evidence.

Material characteristics observed in the nine crops are:

| Characteristic | Crops |
| --- | ---: |
| sparse cells | 8 |
| totals/subtotals | 6 |
| borderless layout | 5 |
| simple grid | 4 |
| merged headers | 3 |
| complex broker layout | 3 |
| long-form prose grid | 1 |

The actual contour contains no verified cross-page continuation and no
unreadable or obscured value. Those categories are explicitly unmeasured here;
they are not inferred from synthetic coverage. The long-form standards prose
grid was reviewed and rejected as outside the value-grid product envelope.

## Reference authority

The source-only draft contains 89 visible value-bearing entries. Its old crop
assets used a different no-padding render and six extended entries lacked old
fact-reference coordinates. Goal 1 did not fabricate coordinates or claim the
old crop identity. The delegated reference instead projects only the reviewed
literal label/header/value/state fields and binds each table to the exact
production crop SHA used by the live runtime.

All nine exact production crops were opened at original resolution before the
reference was sealed. The reference records:

- `human_reviewed=false`;
- `delegated_agent_reviewed=true`;
- `customer_accepted=false`;
- `provider_outputs_used=false`;
- `provider_consensus_used=false`.

The review was completed from source crops before provider proposals were
opened for scoring. Provider output and consensus therefore have zero
reference-truth authority.

## Factory-first execution

The evaluator contains explicit `FACTORY_REQUIRED` and `FORBIDDEN` guards.
The live route is:

`evaluate_pdf_dual_vlm_actual_corpus.py:184 -> PdfDualVlmRuntimeFactory.create_for_openwebui:248`

and source rendering is:

`evaluate_pdf_dual_vlm_actual_corpus.py:344 -> PdfTableRasterFactory.create`

The production limit remained eight candidates. Each repetition used chunks
of 8 and 1; the evaluator did not raise the budget. It contains no direct
provider adapter construction, provider payload, credential resolver,
`urlopen`, retry, failover or `create_with_providers` path.

## Live terminal accounting

Two independent repetitions produced 18 runtime decisions and 36 native
provider executions in 583.2 seconds.

| Result | Gemini | OpenAI | Total |
| --- | ---: | ---: | ---: |
| terminal `completed`, validator passed | 16 | 13 | 29 |
| terminal `parse_failure`, validator failed | 2 | 5 | 7 |

The failed Gemini outputs left uncovered grid slots. Failed OpenAI outputs
declared cells with row indexes outside the declared row count and, in two
cases, also left uncovered grid slots. Every failure was terminal; no retry,
provider switch or failover occurred.

Runtime decision accounting:

- 11 `proposal_requires_review`;
- 7 `malformed_provider_output`;
- 9 visible provider disagreements;
- 2 full provider agreements without canonical authority;
- 7 decisions without comparison because a provider contract failed;
- 0 identical-input mismatches;
- 0 canonical tables;
- 0 provider proposals with canonical authority.

Requested and resolved models matched exactly in every execution:

- Gemini `models/gemini-3.5-flash`;
- OpenAI `gpt-5.4-mini-2026-03-17`.

Every execution used prompt
`pdf_dual_vlm_canonical_table_normalizer / dual_vlm_canonical_table_normalizer_v4`,
prompt hash
`59a5d0a27cb8e0d638527ea7721ea575e93c3e5887de13360e3417a2aeb8106b`,
and canonical schema `broker_reports_canonical_table_v1`, hash
`7b9b0fb4e83564d30304f0bf946c100651ea48f1f3f516b1e1f01ab66677140c`.
Gemini's provider-adapted schema hash was
`d71cbb03fd9a0956808952d657f9e1b194533a30e6db73c1314f00c790cc2481`;
OpenAI used the canonical schema unchanged.

## Separate quality measurements

The denominator is 356 literal entry opportunities: 89 source-reviewed
entries × two providers × two repetitions. Numeric agreement uses 332
parseable numeric opportunities. Hallucination is a conservative numeric
value-cell candidate measure: a provider numeric cell not accounted for by a
reviewed source label, header or numeric value. It is not relabelled as a
semantic financial hallucination.

| Metric | Result |
| --- | ---: |
| contract validity | 80.56% |
| strict structural usefulness | 13.89% (5/36 outputs) |
| useful distinct crops | 2/9 |
| cross-provider/repeat-qualified crops | 0/9 |
| exact literal cell/value agreement | 48.03% |
| numeric value agreement | 67.47% |
| row-binding support | 48.03% |
| omission rate | 51.97% |
| numeric value hallucination-candidate rate | 3.65% |
| exact proposal repeatability | 50.00% (9/18 unit/provider pairs) |
| provider disagreement | 50.00% (9/18 decisions) |
| review rate | 100.00% |
| runtime rejection rate | 38.89% (7/18 decisions) |
| provider terminal failure rate | 19.44% (7/36 executions) |
| delegated unsupported-layout rejection | 11.11% (1/9 crops) |

## Product envelope

Supported, with conditions:

- generation of a non-canonical proposal for a source-bound single-page
  numeric crop;
- assisted review only while the exact source crop remains visible and every
  proposed cell is checked;
- unconditional ability to discard the proposal without publication.

Not supported:

- unattended extraction;
- automatic publication or canonical promotion;
- treating provider agreement as truth;
- long-form prose grids;
- cross-page continuations, unreadable values or obscured values based on this
  contour, because those actual categories were not present;
- any claim of universal visual-table automation.

This is a narrow useful boundary: some proposals reduce transcription work,
but no layout/provider combination is reliable enough to remove review.

## Evidence integrity and privacy

| Evidence | SHA-256 |
| --- | --- |
| sealed detection terminal | `301a328a70ac90e228e1bdc01d010381f226479c37f9fbe85c15537df24bd65a` |
| live terminal canonical payload | `d26a961e498ca84290354ef0d3a85a16347d520b76009b2b5330ba11698d5aea` |
| live terminal seal | `47065094276912273fb2fc3941237f01fa205b350e6452d2e9e3d54f7da97539` |
| delegated reference canonical payload | `681dffecf7169addb127a7c7d861c76b98e57d8b0b46747444cb83d03a389d5a` |
| delegated reference seal | `23e02d3d1d3143895bae0a23016846999e28b4bc648f9af7701b0fb2760ca4f9` |
| private score | `fc08a5ef6140fa9a70ca52a34f3035d8f06aaf9585fa9713b5ec4124ca0f1c3d` |
| safe receipt | `f8862b9a2104a8b4f08b24b6ebe06fc784ce78bb27524e2dd67e8cce92eff1f5` |
| transferred live-run evaluator | `c6e93df0b7566dbdc2b3d067c399863540785340334155853cdc2fe81a86f38f` |

The safe repository receipt contains no source values, filenames, private
paths, provider output values, raw provider responses or credentials. Private
terminal, crop, reference and scoring payloads remain under ignored local
evidence only.

The live proof ran from isolated container `/tmp` storage. It did not mutate a
Function, Action, prompt, valve, loader, application record or image. The
OpenWebUI config import emitted the known read-only warning while attempting
to regenerate `static/loader.js`; provider work and terminal sealing completed.

## Deterministic verification

The dedicated test module covers:

- source-only delegated reference finalization and explicit non-human labels;
- rejection when provider output is opened during reference review;
- separate contract, value, omission, hallucination and structure metrics;
- repeatability and review-required aggregation;
- the unchanged 8+1 runtime budget and terminal decision count;
- `FACTORY_REQUIRED` / `FORBIDDEN` anti-drift source guards.

Broader verification also covers the maintained runtime's unresolved and
unsupported fail-closed states, privacy scans, import closure and production
dependency constraints.

Verification result:

- focused runtime/reference/privacy/architecture/bundle suite: `52 passed`;
- full Gate 1 proof service suite: `977 passed, 20 skipped`;
- Ruff on the evaluator and its tests: passed;
- the five full-suite warnings are the existing PyMuPDF SWIG deprecations.

## Acceptance

`ACTUAL_CORPUS_VLM_EVALUATION: COMPLETED`

`PROVIDER_OUTPUT_AS_REFERENCE_TRUTH: ZERO`

`REAL_DISAGREEMENT: VISIBLE`

`REAL_NONDETERMINISM: MEASURED`

`REVIEW_RATE: MEASURED`

`SUPPORTED_PRODUCT_ENVELOPE: EXPLICIT`

`UNSUPPORTED_OR_AMBIGUOUS_INPUT: FAIL_CLOSED`

`CUSTOMER_ACCEPTANCE: NOT_FALSELY_CLAIMED`
