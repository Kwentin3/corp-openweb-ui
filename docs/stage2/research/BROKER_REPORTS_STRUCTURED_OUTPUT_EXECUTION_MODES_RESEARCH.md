# Broker Reports Structured Output Execution Modes Research

Status: Research note
Date: 2026-07-04
Scope: OpenWebUI-first execution modes for `broker_reports_extraction_v0`

## 1. Summary Verdict

Start with prompt-only JSON extraction plus external validation for the first proof.

Reason:

- Local repository evidence does not show an existing LLM `response_format/json_schema` path.
- OpenWebUI docs confirm Workspace Models, Prompts, Knowledge, Skills, file context, tools, actions, functions and OpenAPI/MCP tool servers.
- OpenWebUI docs confirm model parameters and global/default model params, but the reviewed docs do not establish `response_format/json_schema` pass-through as a stable product contract for chat scenarios.
- Provider structured output exists for some providers, but proving it through this OpenWebUI deployment requires a separate runtime probe.

Tool/Function is not required for the first prompt-only proof. It becomes relevant when server-side validation, provider-specific structured-output pass-through, deterministic table parsing, source mapping or repair-loop automation is required.

## 2. Local Repo Findings

Search terms checked:

- `response_format`
- `json_schema`
- `json_object`
- `structured output`
- `tool_call`
- `function_call`
- `tools`
- `actions`
- `openapi`
- `files`
- `upload`
- `rag`
- `xlsx`
- `docx`
- `export`
- `artifact`
- `download`

Findings:

- `response_format` appears in the STT/LemonFox path as `verbose_json`, not as LLM JSON Schema structured output.
- Existing Stage 2 Action bridge supports operations such as `draft_postprocessing_prompt` and `export_message_docx`.
- Message-level DOCX export returns base64 payload plus content type through Action/sidecar/loader, which is a useful future artifact pattern.
- `OPENWEBUI_NATIVE_CAPABILITY_AUDIT.md` classifies TXT/PDF upload as proven and DOCX/XLSX as placeholder upload without extraction claim.
- No existing broker JSON extraction contract, validation loop or schema-bound model output path was found before this task.

## 3. Public OpenWebUI Capabilities

Relevant documented capabilities:

- Workspace Models can wrap a base model with system prompt, tools, knowledge, skills and parameter overrides.
- Prompts provide reusable slash commands and variables.
- Knowledge stores documents for RAG/full context.
- Skills are markdown instruction sets attached to models or invoked in chat.
- Tools and Functions run server-side Python and must be trusted.
- Action Functions are user-triggered message operations.
- OpenAPI/MCP tool servers expose external HTTP services as callable tools.
- File upload/RAG supports chat uploads and Knowledge bases; file content extraction is asynchronous and format-dependent.

Open gap:

- The reviewed OpenWebUI docs do not prove a stable chat UI path for passing provider-specific `response_format`, `json_schema`, `output_config.format` or equivalent structured-output parameters to every provider.

## 4. Mode Matrix

| Mode | Description | JSON parse success | Schema validation success | Repeatability | Source references | OpenWebUI-native MVP fit | Provider lock-in | Complexity | Security | Code need | Update-safety |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A. Prompt-only JSON | Contract embedded in system prompt or slash prompt; model returns JSON only. | Medium | Low to medium without validation/repair | Must be measured | Prompt-dependent | Best first proof | Low | Low | Good if synthetic only | No production code | High |
| B. JSON mode | Provider enforces valid JSON object, not schema adherence. | High when supported | Low without external validation | Better than prompt-only, still variable | Prompt-dependent | Good if OpenWebUI can pass param | Medium | Medium | Provider/data policy needed | Possibly no code, but runtime config proof needed | Medium |
| C. Provider structured output / JSON Schema | Provider enforces supplied JSON Schema. | High | High for supported schema subset | Best format reliability | Still needs factual validation | Best target after proof | High | Medium to high | Provider/data policy and ZDR/cache review needed | May need extension path | Medium |
| D. Function/tool calling | Model emits function arguments; server validates/executes tool. | High for call args when strict supported | High for tool schema subset | Good | Good if tool receives document evidence | Useful when deterministic server step needed | Medium to high | High | Tool code is privileged | Yes for real implementation | Medium |
| E. Validation + repair-loop | External parser/schema validates output; repair prompt fixes errors. | High after repair | Medium to high | Measurable | Can enforce wrappers | Required safety layer | Low | Medium | Good if no real data | Small proof script or manual operator step | High |

## 5. Provider Capability Matrix

| Provider/path | Structured output capability | Vision/raster relevance | OpenWebUI pass-through status | Notes for this MVP |
| --- | --- | --- | --- | --- |
| OpenAI | Structured Outputs via JSON Schema and JSON mode; function calling strict mode also schema-bound. | Vision-capable models can process images, but structured output still needs factual validation. | Not proven through current OpenWebUI deployment. | Best candidate for provider structured-output proof if approved. |
| Anthropic/Claude | Claude docs describe JSON outputs via `output_config.format` and strict tool use as distinct capabilities. | Docs explicitly mention extraction from images or text for JSON outputs. | Not proven through current OpenWebUI deployment. | Relevant if Claude provider path is approved and exact OpenWebUI pass-through is tested. |
| Gemini | Gemini API supports structured output with JSON schema subset and `application/json` response format. | Gemini models can be vision-capable depending on model. | Not proven through current OpenWebUI deployment. | Good candidate for structured output plus raster experiment only after provider policy. |
| DeepSeek | Official docs describe JSON Output via `response_format: {"type":"json_object"}` and function calling, with strict function mode in beta. | Vision depends on selected DeepSeek/provider model, not assumed. | Generic OpenAI-compatible pass-through not proven. | Treat as JSON mode/function-calling candidate, not schema-first unless exact support is proven. |
| Qwen / Alibaba DashScope | Alibaba docs describe JSON mode via `response_format: {"type":"json_object"}`; Qwen function calling uses JSON Schema parameters. | Vision/raster depends on selected Qwen-VL/OCR model path. | Generic OpenAI-compatible pass-through not proven. | Useful candidate for JSON mode or function-calling proof, not guaranteed strict schema final output. |
| Generic OpenAI-compatible path in OpenWebUI | Depends on provider and whether OpenWebUI forwards the needed parameter. | Depends on base model. | Unproven. | Must be tested; do not assume provider-specific params survive OpenWebUI. |

## 6. Mode A: Prompt-Only JSON

Use when:

- no runtime changes are approved;
- no provider-specific structured output path is proven;
- proof uses synthetic text/table fixtures;
- output can be validated externally.

Prompt requirements:

- include the exact schema version;
- include top-level keys;
- instruct JSON only;
- forbid Markdown fences;
- require evidence wrapper for every extracted field;
- require `missing_data`, `uncertain_data` and `conflicts`;
- require manual review warning;
- require no tax correctness/FNS/XLS claim.

Risk:

- valid JSON is not guaranteed;
- schema adherence is not guaranteed;
- repair-loop may be needed;
- source references may be plausible rather than exact unless input is pasted/text-layer.

## 7. Mode B: JSON Mode

Use when provider path supports `json_object` or equivalent.

Benefits:

- valid JSON is more likely;
- less parsing failure.

Limits:

- JSON mode does not guarantee schema adherence.
- Model can still omit required keys or use wrong enum values.
- External validation remains mandatory.
- OpenWebUI parameter pass-through must be proven.

## 8. Mode C: Provider Structured Output / JSON Schema

Use when:

- provider supports JSON Schema structured outputs;
- selected model supports the feature;
- OpenWebUI or a minimal extension path can pass the schema;
- provider/data policy allows the content.

Benefits:

- best format reliability;
- supports fail-fast validation around schema;
- simplifies downstream parsing.

Limits:

- supported JSON Schema subset varies by provider;
- schema caching/retention rules may matter for sensitive deployments;
- schema adherence does not prove factual correctness;
- source references still require input extraction quality.

## 9. Mode D: Function / Tool Calling

Use when:

- model should call a validator/extractor;
- deterministic server-side logic is needed;
- extraction should become structured arguments;
- file/table parsing must be done outside the model.

Do not use as first proof unless prompt-only fails or structured output cannot be passed through.

Security note:

- OpenWebUI Tools execute server-side code. Only trusted admins should create/import them. This is stronger than a prompt and should be treated as privileged implementation work.

## 10. Mode E: Validation + Repair Loop

Required for all modes.

Recommended flow:

1. Parse JSON.
2. Validate contract.
3. If invalid, return only validation errors to the model.
4. Retry up to 2 times.
5. If still invalid, fail closed.

Do not silently patch output by hand and call it a model success.

## 11. Recommended First MVP Mode

Recommended first mode:

1. Prompt-only JSON with synthetic pasted text and CSV/simple table inputs.
2. Local static validation for parse and required keys.
3. Manual review of evidence wrappers.
4. If format failures occur, add repair-loop.
5. Only then test provider JSON mode or structured output through approved runtime path.

No Tool/Function is required before the first prompt-only proof. A Tool/Function becomes justified when:

- validation must be automated in the OpenWebUI UX;
- model outputs need repair-loop inside the workflow;
- provider-specific structured-output params cannot be passed natively;
- deterministic document parsing/source mapping is required.

## 12. Sources

OpenWebUI:

- https://docs.openwebui.com/features/workspace/models/
- https://docs.openwebui.com/features/workspace/prompts/
- https://docs.openwebui.com/features/workspace/knowledge/
- https://docs.openwebui.com/features/workspace/skills/
- https://docs.openwebui.com/features/extensibility/
- https://docs.openwebui.com/features/extensibility/plugin/tools/
- https://docs.openwebui.com/features/extensibility/plugin/tools/development/
- https://docs.openwebui.com/features/chat-conversations/data-controls/files/
- https://docs.openwebui.com/reference/api-endpoints/

Provider docs:

- https://developers.openai.com/api/docs/guides/structured-outputs
- https://developers.openai.com/api/docs/guides/function-calling#strict-mode
- https://platform.claude.com/docs/en/build-with-claude/structured-outputs
- https://ai.google.dev/gemini-api/docs/structured-output
- https://api-docs.deepseek.com/guides/json_mode
- https://api-docs.deepseek.com/guides/function_calling
- https://www.alibabacloud.com/help/en/model-studio/qwen-structured-output
- https://qwen.readthedocs.io/en/latest/framework/function_call.html
