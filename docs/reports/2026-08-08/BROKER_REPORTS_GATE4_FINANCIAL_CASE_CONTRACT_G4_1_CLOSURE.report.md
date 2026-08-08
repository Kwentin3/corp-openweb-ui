# Broker Reports Gate 4 Financial Case Contract — G4.1 Closure

Date: 2026-08-08

GOAL status: `G4.1_CLOSED`

Runtime status: `CONTRACT_ONLY_INACTIVE`

## Result

G4.1 defines one current Gate 4 semantic unit:
`Gate4FinancialCaseFactV1`. The closed schema is sufficient to represent one
current validated Gate 3 annotation as an immutable case-scoped fact with:

- deterministic fact identity;
- exact Gate 3 sidecar, annotation and canonical binding;
- exact financial type selected by Gate 3;
- typed date/decimal/text role values;
- source literal and canonical target provenance for each value;
- explicit missing roles;
- `role_complete` or `role_incomplete` status.

No runtime materializer, storage write, SQL cache, relation, tax logic or
product activation was added.

## Repository evidence used

The contract was derived from the current product path and direct authorities:

- current immutable `FinancialAnnotationsV2` persistence through
  `Gate3FinancialAnnotationsPersistenceFactory.create`;
- exact role resolution through
  `Gate3RoleValueResolverFactory.create_from_active_canonical`;
- current Financial Label Dictionary and Role Pack identities;
- server-injected OpenWebUI user/case/chat/workspace context represented by
  `ArtifactAccessContext`;
- existing ArtifactStore/ArtifactResolver access, retention and purge
  lifecycle.

The historical Managed Financial Domain was audited but not activated. It is
tied to the older Gate 2 classification, terminal source coverage, registry,
HMAC snapshot and generic query model. Reusing it as current Gate 4 would add
unneeded responsibilities and a large migration surface.

## OpenWebUI-first decision

G4.1 introduces no parallel case registry, ACL, lifecycle, API or upstream
OpenWebUI table.

- `case_binding` comes only from the existing trusted `case_id`, or the trusted
  `chat_id` fallback already supplied to the Function runtime.
- user/workspace authorization and retention remain in the existing artifact
  envelope rather than being copied into the fact payload.
- native OpenWebUI File remains source custody.
- private financial values do not move into Chat, Knowledge, RAG or vectors.
- the physical persistence/cache choice remains explicitly deferred to G4.2.

This keeps OpenWebUI upgrades isolated from the Broker Reports domain contract.

## Representative contract proof

All examples are synthetic and contain no customer data. Their structure and
profiles come from the current Gate 3 V2/Role Pack boundary.

| Financial type | Gate 4 values | Source/missing result |
| --- | --- | --- |
| `SECURITY_PURCHASE` | `2026-01-10`, `ACME`, `10`, `125.00`, `USD`, unit price `12.50` | all required roles available; `role_complete` |
| `SECURITY_DISPOSAL` | `2026-02-11`, `ACME`, `4`, `60.00`, `USD`, unit price `15.00` | all required roles available; `role_complete` |
| `DIVIDEND_INCOME` | `2026-03-12`, `8.00`, `USD`, optional asset `ACME` | asset retains exact-text source binding; `role_complete` |
| `TRANSACTION_CHARGE` | `2026-02-11`, `1.25`, `USD` | optional asset remains explicit `missing`; `role_complete` |
| `TAX_WITHHELD` | `2026-03-12`, `1.20`, `USD` | optional asset remains explicit `missing`; `role_complete` |

The proof also shows a required missing purchase date producing
`role_incomplete`, while incorrectly claiming `role_complete` fails schema
validation.

## Fail-closed proof

Executable tests reject:

- an invented tax field or confidence;
- JSON floating-point values for decimals;
- locale-formatted decimal values in the normalized field;
- duplicate roles;
- value/source data attached to a missing role;
- `role_complete` with a required missing role;
- `role_incomplete` when only an optional role is missing.

The schema reuses the exact Gate 3 target schema for annotation and role source
bindings. It does not define a second locator grammar or copy the nine Role
Pack profiles.

## Identity and rebuild proof

The normative `fact_id` algorithm hashes the schema identity, trusted case
binding, exact immutable sidecar ID, annotation index, canonical binding and
financial type. Tests prove:

- the same exact input rebuilds the same ID;
- changing the sidecar ID changes the fact ID;
- changing the canonical version changes the fact ID.

The future SQL cache is therefore derived and replaceable; it is not the
semantic source of truth.

## Cross-platform contract repair

The required Windows branch checkout exposed a pre-existing byte-portability
gap in the newly hash-pinned Gate 3 Role Pack and role-response schema. Their
semantic content was unchanged, but CRLF worktree bytes failed the published
SHA-256 checks.

The narrow repair adds exact `text eol=lf` rules for those three pinned/exact
copy paths. Their resulting SHA-256 values remain the published values:

- Role Pack: `43e98dcbef4637506d79927ef19ae1790f9bcfcb69b0045f97c2af9648cd5ba6`;
- role-response schema/package copy:
  `9585d83de337e8fbacf1f000a797c4018c034ab9fa0e28e5054c1842c29b99d8`.

No resource content, meaning or runtime logic changed.

## Validation

- focused G4.1 contract proof: `12 passed`;
- Gate 3/G4 contract, Role Pack, role labeling, persistence and architecture
  compatibility contour: `101 passed, 1 warning`;
- exact canonical/Gate 3/G4 CI guard contour: `213 passed, 5 warnings`;
- generated managed assets and three Function bundle parity checks: `PASS`;
- Ruff correctness checks: `PASS`;
- full service suite: `2960 passed, 5 skipped, 6 warnings` in `977.91s`.

The warning is the existing invalid-escape deprecation in
`local_pdf_dual_vlm_canonical_table_report.py`; it is unrelated to G4.1.

## KISS check

Added:

- one versioned fact contract;
- one closed schema;
- one executable contract test module;
- current authority/handoff updates;
- one dated closure report;
- three exact LF checkout policies for already hash-pinned files.

Reused:

- `FinancialAnnotationsV2`;
- the current Dictionary and Role Pack;
- `Gate3RoleValueResolverFactory` boundary;
- shared Gate 3 target grammar;
- OpenWebUI-injected scope;
- existing ArtifactStore access/lifecycle semantics.

Not added:

- aggregate case DTO;
- materializer or parser;
- SQL/ORM/migration;
- storage artifact type;
- API/read service;
- relation/graph/LLM layer;
- broker-specific or tax logic;
- OpenWebUI upstream fork.

## Next allowed Goal

`G4.2 — deterministic materialization + SQL cache`.

G4.2 must start from current clean `main` after this Goal is merged. It must
first compare native OpenWebUI persistence/extension points with the existing
ArtifactStore boundary before admitting any new SQL surface.
