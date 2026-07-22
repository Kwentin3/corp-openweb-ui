# Broker Reports Workflow — Final Live Reproof And Repository Closure

Date: 2026-07-22

Branch: `codex/broker-reports-goal6-final-live-reproof-v1`

Program status: COMPLETED

## Revisions and release

- repository evidence base: `7e974cd74007a920bfeb1938d80f4420e2bf8f54`;
- live stage source revision:
  `60b273694479705848d9b0c4ac8f3392ea9b351d`;
- release ID: `broker-reports-60b273694479`;
- release manifest SHA-256:
  `a24134001ce8bfabcc3804b07788fbb668b89190e81f949e37f11267b1ca297c`;
- rollback identity SHA-256:
  `699a0728f18b5a13d7383f433655c5620f0b28979dfd427c6f10363487c5beb8`.

The stage source revision is an ancestor of the evidence base. All commits
after it are documentation-only closure commits, so a second runtime release
was neither required nor performed.

Two independent read-only live verifiers returned `passed`: the atomic-release
verifier and the repository/live delivery verifier.

## Exact live identities

### Functions and Action

| Runtime object | Live/repository SHA-256 | State |
|---|---|---|
| `broker_reports_gate1_pipe` | `8dcbb731c3427ecd83edc0cdf2f1685cbd448e497f53ff3e114eaca464646d11` | active, exact |
| `broker_reports_gate2_source_fact_pipe` | `9b5b54ccccfe1a4b04b2e4bb497612c33d70d53116aa78cd438552702faa886d` | active, exact |
| `broker_reports_gate2_domain_source_fact_pipe` | `74cabe002ad65805b23e516e1e99da2964fd596d6d03be6af77d90109b116709` | active, exact |
| `broker_reports_private_intake_action` | `874a07129aa626e61807095b19e531972395934ce1a9aad72d378a3104530ae4` | active, exact |

Loader SHA-256:
`28c5eadf6839d9aac5db4f125c31bda5ca6f08d9ce82723c832dd319126703b2`.

### Image

- configured image:
  `corp-openwebui/openwebui:v0.9.6-native-web-stt-broker-intake-v2-8e6a71f`;
- image ID:
  `sha256:c862956b5a88f490de3a13829cb4176ce9a2e3fb3621ebf0198b059be65f8e83`;
- image source revision:
  `8e6a71f13cf4f9cec0e5be191fac924548050e48`;
- running: yes;
- restart count: 0;
- private-intake contract: `server-authoritative-v2`.

### Managed prompts

| Prompt | Live/repository SHA-256 |
|---|---|
| `broker_reports_document_metadata_passport_prompt_v0` | `1f9827ad62e1f20c5187f92aa3814f2c149f28148a61356b52850afc301f2de6` |
| `broker_reports_gate1_clarification_prompt_v0` | `7fd0b6dc935395bfb61aeabd24194941ed32b590ba58af03ff1581849dc2048a` |
| `broker_reports_gate2_cash_movement_prompt_v0` | `c9394d07189cd3aec476a27a2fd2f3cc4b3e7883e3abaa6d43066902060d7e0e` |
| `broker_reports_gate2_currency_fx_prompt_v0` | `917c1cae378223bdd2316dc8ec7d317352107943dd5988360e7572719e1bb715` |
| `broker_reports_gate2_document_summary_evidence_prompt_v0` | `9bad1a06bb8556e0fa62f1f47de73c7d7b1d41e57aa752de9206c0749133088d` |
| `broker_reports_gate2_fee_commission_prompt_v0` | `1d7b5c5e25f1e520d55ef8e9c84d323e6a27d73da392b428a74e95a0af6910fc` |
| `broker_reports_gate2_income_prompt_v0` | `af7fcd78f4533d0f5a1f8bcef58ad113f72f102e58f547f0c30f8810ddced187` |
| `broker_reports_gate2_position_snapshot_prompt_v0` | `b250663fc078782b28dfb530f10e99ee13f97789a12d4e67852938b3088c36fd` |
| `broker_reports_gate2_source_fact_prompt_v0` | `97d7f27850e74f8869cedc2c4f8675f44933460fec3d077b192ed222230aae12` |
| `broker_reports_gate2_trade_operation_prompt_v0` | `e819ded91b58bea3012e9bd9cde0444b63427d60120ef6712e33a4d8b515c0d1` |
| `broker_reports_gate2_unknown_source_row_prompt_v0` | `776a7574542cba7b77b2c5e7686af5990c652420823bbea9a78749ac12428aa1` |
| `broker_reports_gate2_withholding_tax_prompt_v0` | `e952e09ab395d21093102e9264effd0d8fce54e5b913b57c046538168d3eb228` |

All 12 prompts are active and match command, content, metadata and version.

## Exact workload configuration and quiescence

- authority: one shared SQLite cross-process workload authority;
- lease: 90 seconds;
- poll interval: 0.2 seconds;
- provider budgets: Alibaba 1, Anthropic 1, DeepSeek 1, Gemini 1,
  OpenAI 2, OpenWebUI completion 2, Z.AI 1;
- Gate 1: at most 64 pages, 32 candidates/page, 8 visual candidates,
  24,000 counted input tokens, 16,384 output tokens, 240-second provider
  timeout, 150 DPI;
- Gate 2 source: 12,000 estimated input tokens, 40 table rows, 6,000 text
  characters;
- Gate 2 domain: 40 table rows, 6,000 text characters, table/text segment
  limits 8/12, one repair attempt, standalone semantic visual projections and
  answer-context selection enabled;
- candidate binding default: disabled;
- Gate 3 context-manifest default: disabled;
- nonterminal jobs: 0;
- owned temporary entries: 0;
- release staging entries: 0;
- completed workload jobs: 19.

The final live readback reported 0 Knowledge rows, 0 document rows, 272 file
rows, 595 vector files and 309,808,908 vector bytes. Those existing repository
totals did not change during the answer and follow-up checks; the workflow's
Knowledge/RAG/vector deltas are zero.

## Native private intake and real broker workflow

Native chat: `1c888389-7cce-4e3d-a26b-243b57292170`.

- authenticated private byte resolution: passed;
- pages: 12;
- detected candidates: 7;
- accepted semantic tables: 5;
- review-required or unsupported candidates: 2;
- failed pages: 0;
- DCP and Gate 2 handoff: validated;
- Knowledge/RAG/vectorization: not used.

Final full-domain Gate 2 run:
`art_TnEoBnCY04zQWaBHoXABfd4IAZHQJnNF`.

- packages accepted: 39/39;
- rejected: 0;
- facts: 63;
- validations passed: 39/39;
- uncovered source refs: 0;
- conflicts: 0;
- fallback outputs: 0;
- terminal status: `completed`;
- workload-owned temporary files cleaned: yes; validated private artifacts
  remain under their configured ArtifactStore lifecycle.

The run has an answer context and selection receipt. Its 28 evidence groups
each expose exactly one interpretation-bearing representation; 5 groups use
semantic visual logical tables and 23 use validated Gate 2 facts. There are 28
presented fact IDs and no duplicates or forbidden context keys.

Answer-context identity:

- ref: `answerctx_9c3d061c120cb6e4ad76c3f6`;
- integrity hash:
  `b422b312b6f7f3de2c6911c17f83a7b6af2c62a62549f10a65eb55a00fafeef8`;
- canonical SHA-256:
  `819b995323a07f3bd2e641abda4241a5a59017460ebe79afa3478e1c07552788`;
- size: 42,215 bytes.

The optional Gate 3 manifest remains policy-blocked because this run contains
an `unknown_source_row` ownership and one repaired provider response. This is
an explicit conservative downstream policy state, not a hidden workflow
failure: Gate 3 is outside this program's acceptance, while the answer-context
handoff is ready and the required user workflow is terminally complete.

## Three-metric semantic checksum

The native answer call used `models/gemini-3.5-flash` with only the assembled
answer context. Results:

- labels, amounts, currency/unit, signs, periods and source references: 3/3;
- arithmetic reconciliation: 1/1;
- semantic-table focused follow-up: passed;
- duplicate counting: 0;
- invented control metrics: 0;
- answer repair: no;
- sealed-reference mutation: no;
- technical JSON/internal IDs in chat: no;
- Knowledge/RAG/vector delta: 0.

Private checksum receipt SHA-256:
`9fd71077755df65450bb8c5dff163bc9736242d8485d8a5fa11b7dce1dbc1084`.

## Product UX

Read-only system-Chrome proof loaded the authenticated chat and API payload.
Processing and completed states were visible, the composer remained available,
and no technical stack or internal artifact IDs were shown. Failure, partial,
retry and cancellation semantics passed 61 focused tests. The UX audit found
no material defect and made no UI changes.

## Repository closure

At the audited evidence base:

- local `main` equals `origin/main`;
- stage revision is reachable from `main`;
- worktree porcelain entries: 0;
- tracked files under ignored `local/`: 0;
- repository privacy guard: 3/3 passed;
- merged temporary branches removed during closure: 12 local and 17 remote.

Four pre-program historical branches are retained but terminally classified:

| Branch | Classification |
|---|---|
| `codex/broker-reports-architecture-recovery-v1` | closed unmerged by PR #1; superseded |
| `codex/broker-reports-blocker-closure-v1` | historical unmerged work; superseded by accepted `main` |
| `codex/broker-reports-runtime-audit-v1` | historical unmerged audit work; superseded by accepted `main` |
| `codex/vlm-guided-intake-development-gate-repair` | terminal failed development gate; superseded |

They are not active delivery branches and do not create a stage-ahead-of-main
condition.

## Goal status

| Goal | Status |
|---|---|
| `GOAL_0_SOURCE_CONTROL_VECTOR` | `COMPLETED` |
| `GOAL_1_CONTEXT_REPRESENTATION_SELECTION` | `COMPLETED` |
| `GOAL_2_NATIVE_USER_WORKFLOW` | `COMPLETED` |
| `GOAL_3_SEMANTIC_CHECKSUM` | `COMPLETED` |
| `GOAL_4_PRODUCT_UX` | `COMPLETED` |
| `GOAL_5_CORRECTIVE_SLICES` | `COMPLETED` |
| `GOAL_6_FINAL_LIVE_REPROOF` | `COMPLETED` |

## Final acceptance

| Invariant | Result |
|---|---|
| `USER_WORKFLOW` | `PASSED` |
| `BROKER_REPORT_CONTROL_VECTOR` | `THREE_OF_THREE` |
| `SEMANTIC_TABLE_CONTEXT` | `PROVEN` |
| `DOUBLE_COUNTING` | `ZERO` |
| `KNOWLEDGE_RAG_VECTOR_DELTAS` | `ZERO` |
| `REPOSITORY_LIVE_PARITY` | `EXACT` |
| `MAIN_AND_ORIGIN_MAIN` | `EQUAL` |
| `STAGE_SOURCE_REVISION` | `TRACEABLE` |
| `PRIVATE_EVIDENCE_IN_GIT` | `ZERO` |
| `PROGRAM_STATUS` | `COMPLETED` |

## External evidence debts

No new unseen visual tables are currently available, and the same-family
positive holdout is still unavailable. These remain future qualification debts,
not blockers for this program.
