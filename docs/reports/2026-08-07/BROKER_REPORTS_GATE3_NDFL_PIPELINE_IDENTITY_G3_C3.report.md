# Broker Reports Gate 3 NDFL Pipeline Identity — G3.C3

Date: 2026-08-07
Status: PASS

## Outcome

OpenWebUI now exposes exactly one Broker Reports product entrypoint:
`NDFL`, with stable Workspace Model ID `broker-reports-ndfl`. It reuses the
existing technical Pipe `broker_reports_gate1_pipe`; Gate 1, Gate 2 and Gate 3
remain internal stages. The historical Workspace Model `test` is retained but
inactive. The base Pipe remains active as an ACL-restricted technical runtime
model because OpenWebUI 0.9.6 requires `base_model_id` to exist in its runtime
model map before it will execute a custom Workspace Model. It is not a second
Workspace Model or product preset. Both legacy Gate 2 Pipe models remain
inactive.

Operator path:

```text
Workspace
-> Models
-> NDFL
```

No Knowledge/RAG, Prompt, Workspace Tool invocation or provider call was added
by this topology publication.

## Stable-ID topology

| Entity | Display name | Stable ID | Referenced by | Resolution |
|---|---|---|---|---|
| Workspace Model | NDFL | `broker-reports-ndfl` | OpenWebUI chat/user | exact model ID |
| Base Pipe | NDFL technical intake | `broker_reports_gate1_pipe` | Workspace Model `base_model_id` | exact Function/model ID |
| Workflow | NDFL | `broker-reports-ndfl` | product binding and `NdflWorkflowFactory.create` | imported constant/factory |
| Provider profile | Google Gemini | `google_gemini` | NDFL workflow/model client | exact profile ID |
| Provider model | Gemini 3.5 Flash | `models/gemini-3.5-flash` | NDFL workflow/model client | exact provider model ID |
| Dictionary | Broker Reports Financial Labels | `broker-reports-financial-labels@1.0.0` | Gate 3 dictionary factory | exact package identity/version |
| Skill | Broker Reports Financial Labels | `broker-reports-financial-labels` | managed operator surface/product binding | exact Skill ID |
| Tool | Broker Reports Financial Label Dictionary | `broker_reports_financial_label_dictionary` | managed delivery/product binding | exact Tool ID; method `load_financial_label_dictionary` |
| Prompt | n/a | `null` | n/a | definitions are not duplicated in a Prompt |
| Knowledge | n/a | none | n/a | Knowledge/RAG is forbidden for the dictionary |

The machine-readable topology is returned by
`ndfl_product_binding_snapshot()`. Display names are absent from that snapshot.
Changing a display name therefore does not change routing.

## Live migration and readback

Before publication, the live catalog exposed these Broker Reports routes:

```text
test
broker_reports_gate1_pipe
broker_reports_gate2_source_fact_pipe
broker_reports_gate2_domain_source_fact_pipe
```

The stable-ID publisher then:

- created Workspace Model `broker-reports-ndfl`;
- preserved the access grants/capabilities already proven by historical model
  `test`;
- set `test.is_active=false` without deleting it;
- reused the existing same-ID Pipe access/model records;
- kept the Gate 1 base Pipe override active and ACL-restricted because the
  native custom-model resolver requires that exact base ID at execution time;
- kept both legacy Gate 2 Pipe overrides inactive.

The first C3 publication incorrectly made the base override inactive. A later
G3.C5 user-path check proved that state was catalog-visible but not executable:
OpenWebUI returned `Model not found` when validating the custom model's missing
base ID. C3 was corrected by live source inspection, regression tests and a
new exact-ID readback before final Gate 3 acceptance.

The final read-only live readback returned:

```text
USER_FACING_NDFL_MODELS=1
VISIBLE_PRODUCT_ROUTE_IDS=[broker-reports-ndfl]
VISIBLE_INTERNAL_RUNTIME_BASE_IDS=[broker_reports_gate1_pipe]
LEGACY_OR_COMPETING_ROUTES_VISIBLE=[]
NDFL_BASE_PIPE_ID_MATCH=true
NDFL_STABLE_BINDING_EXACT=true
LEGACY_TEST_INACTIVE=true
KNOWLEDGE_RAG=NONE
PROVIDER_CALLS=0
```

## Name-coupling and rename proof

The product binding, publisher API reads/updates and workflow route all use
stable IDs. Product-source search found no behavioral lookup by the mutable
display strings `NDFL`, `Financial Labels` or `Broker Labels`.

The integration fixture changes only the Workspace Model display name and
proves:

```text
display_name_match=false
routing_passed=true
stable_binding_unchanged=true
```

## Prior implementation value

The old `test` Workspace Model was not a suitable final identity, but its proven
`base_model_id=broker_reports_gate1_pipe`, upload capabilities and access grants
were useful migration evidence. Those operational properties were reused; the
mutable name and temporary ID were not promoted into product behavior.

## Evidence

```powershell
python -B scripts/live_publish_ndfl_workspace_model.py --publish
python -B scripts/live_publish_ndfl_workspace_model.py
python -m pytest -q tests/test_broker_reports_ndfl_workspace_model.py tests/test_broker_reports_gate3_ndfl_workflow.py --tb=short
```

Result after the topology correction: `14 passed` across the identity,
cleanup and product-Pipe boundary tests; live readback status `passed`.

Machine-readable evidence:

- `BROKER_REPORTS_GATE3_NDFL_PIPELINE_IDENTITY_G3_C3.receipt.safe.json`

## Acceptance

```text
USER_FACING_NDFL_MODELS=1
INTERNAL_BINDINGS_BY_STABLE_ID=PASS
BEHAVIORAL_DISPLAY_NAME_LOOKUPS=0
RENAME_SAFETY=PASS
G3.C3=PASS
```

Scope stops at product identity/routing. Provider execution and the real
end-to-end product document are G3.C5, after the G3.C4 duplicate-owner audit.
