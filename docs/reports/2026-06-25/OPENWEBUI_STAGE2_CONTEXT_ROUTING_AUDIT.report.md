# OpenWebUI Stage 2 Context Routing Audit Report

Дата: 2026-06-25

Статус: docs-only audit report. Runtime proof не запускался, OpenWebUI config
не менялся, `.env`/secrets/customer data не читались.

## 1. Задача

Проверить, был ли реально усилен Stage 2 context routing: может ли будущий
агент быстро и безопасно подобрать нужные документы под задачу, не перепутать
research, report, proposal, backlog, gate, ADR and proof plan, и не начать
runtime/config/customer-data действия из docs-only документов.

## 2. Что было прочитано

Обязательный набор прочитан и проверен:

- [Root README](../../../README.md)
- [Stage 2 README](../../stage2/README.md)
- [Stage 2 Context Index](../../stage2/CONTEXT_INDEX.md)
- [Stage 2 Context Usage Rules](../../stage2/CONTEXT_USAGE_RULES.md)
- [Stage 2 Roadmap](../../stage2/ROADMAP.md)
- [Stage 2 Engineering Backlog](../../stage2/ENGINEERING_BACKLOG.md)
- [Stage 2 Implementation Gates](../../stage2/IMPLEMENTATION_GATES.md)
- [Stage 2 Contract Boundaries](../../stage2/CONTRACT_BOUNDARIES.md)
- [Stage 2 Unblocked Work Plan](../../stage2/implementation/STAGE2_UNBLOCKED_WORK_PLAN.md)
- [Stage 2 Selected User Stories](../../stage2/implementation/STAGE2_SELECTED_USER_STORIES.md)
- [Stage 2 Selected Stories Synthetic Data Requirements](../../stage2/testdata/STAGE2_SELECTED_STORIES_SYNTHETIC_DATA_REQUIREMENTS.md)
- [Stage 2 Selected Stories Proof Plans](../../stage2/implementation/STAGE2_SELECTED_STORIES_PROOF_PLANS.md)
- [Selected Stories Proof Prep Report](OPENWEBUI_STAGE2_SELECTED_STORIES_PROOF_PREP.report.md)
- [Corporate AI Workspace Use Cases Research](../../stage2/research/CORPORATE_AI_WORKSPACE_USE_CASES_RESEARCH.md)
- [Customer Stage 2 Governance Proposal](../../stage2/proposals/CUSTOMER_STAGE2_GOVERNANCE_PROPOSAL.md)
- [Customer Runtime Decisions](../../stage2/proposals/CUSTOMER_STAGE2_RUNTIME_DECISIONS.md)
- [Acceptance Matrix](../../stage2/acceptance/ACCEPTANCE_MATRIX.md)
- [Test Data Requirements](../../stage2/acceptance/TEST_DATA_REQUIREMENTS.md)

Перед началом проверены:

- `git status --short --branch`: `## main...origin/main` plus untracked
  `docs/out/`;
- последние коммиты:
  - `34e8968 docs: strengthen stage2 context routing`;
  - `a904e3c docs: add selected stage2 story proof prep`.

`docs/out/` классифицирован как delivery buffer из предыдущей задачи, не как
часть этого audit.

## 3. Что реально существует сейчас

Context routing layer существует и состоит из:

- `docs/stage2/CONTEXT_INDEX.md` as главный route index;
- `docs/stage2/CONTEXT_USAGE_RULES.md` as правила использования документации;
- links from `docs/stage2/README.md`, root `README.md`,
  `IMPLEMENTATION_GATES.md`, `ENGINEERING_BACKLOG.md`,
  `ROADMAP.md` and `STAGE2_UNBLOCKED_WORK_PLAN.md`;
- selected-story package:
  - selected stories;
  - synthetic data requirements;
  - proof plans;
  - proof-prep report;
  - synthetic test data index;
  - acceptance matrix;
  - implementation gates.

Проверка ссылок по обязательным документам:

```text
required_docs_relative_link_missing_count=0
```

## 4. Есть ли полноценный context routing layer

Да, layer в целом полноценный.

Подтверждено:

- есть точка входа: Stage 2 README говорит начинать с `CONTEXT_INDEX.md`;
- root README ссылается на Stage 2 context index and context usage rules;
- `CONTEXT_INDEX.md` содержит `How to use this index`;
- `CONTEXT_INDEX.md` содержит domain routes and task shortcuts;
- есть route для selected stories / synthetic data / proof prep;
- есть route for synthetic data creation через task shortcuts;
- есть route for proof execution / runtime checks;
- есть routes for Web Search, OCR / VL OCR, usage analytics, customer-facing
  proposals, implementation planning, data policy and provider/model catalog;
- есть explicit blockers/gates for selected story and runtime routes.

Ограничение: provider setup как отдельный route не вынесен отдельным заголовком.
Он покрыт через `Provider catalog / models`, `Data policy / provider data
classes` and task-shortcut row, но будущему агенту было бы проще, если бы был
явный route "Provider setup".

## 5. Source-of-truth hierarchy

Hierarchy присутствует в двух местах:

- [CONTEXT_INDEX.md](../../stage2/CONTEXT_INDEX.md)
- [CONTEXT_USAGE_RULES.md](../../stage2/CONTEXT_USAGE_RULES.md)

Понятно зафиксировано:

- PRD-1 - главный продуктовый источник;
- Stage 2 README / CONTEXT_INDEX - navigation and context routing;
- ROADMAP - порядок движения;
- IMPLEMENTATION_GATES - условия перехода к implementation/runtime work;
- CONTRACT_BOUNDARIES - backend/frontend/custom logic/provider calls;
- ENGINEERING_BACKLOG - planning/status backlog;
- ADRs - decisions only if approved;
- proposed ADR is not final decision;
- reports are evidence, not implementation plans;
- research is context, not implementation command;
- proposals are customer-facing docs, not engineering backlog;
- selected stories are planning artifacts;
- synthetic data docs are mechanics-only;
- proof plans are plans, not executed proof.

Оценка: hierarchy адекватная. Риск drift есть, потому что hierarchy
продублирована в `CONTEXT_INDEX.md` and `CONTEXT_USAGE_RULES.md`.

## 6. Document type rules

Document type rules есть явно:

- research не является решением;
- report не является планом реализации;
- proposal не является backlog;
- draft/proposed ADR не является approved decision;
- synthetic data не доказывает качество на реальных данных;
- docs-only document не разрешает runtime changes;
- customer-facing document не должен использоваться как engineering source без
  связанного internal doc;
- proof plan не означает, что proof выполнен.

Дополнительные подтверждения:

- customer proposals have status headers saying they are not final technical
  specification;
- research file says it is research base and not product scope;
- proof prep report says runtime proof was not executed and config was not
  changed;
- proof plans repeat `Runtime changes needed: none`.

Оценка: strong.

## 7. Guardrails

Guardrails есть и видны в `CONTEXT_INDEX.md` and `CONTEXT_USAGE_RULES.md`:

- не использовать customer data без separate approval;
- не запускать runtime proof or smoke;
- не читать `.env`, secrets, tokens, credentials or private URLs;
- не подключать provider accounts;
- не создавать users/groups/models/prompts/Knowledge;
- не менять OpenWebUI config;
- не писать production code;
- не считать synthetic proof production acceptance;
- не считать proposed ADR approved;
- не считать customer proposal implementation task.

Дополнительно по доменам:

- Web Search route says not to use private/customer queries or rollout
  globally.
- Web Search section states production rollout and full provider comparison are
  pending.
- Selected proof plan for Web Search fails if it treats rollout as approved.
- OCR / VL OCR route says not to promise production OCR quality.
- Synthetic requirements say synthetic data does not prove production OCR
  quality.

Gap: Web Search smoke and OCR synthetic benchmark guardrails are present, but
not duplicated in the global guardrail list. They are discoverable, but could
be missed by an agent that reads only the top guardrails and not the domain
route.

## 8. Route для selected stories / synthetic data / proof prep

Route exists in both:

- [CONTEXT_INDEX.md](../../stage2/CONTEXT_INDEX.md)
- [CONTEXT_USAGE_RULES.md](../../stage2/CONTEXT_USAGE_RULES.md)

Required order is present:

1. `STAGE2_SELECTED_USER_STORIES.md`
2. `STAGE2_SELECTED_STORIES_SYNTHETIC_DATA_REQUIREMENTS.md`
3. `STAGE2_SELECTED_STORIES_PROOF_PLANS.md`
4. `OPENWEBUI_STAGE2_SELECTED_STORIES_PROOF_PREP.report.md`
5. `SYNTHETIC_TEST_DATA_INDEX.md`
6. `ACCEPTANCE_MATRIX.md`
7. `IMPLEMENTATION_GATES.md`

Boundary is clear:

- synthetic files are not created yet unless a later task explicitly says so;
- proof plans are not executed unless a later task approves runtime proof;
- runtime proof requires a separate approved task;
- customer acceptance remains blocked for real documents, real groups,
  provider/data policy, expected outputs and customer decisions.

Stage 2 README links the selected docs in the document map. It does not repeat
the full ordered route, but points to `CONTEXT_INDEX.md` and
`CONTEXT_USAGE_RULES.md`, where the ordered route lives.

Оценка: strong.

## 9. Оценка удобности

Scale:

```text
5 — будущий агент быстро и безопасно доберёт нужный контекст;
4 — в целом удобно, но есть мелкие gaps;
3 — работает, но агенту легко ошибиться;
2 — навигация неполная, нужен ручной контекст от владельца;
1 — контекстный домен фактически не самонаводящийся.
```

| Критерий | Оценка | Обоснование |
| -------- | ------ | ----------- |
| Вход в Stage 2 docs | 4 | Root README and Stage 2 README lead to context index/rules. |
| Поиск документов по задаче | 4 | Task shortcuts and domain routes cover main cases; `CONTEXT_INDEX.md` is long. |
| Понятность статусов | 4 | Status exists across core docs; some statuses still scattered between reports/backlog/gates. |
| Понятность blockers | 4 | Gates/backlog/selected routes expose blockers; customer-blocked state is visible. |
| Internal vs customer-facing docs | 4 | Proposals are marked not technical specs; routing says proposal is not backlog. |
| Research vs decisions | 5 | Explicit hierarchy and document type rules cover this well. |
| Proof plans vs executed proof | 5 | Proof plans and selected report clearly say proof not executed. |
| Safety for future agent | 4 | Strong guardrails; Web Search/OCR guardrails should be duplicated globally. |
| Route completeness by key domains | 4 | Main domains covered; provider setup could use explicit route heading. |

Overall convenience score: **4 / 5**.

## 10. Оценка адекватности

Verdict: **mostly adequate**.

Почему:

- navigation соответствует реальной структуре проекта;
- blockers are not hidden: customer data, provider/data policy, Web Search
  rollout, OCR real samples, runtime proof and gates remain visible;
- docs-only routes do not authorize runtime changes;
- customer-facing and engineering docs are separated by rules;
- synthetic data and proof plans are explicitly not acceptance/evidence;
- selected stories route gives a practical next-task path.

Почему не `adequate` без оговорок:

- `CONTEXT_INDEX.md` стал большим and dense; future agent can still scan too
  much unless it uses task shortcuts;
- some high-risk domain guardrails live in domain rows/routes, not in the global
  guardrail list;
- hierarchy duplicated in two files can drift later;
- provider setup is split across provider catalog and data policy rather than
  one route heading.

## 11. Gaps and risks

### Missing links

No broken relative links found in required docs.

Potential missing discoverability:

- explicit `Provider setup` route heading in `CONTEXT_INDEX.md`;
- short `Selected stories route` pointer in Stage 2 README near the selected
  docs table.

### Outdated statuses

No clear stale status found in the audited set. The old `Source status` in
`CONTEXT_INDEX.md` was already corrected in the prior context-routing commit:
it now lists current routing entrypoints and says no separate `docs/README.md`
is expected.

### Ambiguous wording

- `CONTEXT_INDEX.md` mixes English route labels and Russian explanations. It is
  understandable, but not visually uniform.
- `docs-only`, `runtime proof`, `approval` and `customer acceptance` are
  repeated in many places. This is safer than under-documenting, but increases
  scan load.

### Risky routes

- Web Search: route is safe, but smoke/proven connectivity can still be
  misread as rollout readiness if the agent skips route comments and gates.
- OCR / VL OCR: route is safe, but synthetic benchmark can still be overread as
  quality proof if an agent ignores selected requirements and acceptance matrix.
- Provider setup: covered by data policy and provider catalog, but should be
  one explicit route because provider accounts/keys are a high-risk boundary.

### Docs needing stronger status header

- `CONTEXT_INDEX.md` could state at top: "navigation only, not source of
  implementation permission." It implies this through rules, but not in a
  status line.
- Customer-facing proposal headers are acceptable, but could explicitly add
  "not engineering backlog" to match routing rules.

### Docs that can be confused with implementation permission

- `ENGINEERING_BACKLOG.md` can be overread as permission to execute because it
  has "Ready for runtime proof" sections. It now links context rules and says
  backlog status does not override gates, which is enough for now.
- `IMPLEMENTATION_GATES.md` is clear that unblocked planning does not authorize
  runtime changes.

### Docs that should be added to routes

- `WEB_SEARCH_CONTEXT_INDEX.md` is already in Web Search route.
- `WEB_SEARCH_CANDIDATE_SET_COMPARISON_PLAN.md` is already in Web Search
  additional context.
- Provider setup would benefit from explicitly grouping provider catalog, data
  policy, provider accounts/access and secrets policy in one route.

## 12. Рекомендованные исправления

Recommended next fixes:

1. Add explicit `Provider setup / provider accounts` route to
   `CONTEXT_INDEX.md`.
2. Add two global guardrails:
   - Web Search smoke/proven connectivity does not approve rollout;
   - OCR/VL OCR synthetic benchmark does not prove production OCR readiness.
3. Add a one-line status under `CONTEXT_INDEX.md` title: navigation only, not
   implementation permission.
4. Add a short "Selected stories route lives in CONTEXT_INDEX / rules" note in
   Stage 2 README near the selected docs table.
5. Consider a compact table of contents at the top of `CONTEXT_INDEX.md` if the
   file grows further.

These are small docs-only fixes. They were not applied in this audit because
the requested primary deliverable is an honest report, not silent correction.

## 13. Что не делалось

- Runtime proof не запускался.
- `.env`, secrets, tokens, private URLs, credentials не читались.
- Customer data не использовались.
- Users/groups/models/prompts/Knowledge не создавались.
- OpenWebUI config не менялся.
- Production code не писался.
- Existing `docs/out/` delivery buffer не изменялся и не включался в staging.
- Навигационные правки не вносились молча.

## 14. Итоговый вердикт

Stage 2 context routing is **mostly adequate** and materially stronger than a
plain link index.

Future agent can now:

- start from `CONTEXT_INDEX.md`;
- use `CONTEXT_USAGE_RULES.md` to classify document types;
- find selected stories / synthetic data / proof prep route;
- distinguish research, report, proposal, backlog, gate, ADR and proof plan;
- see customer-blocked and runtime-gated boundaries before acting.

Main remaining risk: the routing layer is comprehensive but long. A future
agent that scans only one route row and skips gates/rules can still miss a
high-risk domain caveat. The best next fix is to add a small explicit
`Provider setup / provider accounts` route and duplicate Web Search/OCR
high-risk caveats in global guardrails.
