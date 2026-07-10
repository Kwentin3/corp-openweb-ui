# Broker Reports Gate 1 Domain Ingestion Refactor Research

Status: `GATE1_DOMAIN_INGESTION_RESEARCH_READY`
Date: 2026-07-09

## Finding

Gate 1 should treat the uploaded package as input reality, not as a set of documents waiting for approval before ingestion. The safe boundary is:

- ingest every readable document;
- preserve deterministic passports, profiles, taxonomy, blockers and private slice refs;
- classify how each document may be used by downstream stages;
- carry unresolved issues forward by stable issue refs;
- keep raw/private payloads behind the ArtifactStore resolver;
- keep Knowledge/RAG/vector stores out of Gate 1.

The old `document_source_eligibility_v0` artifact remains useful as a compatibility view, but it is no longer sufficient as the Gate 1/Gate 1.5 source of truth. It mixed ingestion, source-role approval, duplicate resolution and Gate 2 readiness into one blocking decision.

## Refactor

The refactor adds three deterministic safe artifacts:

- `gate1_issue_ledger_v0`: traceable unresolved/resolved issue ledger.
- `document_usage_classification_v0`: per-document stage usage/readiness classification.
- `domain_context_packet_v0`: handoff packet for downstream source extraction with issue context.

PDF/HTML source-role uncertainty, semantic duplicates and unanswered clarification questions are no longer Gate 1 ingestion blockers. They remain explicit issues and can block later consolidation/declaration-support stages.

## Guardrails

Gate 1 still does not perform:

- source-fact extraction;
- tax/declaration calculation;
- XLS/XLSX export;
- OCR/VLM;
- Knowledge/RAG/vector upload.

The LLM may produce document passports or safe question wording under strict validators. It must not decide issue criticality, downstream readiness or final document use.

## Proof Hooks

Implemented proof hooks:

- new artifacts are persisted as `safe_internal`;
- skipped/unasked gaps remain unresolved in `gate1_issue_ledger_v0`;
- `domain_context_packet_v0` carries unresolved issue refs;
- compact Russian report is ingestion-centric;
- PDF/HTML source-role policy uncertainty is `source_role_policy_uncertainty`, not `source_policy_review_required`;
- vector/Knowledge guard remains expressed in safety flags and live smoke checks.
