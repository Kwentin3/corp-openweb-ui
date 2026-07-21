# ADR-0009 Broker Reports Bounded VLM and Private Intake

Status: accepted
Date: 2026-07-21
Domain: Broker Reports

## 1. Context

Broker Reports has a maintained deterministic normalization and source-fact
pipeline, but two experimental assumptions must not become product defaults:
generic OpenWebUI file processing and local Paddle-based OCR.  Both violate the
resource or privacy boundary required by this feature.

## 2. Decision

The single normative architecture authority is
[Broker Reports Global Gate Architecture](../blueprints/BROKER_REPORTS_GATE_ARCHITECTURE.md).
This ADR records the acceptance of its 2026-07-21 policy revision:

- Broker Reports owns a private, server-authoritative source intake that cannot
  enter OpenWebUI Knowledge, RAG, embeddings or vector storage;
- Gate 1 owns neutral representation and Gate 2 owns source-local financial
  interpretation;
- production visual-table recovery accepts one declared page or one bounded
  table crop through replaceable Gemini or OpenAI VLM adapters;
- provider output is a typed proposal; deterministic validation and explicit
  source accounting alone can promote it;
- PaddleOCR, PaddleOCR-VL and comparable local OCR stacks are excluded from the
  production runtime and remain proof/offline evidence only;
- Gate 3 and Gate 4 are outside this implementation program.

## 3. Options considered

- Generic OpenWebUI upload plus browser flags: rejected because alternative
  clients and reload can bypass browser policy.
- Local Paddle worker pool: rejected for the qualified production host.
- Whole-document VLM upload: rejected when a page or crop is available.
- Bounded Gemini/OpenAI proposals with deterministic promotion: accepted.

## 4. Boundary / contract

Runtime policy is anchored by `broker_reports_gate1.architecture_policy` and
guarded by architecture tests.  Source intake must issue a server-verifiable
receipt.  Visual requests must record source/image/prompt/provider/model/schema
and validator identities.  Raw provider output and private source material are
never safe-report content.

## 5. Consequences

Existing OCR and dual-VLM research remains reachable Git evidence but has no
production authority.  A provider agreement or confidence score cannot publish
a table.  Unsupported or ambiguous scopes remain review/reject/unresolved
terminal outcomes.

## 6. Risks

Provider schema differences and OpenWebUI upgrade drift require adapter and
bundle guards.  Customer data transfer still requires explicit policy approval.

## 7. Acceptance signal

Architecture guards pass; production bundles have no Paddle dependency; visual
provider profiles are exactly Gemini and OpenAI; generic native file refs are
ineligible for Broker Reports; model canonical authority remains zero.

## 8. Deferred work

The unseen same-family Sber holdout remains an independent external acceptance
debt under `BROKER_REPORTS_CUSTOMER_TEST_DEBT.v1.md`.
