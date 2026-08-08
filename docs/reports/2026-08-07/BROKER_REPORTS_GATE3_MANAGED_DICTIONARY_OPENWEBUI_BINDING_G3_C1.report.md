# Broker Reports Gate 3 managed dictionary OpenWebUI binding — G3.C1

Date: 2026-08-07

Status: `COMPLETED`

## Plain-language result

The nine Gate 3 financial labels have one meaning owner: the hash-pinned
package resource `broker-reports-financial-labels@1.0.0`. An operator opens its
generated readable projection in OpenWebUI at:

```text
Workspace
-> Skills
-> Broker Reports Financial Labels
```

The live Skill has stable ID `broker-reports-financial-labels`. The companion
Workspace Tool has stable ID `broker_reports_financial_label_dictionary` and
returns the exact published resource through
`load_financial_label_dictionary`. There is no definitions-owning Prompt and
no Knowledge/RAG collection.

Gate 3 does not reinterpret either managed asset. Its runtime loads the same
pinned package resource through `Gate3FinancialLabelDictionaryFactory.create`,
renders the validated complete model view, and inserts that view exactly once
between the document projection and the versioned instruction. The Skill and
Tool are generated projections for operator inspection and exact delivery, not
additional meaning owners.

## Reused and minimally completed

- Reused the existing package JSON, lifecycle factory, deterministic renderer,
  managed-asset builder and OpenWebUI native Skill/Tool APIs.
- Added one deterministic Skill projection and one byte-exact Tool projection
  to the existing managed-asset build system.
- Added a stable-ID publisher/readback check. It creates or updates only these
  two IDs, rejects foreign ID collisions, verifies exact content and rolls back
  its own write if verification fails.
- Did not create a Prompt copy, Knowledge collection, registry, database,
  provider route or second dictionary-management system.

## Stable identities and exact hashes

```text
Prompt ID: null
Skill ID: broker-reports-financial-labels
Tool ID: broker_reports_financial_label_dictionary
Tool method: load_financial_label_dictionary
Dictionary ID: broker-reports-financial-labels
Dictionary version: 1.0.0
Dictionary file SHA-256: 182e8d7f3604ad3d06d93c4d913df17979f21aeea669123d70c10be9d9652850
Model-view SHA-256: b5b89e1b17932c6429b71724667053287e65f7a72b0beec7dcd86cc1190d1b5b
Skill content SHA-256: f486826d017f7314c2da807fd8613a3524521135c29509df4003aeb21e5c9d7d
Tool content SHA-256: 1b03692f04abc6eb59fc043244b29db7842de0b62f0445b4ee85e75ea7e30371
```

Display names remain human-facing metadata. Publication, update and readback
use the stable Skill and Tool IDs above.

## Runtime chain

```text
operator
-> Workspace / Skills / Broker Reports Financial Labels
-> Skill ID broker-reports-financial-labels
-> generated exact model-view projection

managed exact delivery
-> Tool ID broker_reports_financial_label_dictionary
-> load_financial_label_dictionary
-> exact verified package-resource bytes

Gate 3 labeling runtime
-> Gate3FinancialLabelDictionaryFactory.create
-> exact file-hash-pinned package resource
-> exact model-view hash check
-> one dictionary insertion in the model context
```

The Tool is deliberately not model-invoked in the labeling attempt: doing so
would introduce a nondeterministic second insertion. The runtime and managed
assets instead carry the same closed binding identity and hashes.

## Evidence

Local deterministic checks:

- managed asset builder `--check`: `passed`;
- focused dictionary/binding/labeling tests: `30 passed`;
- expanded Gate 3 plus architecture/canonical regressions: `145 passed`;
- generated manifest asserts one meaning owner, generated Skill projection,
  exact Tool delivery, no Prompt definitions, no Python definitions and no
  Knowledge/RAG;
- Tool execution returns byte-identical UTF-8 dictionary JSON after embedded
  SHA-256 and identity validation;
- tests prove native API routes and stable IDs are used without name lookup.

Live OpenWebUI evidence:

- before publication: zero Skills and zero Tools, so the new nine-label
  dictionary was not connected to the earlier managed surface;
- authorized publication created exactly the stable Skill and Tool;
- immediate exact readback passed;
- a later independent read-only run again reported both objects present,
  active where applicable, stable-ID exact, content/name/description/metadata
  exact and Tool method exact;
- provider calls: `0`; Knowledge/RAG: `none`.

The safe machine-readable receipt is
[BROKER_REPORTS_GATE3_MANAGED_DICTIONARY_OPENWEBUI_BINDING_G3_C1.receipt.safe.json](./BROKER_REPORTS_GATE3_MANAGED_DICTIONARY_OPENWEBUI_BINDING_G3_C1.receipt.safe.json).

## Prior managed information: critical assessment

The earlier OpenWebUI managed Skill/Prompt/Tool family remains valuable as a
proven lifecycle and native-publication pattern. Its financial semantic pack,
however, belongs to the historical Gate 2 contour and defines a broader,
different semantic model. Reusing those definitions would create a second
owner and weaken the smaller current nine-label contract. G3.C1 therefore
reuses the infrastructure and operational lessons, but not the old meanings.

## Limits and next boundary

This proves the managed dictionary GUI and exact runtime binding only. It does
not prove or activate the NDFL product route, Gate 2 to Gate 3 orchestration,
single user-facing NDFL identity, legacy-route cleanup or final product-path
execution. Those remain sequenced after this GOAL.

```text
GOAL_G3_C1=COMPLETED
FINANCIAL_MEANING_OWNER=1
KNOWLEDGE_RAG=NONE
HARDCODED_DEFINITIONS=NONE
GUI_PATH=PROVEN
RUNTIME_BINDING=PROVEN
AUTO_CONTINUE=G3.C2
```
