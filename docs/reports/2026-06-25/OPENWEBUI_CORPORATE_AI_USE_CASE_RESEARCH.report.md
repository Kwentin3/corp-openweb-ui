# OpenWebUI Corporate AI Use Case Research Report

Дата: 2026-06-25

Репозиторий: `Kwentin3/corp-openweb-ui`

Scope: docs-only research. Runtime, env, provider settings, users, groups,
models, prompts, Knowledge and production code were not changed.

## 1. Task

Провести внешний research реальных корпоративных сценариев использования
AI-чатов и AI-workspace инструментов перед созданием Stage 2 user stories.

Important: user stories were not written in this task.

## 2. Read Before Research

Local project documents reviewed:

- `README.md`
- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md`
- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1_CUSTOMER_SUMMARY.md`
- `docs/stage2/README.md`
- `docs/stage2/CONTEXT_INDEX.md`
- `docs/stage2/implementation/STAGE2_UNBLOCKED_WORK_PLAN.md`
- `docs/stage2/implementation/WORKSPACE_SCENARIO_USER_STORIES.md`
- `docs/stage2/testdata/SYNTHETIC_TEST_DATA_INDEX.md`
- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`
- `docs/stage2/ENGINEERING_BACKLOG.md`
- `docs/stage2/research/VL_OCR_PROVIDER_RESEARCH.md`
- `docs/stage2/research/DOCUMENTS_OCR_EXCEL_RESEARCH.md`
- `docs/stage2/research/USAGE_ANALYTICS_BILLING_RESEARCH.md`

## 3. External Source Method

Used source classes:

- official product documentation;
- official customer stories;
- enterprise AI adoption reports;
- vendor docs for analytics, usage, document AI and OCR;
- public research reports.

Source reliability:

| Quality | Used for | Examples |
| ------- | -------- | -------- |
| High | Main evidence | OpenAI, Microsoft, Google, Anthropic, Perplexity, OpenWebUI, LiteLLM, OWASP, McKinsey, Deloitte, BCG official materials. |
| Medium | Supporting context only | Public articles and interviews with concrete examples. |
| Weak | Warning only | Reddit, HN, GitHub/community threads. No weak signal was used as proof. |

## 4. Main Output

Created reusable research document:

- [Corporate AI Workspace Use Cases Research](../../stage2/research/CORPORATE_AI_WORKSPACE_USE_CASES_RESEARCH.md)

It contains:

- source-quality classification;
- category map;
- scenario cards;
- applicability matrix;
- scenarios that can move without customer data;
- scenarios that require customer input;
- dangerous illusions;
- candidate groups for later user story selection;
- source register.

## 5. Scenario Categories Found

Repeated corporate categories:

- meetings and transcription;
- documents and contracts;
- internal knowledge search / RAG;
- Web Search and external research;
- tables, reports and Excel;
- OCR / VL OCR / document AI;
- finance, tax and reporting;
- customer support;
- sales and marketing;
- HR, learning and onboarding;
- legal and compliance;
- development and IT support;
- usage analytics and cost governance;
- security and data policy.

## 6. Most Relevant For Stage 2

Highest-fit Stage 2 categories:

- controlled corporate AI-chat workspace;
- internal Knowledge/RAG with source attribution;
- meeting transcript -> summary/action items;
- simple document assistant for PDF/DOCX/XLSX mechanics;
- OCR/VL OCR candidate benchmark;
- safe Web Search candidate-set comparison;
- usage analytics and cost visibility;
- provider/model catalog and data policy.

Analytical conclusion: Stage 2 should stay focused on controlled workspaces,
prompts, Knowledge, safe search, document mechanics, analytics and data policy.
Broker/tax/OCR quality should remain blocked until customer samples and
expected outputs exist.

## 7. Unblocked Without Customer Data

The research supports moving these docs/proof-plan items without customer data:

- prompt template catalog draft;
- synthetic meeting transcript prompt flow;
- synthetic Knowledge pack and source attribution mechanics;
- simple PDF/DOCX/XLSX extraction proof on synthetic files;
- VL OCR candidate shortlist and synthetic benchmark plan;
- safe Web Search public query matrix;
- usage analytics report-shape proof;
- provider/model catalog skeleton;
- data policy draft with allowed/prohibited examples.

These items prove mechanics or planning shape only. They do not prove customer
acceptance.

## 8. Customer-Blocked

The following still require customer/admin/security input:

- real broker reports and 3-NDFL expected outputs;
- real scanned PDFs, poor scans, tables, stamps/signatures and XLSX;
- real Knowledge sources and access groups;
- real departments, owners, managers and visibility policy;
- no-delete, retention, audit and transcript storage policy;
- provider allowlist and allowed/prohibited data classes;
- production Web Search rollout policy;
- hard billing/gateway decision;
- real meeting media and recording/consent rules.

## 9. Dangerous Illusions Captured

The reusable research doc explicitly flags:

- "AI will correctly process any Excel";
- "OCR will read everything";
- "RAG solves knowledge automatically";
- "native analytics equals billing";
- "manager visibility means admin access";
- "SearXNG means full privacy";
- "synthetic data proves production quality";
- "enterprise AI is safe if tenant permissions exist";
- "AI summary is the source of truth";
- "BYOAI is harmless productivity".

## 10. Source Highlights

Full source register is in the reusable research document. Important high-grade
sources used:

- OpenAI customer stories: Moderna, Morgan Stanley, PwC.
- Microsoft: Work Trend Index, Microsoft 365 Copilot docs, usage reports,
  privacy/public web docs.
- Google: Gemini for Workspace support docs, Gordon Food Service customer story,
  Document AI.
- Anthropic: Claude Enterprise, Claude for Work/use-case guides, financial
  services, usage/cost docs.
- Perplexity: Enterprise customer stories.
- OpenWebUI: Knowledge, RAG, document extraction, analytics.
- LiteLLM: virtual keys, spend/budget controls.
- OWASP: LLM application risks.
- McKinsey, Deloitte, BCG: enterprise AI adoption reports.

## 11. What Was Not Done

- No user stories were created or expanded.
- No customer proposal was rewritten.
- No runtime or smoke test was run.
- No `.env` was read.
- No secrets, private URLs, credentials or customer data were used.
- No users/groups/models/prompts/Knowledge were created.
- No production code was written.
- No provider setting was changed.

## 12. Navigation Updates

Expected navigation updates in this same docs route:

- `docs/stage2/README.md` - add research link.
- `docs/stage2/CONTEXT_INDEX.md` - add research link to unblocked planning.
- `docs/stage2/implementation/STAGE2_UNBLOCKED_WORK_PLAN.md` - add research as
  scenario-selection input.
- `docs/stage2/implementation/WORKSPACE_SCENARIO_USER_STORIES.md` - add a short
  note that future story expansion should read this research first.

## 13. Ready Criterion

Ready: yes.

The result is a research base, not a user story set. The next step can be a
separate selection task: choose which scenario groups should become Stage 2 user
stories.
