# Broker Reports LLM Document View Checklist v1

Status: `CONTRACTED_INACTIVE`

Schema version: `broker_reports_llm_document_view_checklist_v1`

Machine schema: `BROKER_REPORTS_LLM_DOCUMENT_VIEW_CHECKLIST.v1.schema.json`

## Three-pass law

1. `MANAGED_DOCUMENT_ONLY` receives only one validated Managed Document. It
   projects model-visible metadata, safe anchors, complete ordered blocks,
   tables, unknowns, visuals, relations, issues, losses and quality.
2. `LLM_VIEW_ONLY` receives only `*.llm-view.txt`. The independent
   `ManagedDocumentLlmViewAuditor` parses the tagged-text grammar without
   importing the renderer or reading the Managed Document or Pass A output.
3. Comparison receives only the two integrity-sealed checklists.

Each checklist contains the complete private projection, structural inventory,
one SHA-256 per scalar path, ordered and unordered aggregate value hashes and a
canonical integrity seal. Full checklist values remain outside Git.

## Comparison dimensions

```text
DOCUMENT_PASSPORT
METADATA
ANCHORS
BLOCK_ORDER
BLOCK_CONTENT
TABLES
UNKNOWNS
VISUALS
RELATIONS
ISSUES
LOSSES
VALUE_HASHES
QUALITY
```

Allowed comparison statuses are `MATCH`, `MISSING_IN_VIEW`, `EXTRA_IN_VIEW`,
`WRONG_ORDER`, `WRONG_VALUE`, `WRONG_STATUS`, `WRONG_RELATION`,
`WRONG_POINTER`, and `UNVERIFIABLE`.

Any non-MATCH result is critical for DOC3. Pass C reports only hashes,
dimensions and categories; it does not echo source content.

## Acceptance

```text
CRITICAL_VIEW_PARITY_MISMATCHES_TOTAL = 0
NONCRITICAL_VIEW_PARITY_FINDINGS_TOTAL = 0
FULL_VIEW_PARITY = TRUE
```

This is representation parity only. It does not qualify PDF-to-LLM semantic
equivalence, a model, a prompt, a provider or product activation.
