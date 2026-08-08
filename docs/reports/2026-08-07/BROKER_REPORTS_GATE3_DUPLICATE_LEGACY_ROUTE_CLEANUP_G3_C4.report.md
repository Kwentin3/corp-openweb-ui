# Broker Reports Gate 3 Duplicate / Legacy Route Cleanup — G3.C4

Date: 2026-08-07
Status: PASS

## Outcome

The production contour has one owner per meaning and one user-facing NDFL
entrypoint. Three live legacy routes were proven to compete with that contour
and were toggled inactive by exact ID. Nothing was deleted.

Disabled:

```text
broker_reports_gate1_normalizer_action
broker_reports_gate2_source_fact_pipe
broker_reports_gate2_domain_source_fact_pipe
```

Preserved active:

```text
broker_reports_gate1_pipe
broker_reports_private_intake_action
broker_reports_gate2_economy_qualification_action
```

The qualification Action is not global and is not attached to `NDFL`; it is a
bounded operator/qualification utility, not a product-stage owner. The private
intake Action verifies server attestations and does not normalize or label a
document. The Gate 1 Pipe is the technical base of the sole Workspace Model.

## Owner inventory

| Function | Sole owner | Other technical components | Why not competing |
|---|---|---|---|
| Gate 2 canonical read/version selection | `CanonicalReaderFactory.create` | proof/readiness scripts | consumers of the same reader contract |
| Gate 3 projection | `Gate3ProjectionFactory.create` | structural chunking | chunking consumes projection; it does not read source independently |
| Gate 3 document labeling/merge | `Gate3ChunkBatchLabelingFactory.create` | bounded per-chunk labeler | layered batch and chunk operations |
| Financial label meaning | `Gate3FinancialLabelDictionaryFactory.create` | generated Skill and generated Tool | GUI projection and byte-exact delivery, not meaning owners |
| Provider execution | `Gate2StructuredModelClientFactory.create` plus existing provider adapter | live proof scripts | same client/adapter boundary; scripts are not published routes |
| FinancialAnnotationsV1 persistence | `Gate3FinancialAnnotationsPersistenceFactory.create` | readiness reader | readiness only validates/reads the same sidecar |
| NDFL orchestration | `NdflWorkflowFactory.create` | OpenWebUI Workspace Model | Workspace Model is the shell bound to the workflow ID |
| User entrypoint | Workspace Model `broker-reports-ndfl` | base Pipe | Pipe is the ACL-restricted internal runtime base required by OpenWebUI, not a second product preset |

Every listed meaning has `OWNER_COUNT=1`.

## Semantic duplication audit

- The nine label definitions exist in the published JSON package only.
- Maintained Python modules and managed Prompt files contain no copied set of
  the nine label IDs/definitions.
- The generated Skill is derived from the dictionary model view.
- The generated Tool embeds the exact verified dictionary bytes.
- The older Gate 2 Prompts describe source-fact extraction operations; they do
  not contain or own the Gate 3 nine-label dictionary and are not attached to
  `NDFL`.
- Live OpenWebUI contains one relevant Skill and one relevant Tool, both already
  read back exact in G3.C1. No duplicate Gate 3 Prompt or Knowledge asset exists.

## Product-path anti-bypass audit

`NdflWorkflowFactory.create` delegates only to:

```text
CanonicalReaderFactory.create
Gate3ChunkBatchLabelingFactory.create
Gate3FinancialAnnotationsPersistenceFactory.create
```

The bounded labeler obtains dictionary meaning through
`Gate3FinancialLabelDictionaryFactory.create`. The product orchestrator has no
direct `ArtifactStore` record read/write, no Pipe-to-Pipe chat, no name lookup,
no old financial semantic-pack import and no second annotation writer.

## Live readback

After cleanup:

```text
LEGACY_FUNCTIONS_INACTIVE=3/3
REQUIRED_FUNCTIONS_ACTIVE=2/2
VISIBLE_PRODUCT_ROUTE_IDS=[broker-reports-ndfl]
VISIBLE_INTERNAL_RUNTIME_BASE_IDS=[broker_reports_gate1_pipe]
USER_FACING_NDFL_MODELS=1
DELETED_RECORDS=0
KNOWLEDGE_RAG=NONE
PROVIDER_CALLS=0
```

## Evidence

```powershell
python -B scripts/live_cleanup_gate3_legacy_routes.py --apply
python -B scripts/live_cleanup_gate3_legacy_routes.py
python -m pytest -q tests/test_broker_reports_gate3_legacy_route_cleanup.py tests/test_broker_reports_ndfl_workspace_model.py tests/test_broker_reports_gate3_openwebui_managed_dictionary.py tests/test_broker_reports_gate3_ndfl_workflow.py --tb=short
```

Result: `21 passed`; live cleanup/readback status `passed`.

Machine-readable evidence:

- `BROKER_REPORTS_GATE3_DUPLICATE_LEGACY_ROUTE_CLEANUP_G3_C4.receipt.safe.json`

## Acceptance

```text
GATE2_READER_OWNER_COUNT=1
GATE3_ORCHESTRATION_OWNER_COUNT=1
DICTIONARY_MEANING_OWNER_COUNT=1
PROVIDER_ROUTE_OWNER_COUNT=1
ANNOTATION_PERSISTENCE_OWNER_COUNT=1
NDFL_USER_ENTRYPOINT_OWNER_COUNT=1
DUPLICATE_RUNTIME_OWNERS=NONE
G3.C4=PASS
```

Historical proof code and records remain for audit. G3.C5 may now perform the
single authorized real NDFL product-path proof; this does not authorize Gate 4.
