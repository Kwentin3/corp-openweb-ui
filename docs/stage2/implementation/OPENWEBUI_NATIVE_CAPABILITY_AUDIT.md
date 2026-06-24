# OpenWebUI Native Capability Audit

Status: reusable Stage 2 documentation based on the 2026-06-24 runtime audits
and authenticated four-actor proof.

Primary reports:

- [OPENWEBUI_NATIVE_CAPABILITY_RUNTIME_AUDIT.report.md](../../reports/2026-06-24/OPENWEBUI_NATIVE_CAPABILITY_RUNTIME_AUDIT.report.md)
- [OPENWEBUI_ADMIN_TEST_USER_RUNTIME_PROOF.report.md](../../reports/2026-06-24/OPENWEBUI_ADMIN_TEST_USER_RUNTIME_PROOF.report.md)

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
| Web Search | native providers and feature controls | provider baseline and pilot | current runtime default is global allow |
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
   - one sharing/business group for scenario resources;
   - permission groups only when global defaults are not already broader;
   - keep global defaults aligned with customer policy.

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
   - permissions do not reappear through another group or global default.

7. Capture evidence:
   - exact non-secret setting paths/names;
   - screenshots only if they contain no secrets/customer data;
   - actor matrix;
   - gaps and fallback options.

## 4. Capability Status

| Domain | Current classification | Confirmed runtime finding | What remains |
| --- | --- | --- | --- |
| Workspaces / scenario setup | native-with-configuration, synthetic actor proof | `Stage2 Proof Scenario` was visible to inside user and hidden from outside user | real customer scenario owner/group matrix |
| RBAC/groups | native-with-configuration, synthetic actor proof | `Team-Stage2-Proof` gave inside user one group; outside user had zero test groups; Preview Access worked | real department mapping and no unintended global grants |
| Shared prompts | native-proven for synthetic prompt | `/stage2_proof_summary` visible to inside user, hidden from outside user; history endpoint worked | owner/change approval and UI screenshot proof if required |
| Knowledge | native-proven for synthetic Knowledge | inside user saw/retrieved synthetic Knowledge; outside user did not | customer documents, OCR samples and extraction quality |
| Model catalog | native-with-configuration | restricted model can be created over an existing base model | exact production model IDs and data policy |
| Analytics | native-partial | two synthetic completions succeeded, but admin analytics returned `synthetic_rows=0` during run | timing/export/cost proof and hard billing decision |
| Web Search | native-runtime global allow, scoped rollout not proven | safe query returned results for both inside and outside users because `permissions.features.web_search=true` | customer scope/default policy before claiming group-only Web Search |
| STT sidecar | current-stage closed | static loader/config remain served; native audio config keys inventory confirmed | production retention/cancel/limits for sidecar |
| Native STT microphone | native inventory proven | `/api/v1/audio/config` exposes STT/TTS config key names; values not printed | UI screenshot/mobile microphone retest if needed |
| Files/documents | native-partial | TXT/PDF uploaded with processing; DOCX/XLSX placeholders uploaded without extraction claim | valid DOCX/XLSX parsing, OCR/layout-heavy docs, broker reports, complex Excel |
| Manager visibility | native-partial | manager could not access inside personal chat; outside could not open tested shared link | positive manager shared-list visibility and policy model |
| Chat deletion/no-delete | current runtime allows delete | non-admin delete probe returned `200`; `permissions.chat.delete=true` | retention/no-delete decision and possible custom delete guard |

## 5. Confirmed Runtime Setting Names

Authenticated `/api/config` non-secret setting paths:

```text
permissions.workspace.models=false
permissions.workspace.prompts=false
permissions.workspace.knowledge=false
permissions.features.web_search=true
permissions.chat.file_upload=true
permissions.chat.delete=true
permissions.chat.delete_message=true
permissions.chat.stt=true
```

Authenticated `/api/v1/audio/config` key inventory, names only:

```text
stt_keys=ALLOWED_EXTENSIONS,AZURE_API_KEY,AZURE_BASE_URL,AZURE_LOCALES,AZURE_MAX_SPEAKERS,AZURE_REGION,DEEPGRAM_API_KEY,ENGINE,MISTRAL_API_BASE_URL,MISTRAL_API_KEY,MISTRAL_USE_CHAT_COMPLETIONS,MODEL,OPENAI_API_BASE_URL,OPENAI_API_KEY,SUPPORTED_CONTENT_TYPES,WHISPER_MODEL
tts_keys=API_KEY,AZURE_SPEECH_BASE_URL,AZURE_SPEECH_OUTPUT_FORMAT,AZURE_SPEECH_REGION,ENGINE,MISTRAL_API_BASE_URL,MISTRAL_API_KEY,MODEL,OPENAI_API_BASE_URL,OPENAI_API_KEY,OPENAI_PARAMS,SPLIT_ON,VOICE
```

Provider credential values were not printed.

## 6. Actor Matrix Summary

| Actor | Runtime proof role | Confirmed | Limit |
| --- | --- | --- | --- |
| Admin | env-backed OpenWebUI admin | authenticated and configured synthetic resources | credentials remain secret and not documented |
| Manager/PO | ordinary synthetic user | no admin role; personal chat access blocked; outside shared-link negative control blocked | positive shared-list visibility did not confirm |
| Employee inside group | ordinary synthetic user in `Team-Stage2-Proof` | saw restricted model, prompt and Knowledge; uploaded TXT/PDF plus DOCX/XLSX placeholders; completions worked | current Web Search global default means group-only search not proven |
| Employee outside group | ordinary synthetic user without test group | did not see restricted model, prompt or Knowledge; safe Web Search still worked | outside search allowed by current global default |

All synthetic proof users/resources were deleted after the run. Cleanup
verification found no leftovers.

## 7. Boundaries Of The Native Path

Native path is enough when:

- a requirement can be expressed as groups, resource sharing, model visibility,
  prompts, knowledge or built-in feature controls;
- the workflow can stay inside OpenWebUI without provider keys in browser;
- basic reporting is enough;
- customer data is not required for proof.

Native path is not enough when:

- deny semantics are required;
- manager must automatically see subordinate private chats;
- deletion must be blocked while the deployed runtime allows non-admin delete;
- exact OCR/table/XLSX quality is required;
- hard budgets, virtual keys or provider routing are required;
- provider-specific policy/retention/usage accounting must be enforced outside
  OpenWebUI;
- a feature needs production-grade workflow state not available in OpenWebUI.

## 8. Where Custom Slices Start

Use the extension-first order:

1. native configuration;
2. Functions / Actions / Tools / OpenAPI Tool Servers;
3. thin static loader or minimal UI shim;
4. private backend/domain sidecar;
5. deep fork only after proof and owner/ADR approval.

Custom slice candidates:

- STT sidecar hardening, already chosen for media attachment transcription;
- custom supervisory export/report if manager visibility cannot be native;
- server-side delete guard if customer requires no-delete and native permission
  is insufficient;
- OCR/document extraction pipeline after customer samples prove need;
- usage event collector or gateway only if native analytics is insufficient.

## 9. Runtime Proof Status

The 2026-06-24 public audit proved:

- deployed public version `0.9.6`;
- public health;
- protected unauthenticated `/api/models`;
- Stage 2 static STT loader and normalization config are served.

The authenticated admin follow-up proved:

- approved admin credential variable names were present in local `.env`;
- credential values were not printed or committed;
- authenticated admin API login succeeds with role `admin`;
- users/groups/models/prompts/knowledge/files/chats/functions/audio config and
  analytics endpoints are reachable;
- Preview Access endpoints work for user and group views;
- default Workspace and Sharing permissions are false for ordinary users;
- default Chat permissions include `file_upload=True`, `delete=True`,
  `delete_message=True`, `stt=True` and `web_upload=True`;
- default Features include `web_search=True`, while `api_keys=False` and
  `direct_tool_servers=False`;
- Analytics endpoints return model/user aggregate structure with token-count
  fields;
- native STT settings are visible through the audio config API, while the Stage
  2 media attachment sidecar remains the accepted architecture.

The authenticated synthetic actor proof added:

- creation and cleanup of three ordinary synthetic users and one test group;
- inside/outside proof for restricted model, prompt and Knowledge;
- prompt history endpoint proof;
- Knowledge file attach and retrieval endpoint proof;
- TXT/PDF processing proof and DOCX/XLSX placeholder upload acceptance;
- safe Web Search query proof for ordinary users under current global default;
- non-admin delete behavior proof showing delete is currently allowed;
- manager negative control proof for personal chat access, but not positive
  shared-list visibility.

Current verdict:

```text
admin_test_user_runtime_proof_partial_with_actor_matrix
```

## 10. Recommended Next Work

1. Keep Gate 7 unblocked by credentials; use the actor proof as the current
   runtime baseline.
2. Ask the customer to decide retention/no-delete, manager visibility and Web
   Search scope/default policy before changing production settings.
3. If no-delete is mandatory, test native settings first; if non-admin delete
   still succeeds, design a narrow delete guard.
4. If manager visibility is mandatory, verify OpenWebUI UI/shared-resource
   semantics before building a custom supervisor view.
5. Treat native analytics as basic reporting until delayed rows/export/cost
   behavior is proven.
6. Continue Web Search comparison only inside rollout gates.
7. Ask customer for data policy and document/OCR/XLSX samples before document
   quality conclusions.

## 11. Non-Goals

- No production rollout.
- No Web Search broad rollout.
- No provider setup.
- No LiteLLM/gateway.
- No deep OpenWebUI fork.
- No customer-data document tests.
- No final customer policy decision.
