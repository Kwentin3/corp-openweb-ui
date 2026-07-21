# OpenWebUI Broker Reports: PDF Structural and Semantic Closeout

Date: 2026-07-15
Repository: `<repository-root>`
Mode: default-disabled, non-authoritative Gate 1 shadow; production Gate 2 selection unchanged.

## Verdict

`BROKER_REPORTS_PDF_STRUCTURAL_AND_SEMANTIC_PARTIAL`

Specific remaining defect: the frozen seven-document `fresh_holdout_v5` corpus produced 27 parser table candidates, but zero passed the preregistered parser-only eligibility contract. The one pre-registration attempt stopped before provider execution, so no fresh structural terminal, post-seal reference or exact-topology score exists.

The semantic-header contract and its live-shadow integration are useful bounded implementation evidence. The synthetic live runtime executed, but the canary proof itself failed in its evidence collector and was rolled back. Neither result repairs the missing fresh structural accuracy evidence. Production Gate 2 authority must remain unchanged.

## What was and was not proved

Proved in this slice:

- process evidence shows that an exact seven-PDF corpus and v5 selection/eligibility policy were declared before execution; no sealed preregistration artifact was produced because eligibility failed;
- the runner failed closed without target substitution or validator weakening;
- no provider, reference or terminal activity occurred after the failed preregistration;
- a separate bounded semantic-header contract binds only existing physical evidence;
- physical ambiguity and semantic equivalence remain separate statements;
- semantic execution is deterministic, private, default-disabled and non-authoritative;
- one synthetic live request produced validated structural, continuation and semantic safe metadata before the evidence collector failed;
- the fail path restored the previous Function, valves and Workspace Model exactly, removed the upload and purged all 33 case records to payload-free tombstones.

Not proved:

- repaired v5 provider behaviour on a fresh real target;
- useful real-document acceptance;
- exact topology accuracy on the new corpus;
- ordinary, borderless/alignment, multi-row/merged and wide target coverage in one completed fresh run;
- a passing standard live canary, retained repository/live bundle parity, exact provider/model routing, token totals, private-payload checksum revalidation or chat-safety assertion;
- any production Gate 2 enablement basis.

## Frozen fresh corpus

Policy id: `official_public_broker_pdf_2026_07_15_v5`
Eligibility policy checksum: `681285290faf3e87d4eccd401d2341ea2d2264e328e361ed064ec3104471b2ec`
Corpus root: ignored private evidence root (path withheld)

The durable declaration is the exact `fresh_holdout_v5` corpus hash set,
selection rule and eligibility-policy checksum in
`broker_reports_gate1/pdf_structural_repair_holdout_contracts.py`, guarded by
`tests/test_broker_reports_pdf_structural_repair_holdout.py`. The fact that this
declaration preceded the one observed command is process evidence from this
bounded run, not a sealed preregistration artifact; the runner intentionally
created no output directory after eligibility failed.

| Document | Official source | Bytes | SHA-256 | Parser candidates | Eligible |
|---|---|---:|---|---:|---:|
| Betterment financial condition 2024 | https://www.betterment.com/BrokerageFinancialStatement | 288909 | `fbe6a299b05615643a0f0264568c65a64bd857b6b77752163b8c2e52bbcbf71e` | 7 | 0 |
| DriveWealth institutional financial condition 2024 | https://legal.drivewealth.com/s/DWI-LLC-Financial-Statements-Short-Final-2024-1.pdf | 1496464 | `738a0279eba3020c9a6cf3a650df254d0a2a8a0800aae80b4889efcc0a8bec57` | 4 | 0 |
| IBKR audited financial condition 2025 | https://www.interactivebrokers.com/download/IB_LLC_4Q25_Aud_Finls.pdf | 1238967 | `6486885e58867d382bd433228193e476a07b6cea2061ddbd74bef1dc6c65a118` | 0 | 0 |
| IBKR mid-year financial condition 2025 | https://www.interactivebrokers.com/download/IB_LLC_2025_UnAud_Finls.pdf | 281480 | `d635df4866a040ce665bfde0da74dbf4dc8933931337a1b023377bf02cf60c2c` | 0 | 0 |
| Moomoo audited financial condition 2025 | https://static.moomoo.com/upload/mfisof/Moomoo%20Financial%20Inc.%20PUBLIC%20Audited%20Financial%20Statements%20FY2025%20%281%29-ba8fb8625ef66452e039e2a473127926.pdf?_=1773715326030 | 1865552 | `bad1e5fa045f0735f02487aca14236d84037f82fd2b1230ee3c56ba3420aee67` | 8 | 0 |
| Moomoo mid-year financial condition 2025 | https://static.moomoo.com/upload/000mfi/Unaudited%20Statement%20of%20Financial%20Condition%20-%20June%2030%202025-8d048206e45d5de503724062532fcad8.pdf?_=1759326419559 | 233753 | `766448b2bf8b9ebe9172e4a07b0392134787a3b642288a93fbe6c0f9999ed0d3` | 8 | 0 |
| Wealthfront financial condition 2026 | https://www.wealthfront.com/static/documents/WB_Financial_Statement.pdf | 731869 | `d3c6736d02e0853369ca6e18d19ab9abdbc79bc46dd346218e949516db0aff63` | 0 | 0 |

During intake, one Fidelity PDF matched the already-known hash `a2d5053e9e3353ad6576c2872579e39aaaeee50663d87b3eb8933f9fdea09009`. It was excluded and replaced before the v5 corpus and policy were frozen. No document or target was changed after the failed attempt.

## Preregistered selection and one-shot outcome

The fixed v5 rule was:

1. sort documents by SHA-256;
2. choose the first document with at least three v5-eligible candidates;
3. select the first alignment-based candidate;
4. select the first wide candidate (`>=12` columns), otherwise the highest-column remaining candidate;
5. select the first ruled candidate, otherwise the first remaining candidate;
6. require both alignment-based and ruled evidence;
7. store targets in page/parser order;
8. permit no post-freeze substitution.

Strategy thresholds remained general and frozen: `aligned_text_v0` required confidence `>=0.8`; `ruled_lines_v0` required confidence `>=0.9` and at least four ruling observations. Existing extent, coverage, area, population and exactly-once word-accounting guards remained enabled.

The only prepare attempt ended with:

`HoldoutError: pdf_structural_holdout_no_eligible_document`

No preregistration output directory was created. Corresponding run, reference and score directories are also absent. There was no retry, policy edit, validator weakening, corpus substitution, provider call or human-reference access after this outcome.

## Structural evidence by document

| Document | Main parser-only rejection families | Target selected | Provider calls | Structural terminal | Exact topology |
|---|---|---|---:|---|---|
| Betterment | coverage `7`; row extent `5`; height `4`; area `4`; sparse `1` | no | 0 | not reached | not measured |
| DriveWealth | coverage `4`; sparse `4`; height `2`; area `2`; row extent `2` | no | 0 | not reached | not measured |
| IBKR audited | no parser table candidate | no | 0 | not reached | not measured |
| IBKR mid-year | no parser table candidate | no | 0 | not reached | not measured |
| Moomoo audited | coverage, height, area and row extent `8` each | no | 0 | not reached | not measured |
| Moomoo mid-year | coverage, height, area and row extent `8` each; sparse `1` | no | 0 | not reached | not measured |
| Wealthfront | no parser table candidate | no | 0 | not reached | not measured |

The reason codes were general contract outcomes:

- `pdf_structural_holdout_candidate_multi_region_coverage_rejected`;
- `pdf_structural_holdout_candidate_row_extent_unsupported`;
- `pdf_structural_holdout_candidate_multi_region_height_rejected`;
- `pdf_structural_holdout_candidate_page_wide_area_rejected`;
- `pdf_structural_holdout_candidate_structural_signal_sparse`.

There were zero accepted tables and therefore zero false accepted tables, but a run with no provider target is not an accuracy success.

## Semantic-header contract

Schema: `broker_reports_pdf_semantic_header_projection_v1`
Policy: `pdf_semantic_header_projection_policy_v1`

The semantic layer is separate from physical topology. It binds to the structural result checksum, physical column ids, header cells/spans/atoms and qualifier evidence. It fixes source-value, geometry and physical-cell mutation to `false`, uses no human reference and cannot change Gate 2 selection.

The bounded vocabulary is:

`description`, `entity`, `date`, `period`, `amount`, `currency`, `unit`, `quantity`, `percentage`, `total_or_subtotal`, `group_header`, `leaf_header`, `unknown`.

`unknown` is valid and produces an incomplete result rather than a guess. Currency and unit qualifiers carry an explicit `cell`, `row`, `column`, `table` or `unknown` scope. A normalized currency code is accepted only when a known literal code is present in bound evidence; symbols are never converted to a currency identity.

The versioned currency allowlist is `AUD`, `CAD`, `CHF`, `CNY`, `EUR`, `GBP`, `HKD`, `JPY`, `NZD`, `RUB`, `SGD`, `USD`; the deliberately narrow unit allowlist is `kg`, `pcs`, `shares`. Out-of-list text remains unknown/incomplete. Hard context limits are `48 KiB`, at most eight physical alternatives and at most three representative rows. Excess is typed and never silently truncated. The v1 projector is deterministic, so it adds zero provider and token calls.

## Physical ambiguity versus semantic equivalence

A controlled core fixture supplied two valid physical alternatives:

- `description | currency symbol | amount`;
- `description | amount containing currency symbol`.

Both projected to `description | monetary_amount`. The result retained:

- `physical_topology_status=ambiguous_multiple_consensus`;
- `physical_ambiguity_preserved=true`;
- `semantic_equivalence_status=equivalent`;
- `semantic_equivalence_does_not_select_topology=true`.

The compact contexts were 1052 and 792 bytes. The qualifier scopes remained physically distinct (`column`/`row` versus `cell`), and the symbol produced no invented ISO code.

The live integration does not materialize an ambiguous structural terminal. It returns `not_projected_physical_ambiguity` and persists no semantic projection until explicit valid physical alternatives are available. Therefore integrated physical/semantic equivalence remains a core-contract proof, not a live ambiguity proof.

## Provider and token accounting

| Path | `countTokens` | Generate | Counted input | Actual input | Output | Hidden retry | Failover |
|---|---:|---:|---:|---:|---:|---|---|
| fresh real v5 holdout | 0 | 0 | 0 | 0 | 0 | no | no |
| deterministic semantic projection | 0 | 0 | 0 | 0 | 0 | no | no |
| live structural shadow attempt, safe metadata only | 4 | 4 | not recovered | not recovered | not recovered | no | no |

The structural runtime invokes synchronous `countTokens` before each generate call and binds the counted request to the generate request. Live safe metadata retained the call totals and no-retry/no-failover flags. The private journal payload was purged before the failed collector could preserve token totals or route details, so independent live call ordering, exact token accounting and provider/model resolution are not claimed.

## Controlled live OpenWebUI shadow

Exactly one controlled canary attempt ran for case
`case_gate1_structural_shadow_canary_112c4da12e2693db` in
the ignored private canary evidence root.
There was no retry.

The synthetic upload and chat reached the shadow runtime. The 33 validated
tombstones retain the following safe metadata:

- two structural fragment terminals, both `accepted_supplied_consensus`, four rows by three columns each;
- four `countTokens` calls and four generate calls in total, with all candidates accounted, zero invented values, no hidden retry and no failover;
- one accepted two-fragment continuation, eight rows by three columns;
- three semantic projections: one `projected` and two `incomplete`;
- the incomplete reasons were `pdf_semantic_header_unknown_or_unmapped_columns` and `pdf_semantic_header_representative_rows_incomplete`;
- the joined continuation projection was persisted and explicitly incomplete for the representative-row bound;
- `base_normalization_mutated=false`, `knowledge_rag_used=false`, no customer values/crop bytes/raw provider response/private diagnostics in safe metadata, and `production_gate2_selection_changed=false`.

The evidence collector then exited with `canary_ssh_command_failed`. Root cause
was a missing `import hashlib` in the embedded remote summary program; its
semantic checksum path necessarily executed because three semantic projection
records existed. Therefore `_assert_canary` did not complete,
`canary.safe.json` was not created, and the new bundle was not retained. The
missing import is fixed locally and an executable regression test now exercises
that checksum path. The live attempt was deliberately not repeated.

The failure path completed rollback. A separate read-only check confirmed:

- current Function SHA equals the backup exactly:
  `4c5d5005bce561e41b2ca50df58b0d958a070b694c9c163471c66b22af1fb150`;
- valves equal the backup exactly, SHA
  `44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a`,
  with both shadow flags `false`;
- Workspace Model `test` equals its backup, SHA
  `e69cbd498fd6a0a8b69ab944f386c038ea5bd3436989df069ebb57d581d0e594`;
- zero uploads remain under the canary filename;
- all 33 case records are `none_tombstone`, with zero active records and zero
  payload references or inline payloads.

The finalizer surfaced the original body error rather than a cleanup error,
which means its safety barrier, upload/artifact cleanup, runtime snapshot,
bounded quiescence, Workspace Model check and terminal restore returned without
recorded error. The conservative postmortem is stored as
`canary.postmortem.safe.json`; it explicitly marks the standard canary as
failed and does not manufacture the missing private evidence.

Repository/live Gate 1 parity is not closed: the local generated bundle SHA is
`a12f23af02221287f3f8fbaf5d202c58147493f0adc79f33ec8796c56ddcd231`,
while live intentionally remains on the restored pre-canary Function SHA above.

## Regression and closed-world evidence

- fresh v5 holdout contract tests: `40 passed`;
- final semantic-focused core/shadow/Pipe/bundle selection: `58 passed`, five warnings;
- live-canary harness after the collector fix: `39 passed`, including execution of the embedded semantic checksum path;
- final full service suite: `589 passed`, five warnings;
- changed-file Ruff scope: clean; `compileall`: clean;
- Gate 1 build executed twice with byte-identical SHA `a12f23af02221287f3f8fbaf5d202c58147493f0adc79f33ec8796c56ddcd231`;
- Gate 1/Gate 2 bundle closed-world tests: `10 passed`;
- repository/live parity: not closed because the failed canary correctly restored the previous live Function.

Repository-wide Ruff cleanliness is not claimed. An exploratory broad check
reported 119 findings outside this changed-file verification scope; unrelated
lint debt was not rewritten in this slice.

The Gate 1 bundle is generated only through the existing bundle builder. No workspace-only runtime import, filesystem path hack, ghost dependency, OpenWebUI core patch, OCR route, Knowledge/RAG/vector path, new parser, provider or solver framework was added.

## Supported and unsupported boundary

Supported by deterministic contract/tests:

- accepted supplied physical bindings with immutable exact values;
- small semantic vocabulary with `unknown`;
- separate/embedded and table/column/row/cell qualifier evidence where unambiguous;
- explicit semantic equivalence across supplied physical alternatives;
- private case-scoped persistence and safe count/status visibility;
- typed context, alternative and evidence-binding failure;
- two-fragment structural continuation and live safe-metadata evidence that the joined semantic projection persisted as explicitly incomplete.

Still unsupported or unproved:

- fresh real provider accuracy under repaired v5;
- real target coverage for ordinary, borderless/alignment, multi-row/merged and wide classes;
- physical ambiguity materialization in the live adapter;
- scanned/image-only PDF and OCR;
- unsafe cuts, tables above existing limits, and more than two continuation fragments;
- production Gate 2 authority.

## Operator, rollback and production boundary

Both valves remain default-disabled:

- `pdf_structural_repair_shadow_enabled=false`;
- `pdf_semantic_header_shadow_enabled=false`.

The canary temporarily enables them only for one synthetic case, then restores the original valves and Function before slow cleanup. It removes the upload, purges case artifacts through `ArtifactStoreFactory`, checks tombstones and private payload absence, repeats bounded quiescence checks, verifies no side effects and redeploys the new bundle only after every check passes. Any failure restores the previous Function and valves.

Production Gate 2 authority must not be recommended. The necessary condition — a fresh real holdout with useful acceptance and zero false accepted tables — was not reached.

## Final decision

`BROKER_REPORTS_PDF_STRUCTURAL_AND_SEMANTIC_PARTIAL`

The frozen v5 eligibility contract rejected all 27 real parser candidates before provider execution, so no sealed fresh terminal/reference score exists. The single synthetic live attempt also failed in its evidence collector before it could seal the standard canary and repository/live parity, even though the runtime safe metadata was useful and rollback completed exactly. Keep the feature default-disabled and non-authoritative; close this epic at the explicit partial boundary rather than starting another open-ended architecture cycle.
