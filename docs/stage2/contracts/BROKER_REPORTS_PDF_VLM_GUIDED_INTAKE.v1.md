# Broker Reports PDF VLM-Guided Intake v1

Status: default-disabled research and shadow contract. It does not change
production Gate 2 selection, source-value authority, OpenWebUI core, OCR, or the
downstream semantic-header contract.

## 1. Purpose

The parser is not required to recognize every unusual table before model use.
It is required to preserve bounded source evidence safely. A VLM may then
propose a concrete physical structure, after which deterministic code binds the
proposal to exact source atoms and either validates it, preserves ambiguity, or
blocks it.

The authority chain is fixed:

```text
original PDF
-> exact parser evidence
-> bounded VLM structural proposal
-> deterministic atom reselection and materialization
-> strict deterministic validation
-> optional downstream semantic projection
```

The original PDF bytes, parser atoms, source references, coordinates, and
checksums remain exact-value authority. A VLM response is never source
authority and cannot promote itself to production use.

## 2. Ownership boundaries

| Domain | Owns | Must not own |
|---|---|---|
| Deterministic intake | Source identity, page identity, atoms, text, coordinates, lines, rectangles, transforms, crops, checksums, budgets, and provenance | Business meaning or a preferred VLM hypothesis |
| Detection assessment | Whether a bounded region is plausible, implausible, uncertain, or absent because upstream work failed | Technical feasibility or holdout selection |
| Processability | Whether the declared bounded scope can be processed safely, with an exact technical reason when it cannot | Table plausibility or accuracy-target usefulness |
| VLM proposal | Visual table presence, bounded regions, approximate axes, headers, spans, alternatives, and uncertainty | Parser thresholds, source values, validator policy, or a final accepted grid |
| Deterministic materialization | Reselecting exact source atoms and applying a supplied topology to physical evidence | Inventing, correcting, or normalizing source values |
| Deterministic validation | Ownership, geometry, separator, span, identity, provenance, budget, and ambiguity decisions | Confidence ranking, majority vote, or silent repair |
| Holdout selection | Frozen target choice under a preregistered policy | Technical feasibility or post-reference target substitution |
| Semantic projection | Meaning of columns and explicit qualifiers after a physical result exists | Physical topology repair or selection |

These boundaries are contracts. A single mixed `eligible=true/false` value is
not a valid replacement for them.

## 3. Independent intake decisions

Each candidate or page scope carries three independent outcomes in the
checksummed internal value produced only by `PdfTableIntakeContractFactory`.
It is embedded in the private target state rather than introduced as a new
standalone artifact or wire format.

### 3.1 Detection assessment

Allowed values:

- `plausible` — bounded evidence may describe one table;
- `implausible` — bounded evidence is normally prose, a table of contents, page
  furniture, or another non-table region;
- `uncertain` — deterministic or VLM evidence cannot distinguish the cases
  safely;
- `absent_due_to_upstream_failure` — the page or region was not observed because
  parsing, inventory, rendering, or another upstream stage terminated.

`plausible` is not acceptance. `implausible` is not technical impossibility.
`absent_due_to_upstream_failure` must never be reported as “no table”.
After a successful VLM call, `table_presence=absent` finalizes detection as
`implausible` and is a normal negative terminal. `table_presence=uncertain`
finalizes detection as `uncertain` and remains an explicit ambiguity. Neither
outcome changes processability by itself.

The record binds the assessment to a document checksum, page reference, scope
type, scope bbox when present, evidence checksum, assessor stage, and closed
reason codes.

### 3.2 Processability

Allowed values:

- `processable` — all hard pre-VLM requirements for the declared scope pass;
- `unsupported` — at least one hard technical requirement fails.

An `unsupported` result contains one or more sorted, unique technical reason
codes and the exact failed observation. A `processable` result contains no
technical failure reason. Processability says nothing about whether a table is
present or useful as a holdout target.

### 3.3 Holdout selection

Allowed values:

- `selected` — chosen by the frozen selection policy before reference access;
- `not_selected` — evaluated but not chosen, with a policy reason;
- `not_evaluated` — target selection never reached this scope.

A processable scope is not automatically selected. Selection cannot read a
human reference, source answer, prior provider response, or post-run forensic
label.

## 4. Minimal deterministic pre-VLM gate

Only demonstrated technical failures may set processability to `unsupported`:

- invalid, empty, non-finite, or out-of-page region;
- invalid or non-invertible coordinate transform;
- neither usable text evidence nor usable raster evidence exists for the scope;
- source document, page, crop, or atom identity cannot be preserved;
- provenance cannot be bound to immutable source references;
- crop bounds, dimensions, pixels, encoding, or bytes are unsafe;
- hard atom, model-JSON, counted-token, output, or transport budget is exceeded;
- exact atom ownership is impossible in the declared scope;
- a closed schema is invalid;
- a required checksum or identity comparison fails.

The following are descriptive evidence or routing metadata. None is a technical
failure by itself:

- page coverage or bbox area;
- row or column count;
- sparse cells or unusual density;
- empty rows, empty columns, separator bands, or currency-symbol columns;
- missing visible grid lines;
- multi-row, merged, or unusually deep headers;
- ruled, alignment-based, mixed, or uncertain border evidence.

Routing metadata may suppress an obvious negative without a provider call, send
an unusual scope to the VLM, or leave it uncertain. It may not silently change
hard budgets or final validation.

## 5. Partial parser evidence

Reaching the existing document inventory cap produces an explicit bounded
partial result. The cap is not raised by this contract.

The existing layout projection carries this evidence without introducing a new
serialization format. Its document diagnostics must record:

- `source_pages_total`;
- `completed_pages_total`;
- `missing_tail_pages_total`;
- `first_missing_page_number`;
- `inventory_objects_retained_total`;
- `inventory_objects_would_be_total`;
- `inventory_objects_limit`;
- the document reason `pdf_layout_document_inventory_budget_exceeded`.

Only fully completed pages are retained. A page on which the cap is crossed is
not presented as complete. The ordered retained prefix, its candidates, source
references, and checksums must survive unchanged. `pages=[]` is valid only when
no page was fully completed; it must not erase an already proven prefix.

Every unprocessed tail page keeps the existing page shape with
`layout_projection_status=partial`, `table_candidate_status=blocked`, empty
inventories, and reason
`pdf_layout_page_not_processed_document_inventory_budget`. Intake maps that
state to detection `absent_due_to_upstream_failure` and holdout
`not_evaluated`. No provider call is permitted merely to compensate for an
inventory-budget terminal.

## 6. VLM structural proposal

Implementation contract: the existing
`broker_reports_pdf_visual_topology_request_v1`,
`broker_reports_pdf_visual_topology_response_v1`, and
`broker_reports_pdf_visual_topology_package_v1` schemas with the closed
revision `pdf_visual_topology_region_proposal_v1`.

The VLM describes a concrete structure visible in the supplied bounded image.
It does not choose a named parser profile or return unrestricted parser
configuration.

Allowed proposal fields are:

- `table_presence=present | absent | uncertain`;
- one bounded table bbox for a candidate-crop request;
- zero, one, or two non-overlapping bounded table bboxes for a page request;
- approximate ordered row and column boundaries;
- `border_evidence=ruled | alignment_based | mixed | uncertain`;
- header-row count;
- merged or spanning regions expressed only as grid geometry;
- descriptive density;
- continuation likelihood;
- bounded alternative structural hypotheses;
- explicit uncertainty and closed unsupported-reason codes.

Coordinates use the coordinate space and transform identity declared by the
request. Axes must be finite, strictly ordered, and inside the proposed bbox.
The response cannot change the coordinate convention.

The output schema contains no authoritative financial values or corrected
numbers. The model must not return:

- parser thresholds or profile names as the interpretation;
- instructions to weaken or disable validators;
- invented, normalized, corrected, or preferred financial values;
- a preferred result selected only by confidence;
- a majority vote or “best-looking” decision;
- business column meaning, currency identity, measure semantics, or fact types;
- unrestricted free-form parser configuration.

Confidence and explanatory text, if present in a bounded field, are diagnostic
only and cannot affect deterministic acceptance.

## 7. Two bounded entry paths

### 7.1 Candidate-crop path

Use this path when a bounded parser candidate exists and deterministic routing
marks it plausible or uncertain.

- exactly one candidate crop is sent;
- the original candidate scope and crop manifest are immutable;
- at most 1,000 opaque source atoms may be supplied with exact parser text,
  bbox, order, and stable anonymous ids;
- the VLM may confirm, reject, or propose one adjusted bbox inside the original
  candidate scope;
- the VLM proposes topology rather than a parser profile.

All atoms in the original candidate scope remain accounted for after adjustment
by three disjoint sets: included, deterministically excluded, or crossing the
adjusted boundary. Their union must equal the complete parent atom set. An
adjusted bbox is admissible for materialization only when the crossing set is
empty. Adjustment cannot make atoms vanish from the ledger or silently cut an
atom at the new boundary.

### 7.2 Page-level proposal path

Use this path only when:

- no bounded candidate exists on an otherwise processable page;
- a broad compound candidate contains several possible table regions; or
- a visible table may lie outside the candidate bbox.

The request contains exactly one rendered page and zero source atoms before the
region proposal. The VLM may return at most two non-overlapping regions. Each
returned region must pass the deterministic technical gate independently before
source atoms are reselected.

Zero model-visible atoms does not mean missing source evidence. Before the
provider call, the page identity and the complete same-page word projection are
validated. After a proposal, the provider-free binder reopens that exact
projection. A page with no exact word projection, duplicate ownership, or any
same-page word outside the declared full-page bbox is `unsupported`; it is not
sent to the model as an image-only guess.

The page image is a proposal surface, not permission to treat the whole page as
one table. A compound page region cannot be accepted whole merely because the
model reports table presence.

## 8. Deterministic materialization

Implementation contract:
`broker_reports_pdf_vlm_region_binding_result_v1`, which embeds the existing
parser observation, geometry, assembly, and source-only materialization
contracts instead of creating another parser or serialization format.

For every proposed region, deterministic code reopens the exact source identity
and reselects parser atoms, words, lines, and rectangles by physical
coordinates. The VLM response contains no source authority.

Materialization must:

- bind document, page, crop, transform, proposal, parser-policy, and source
  checksums;
- revalidate the persisted binder result against the caller-owned proposal
  package, original text-layer projection, parent bbox, and exact region crop
  manifests rather than trusting self-reported nested checksums;
- retain immutable atom text, bbox, source order, and source references;
- use only versioned deterministic tolerances frozen before the provider call;
- account for every source atom in scope as included or excluded;
- assign each included atom to at most one proposed physical cell;
- preserve lines and rectangles as separator evidence;
- expose unresolved placement instead of guessing;
- support a supplied structure that was not anticipated by a template catalog.

Profiles such as `sparse_profile`, `borderless_profile`, or
`financial_profile` must not become the main interpretation mechanism.

## 9. Strict post-interpretation validation

Validation is the terminal portion of
`broker_reports_pdf_vlm_region_binding_result_v1` plus the existing topology
assembly and materialization validators. It is not a second competing solver.

An accepted physical table proves all of the following:

- every included source atom is owned exactly once;
- no source atom or value is invented, duplicated, dropped silently, or mutated;
- row and column placement is compatible with physical coordinates;
- certified separators are not crossed;
- spans are in bounds, non-conflicting, and structurally valid;
- header rows and header spans are structurally valid;
- crop, transform, document, page, parser, and source identities match;
- budgets and provider accounting are valid;
- every excluded atom has an explicit deterministic accounting state;
- ambiguity is not hidden.

If no supplied hypothesis validates, the result is blocked. If two or more
distinct supplied hypotheses validate and deterministic evidence cannot
distinguish them, the result is ambiguous and no table is materialized. A single
accepted result may contain only exact parser evidence.

No confidence winner, majority vote, cross-attempt vote, retry-based selection,
or silent repair is allowed.

## 10. Structural and semantic separation

This contract ends at a validated physical table or an explicit blocked or
ambiguous terminal. It does not decide:

- business meaning of columns;
- ISO currency identity;
- measure semantics;
- financial fact types.

Semantic-header projection may run only after a physical result exists. It may
not repair, merge, split, or select physical topology. Structural ambiguity
remains structural ambiguity even when alternatives appear semantically
equivalent.

## 11. Context and provider cost limits

Each VLM invocation obeys the following fixed ceilings:

| Resource | Candidate crop | Page proposal |
|---|---:|---:|
| PDF scope | No PDF bytes | No PDF bytes |
| Image count | Exactly 1 crop | Exactly 1 page |
| Maximum dimensions | 4,096 x 4,096 | 4,096 x 4,096 |
| Maximum pixels | 16,000,000 | 16,000,000 |
| Maximum encoded image | 8 MiB | 8 MiB |
| Source atoms before proposal | 1,000 | 0 |
| Maximum model JSON | 48 KiB | 48 KiB |
| Maximum counted input | 20,000 tokens | 20,000 tokens |
| Maximum output | 8,192 tokens and 512 KiB parsed JSON | Same |
| Maximum transport response | 2 MiB | 2 MiB |
| Provider calls | 1 `countTokens`, then at most 1 generate | Same |
| Retry and failover | 0 | 0 |

If token counting fails or exceeds the limit, generate-call count is zero. A
generate call must use the exact qualified provider profile and model recorded
before counting. Requested and resolved model identity must match. Hidden retry,
provider failover, and provider-side result selection are invalid terminals.

Model context may contain only the bounded image, declared coordinate space,
the permitted atom view for candidate crops, the bounded structural question,
and the closed output schema. It must not contain whole PDFs, raw forensic
payloads, full source ledgers, business prompts, human references, prior
provider answers, or duplicated metadata.

## 12. Routing and zero-call negatives

Obvious prose, page furniture, and table-of-contents regions should normally
terminate as `implausible` with zero provider calls. Page-level VLM routing is a
bounded exception for a declared page scope, not a fallback over every page in a
document.

Provider accounting is recorded per invocation and in aggregate:

- routed and suppressed scopes;
- count-token and generate calls;
- counted, actual input, and output tokens;
- image and JSON bytes;
- requested and resolved provider/model identity;
- hidden retries and failovers, both fixed to false.

## 13. Holdout purity and metrics

Audited v5 PDFs and every derived crop or label are development evidence only.
A certifying holdout requires new source-frozen PDF hashes and a policy declared
before parser, VLM, or human inspection.

The frozen record must include acquisition rule, source URL, acquisition time,
size, SHA-256, disjointness scan, code inventory, parser policy, intake policy,
selection policy, provider profile, model id, budgets, and target diversity.
Selection operates across the corpus and cannot substitute targets after
freeze. Human references remain sealed until every provider invocation and
deterministic terminal is complete.

Metrics are reported separately:

- detection: real-table recall, false-candidate suppression, upstream-absence
  accounting, and zero-call negatives;
- processability: processable and unsupported scopes by exact technical reason;
- reconstruction: accepted, blocked, ambiguous, atom ownership, provenance,
  topology, omission, duplication, and invention;
- holdout selection: selected, not selected, and not evaluated by frozen reason;
- provider cost: exact calls, tokens, image bytes, response bytes, retry, and
  failover counts.

Transport success is not reconstruction accuracy. Processability is not holdout
eligibility. A safe abstention is not an accuracy pass.

## 14. Shadow integration and persistence

The canonical feature flag is
`pdf_vlm_guided_intake_shadow_enabled=false`. It defaults to false and cannot
change production Gate 2 selection.

The implemented product router has its own default-off control,
`vlm_guided_product_routing_enabled=false`. Enabling guided intake does not
implicitly enable this router. When the product router is enabled for a bounded
run, it emits exactly one target per selected document page using the fixed
precedence `upstream_failure > page_level > candidate_crop >
skip_obvious_non_table`. Ties between candidate inputs are resolved by parser
ordinal and stable candidate reference. This is deterministic routing, not a
model decision.

Page-level routing is additionally closed by
`pdf_vlm_guided_intake_shadow_page_allowlist=""`. The value is an explicit set
of comma-separated scope tokens and is empty by default. The canonical token is
`document_ref::page_ref`. A plain `page_ref` is accepted only when that page ref
is globally unique across the current package; an ambiguous plain ref selects
nothing. The allowlist must not be interpreted as permission to scan every
page. An allowlisted page replaces candidate-crop targets on that page so the
provider is called once for the declared scope. With product routing enabled,
the allowlist only selects which pages the router may inspect; it does not
enable the router or predetermine `page_level` as the route.

The routed terminal artifacts are closed and explicit:

- `broker_reports_pdf_vlm_guided_candidate_intake_result_v1` persists a
  candidate-crop result;
- `broker_reports_pdf_vlm_guided_page_intake_result_v1` persists a page-level
  result and its independently bound regions;
- `broker_reports_pdf_vlm_guided_upstream_terminal_v1` persists a typed
  `guided_upstream_blocked` terminal before a usable guided target exists;
- `broker_reports_pdf_vlm_guided_skip_terminal_v1` persists
  `skipped_obvious_non_table` with zero `countTokens` and zero generate calls.

Candidate-crop results preserve exactly one of `preflight_blocked`,
`provider_failed`, `proposal_absent`, `proposal_unsupported`,
`proposal_ambiguous`, `validation_blocked`, or
`accepted_physical_structure`. Page-level binding preserves exactly one of
`no_table_proposed`, `proposal_ambiguous`, `validation_blocked`,
`partially_validated`, or `accepted_physical_structure`; the persisted
page-level wrapper also uses `proposal_blocked` when no bindable proposal was
created. Routing-only terminals are `guided_upstream_blocked` and
`skipped_obvious_non_table`. A skip is a persisted zero-call terminal, not a
missing result.

Expected startup, factory, source, parser, geometry, raster, identity, package,
JSON-budget, and token-budget failures retain a closed public reason code and
all three intake decisions. They must not be represented only as
`internal_processing_failed`. A genuinely unexpected programming error may use
that safe public reason only when it also persists the three decisions and an
opaque reference to a private diagnostic. Private exception details never
enter the safe artifact.

Candidate-crop target state persists the intake decision finalized with the
actual counted-token observation. Page-level shadow persists the page proposal,
provider-free region binding, region crops, and finalized intake decisions in
one private non-authoritative
`broker_reports_pdf_vlm_guided_page_intake_result_v1` artifact.

Private case artifacts may contain crops, atom text, proposals, provider
responses, materializations, validation details, and diagnostics. Safe summaries
contain only bounded counts, statuses, reason codes, opaque references,
checksums, and provider accounting. Source values, crop bytes, raw provider
responses, and private diagnostics do not enter a user-facing safe report.

The path uses no Knowledge, RAG, vectorization, OCR, or OpenWebUI core patch.
Artifacts follow existing private case retention and verified cleanup rules.

## 15. Acceptance boundary

This contract does not itself prove implementation, fresh-holdout accuracy, or
live readiness. Shadow readiness requires all of the following on the same
frozen source revision:

1. complete repository tests and development regressions;
2. a new unseen source-frozen one-call holdout with post-terminal scoring;
3. exact atom, provenance, provider, and cost accounting;
4. one successful default-disabled live shadow canary;
5. exact cleanup and rollback evidence;
6. repository/live Gate 1 bundle parity;
7. both the new intake shadow and production Gate 2 selection left disabled or
   unchanged as applicable.

If the development gate fails, the only project status is
`BROKER_REPORTS_PDF_VLM_GUIDED_INTAKE_E2E_NOT_WORKING` with exact failed
contracts. If development passes but fresh holdout or live canary has not
passed, use `BROKER_REPORTS_PDF_VLM_GUIDED_INTAKE_E2E_DEVELOPMENT_READY` with
the missing external proof named explicitly. Only a passing development gate,
fresh holdout, and live canary may use
`BROKER_REPORTS_PDF_VLM_GUIDED_INTAKE_READY_FOR_SHADOW_E2E`; that label still
does not authorize production Gate 2 selection.
