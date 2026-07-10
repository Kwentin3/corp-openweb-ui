# Broker Reports OpenWebUI Workspace Configuration v0 Proposal

Status: WORKSPACE_CONFIGURATION_PROPOSAL_READY
Date: 2026-07-06
Scope: Stage 2 Broker Reports / XLS NDFL OpenWebUI configuration model

## 1. Purpose

This is a configuration proposal, not implementation code.

It defines how to configure the Broker Reports scenario in OpenWebUI so the next runtime proof can validate:

```text
Workspace Model -> client chat -> uploaded files -> Gate 1 trigger -> safe report
```

No OpenWebUI resources were created by this document.

## 2. Workspace Model

Recommended display name:

```text
Broker Reports / XLS NDFL Draft Scenario
```

Recommended internal id:

```text
broker_reports_xls_ndfl_draft
```

Description:

```text
Draft workflow for broker report document intake and review.
Gate 1 normalizes uploaded documents and returns a safe report.
Manual specialist review is required. No tax correctness, declaration, XLS/XLSX or FNS filing claim.
```

Visibility:

```text
Private / group-scoped
```

Allowed group:

```text
BrokerReportsPilot
```

Exact group name is runtime/operator decision.

## 3. Base Model Requirements

Base model should:

- follow system prompts reliably;
- support tool calling if Tool-triggered Gate 1 is selected;
- handle Russian and English domain text;
- support long enough context for safe reports and methodology summaries;
- be allowed for broker/tax/financial data under provider policy;
- have deterministic/low-temperature settings available.

Base model does not need:

- vision for first Gate 1 proof;
- image generation;
- autonomous web search;
- code interpreter for customer docs;
- final tax calculation capability.

## 4. System Prompt Outline

System prompt should include:

```text
Role:
You support a Broker Reports / XLS NDFL draft workflow inside OpenWebUI.

Boundary:
You do not provide tax advice, final tax correctness, declaration filing, FNS integration or automatic XLS/XLSX generation.

Gate 1:
Gate 1 normalizes uploaded documents technically. It does not extract source facts through LLM.

Knowledge:
Use attached Knowledge only for approved methodology, official requirements and examples.
Do not treat raw customer uploads as Knowledge.

Files:
Customer documents are chat files for the current case. Do not print raw filenames, private paths, account numbers or full financial operation rows.

Tools:
Use the approved normalizer Action/Tool only when the user explicitly requests Gate 1 normalization.

Output:
Return safe counts, document ids, case_group ids, blockers and next steps. Keep manual review required.
```

## 5. Attached Knowledge Candidates

Allowed:

- official FNS requirements and forms;
- approved customer methodology;
- approved review rules;
- approved examples and layout samples;
- safe synthetic fixtures.

Forbidden by default:

- raw broker reports;
- customer uploaded files from chats;
- private normalized slices;
- full financial operation rows;
- customer samples pending review.

Knowledge access:

- share only with the approved group;
- verify that users who can use the Workspace Model can also read attached Knowledge;
- do not rely on model attachment alone as an access grant.

## 6. Attached Skills Candidates

Candidate Skills:

- `broker_reports_safe_output_rules`
- `broker_reports_source_evidence_boundary`
- `broker_reports_methodology_gap_handling`
- `broker_reports_review_discipline`

Skill usage:

- attach to the Workspace Model if target runtime supports Skills;
- share with the approved group;
- if Skills are unavailable, move the same content into system prompt, Prompts and Knowledge.

## 7. Attached Prompts

Candidate Prompts:

| Prompt | Purpose |
| --- | --- |
| `/broker_gate1_normalize` | Start Gate 1 normalization or delegate to Action/Tool. |
| `/broker_gate1_show_report` | Re-display latest safe normalization report. |
| `/broker_select_case_group` | Select safe `case_group_id` for next gate. |
| `/broker_next_gate_source_facts` | Start next-gate proof after review approval. |
| `/broker_questions_to_specialist` | Produce safe review questions. |

Prompt access:

- share only with approved group;
- version changes require review;
- prompts must not contain secrets or customer raw data.

## 8. Allowed Tools And Actions

Allowed for Gate 1 proof:

- `broker_reports_gate1_normalizer` Action or Tool;
- optional OpenAPI Tool Server connection to backend normalizer helper.

Tool/Action responsibilities:

- receive approved file refs;
- call backend helper if needed;
- return safe report;
- emit progress/status if supported;
- avoid raw content in chat-visible output.

Forbidden:

- user-created arbitrary tools;
- public unreviewed community tools/functions;
- tools that expose raw local paths;
- tools that perform tax calculation in Gate 1;
- tools that auto-load raw customer docs into Knowledge.

## 9. Capability Flags

Recommended initial settings for proof:

| Capability | Recommendation | Reason |
| --- | --- | --- |
| File upload | Enabled for approved group | Required for customer/source file upload. |
| File Context | Disabled for Broker Reports source intake unless a separate proof says otherwise | `file_context=false` is required but not sufficient; the 2026-07-08 synthetic smoke showed default upload processing/vectorization can still run. |
| Knowledge | Enabled with approved KB only | Needed for official/methodology references. |
| Tools | Enabled only for approved normalizer path | Needed for deterministic helper trigger. |
| Actions | Enabled only for approved Gate 1 action | Preferred explicit UX if file refs are accessible. |
| Skills | Enabled if runtime-proven | Useful for discipline/playbooks. |
| Web Search | Disabled by default for Gate 1 | Not needed for source document normalization. |
| Code Interpreter | Disabled by default | Avoid ungoverned customer-file analysis. |
| Image Generation | Disabled | Irrelevant. |
| Vision | Disabled for first proof | Raster/OCR is review-blocked unless separate OCR proof exists. |
| Memory | Disabled or constrained | Avoid cross-case leakage. |

## 10. Groups And RBAC

Required checks:

- global defaults are minimal;
- approved group can see Workspace Model;
- outside user cannot see Workspace Model;
- approved group can use attached Prompts;
- approved group can use attached Skills if enabled;
- approved group can read attached Knowledge;
- approved group can use attached Tool/Action;
- ordinary users cannot create/import Workspace Tools/Functions;
- direct user-added tool servers are disabled unless explicitly approved.

OpenWebUI permissions are additive. If any broad default or second group grants a feature, it may bypass intended restriction. Runtime proof must check an inside user and an outside user.

## 11. Backend Helper Checks

The backend helper must verify:

- request comes from approved OpenWebUI path;
- user is authorized for Broker Reports scenario;
- file refs belong to the active chat/case context;
- original bytes are read only through approved boundary;
- artifact refs are opaque;
- private slices are not chat-visible;
- safe report passes privacy validation;
- no raw customer files are copied to repo;
- no Knowledge write occurs automatically.

## 12. Runtime Checks

Before accepting the configuration:

1. Record deployed OpenWebUI version.
2. Record exact selected base model id without secrets.
3. Verify group-scoped Workspace Model visibility.
4. Verify Prompt access and slash command availability.
5. Verify Skill availability or fallback.
6. Verify attached Knowledge access.
7. Verify file upload and file refs.
8. Verify Action or Tool access to file refs.
9. Verify same-chat safe report.
10. Verify outside user negative controls.

## 13. Data Policy Notes

Gate 1 proof should use synthetic files first.

Customer-approved files can be used only after:

- transfer method approved;
- provider/data policy approved;
- retention/access policy accepted;
- no-RAG/no-vector source-intake proof accepted;
- vector DB delta for the case proven zero;
- uploaded file data proven not to contain extracted customer text;
- raw filenames/private paths safety checks pass;
- Knowledge boundary accepted.

Normal OpenWebUI bulk chat upload remains blocked for Broker Reports customer packages.
The no-RAG/no-vector source-intake guard is passed only for the project-owned
`process=false` private intake path. `Knowledge count = 0` is not enough.

## 14. Status

```text
WORKSPACE_CONFIGURATION_PROPOSAL_READY
WORKSPACE_MODEL_RECOMMENDED_AS_SCENARIO_ENTRYPOINT
KNOWLEDGE_FOR_APPROVED_METHODOLOGY_ONLY
RAW_CUSTOMER_DOCS_NOT_KNOWLEDGE
RAW_CUSTOMER_DOCS_NOT_NATIVE_RAG_VIA_PROCESS_FALSE_PRIVATE_INTAKE
GATE1_TRIGGER_ACTION_OR_TOOL_TO_BE_PROVEN
CUSTOMER_APPROVED_UPLOAD_ALLOWED_ONLY_VIA_PROCESS_FALSE_PRIVATE_INTAKE
```
