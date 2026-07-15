# Broker Reports PDF Semantic Header Projection v1

Status: default-disabled, non-authoritative Gate 1 shadow. The contract does not change the physical table, source-value authority or production Gate 2 selection.

## Purpose and boundary

The physical contract answers where rows, columns, cells, headers and spans are. This semantic contract answers what the already-existing headers and columns appear to mean.

The semantic projection may bind existing physical evidence together. It must not:

- move or rewrite a source value;
- add, remove or merge a physical cell;
- repair or select a physical topology;
- invent a header, amount, currency or unit;
- use a human reference;
- override a structural conflict;
- become production Gate 2 authority.

The original PDF and parser source references remain exact-value authority. A semantic result is always non-authoritative.

## Versioned contract

- projection schema: `broker_reports_pdf_semantic_header_projection_v1`;
- policy: `pdf_semantic_header_projection_policy_v1`;
- configuration schema: `broker_reports_pdf_semantic_header_projection_configuration_v1`;
- currency policy: `semantic_currency_code_allowlist_v1`;
- unit policy: `semantic_unit_code_allowlist_v1`;
- factory entrypoint: `PdfSemanticHeaderProjectionFactory.create`;
- projection statuses: `projected`, `incomplete`;
- physical statuses accepted by the standalone projector: `accepted_supplied_consensus`, `ambiguous_multiple_consensus`;
- semantic equivalence statuses: `not_applicable`, `equivalent`, `different`, `incomplete`.

The compact vocabulary is:

`description`, `entity`, `date`, `period`, `amount`, `currency`, `unit`, `quantity`, `percentage`, `total_or_subtotal`, `group_header`, `leaf_header`, `unknown`.

`unknown` is a valid and expected answer. An unknown or unmapped physical column makes the overall projection incomplete; it is not silently guessed.

`amount` projects to the logical type `monetary_amount`. This lets a separate currency column and an amount cell containing currency produce the same logical business signature while preserving their different physical layouts.

## Required structural evidence

Every projection is bound to the sealed `structural_result_checksum`. Every physical alternative has a canonical grid checksum and derived physical column identifiers.

Every semantic field binds to one or more existing items:

- physical column ids;
- header cell refs;
- canonical header-span refs;
- header atom ids;
- qualifier refs when applicable.

Validators recompute the input hash from the supplied structural checksum,
topology status and complete physical-alternative input. They also recompute
physical column and span ids and reject cross-column evidence, unbound refs,
changed checksums, unknown keys, duplicate ownership and non-canonical order.
Span anchors are checked against their covered column range. The input is hashed
before and after projection; mutation is a typed failure.

The effective context limits and literal-code policy versions are stored in a
checksummed configuration object. Its checksum is part of the projection id, so
two different budgets cannot produce the same artifact identity.

## Currency and unit qualifiers

Currency and unit are qualifiers of a measure, not assumed physical columns. A qualifier records:

- `kind`: `currency` or `unit`;
- `scope`: `cell`, `row`, `column`, `table` or `unknown`;
- the measure field id;
- bound physical column ids;
- evidence cell and atom refs;
- an optional normalized three-letter code.

A normalized currency code is legal only when one literal allowlisted code
exists in the bound physical evidence. The v1 allowlist is `AUD`, `CAD`, `CHF`,
`CNY`, `EUR`, `GBP`, `HKD`, `JPY`, `NZD`, `RUB`, `SGD`, `USD`. Arbitrary
three-letter text is not currency. Embedded literal evidence such as
`Amount (USD)` is supported. A symbol such as `$` is evidence of currency but is
never converted to `USD`. Missing, multiple or conflicting evidence remains
`unknown` or incomplete.

The v1 unit allowlist is deliberately small: `kg`, `pcs`, `shares`. Other unit
text remains unknown rather than being normalized speculatively.

The projector supports qualifiers found in a separate column, a measure cell, a
column header, a group header, the whole table, a representative row or a
representative cell. A separate qualifier column is absorbed only for an
unambiguous one-to-one measure binding. Multiple candidate measures yield a
typed incomplete result. It never creates a missing currency or unit column.

## Physical ambiguity and semantic equivalence

For an explicit set of valid physical alternatives, the standalone projector evaluates every alternative independently.

- Physical status remains `ambiguous_multiple_consensus`.
- `physical_ambiguity_preserved=true` remains mandatory.
- `semantic_equivalence_does_not_select_topology=true` remains mandatory.
- Equivalent logical signatures may yield `semantic_equivalence_status=equivalent`.
- Different signatures yield `different`.
- An unknown field, unmapped column or budget block yields `incomplete`.

Semantic equivalence never proves that one physical grid is correct. The current live adapter persists a projection only for an accepted materialized binding. An ambiguous structural terminal has no authoritative materialized binding, so the live adapter reports `not_projected_physical_ambiguity`; the standalone contract and fixtures still prove that explicit physical alternatives can be compared without hiding ambiguity.

## Context and execution budgets

The v1 projector is deterministic and makes no provider/model call. Therefore it adds zero `countTokens` and zero generate calls.

Its bounded semantic context contains only:

- the canonical grid checksum and dimensions;
- physical header rows, hierarchy and spans;
- exact header cells and atoms;
- at most three representative non-header rows when qualifier evidence requires them.

Limits:

- hard maximum `48 KiB` canonical JSON per physical alternative;
- hard maximum `8` physical alternatives;
- hard maximum `3` representative rows.

Callers may configure lower limits but cannot raise these maxima. An over-limit
alternative list is rejected before deep-copy or shape traversal. The full PDF,
crop bytes, forensic payload, source ledgers, human reference and unrelated Gate
2 context are excluded. Context excess returns a typed incomplete result; it
does not truncate silently. If qualifier-bearing data rows exceed the
representative-row limit, the result records `representative_sample_incomplete`
instead of claiming exhaustive row/cell semantics.

## Persistence, visibility and safety

The live path requires both valves:

- `pdf_structural_repair_shadow_enabled`;
- `pdf_semantic_header_shadow_enabled`.

Both default to `false`. A successful projection is stored as a private case
artifact. Accepted two-fragment continuations receive a separate projection over
the canonical joined materialization; fragment projections do not substitute
for it. Only bounded safe metadata enters the structural shadow summary,
including counts, statuses, reason codes, opaque refs, target ids, provider-call
flags and safe file outcomes. Typed failures may persist a
private diagnostic, while customer values, raw provider responses and private
diagnostics do not enter the safe report.

All semantic results fix these guards:

- `source_value_change_allowed=false`;
- `geometry_change_allowed=false`;
- `physical_cell_change_allowed=false`;
- `reference_answer_used=false`;
- `authority_state=non_authoritative`;
- `production_gate2_selection_changed=false`.

## Supported and unsupported cases

Supported by the contract and repository fixtures:

- one- and multi-row headers;
- grouped and leaf headers;
- separate and embedded currency evidence;
- table, column, row and cell qualifier scopes;
- explicit unknown qualifiers;
- semantic comparison across supplied physical alternatives;
- fail-closed context and alternative budgets.

Typed incomplete or not-projected outcomes remain correct for:

- a structural terminal other than accepted or explicit ambiguity;
- an ambiguous live terminal without usable materialized alternatives;
- unknown or conflicting header meaning;
- an unbound semantic field or qualifier;
- non-literal currency normalization;
- context or alternative budget excess.

No semantic outcome can promote the feature to production Gate 2. That decision still requires a fresh source-frozen structural holdout with useful zero-false-acceptance results plus a passing live shadow proof.

## Operator procedure and rollback

Run from:

`D:\Users\Roman\Desktop\Проекты\corp-openweb ui\services\broker-reports-gate1-proof`

PowerShell procedure:

```powershell
$runId = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$outputDir = "..\..\local\stage2\broker_reports_gate1_structural_semantic_shadow_canary_$runId"
python scripts/build_openwebui_pipe_bundle.py --target gate1
python scripts/live_gate1_structural_shadow_canary.py `
  --env-file '..\..\.env' `
  --output-dir $outputDir
if ($LASTEXITCODE -ne 0) { throw 'live structural/semantic canary failed' }
python scripts/live_verify_broker_reports_stage2_delivery.py --env-file '..\..\.env'
```

Preconditions: the output directory is absent; the SSH target is already in
`known_hosts`; the Workspace Model `test` is active, allows file upload, has
file context disabled and has no Knowledge attachment; both semantic and
structural valves are false or absent.

The canary temporarily deploys the generated Gate 1 bundle, uploads one
synthetic two-page PDF with `process=false`, enables both valves only for its
case, and exercises the real provider. Before slow cleanup it restores the old
valves and Function. It then removes the upload, purges the case through
`ArtifactStoreFactory`, verifies tombstones/private payload absence, observes a
bounded `5 + 15 + 30` second no-late-write window and checks no-RAG runtime
counters. The new default-disabled bundle is redeployed only after every check
passes. Any failure keeps or restores the prior Function and valves.

The safe result is `canary.safe.json` in the requested output directory. Private
rollback input and the synthetic PDF stay under its `private` subdirectory and
must not be shared as customer output.

### Observed 2026-07-15 attempt

The one bounded attempt used
`broker_reports_gate1_structural_semantic_shadow_canary_2026-07-15_run1`. The
synthetic runtime created two accepted fragment records, one accepted joined
continuation and three semantic projections (`projected=1`, `incomplete=2`).
The evidence collector then failed with `canary_ssh_command_failed` because its
embedded remote program omitted `import hashlib` before recomputing a semantic
configuration checksum. Consequently the standard canary did not pass and the
new bundle was not retained. The missing import and an executable checksum-path
test are fixed locally; this live attempt was not repeated.

A read-only postmortem confirmed exact restoration of the previous Function,
valves and Workspace Model, both shadow flags disabled, no matching upload, and
all 33 case records reduced to payload-free tombstones. The safe postmortem is
`local/stage2/broker_reports_gate1_structural_semantic_shadow_canary_2026-07-15_run1/canary.postmortem.safe.json`.
It deliberately does not claim the provider/model route, token totals, chat
safety, private checksum revalidation or repository/live bundle parity that the
failed collector could not seal.

## Troubleshooting statuses

| Status or reason | Meaning | Operator action |
|---|---|---|
| `disabled` | Semantic valve is off. | Expected outside the bounded canary; do not enable production authority. |
| `not_projected_structural_terminal` | The physical table was not accepted. | Inspect the safe structural outcome; semantics cannot repair it. |
| `not_projected_physical_ambiguity` | More than one physical supplied grid remains valid. | Preserve ambiguity; do not materialize or select a topology. |
| `not_projected_historical_conflict` | Durable repeat history contains a conflict. | Require review; later agreement cannot erase the conflict. |
| `not_projected_structural_failure` | Structural shadow failed before a usable terminal. | Follow the safe file outcome/next action; keep both valves off. |
| `incomplete` + `pdf_semantic_header_unknown_or_unmapped_columns` | At least one physical column has no supported meaning. | Accept `unknown`; add no document-specific alias. |
| `representative_sample_incomplete` | More qualifier-bearing rows exist than the bounded sample covers. | Treat row/cell qualifier semantics as incomplete. |
| `qualifier_binding_incomplete` | A qualifier cannot be bound one-to-one to a measure. | Preserve separate physical columns; do not guess the measure. |
| `context_budget_exceeded` or `alternative_budget_exceeded` | The semantic input exceeds a hard bound. | Keep the typed block; reduce the upstream supported scope only through a general contract change. |
| `projection_failed` | Validation or persistence failed. | Use the private diagnostic only with case-authorized access; never expose raw details to the user/LLM. |

The safe summary exposes bounded status/reason counts. If cleanup, quiescence,
Workspace Model state, bundle SHA, provider accounting or no-RAG counters fail,
the canary is failed evidence even when the chat request itself returned `200`.
