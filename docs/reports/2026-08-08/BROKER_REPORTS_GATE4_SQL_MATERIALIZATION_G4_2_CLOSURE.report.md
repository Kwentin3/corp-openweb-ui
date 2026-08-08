# Broker Reports Gate 4 Deterministic Materialization + SQL Cache — G4.2 Closure

Date: 2026-08-08

GOAL status: `G4.2_CLOSED`

Runtime status: `IMPLEMENTED_INTERNAL_SLICE`

## Result

Current validated `FinancialAnnotationsV2` can now be mechanically converted
into `Gate4FinancialCaseFactV1`, persisted in a minimal SQL read cache and read
by ordinary code. The path uses no LLM, broker-format parser, financial
classification, role inference, relation logic or tax rules.

The SQL rows are a rebuildable projection of the G4.1 fact contract. Their
deletion loses no semantic authority: the same exact current Gate 3 sidecar,
canonical binding and trusted case context rebuild the same logical fact IDs
and values.

## OpenWebUI-first decision

G4.2 reuses the existing project-local OpenWebUI integration boundaries:

- the existing `ArtifactStore` SQLite file, rather than a second database;
- `ArtifactResolver` and `ArtifactAccessContext`, rather than a new ACL or case
  registry;
- Gate 3 readiness and exact active canonical identities for freshness;
- the existing artifact lifecycle, extended by two small cleanup triggers for
  derived rows;
- the existing bundled Function build and closed-world import path.

No upstream OpenWebUI table, model, API, storage subsystem, user/workspace
model, Knowledge/RAG path or vector store was added or changed.

## Materialization boundary

`Gate4FinancialCaseMaterializerFactory.create` owns the deterministic
projection for one exact V2 sidecar. It:

- reads the sidecar through the current Gate 3 persistence owner;
- resolves role values through
  `Gate3RoleValueResolverFactory.create_from_active_canonical`;
- verifies the published Role Pack identity;
- keeps exact source literals and canonical targets;
- applies only the closed G4.1 date/decimal/text normalization policy;
- preserves explicit missing roles and computes `role_complete` or
  `role_incomplete`;
- computes the closed deterministic `fact_id`.

Invalid values and stale or inconsistent upstream bindings fail closed. Missing
required values remain explicit and are never guessed or defaulted.

## SQL cache boundary

Two technical tables are created in the existing ArtifactStore SQLite:

- `gate4_financial_case_cache_generation_v1` records the exact upstream
  generation for each materialized document;
- `gate4_financial_case_fact_cache_v1` stores the canonical G4.1 fact JSON plus
  the minimal indexed projections required for current reads.

The cache exposes only case-scoped reads for all materialized facts, financial
type, exact `fact_id`, asset and inclusive ISO date period. Three matching
indexes cover type, asset and date within the authenticated
user/case/workspace-model scope. SQL does not define financial roles or
financial types.

## Representative proof

The real-behaviour proof builds a synthetic canonical artifact and a validated
V2 sidecar through the maintained ArtifactStore path. It materializes,
persists and reads:

| Financial type | Ordinary-code read proof |
| --- | --- |
| `SECURITY_PURCHASE` | typed purchase query, asset query and period query |
| `SECURITY_DISPOSAL` | typed disposal query |
| `DIVIDEND_INCOME` | typed dividend query |
| `TRANSACTION_CHARGE` | typed charge query |
| `TAX_WITHHELD` | typed withholding query |

The proof also checks comma-decimal and day-first date normalization while
retaining the exact source literal, and checks a required missing role as
`role_incomplete`.

## Rebuild, freshness and lifecycle proof

The executable proof performs:

1. materialize;
2. persist and read;
3. clear the case cache;
4. rebuild the same exact sidecar;
5. compare the complete fact values and IDs byte-for-byte.

The rebuilt facts are identical. Replacing either the selected Gate 3 sidecar
or the active canonical version makes the old generation fail with
`gate4_cache_stale`; it is never silently returned as current. Existing
ArtifactStore purge/lifecycle transitions delete the matching derived rows.
Cross-tenant reads cannot observe or reuse another scope's cache.

## Validation

- focused G4.2 materialization/cache proof: `6 passed`;
- Gate 3/Gate 4 boundary and bundled Function contour: `80 passed, 5 warnings`;
- all previously failing full-suite files after correcting the external pytest
  TEMP boundary and declaring the two G4.2 package authorities:
  `62 passed, 1 warning`;
- ten managed generated-asset/proof checks: `PASS`, with zero provider calls;
- three generated Function bundles reproduced byte-identically: `PASS`;
- final full service suite: `2966 passed, 5 skipped`, zero failures and zero
  errors in `1011.922s`.

Warnings are existing dependency/deprecation warnings and are unrelated to
G4.2.

## KISS review

Added:

- one deterministic materializer module;
- one SQL cache/runtime module;
- two technical tables, three query indexes and lifecycle cleanup triggers;
- one real-behaviour test module;
- current authority/handoff updates and this closure report.

Reused:

- the G4.1 fact contract;
- current Gate 3 V2 persistence, Role Pack and role-value resolver;
- exact active canonical selection;
- ArtifactStore SQLite, resolver, access context and lifecycle;
- the existing closed-world Function bundler.

Removed during self-review:

- the initial case-wide loop that rebuilt every selected document. G4.2 now
  rebuilds one exact sidecar/document only; multi-document assembly remains a
  separately approved G4.3 responsibility.

Not added:

- a second database, ACL, case registry, lifecycle or API;
- broker-specific code or source-format parsing;
- new financial meaning, tax logic or LLM calls;
- reconciliation, deduplication, relations or generic query/event layers.

## Scope limit and next allowed Goal

Case reads contain the current generations that have actually been
materialized and make no whole-case completeness or reconciliation claim.

Next allowed Goal: `G4.3 — multi-document case assembly`.

G4.3 has not started.
