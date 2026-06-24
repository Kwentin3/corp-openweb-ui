# OpenWebUI Web Search Integration Boundary

Status: draft with native Brave smoke baseline observed on 2026-06-23.

## Purpose

Define the allowed integration order for Stage 2 Web Search so the first slice
does not create unnecessary custom code.

## Boundary Order

1. Native OpenWebUI Web Search configuration and runtime proof.
2. OpenWebUI Functions / Actions / Tools / OpenAPI Tool Servers when native
   capability has a proven product gap.
3. OpenWebUI `external` Web Search provider or a thin wrapper when provider
   protocol or policy requires normalization.
4. Private sidecar only when native/external-wrapper paths cannot satisfy
   privacy, cost, source or runtime requirements.
5. Deep fork only after separate proof, owner approval and ADR.

## Native-Owned Concerns

Native OpenWebUI should own for the first pilot:

- Web Search toggle;
- provider engine selection;
- provider key storage through Admin UI/env/config;
- result count;
- search concurrency;
- web loader controls;
- domain/fetch filters when available;
- group/feature permissions when available;
- source display behavior.

Current runtime note:

- Brave `brave_llm_context` passes native smoke when OpenWebUI uses direct
  Web Search docs context.
- The extra vectorized web-search retrieval path is not accepted yet; runtime
  diagnostics showed it can return `0` sources after successful search and
  embedding.
- Treat that path as a deferred known issue. It should be fixed later only when
  the product needs long page loading, classic `brave`, SearXNG page loading, or
  full RAG over fetched content.
- Do not introduce a wrapper or sidecar to solve that path until the current
  native direct-context baseline is insufficient for a product scenario.

## Stage 2-Owned Concerns

Stage 2 docs/contracts own:

- provider choice recommendation;
- privacy boundary;
- source attribution acceptance;
- usage/cost event expectations;
- smoke matrix;
- runtime probe report;
- owner decision list.

## Provider Keys

- Keys live only in server-side env/Admin UI/approved secret store.
- Browser must not receive key values.
- Reports may name required config variables but must not print values.

## Group Permissions

- Web Search should start with admin-only or a small pilot group.
- All-user rollout is allowed only after provider, privacy, source and cost
  acceptance pass.
- If native group permissions are insufficient, document the exact runtime gap
  before proposing wrapper/sidecar work.

## Cost And Usage

- Use native analytics/provider dashboard first.
- Add usage event capture only if pilot visibility is insufficient.
- Hard billing/rate enforcement is a separate owner decision and must not be
  silently folded into the native pilot.

## When A Wrapper Is Allowed

Use OpenWebUI `external` provider or a thin wrapper when:

- the selected provider has no direct native engine;
- query minimization/redaction must happen outside OpenWebUI;
- source metadata must be normalized;
- provider errors/rate limits need stable typed mapping.

## When A Sidecar Is Allowed

Use a private sidecar only after runtime proof shows a specific unresolved gap:

- provider key or metadata exposure cannot be controlled natively;
- group permissions cannot be enforced;
- logs cannot be sanitized;
- source attribution cannot meet acceptance;
- required cost controls cannot be implemented through native config, provider
  dashboard or a thin wrapper.

## When A Fork Is Allowed

A fork is allowed only with:

- reproduced native failure;
- owner approval;
- ADR update;
- rollback plan;
- narrow patch scope.
