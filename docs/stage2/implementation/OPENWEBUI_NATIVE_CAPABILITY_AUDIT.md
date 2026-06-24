# OpenWebUI Native Capability Audit

Status: reusable Stage 2 documentation based on the 2026-06-24 audit.

Primary report:
[OPENWEBUI_NATIVE_CAPABILITY_RUNTIME_AUDIT.report.md](../../reports/2026-06-24/OPENWEBUI_NATIVE_CAPABILITY_RUNTIME_AUDIT.report.md).

## 1. Position

Stage 2 should stay native-first.

OpenWebUI already has the building blocks needed for the first managed
corporate AI environment:

- Workspace Models;
- Groups/RBAC and resource access control;
- Workspace Prompts;
- Workspace Knowledge;
- native Web Search providers;
- native Analytics;
- native STT for microphone/voice input;
- file upload/RAG/document extraction surfaces;
- extension mechanisms: Functions, Actions, Tools and OpenAPI Tool Servers.

The missing product object is a single "business workspace" entity. For Stage 2
we model it as a configured scenario:

```text
scenario owner
-> access group
-> curated Workspace Model
-> system instructions
-> shared prompts/templates
-> attached knowledge/instructions
-> enabled capabilities
-> policy and acceptance checks
```

This is enough for configuration-first work. It is not enough to skip runtime
proof or customer policy decisions.

## 2. Stable Native Pillars

| Pillar | Native mechanism | Use in Stage 2 | Known limit |
| --- | --- | --- | --- |
| Scenario model | Workspace Models | curated model per scenario | not a full business-workspace entity |
| Access | Groups/RBAC/resource access | allowed users, models, prompts, knowledge | additive permissions, no deny |
| Shared templates | Workspace Prompts | slash commands and forms | owner/change policy needed |
| Instructions/data | Workspace Knowledge | methods, templates, examples, approved docs | not a document pipeline |
| Provider catalog | Workspace Models + admin provider config | curated model list | needs exact IDs and data policy |
| Usage visibility | Analytics | basic admin reporting | not hard billing |
| Web Search | native providers and feature controls | provider baseline and pilot | rollout gates still pending |
| STT microphone | native STT | voice input baseline | separate from media attachment STT |
| Media attachment STT | Action + static loader + sidecar | closed current-stage MVP | production hardening remains |
| Files/docs | upload + RAG/extraction | simple docs and knowledge | samples/parser/OCR needed |

## 3. How To Build A Work Scenario Natively

Use this sequence for the first safe scenario proof.

1. Define scenario metadata:
   - purpose;
   - owner;
   - allowed user group;
   - allowed data classes;
   - forbidden data/examples;
   - acceptance signal.

2. Create groups:
   - one permission group for feature grants;
   - one sharing/business group for scenario resources;
   - keep global defaults minimal.

3. Create a Workspace Model:
   - choose base model;
   - add clear description;
   - set visibility to approved group;
   - attach system instructions;
   - enable only required capabilities.

4. Add shared prompts:
   - one slash command per repeated task;
   - use variables for user/date/context;
   - document owner and change process;
   - share only to approved group.

5. Add Knowledge:
   - start with instructions, methodics, templates and synthetic examples;
   - attach to model or reference with `#`;
   - avoid customer documents until data policy and samples are approved.

6. Run user proof:
   - admin sees and can configure scenario;
   - allowed user sees and can use it;
   - outside user does not see it;
   - permissions do not reappear through another group.

7. Capture evidence:
   - exact setting names;
   - screenshots without secrets/customer data;
   - actor matrix;
   - gaps and fallback options.

## 4. Capability Status

| Domain | Current classification | What is safe now | What remains |
| --- | --- | --- | --- |
| Workspaces / scenario setup | native-with-configuration, admin API partial proof | scenario skeletons and admin endpoint proof | customer groups/owners and test actors |
| RBAC/groups | native-with-configuration, admin API partial proof | default permissions and Preview Access endpoints | inside/outside actor matrix |
| Shared prompts | native-ready, endpoint proof pending content | prompt templates with synthetic data | owner/change approval and test prompt |
| Knowledge | native-with-configuration, endpoint proof pending content | instructions/templates | customer docs, OCR samples and synthetic KB proof |
| Model catalog | native-with-configuration | catalog skeleton | data policy, exact IDs |
| Analytics | native-partial, admin API proof | model/user aggregate endpoint proof | hard billing decision if needed |
| Web Search | provider baseline ready, default permission visible | comparison and rollout gates | customer policy/cost/group scope |
| STT sidecar | current-stage closed | hardening checklist | production retention/cancel/limits |
| Files/documents | native-partial, default upload permission visible | synthetic file proof | parser/OCR/customer samples |
| Manager visibility | native-partial | sharing proof | customer privacy policy |
| Chat deletion/no-delete | setting visible, behavior proof pending | non-admin UI/API test | retention/audit decision |

## 5. Boundaries Of The Native Path

Native path is enough when:

- a requirement can be expressed as groups, resource sharing, model visibility,
  prompts, knowledge or built-in feature controls;
- the workflow can stay inside OpenWebUI without provider keys in browser;
- basic reporting is enough;
- customer data is not required for proof.

Native path is not enough when:

- deny semantics are required;
- manager must automatically see subordinate private chats;
- deletion must be enforced but native permission/API proof fails;
- exact OCR/table/XLSX quality is required;
- hard budgets, virtual keys or provider routing are required;
- provider-specific policy/retention/usage accounting must be enforced outside
  OpenWebUI;
- a feature needs production-grade workflow state not available in OpenWebUI.

## 6. Where Custom Slices Start

Use the extension-first order:

1. native configuration;
2. Functions / Actions / Tools / OpenAPI Tool Servers;
3. thin static loader or minimal UI shim;
4. private backend/domain sidecar;
5. deep fork only after proof and owner/ADR approval.

Custom slice candidates:

- STT sidecar hardening, already chosen for media attachment transcription;
- custom supervisory export/report if manager visibility cannot be native;
- server-side delete guard if native no-delete fails and customer approves;
- OCR/document extraction pipeline after customer samples prove need;
- usage event collector or gateway only if native analytics is insufficient.

## 7. Runtime Proof Status

The 2026-06-24 public audit proved:

- deployed public version `0.9.6`;
- public health;
- protected unauthenticated `/api/models`;
- Stage 2 static STT loader and normalization config are served.

The 2026-06-24 authenticated follow-up proved through admin API:

- approved admin credential variable names were present in local `.env`;
- credential values were not printed or committed;
- authenticated admin API login succeeds with role `admin`;
- users/groups/models/prompts/knowledge/files/chats/functions/audio config and
  analytics endpoints are reachable;
- runtime has 4 users, 1 group, no `stage2-proof-*` actors, no users with
  groups, 4 models, 0 prompts, 0 knowledge items, 40 files and 1 function;
- Preview Access endpoints work for user and group views;
- default Workspace and Sharing permissions are false for ordinary users;
- default Chat permissions include `file_upload=True`, `delete=True`,
  `delete_message=True`, `stt=True` and `web_upload=True`;
- default Features include `web_search=True`, while `api_keys=False` and
  `direct_tool_servers=False`;
- Analytics endpoints return model/user aggregates with token-count fields;
- native STT settings are visible through the audio config API, while the Stage
  2 media attachment sidecar remains the accepted architecture.

It still does not prove:

- group/model/prompt/knowledge visibility;
- slash-command prompt behavior;
- Knowledge retrieval behavior;
- group-restricted Workspace Model behavior;
- two-user analytics workflow;
- non-admin chat delete behavior;
- manager visibility behavior;
- Web Search feature permission behavior;
- file extraction behavior.

Use the runtime checklist in the audit report before state-changing proof.

## 8. Recommended Next Work

1. Get explicit operator approval to create or use `stage2-proof-*` actors and
   `Team-Stage2-Proof` / permission groups on the deployed stand.
2. Prepare one safe configuration-first scenario with synthetic data.
3. Complete the four-actor proof matrix and decide whether ADR-0008 stays
   native-first.
4. Continue Web Search comparison only inside rollout gates.
5. Ask customer for data policy, group matrix, manager visibility policy,
   retention requirements and document/OCR samples before production changes.

## 9. Non-Goals

- No new production features from this audit.
- No Web Search rollout.
- No new provider setup.
- No LiteLLM/gateway.
- No deep OpenWebUI fork.
- No customer-data document tests.
- No final customer policy decision.
