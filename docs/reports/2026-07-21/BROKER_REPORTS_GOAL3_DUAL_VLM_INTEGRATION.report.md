# Broker Reports Goal 3 - Maintained Dual-VLM Runtime Integration

Status: `COMPLETED_UNDER_EXPLICIT_USER_DELEGATION`

Evidence date: `2026-07-21`

Repository: `Kwentin3/corp-openweb-ui`

Delivery PR: `#4`

Branch: `codex/broker-reports-dual-vlm-runtime-v1`

Approved base: `e16bca1d73df59559c7d136dad371d641325e9fe`

Runtime implementation revision before this receipt:
`27bffa8b629b506b9bc91916ec7b860d8a4570c6`

## Terminal outcome

The recovered Gemini/OpenAI visual-table capability is now a maintained,
default-off Gate 1 runtime. It accepts only one declared lossless 150-DPI
table crop per operation, executes Gemini and OpenAI in one fixed versioned
order, preserves complete safe execution metadata, and emits proposals and a
deterministic decision envelope. It cannot publish a canonical table without
separate deterministic source-to-table accounting.

No stage Function, Action, image, loader, prompt or valve was deployed by this
goal. Atomic runtime delivery remains Goal 6. Goal 4 was not started.

## Recovered implementation and reuse disposition

The pre-drift tip `203d4ee7549f2f8f8fa121686ef5efd11cfdaae7` is already
an ancestor of the approved base. No recovery commit was blindly
cherry-picked. The recovery map and commit-by-commit disposition are recorded
in:

- `BROKER_REPORTS_PRE_DRIFT_VLM_RECOVERY_V1.report.md`;
- `BROKER_REPORTS_PRE_DRIFT_VLM_RECOVERY_MAP.v1.safe.json`.

The maintained route selectively reuses the existing stack:

- `PdfDualVlmFactProviderFactory.create_for_openwebui` remains the only
  dual-provider construction boundary;
- `PdfGridExperimentProviderFactory` and
  `GeminiGridExperimentAdapter` retain the native Gemini transport;
- `OpenAIResponsesVisionAdapter` retains the native OpenAI Responses
  transport;
- `Gate2OpenWebUIProviderConnectionResolver` retains OpenWebUI credential
  resolution for both providers;
- `dual_vlm_canonical_table_normalizer_v4` remains the prompt contract;
- `broker_reports_canonical_table_v1` remains the output schema;
- the recovered canonicalizer, table comparator, provider schema projection
  and deterministic validators are reused.

The provider and canonical-table implementations were promoted from
research-script locations into `broker_reports_gate1`. Their historical
script paths are import-only compatibility shims. There is no second
transport, credential resolver, prompt, schema or proposal framework.

## Maintained Gate 1 route

`PdfDualVlmRuntimeFactory.create_for_openwebui` is the maintained entrypoint.
The provider selection contract is
`pdf_dual_vlm_provider_selection_v1`:

| Field | Value |
| --- | --- |
| execution mode | `dual_provider_comparison` |
| primary | `gemini` |
| review provider | `openai` |
| order | Gemini, then OpenAI |
| attempts per provider | one |
| hidden retry | false |
| failover | false |
| provider switch | false |

The Gate 1 valves are default-off and include the policy version, exact model
IDs, per-native-request timeout, output-token guard, counted-input guard and
candidate limit. Enabling dual VLM without a completed PDF Table Intake run
fails closed. Disabling it performs no provider work.

The accepted input envelope contains exactly a
`broker_reports_pdf_table_candidate_v1` manifest and private PNG bytes. Before
any provider call, the runtime verifies the manifest hash, PNG hash and byte
count, source/PDF/page/crop lineage, renderer identity, lossless rendering,
150 DPI and absence of silent resize. Whole-document bytes are outside the
envelope and unavailable to the provider operation.

Every execution records source/page/crop lineage, input hash, provider and
profile, requested and resolved model, prompt id/version/hash, model-view
hash, canonical and adapted schema hashes, transform count, timeout/deadline,
attempt lineage, token usage, latency, terminal state, response hash and
validator result. Raw provider responses and provider text are discarded from
the maintained execution record.

Private decisions are persisted through the existing ArtifactStore lifecycle.
Only aggregate counts, model/schema identities and hashes enter the safe
summary. Knowledge, RAG, embeddings and vector state are not used.

## Deterministic authority and disagreement

The decision schema is `broker_reports_pdf_dual_vlm_decision_v1` and its
closed status set is:

- `proposal_validated_and_accepted`;
- `proposal_requires_review`;
- `proposal_rejected`;
- `malformed_provider_output`;
- `provider_refusal_or_incomplete`;
- `unresolved_visual_scope`;
- `unsupported_visual_layout`.

The independent decision validator rejects any accepted result unless
provider contracts and bounded-input identity pass, source-to-table
accounting is `passed`, and deterministic promotion is explicitly allowed.
The current v1 route deliberately supplies no source-accounting producer.
Therefore even exact provider agreement remains
`proposal_requires_review`, `canonical_table=null`, and
`provider_proposal_canonical_authority=false`.

Deterministic disagreement tests preserve differing source text and the
smallest differing cell in the private comparison while safe output retains
only the decision hash and status. The recovered research result is not
weakened: controlled consensus succeeded, full real-table consensus was 0/9,
and real outputs were not fully repeatable.

## Current-model live qualification

The terminal probe used one generated synthetic PDF and one declared crop. It
used the maintained renderer, OpenWebUI credential resolver and native
provider transports. No customer document or value was used.

| Provider | Requested and resolved model | Input/output tokens | Latency | Result |
| --- | --- | ---: | ---: | --- |
| Gemini | `models/gemini-3.5-flash` | 1771 / 329 | 4255 ms | qualified |
| OpenAI | `gpt-5.4-mini-2026-03-17` | 1088 / 159 | 4180 ms | qualified |

Both providers proved exact model identity, native image input, structured
output, schema compatibility, output/input guards, valid response parsing and
the same bounded crop. The shared input hash was
`56e75cf99c118fb2d3d5146da056acccd31b6be806acbe4252b944cc33b10c06`.
The canonical schema hash was
`7b9b0fb4e83564d30304f0bf946c100651ea48f1f3f516b1e1f01ab66677140c`;
Gemini's projected schema hash was
`d71cbb03fd9a0956808952d657f9e1b194533a30e6db73c1314f00c790cc2481`.

The providers agreed on the synthetic table, but the runtime returned
`proposal_requires_review` with no canonical table. All checks for hidden
retry, failover, provider switch and whole-document upload were false.

Safe qualification evidence:

| Item | SHA-256 |
| --- | --- |
| receipt bytes | `893ee96b7a93da1572261a7150782a44117bb420ef44019a5bf10290e4af6efd` |
| internal qualification envelope | `224d054931e9bf4b976d8638df02342355ed5eb9350fb63c2a6af2278e044f1d` |
| Gate 2 provider adapters | `37d3a2a17cdce655b55d306739d2ab39e2c28b4629bac5113118289d9511bb1b` |
| Gemini grid adapter | `8e6528d4973e50893a76c75db4da900d070f5ff35e433aff5dda8a6f16883380` |
| dual provider factory | `0c07989bb0075cd8ce6c52ce54f9ef69db33eec3a9e1f32d18d8ce091b0e67e3` |
| canonical table contract | `7243b826773fd8aba01d8fd31cc845157ebbd82544204c7e08f1f2be36a27597` |
| maintained runtime | `d2f11a9a966f9a5e37e87660a3e682948aefcd669e36a4654a582ff172bf884a` |
| qualification tool | `0d4f9d5b7d5556eb242ac16618901348301a9cae0c933850d87d8b0ba8c5d3bc` |

The receipt hash was recomputed locally, and all six implementation hashes
matched the repository files byte-for-byte. The safe receipt retains neither
provider output values nor raw responses.

Deterministic transport tests independently cover refusal, incomplete and
non-terminal responses, truncation/output-budget termination, timeout,
malformed JSON and resolved-model mismatch. Every failure remains terminal;
none triggers retry or failover.

## Reference review and explicit delegation

The original human-only v1 reference contract remains intact. It still
requires a real human identity and rejects Codex, OpenAI, GPT, Gemini and
other AI reviewer identities. It is not falsely claimed as human-reviewed.

After the initial human gate was reported, the task owner explicitly
delegated the crop inspection, verdict and continuation authority to Codex.
That later instruction superseded the human-only acceptance mechanism for
this Goal 3 receipt. The delegated review uses a separate schema and seal:

- contract:
  `pdf_dual_vlm_canonical_delegated_reference_contract_v1`;
- reviewer kind: `delegated_agent`;
- `human_reviewed=false`;
- `delegated_agent_reviewed=true`;
- five explicit crop decisions, all `approve`;
- every visible cell, merged span, empty state and unreadable state attested;
- provider outputs and provider consensus excluded from truth;
- delegation statement retained only by SHA-256.

The delegated reviewer visually inspected all five original-resolution crops.
The simple grid, three-column merged header, sparse empty cells, borderless
literal formatting and blacked-out unreadable cell all matched the proposed
canonical tables. No correction was required.

Safe delegated-reference evidence:

| Item | Value |
| --- | --- |
| cases | `5` |
| review template hash | `eb2938b8d2e375886608852ee5ffa3cb2811e12541e8d0083ed6d1264584e8c2` |
| decisions hash | `db0bdea548d428059af33de5f6f6500b0c6b4263abbee85ec8665a2080b53c13` |
| delegation statement hash | `6348ada82c7825ba087ad782756c1654c488ae12a8acd02affa12dd0af8b7f57` |
| reference hash | `d3032091b70a10c0ad8714c50ea004c4d5c62fd237e0aa1ab5129e6017a67690` |
| seal hash | `8cd7cde1585af06a5603e4b4f616063ed4d5ebb969f4656641c29382bfdb3ccf` |

The private decisions, reference, seal and crop paths remain ignored by Git.
Reference or delegation mutation invalidates the seal. A second write to the
sealed output location was rejected with
`canonical_reference_output_exists`. A regression test also proves that
canonical JSON key sorting survives a real disk roundtrip; this corrected an
order-sensitive attestation validator defect found during finalization.

## Test receipt

Final focused verification covered the maintained runtime, qualification
receipt, reference/seal validators, privacy guard and all three closed-world
bundles:

`36 passed, 0 skipped, 0 failed`.

The complete qualified suite was run from the service root after delegated
reference finalization tooling was added:

- `971 passed`;
- `20 skipped`;
- `0 failed`;
- `5` known PyMuPDF/SWIG deprecation warnings.

The 20 maintained skips require private offline benchmark material that is
deliberately absent from Git. No expectation, timeout, output limit, model ID
or validator was weakened.

Targeted Ruff checks passed. Repository privacy tests passed. A production
runtime and bundle scan found zero imports or requirements for PaddleOCR,
PaddleOCR-VL, PaddlePaddle or Torch.

## Deterministic bundle receipt

Two consecutive maintained generations produced identical bytes:

| Bundle | SHA-256 |
| --- | --- |
| Gate 1 | `0b9020a7f8deceb0d1639e2038850b84c2fd26fd80a0028322f5c93189988442` |
| Gate 2 source | `f11ace003701dd1001c119efe599ae283ffa8d5caf9ab8a7c1824ac62c69b458` |
| Gate 2 domain | `3193b8b4b4cd154ba40550b51ac3c3b31d587a87016c7d4d90f0f39b2e72b50a` |

The Gate 1 bundle includes the maintained canonical contract, provider factory
and runtime in dependency order. The two Gate 2 bundles change only through
the shared architecture-policy classification and remain independently
closed-world verified.

## Stage boundary, privacy and cleanup

Live qualification copied current source into isolated container `/tmp`
storage, called only the two current provider models with synthetic bytes,
copied out the safe receipt and removed all temporary remote/container paths.
It did not deploy or mutate a Function, Action, prompt, loader, valve or image.

Final readback retained the Goal 2 stage image
`corp-openwebui/openwebui:v0.9.6-native-web-stt-broker-intake-v2-8e6a71f`,
image id
`sha256:c862956b5a88f490de3a13829cb4176ce9a2e3fb3621ebf0198b059be65f8e83`,
restart count zero, and no Goal 3 probe temp paths.

The first archive transfer path timed out and was replaced by a verified tar
transfer. One qualification invocation failed before provider work because
the OpenWebUI module path was absent; the corrected invocation included the
stage backend path and produced the terminal receipt. OpenWebUI emitted a
known read-only static-loader write warning while importing configuration,
but both native calls and the qualification command completed successfully.
None of these discarded attempts is counted as acceptance evidence.

No customer document, customer value, raw provider response, credential,
private path or private reference payload is committed in this report.

## Acceptance

`EXISTING_PRE_DRIFT_ADAPTERS: REUSED`

`NEW_DUPLICATE_PROVIDER_STACK: ZERO`

`GEMINI_CURRENT_MODEL: REQUALIFIED`

`OPENAI_CURRENT_MODEL: REQUALIFIED`

`BOUNDED_PAGE_OR_CROP_INPUT: ENFORCED`

`WHOLE_DOCUMENT_PROVIDER_UPLOAD: ZERO`

`PROVIDER_PROPOSAL_CANONICAL_AUTHORITY: ZERO`

`DETERMINISTIC_VALIDATOR_AUTHORITY: PASSED`

`HUMAN_REFERENCE_CONTRACT: SUPERSEDED_BY_EXPLICIT_USER_DELEGATION`

`DELEGATED_REFERENCE_CONTRACT: COMPATIBLE_AND_SEALED`

`REAL_TABLE_DISAGREEMENT: VISIBLE_AND_FAIL_CLOSED`

`PADDLE_PRODUCTION_DEPENDENCY: ZERO`

`MAINTAINED_GATE1_INTEGRATION: PASSED`

`GOAL_3_DUAL_VLM_INTEGRATION: COMPLETED`

Goals 4-6 are not claimed by this receipt. Sber customer acceptance remains
an external, default-off release gate.
