# Broker Reports Gate 3 Financial Label Dictionary v1

Status: `G3.C1_MANAGED_OPENWEBUI_BINDING_ACTIVE`

Closeout status: `G3.3M_C_COMPLETED`

Managed GUI binding: `active`

Gate 3 product route activation: `NDFL_ONLY`

Product cutover: `NDFL_ONLY_BY_G3.C5`

Date: 2026-08-07

## Purpose and sole authority

The sole normative owner of current Gate 3 financial-label meaning is the
versioned package resource
[`gate3_financial_label_dictionary.v1.json`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_financial_label_dictionary.v1.json).
All loads, drafts, validation, diffs and deterministic model rendering go
through
[`Gate3FinancialLabelDictionaryFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_financial_label_dictionary.py).

Prompt, Skill, Tool, Knowledge, renderer code, provider output and generated
Markdown are not meaning authorities. The managed OpenWebUI Skill and Tool are
hash-pinned generated projections of this resource: the Skill is the readable
operator surface and the Tool returns the exact resource bytes. The earlier
Gate 2 Financial Semantic Pack is a separate historical contour and is not
imported or adapted here.

Published v1 identity is:

```text
dictionary_id: broker-reports-financial-labels
semantic_version: 1.0.0
status: PUBLISHED
file_sha256: 182e8d7f3604ad3d06d93c4d913df17979f21aeea669123d70c10be9d9652850
```

## Exact v1 scope

The published version contains exactly these nine human-approved labels, in
this order:

1. `SECURITY_PURCHASE`
2. `SECURITY_DISPOSAL`
3. `DIVIDEND_INCOME`
4. `COUPON_INCOME`
5. `INTEREST_INCOME`
6. `SECURITIES_LENDING_INCOME`
7. `ACCRUED_COUPON_COMPONENT`
8. `TRANSACTION_CHARGE`
9. `TAX_WITHHELD`

`BROKER_SERVICE_CHARGE` is not part of v1. The deferred labels
`REPO_EVENT`, `SECURITIES_CUSTODY_CHARGE`, `RETURN_OF_CAPITAL`,
`STOCK_DISTRIBUTION_EVENT` and `TAX_SETTLEMENT_OR_REFUND` are also absent.
Their absence is not a financial or tax conclusion.

Each label has exactly one identifier, meaning, positive application rule,
negative application rule, example list and confusion list. The normative
wording exists only in the published JSON resource.

## Lifecycle

The minimal lifecycle is:

```text
immutable published version
-> explicit package-resource load
-> editable full-copy draft bound to the base identity
-> structural and mechanical conflict validation
-> deterministic unified diff
-> exact-draft human approval receipt
-> deterministic prepared version bytes
-> separate human-reviewed repository change adding resource and hash pin
-> explicit load by semantic version
```

Draft validation rejects unknown fields, malformed or duplicate label IDs,
empty required text/lists, an example owned by more than one label and a rule
repeated on both positive and negative sides of one label. These are mechanical
checks only; code does not claim to validate financial truth.

An approval is valid only when its decision is `APPROVED`, all reviewer fields
are non-empty and its `draft_sha256` equals the exact validated draft. Preparing
bytes never activates them. A version is loadable only after a separately
reviewed code change adds a new versioned package resource and its exact file
hash to the immutable published-version pin set. Existing version resources
and pins must never be overwritten.

Old annotation results bind `dictionary_id` and `semantic_version` under the
current `FinancialAnnotationsV2` contract (and historical V1 identity).
Publishing a later version cannot
silently change that binding.

## Deterministic model view

`render_model_markdown(semantic_version)` loads the complete selected
dictionary and deterministically renders all labels. It performs no retrieval,
ranking, truncation, lazy loading or RAG. The checked
[`model.generated.md`](../research/BROKER_REPORTS_GATE3_FINANCIAL_LABEL_DICTIONARY.v1.model.generated.md)
is a reviewable generated view whose exact parity is tested; it is not a second
authority.

The model view contains only the nine label cards and their classification
content. Dictionary identity, version binding, approval and exact-file hash stay
outside model-visible text because they do not help choose a label.

## Managed OpenWebUI binding

The operator path is:

```text
Workspace
-> Skills
-> Broker Reports Financial Labels
```

Stable IDs are:

```text
Skill ID: broker-reports-financial-labels
Tool ID: broker_reports_financial_label_dictionary
Tool method: load_financial_label_dictionary
Prompt ID: NONE
```

The Skill content contains the deterministic full `render_model_markdown`
projection and pins its SHA-256. The Tool contains a compressed exact copy of
the published JSON and verifies its file SHA-256, dictionary ID, semantic
version, published status and label count before returning it. Neither asset
reads the repository filesystem, uses network, Knowledge or RAG at runtime.

`Gate3FinancialLabelDictionaryFactory.create().managed_binding()` owns the
stable association between the package resource, Skill ID and Tool ID. The
G3.4 attempt records this binding and injects the same deterministic model view
exactly once. It does not resolve any asset by display name.

## G3.4 injection rule

One model request contains the complete renderer output for its exact selected
dictionary version exactly once. The operator-facing Skill and exact-delivery
Tool are management/readback projections; they are not separately injected
into that request. The request must not also receive the same definitions
through a Prompt, Knowledge/RAG source, system-context copy or second renderer.

Task instruction and dictionary remain separate. An instruction may require
sparse confident selection and forbid unknown labels, but it must not restate
or paraphrase financial-label definitions. Version binding is code-owned
request metadata, not model-facing prose.

## Review CLI

The package-local, UTF-8 CLI exposes only the bounded lifecycle:

```text
python -B -m broker_reports_gate1.gate3_financial_label_dictionary_cli show
python -B -m broker_reports_gate1.gate3_financial_label_dictionary_cli draft
python -B -m broker_reports_gate1.gate3_financial_label_dictionary_cli validate
python -B -m broker_reports_gate1.gate3_financial_label_dictionary_cli diff
python -B -m broker_reports_gate1.gate3_financial_label_dictionary_cli review-template
python -B -m broker_reports_gate1.gate3_financial_label_dictionary_cli prepare-publish
```

File-producing commands use exclusive creation and do not overwrite an
existing draft, approval or prepared version.

## Explicit non-goals

G3.3M/G3.C1 do not implement or authorize:

- a Prompt-owned definition copy or model-invoked semantic Tool call;
- annotation validation or persistence;
- a second registry, database, service, RAG or Knowledge ingestion;
- source-document, canonical-artifact or private-evidence reads;
- multi-document workflow, reconciliation or NDFL calculation;
- dictionary-owned product activation, an independent G3.4 route or Gate 4;
- research or addition of deferred labels.

G3.C5 consumes this exact published version inside the stable NDFL route. The
dictionary remains a meaning authority and never becomes a workflow, provider
or annotation owner. There is no next Gate 3 GOAL. Gate 4 later closed under
the separate current Pipeline Gates authority; this dictionary did not start
or redefine it.
