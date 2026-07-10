# Broker Reports OpenWebUI-Native LLM Passport Research

Status:

- OPENWEBUI_NATIVE_LLM_PASSPORT_RESEARCH_READY
- OPENWEBUI_PROMPT_MANAGEMENT_DECISION_READY

Date: 2026-07-08

Scope: Broker Reports Gate 1 / Gate 1.5 metadata-only document passport design.

This document does not change runtime code, does not process customer documents, does not run Gate 2, does not run source-fact extraction, does not calculate tax, does not generate declaration or XLS/XLSX, and does not use OCR/VLM. It intentionally does not print raw filenames, OpenWebUI file ids, private paths, document rows, document text, personal names, account numbers, secrets or env values.

## 1. Research Question

After the PDF/HTML source-policy V2 rerun, Gate 1 no longer treats text-layer PDF/HTML as OCR candidates, but 11 documents still remain in `source_role_policy_review_required`. The gap is not only technical parsing. The missing layer is:

```text
technical profile
+ normalized private slices
+ managed prompt
+ LLM structured metadata
+ validator
-> document_metadata_passport_v0
-> source eligibility v2
```

The design goal is to add an LLM-assisted metadata passport without turning Gate 1 into source-fact extraction and without hardcoding the final prompt text in backend Python.

## 2. Local Basis Reviewed

Reviewed local project materials:

- `docs/reports/2026-07-08/OPENWEBUI_BROKER_REPORTS_CASE_GROUP_002_PDF_HTML_SOURCE_POLICY_RERUN_V2.report.md`
- `docs/reports/2026-07-08/OPENWEBUI_BROKER_REPORTS_CASE_GROUP_002_REJECTED_DOCS_ELIGIBILITY_AUDIT.report.md`
- `docs/stage2/contracts/BROKER_REPORTS_GATE1_DOCUMENT_SOURCE_ELIGIBILITY.v0.md`
- `docs/stage2/research/BROKER_REPORTS_OPENWEBUI_PER_MODEL_NO_RAG_UPLOAD_RESEARCH.md`
- `docs/stage2/contracts/BROKER_REPORTS_ARTIFACT_LIFECYCLE_CONTRACT.v0.md`
- `docs/stage2/contracts/BROKER_REPORTS_GATE1_PIPELINE_TO_ARTIFACTS_MAPPING.v0.md`
- `docs/stage2/config/BROKER_REPORTS_OPENWEBUI_WORKSPACE_CONFIGURATION.v0_PROPOSAL.md`
- STT v2 prompt catalog reports, especially Gate 3 and Gate 5 prompt proof.
- Current `services/broker-reports-gate1-proof/` code.

Stable local conclusions reused:

- Broker Reports customer files must use the project-owned `process=false` private intake path, not ordinary OpenWebUI bulk upload.
- Knowledge delta zero is necessary but not sufficient; vector/document/file extraction deltas are separate intake proof.
- ArtifactStore is the system of record for derived Gate 1 artifacts, private slices, validation, retention and Gate 2 handoff refs.
- Gate 1 must keep safety flags false for source-fact extraction, tax, declaration, XLS/XLSX, FNS filing, OCR/VLM and Knowledge loading.

## 3. OpenWebUI Native Surfaces Reviewed

Official OpenWebUI docs describe Prompts as reusable slash commands with variables, access control and version history. Prompt edits create versions and can be rolled back to a production version.

Source:

- <https://docs.openwebui.com/features/workspace/prompts/>

Official Function docs describe Functions as server-side Python plugins stored in the OpenWebUI database and managed by admins. A Pipe registers as a selectable model and handles the request itself.

Source:

- <https://docs.openwebui.com/features/extensibility/plugin/functions/>
- <https://docs.openwebui.com/features/extensibility/plugin/functions/pipe/>

The Pipe guide also documents that a Pipe can call OpenWebUI internal chat completion logic through `generate_chat_completion(__request__, body, user)`. This is the most native way for a server-side Pipe to invoke the configured OpenWebUI model stack while keeping provider routing inside OpenWebUI.

Source:

- <https://docs.openwebui.com/features/extensibility/plugin/functions/pipe/>

Reserved-argument docs show that Pipes can receive current user and metadata context, including model/chat/files metadata. That is enough to carry run identity and access context into the passport stage.

Source:

- <https://docs.openwebui.com/features/extensibility/plugin/development/reserved-args/>

OpenWebUI prompt source code currently exposes prompt fields and endpoints that are useful for a managed prompt resolver: `id`, `command`, `content`, `meta`, `tags`, `is_active`, `version_id`, access grants and history endpoints.

Source:

- <https://raw.githubusercontent.com/open-webui/open-webui/main/backend/open_webui/routers/prompts.py>
- <https://raw.githubusercontent.com/open-webui/open-webui/main/backend/open_webui/models/prompts.py>

These source-code details should be treated as implementation evidence, not as a stable public API guarantee.

## 4. Option Matrix

| Option | Native | Versioned | Access-controlled | Avoids Python prompt hardcode | Fit |
| --- | --- | --- | --- | --- | --- |
| OpenWebUI Prompt as managed source, resolved by Pipe/backend | Yes | Yes | Yes | Yes | Selected |
| Workspace Model system prompt | Yes | Weak for per-run prompt hash | Model-scoped | Mostly | Not primary |
| Pipe Valves containing final prompt text | Native-ish | Weak | Admin-only | No | Reject |
| Prompt body stored in repo Python module | Project-native | Git versioned | Code access only | No | Reject |
| External sidecar prompt registry | Project-owned | Possible | Possible | Yes | Not needed now |
| User slash command execution | Native UI | Yes | Yes | Yes | Useful UI concept, not deterministic backend workflow |
| Filter Function | Native | N/A | Broad | N/A | Too broad for this workflow |

## 5. Decision

Selected mechanism:

```text
OpenWebUI Workspace Prompt
-> server-side Broker Reports prompt resolver
-> Pipe/backend LLM passport stage
-> OpenWebUI model call
-> ArtifactStore prompt metadata/input/output/passport records
```

The OpenWebUI Prompt is the source of truth for prompt body, prompt id, command, tags, metadata, access grants and version id. The Broker Reports code stores only:

- prompt locator;
- expected prompt contract id;
- expected output schema id;
- model id;
- fail-closed policy;
- hash computation and validator logic.

The first implementation slice should add a small `DocumentPassportPromptResolver` behind a factory boundary. The resolver can use the runtime-local OpenWebUI prompt source because the Pipe runs inside OpenWebUI. It must be isolated behind an adapter so a future API or internal-model change does not spread through the normalizer.

Recommended prompt locator:

```text
prompt_id preferred
command fallback
required tag: broker-reports-gate1
required meta.template_kind: document_metadata_passport
required meta.template_id: broker_reports.document_metadata_passport.v0
required meta.output_schema_version: document_metadata_passport_v0
```

## 6. Why The Prompt Is Not Hardcoded In Python

Prompt text should not live in `broker_reports_gate1_pipe.py`, `normalizer.py` or static backend modules because:

- prompt edits would require redeploying the Pipe bundle;
- operator review, rollback and production pinning would be outside OpenWebUI;
- run evidence could not naturally point to OpenWebUI prompt version/history;
- a Python source diff would mix workflow code with policy wording;
- secrets and customer data policy is clearer when the prompt is a managed workspace asset;
- ArtifactStore audit can record prompt id/version/hash without copying prompt bodies into chat.

Python may include the resolver, schema id, validator, hash algorithm and fail-closed checks. Python must not embed the final managed prompt body as the permanent source of truth.

## 7. Prompt Version And Hash

At the start of each passport run, Gate 1 should resolve the active managed prompt and compute:

```text
llm_prompt_ref
llm_prompt_command
llm_prompt_version
llm_prompt_hash
llm_prompt_source=openwebui_prompt
llm_prompt_contract_id=broker_reports_document_metadata_passport_prompt_v0
```

Hash input should be deterministic:

```text
sha256(
  normalized_prompt_content
  + "\ncontract:"
  + prompt_contract_id
  + "\nschema:"
  + output_schema_version
)
```

Persisted artifacts should include:

- prompt metadata in the passport safe projection;
- prompt hash/version in validation result;
- optional prompt snapshot artifact as `safe_internal`, not chat-visible;
- LLM input package as `private_case` or not persisted if policy says transient only;
- LLM raw structured output as `private_case`;
- validated passport safe projection as `safe_internal`.

The prompt body itself contains no customer data. If a prompt snapshot is stored, it is still not rendered in chat.

## 8. LLM Invocation Mechanism

Recommended LLM call path:

```text
broker_reports_gate1_pipe
-> resolve managed prompt
-> build private LLM-friendly document package
-> call OpenWebUI chat completion using selected passport model id
-> parse strict JSON
-> validate
-> persist passport artifacts
```

The selected call path should use OpenWebUI runtime model routing, ideally through the internal chat completion helper documented for Pipe Functions. Direct provider clients should be avoided in the first slice because they duplicate provider auth/routing and move the workflow away from OpenWebUI-native operations.

The Pipe `Valves` should contain only configuration:

- passport stage enabled flag;
- prompt id or command;
- passport model id;
- max input slice limits;
- timeout;
- strict JSON requirement;
- persistence mode;
- fail-closed setting.

They should not contain the final prompt body.

## 9. LLM Input

The LLM must not receive an ordinary OpenWebUI upload or Knowledge context. It receives a private, bounded, Gate 1-built package:

```text
broker_reports_llm_document_package_v0
```

Package contents:

- normalization run id;
- case group id;
- safe document id;
- source file safe ref;
- document container/profile summary;
- parser/readability signals;
- section names and section labels;
- bounded text slice summaries or excerpts prepared for metadata classification;
- table headers and table summaries, not full financial rows in safe surfaces;
- evidence refs that point back to private slices;
- taxonomy candidate and blocker codes;
- current source-policy context;
- explicit list of forbidden tasks.

The LLM-friendly package is private. It must not be printed into chat, OpenWebUI Knowledge, public reports or safe handoff output.

## 10. LLM Output

The LLM returns strict JSON:

```text
document_metadata_passport_v0
```

The output is metadata-only. It may contain:

- candidate document kind;
- broker/client/account-or-contract candidates;
- report period and tax year candidates;
- detected sections;
- source-role hypotheses;
- confidence values;
- evidence refs;
- missing metadata fields;
- conflict flags;
- review requirement.

It must not contain:

- raw rows;
- full source text;
- transaction-level extracted facts;
- tax calculations;
- declaration fields;
- XLS/XLSX rows;
- OCR/VLM output;
- model rationale containing copied customer text.

## 11. Validator Requirements

The validator must fail closed. Minimum checks:

1. JSON parse succeeds and top-level schema version is exact.
2. `document_id`, `normalization_run_id` and `case_group_id` match the current package.
3. `source_file_ref` is safe and opaque.
4. Evidence refs exist, belong to the same document/run and point only to allowed private slices or safe profile refs.
5. No forbidden fields or raw-content markers are present.
6. Candidate date fields are ISO dates or null.
7. Confidence fields are bounded enum/number values.
8. Missing data is represented as null plus `missing_metadata_fields`, not hallucinated values.
9. Prompt metadata is present: prompt ref, version, hash, model id and input refs.
10. Safety flags remain false for source facts, tax, declaration, XLS/XLSX, OCR/VLM and Knowledge.
11. `review_required=true` when required evidence is missing or conflicts exist.
12. `source_candidate_confidence` is not enough by itself to include a document in Gate 2.

## 12. Source Eligibility v2

Current eligibility uses technical document shape, taxonomy candidates and blockers. V2 should use:

```text
technical profile
+ taxonomy candidate
+ document_metadata_passport_v0
+ blockers
+ duplicate state
+ case scope
```

PDF/HTML broker reports can become accepted source candidates only if all are true:

- parser profile proves text/table evidence exists without OCR/VLM;
- passport validator passed;
- passport indicates broker/source report or compatible source role;
- broker/client/account/period fields are present, or explicit alternatives are sufficient;
- relevant financial sections are detected;
- evidence refs support the metadata claims;
- no terminal blocker exists;
- duplicate state is resolved or canonical choice is explicit;
- source-policy context allows promotion.

If the passport is incomplete, the document should move to metadata review, not disappear into a generic unknown bucket.

## 13. Applying To case_group_002

The V2 case_group_002 state is the intended target:

- total documents: 16;
- accepted for reduced Gate 2 subset: 2;
- duplicate canonical-choice review: 1;
- methodology/output artifacts: 2;
- OCR required after V2: 0;
- source-role policy review: 11.

The passport stage should run only after controlled `process=false` custody is already proven. It should focus on the 11 source-policy-review documents and produce metadata passports that help distinguish:

- source broker reports;
- methodology or output artifacts;
- duplicates;
- outside-scope or incomplete documents;
- documents needing metadata review.

It must not promote any document solely because a private registry hint says so. Registry hints are classification hints; the passport validator and source-policy rules still decide whether the document can enter the reduced Gate 2 handoff.

## 14. Risks

1. Prompt API/source drift.
   Mitigation: isolate behind resolver adapter and record capabilities.

2. Prompt body leakage.
   Mitigation: never return prompt body in chat/report metadata; store only hash/version unless an internal snapshot artifact is explicitly enabled.

3. Admin/service access bypass.
   Mitigation: prefer runtime-local same-user context where possible; if service/admin access is used, reapply access checks and prove denial cases.

4. LLM hallucination.
   Mitigation: strict schema, evidence refs, null-on-missing rule and validator fail-closed behavior.

5. Source-fact drift.
   Mitigation: passport prompt and validator prohibit transaction extraction and tax/declaration/XLS outputs.

6. PII/provider exposure.
   Mitigation: passport stage requires customer-approved provider policy and bounded private input package; no Knowledge/RAG path.

7. Latency/cost.
   Mitigation: per-document package caps and optional batching only after single-document validation passes.

8. Prompt version rollback ambiguity.
   Mitigation: persist prompt version id and content hash on every passport.

## 15. Research Verdict

OpenWebUI Prompts are suitable as the primary managed prompt source for Broker Reports Document Metadata Passport if they are used as a server-side managed registry, not as a user slash-command workflow.

The implementation should proceed as a narrow slice:

```text
prompt resolver
-> LLM package builder
-> OpenWebUI model invocation
-> strict JSON parser
-> validator
-> ArtifactStore persistence
-> eligibility v2 integration
```

No architecture redesign is required.
