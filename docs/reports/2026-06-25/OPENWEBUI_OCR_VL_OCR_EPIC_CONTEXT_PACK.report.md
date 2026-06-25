# OpenWebUI OCR / VL OCR Epic Context Pack Report

Дата: 2026-06-25

Статус: docs-only handoff package. Runtime, provider setup, OCR/VL OCR APIs,
`.env`, secrets and customer data were not used.

## 1. Задача

Подготовить самостоятельный handoff-context-pack для нового Stage 2 эпика:
**OCR / VL OCR Infrastructure & Provider Benchmark**.

Цель: будущий агент должен понять, почему `ST2-US-013` нельзя исполнять как
обычный proof, какие OCR/VL OCR contracts нужно определить до benchmark, какие
данные нельзя использовать и какой следующий шаг делать.

## 2. Что было прочитано

Прочитаны обязательные entrypoints and OCR-related docs:

- `README.md`
- `docs/stage2/README.md`
- `docs/stage2/CONTEXT_INDEX.md`
- `docs/stage2/CONTEXT_USAGE_RULES.md`
- `docs/stage2/ROADMAP.md`
- `docs/stage2/ENGINEERING_BACKLOG.md`
- `docs/stage2/IMPLEMENTATION_GATES.md`
- `docs/stage2/CONTRACT_BOUNDARIES.md`
- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md`
- `docs/stage2/research/VL_OCR_PROVIDER_RESEARCH.md`
- `docs/stage2/research/DOCUMENTS_OCR_EXCEL_RESEARCH.md`
- `docs/stage2/implementation/STAGE2_SELECTED_USER_STORIES.md`
- `docs/stage2/implementation/WORKSPACE_SCENARIO_USER_STORIES.md`
- `docs/stage2/testdata/STAGE2_SELECTED_STORIES_SYNTHETIC_DATA_REQUIREMENTS.md`
- `docs/stage2/implementation/STAGE2_SELECTED_STORIES_PROOF_PLANS.md`
- `docs/reports/2026-06-25/OPENWEBUI_STAGE2_SELECTED_STORIES_PROOF_PREP.report.md`
- `docs/stage2/testdata/SYNTHETIC_TEST_DATA_INDEX.md`
- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`
- `docs/stage2/acceptance/TEST_DATA_REQUIREMENTS.md`
- `docs/stage2/decisions/ADR-0005-ocr-vl-ocr-pilot-scope.md`
- `docs/stage2/blueprints/DOCUMENTS_OCR_EXCEL.blueprint.md`

## 3. Почему ST2-US-013 переклассифицирован

`ST2-US-013` remains useful as a user-story marker, but execution is paused as
user-story proof.

Reason: OCR / VL OCR provider shortlist, input/output contract, error contract,
safety boundary and benchmark plan are not defined yet. Running a proof now
would overread a user story as infrastructure readiness.

The architecture position is: OCR/VL OCR should be a separate verifiable
extraction contour. Direct `image/page -> multimodal LLM -> answer` is not the
default corporate OCR baseline.

## 4. Что создано

Created:

- `docs/stage2/context/OCR_VL_OCR_INFRASTRUCTURE_EPIC_CONTEXT_PACK.md`
- `docs/reports/2026-06-25/OPENWEBUI_OCR_VL_OCR_EPIC_CONTEXT_PACK.report.md`

Updated:

- `docs/stage2/implementation/STAGE2_SELECTED_USER_STORIES.md`
- `docs/stage2/implementation/STAGE2_SELECTED_STORIES_PROOF_PLANS.md`
- `docs/stage2/testdata/STAGE2_SELECTED_STORIES_SYNTHETIC_DATA_REQUIREMENTS.md`
- `docs/stage2/CONTEXT_INDEX.md`
- `docs/stage2/README.md`
- `docs/stage2/ENGINEERING_BACKLOG.md`
- `docs/stage2/IMPLEMENTATION_GATES.md`

## 5. Ключевые решения/позиции

- `ST2-US-013` is paused until OCR / VL OCR Infrastructure & Provider Benchmark
  Epic defines shortlist, contracts and benchmark plan.
- Synthetic benchmark can compare candidates, but does not prove production OCR
  readiness.
- OCR/VL OCR output must expose pages, text blocks, tables, fields, confidence,
  warnings, errors and unsupported features.
- LLM analysis should work over extracted normalized representation, not over
  untraceable raw image answers as the only path.
- Human review remains part of the OCR/VL OCR pilot and broker-report path.

## 6. Что не делалось

- Runtime proof не запускался.
- OCR/VL OCR provider APIs не вызывались.
- Provider setup не выполнялся.
- `.env`, secrets, tokens, private URLs, credentials не читались.
- Customer data не использовались.
- Synthetic files не создавались.
- Users/groups/models/prompts/Knowledge не создавались.
- OpenWebUI config не менялся.
- Production code не писался.
- Новый внешний research не проводился.

## 7. Следующий рекомендуемый шаг

```text
Open OCR / VL OCR Provider Shortlist Research task.
```

Do not start benchmark execution immediately. First fill provider capability
profiles and decide which 2-3 candidate classes are worth benchmarking.

## 8. Git status / commit

Preflight status:

```text
## main...origin/main
?? docs/out/
```

Validation before staging:

```text
changed_docs_relative_link_missing_count=0
changed_docs_secret_like_hit_count=0
git diff --check: no findings
non_docs_diff_files=0
```

Commit hash is recorded in the task closeout after commit/push, not embedded in
this report, to avoid self-referential hash churn.
