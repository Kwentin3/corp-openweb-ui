# Stage 2 Selected Stories Proof Plans

Дата: 2026-06-25

Статус: docs-only proof plans for first selected Stage 2 user stories. Proofs
are not executed in this task.

`Proof plan` - план проверки, что механизм работает. `Synthetic input` -
искусственный вход без данных заказчика. `Pass signal` - признак успешной
проверки. `Fail signal` - признак провала проверки. `VL OCR` - распознавание
документа через зрительно-языковую модель. `Runtime` - работающий стенд или
приложение. `Docs-only` - только документация, без запуска стенда и без
настройки OpenWebUI.

## Общие границы

- Не запускать runtime proof in this task.
- Не создавать users, groups, models, prompts, Knowledge or synthetic files in
  this task.
- Не менять OpenWebUI config.
- Не использовать customer data, credentials, private URLs or real provider
  accounts.
- Каждый будущий runtime proof requires separate approval.
- `Runtime changes needed` is `none` for every docs-only plan below.

## ST2-US-001

```text
Story ID: ST2-US-001
Proof goal: Проверить, что synthetic working text можно превратить в краткое summary with key points and review reminder.
Preconditions: Synthetic working text exists; approved prompt/template draft exists; runtime execution has separate approval if needed later.
Synthetic input: Markdown/TXT synthetic working text from selected requirements.
Steps:
1. Feed synthetic working text into the summary prompt.
2. Ask for short summary, key points and optional draft reply note.
3. Check that output does not invent unsupported facts.
4. Check that manual-review reminder is visible.
Expected result: Structured summary with key points and review reminder.
Pass signal: Output contains summary, key points and no customer/sensitive data claim.
Fail signal: Output invents facts, omits review warning or asks for real customer data.
What this proof does not prove: Quality on real customer documents, final prompt style or final data policy.
Customer decisions required later: Allowed working-text classes, real groups, scenario owners and approved data policy.
Runtime changes needed: none
Status: plan prepared; proof not executed.
```

## ST2-US-002

```text
Story ID: ST2-US-002
Proof goal: Проверить, что scenario warning clearly separates allowed, forbidden and safe-rewrite examples.
Preconditions: Synthetic allowed/forbidden examples exist; warning text draft exists; runtime execution has separate approval if needed later.
Synthetic input: Markdown/CSV examples from selected requirements.
Steps:
1. Review each example against draft allowed/prohibited categories.
2. Produce a short warning and a safe rewrite suggestion.
3. Confirm warning does not promise automatic masking, DLP or guaranteed protection.
4. Confirm forbidden examples remain synthetic and redacted.
Expected result: Clear warning plus examples that guide user behavior without overpromising controls.
Pass signal: Warning is short, understandable and explicitly says what not to enter.
Fail signal: Warning is vague, allows sensitive data, promises automatic masking or contains real-looking secrets.
What this proof does not prove: Final policy approval, runtime blocking, provider compliance or DLP.
Customer decisions required later: Final allowed/prohibited data classes, provider classes and owner-approved warning wording.
Runtime changes needed: none
Status: plan prepared; proof not executed.
```

## ST2-US-003

```text
Story ID: ST2-US-003
Proof goal: Проверить post-transcription workflow: fake transcript -> summary, decisions, action items and open questions.
Preconditions: Fake meeting transcript exists; output template exists; runtime execution has separate approval if needed later.
Synthetic input: Markdown/TXT fake meeting transcript from selected requirements.
Steps:
1. Feed fake transcript into the meeting-summary prompt.
2. Ask for summary, decisions, action items and open questions.
3. Check that every action item has owner, due date if present, and source phrase or confidence note.
4. Check that output includes manual-review warning.
Expected result: Structured meeting protocol draft from transcript.
Pass signal: Output separates summary, decisions, action items and unresolved questions without adding unsupported commitments.
Fail signal: Output invents decisions, misses tasks present in transcript or treats AI protocol as source of truth.
What this proof does not prove: STT quality, audio/video upload, consent, retention, transcript permissions or real meeting quality.
Customer decisions required later: Real media samples, consent policy, retention policy, access rules and accepted transcript workflow.
Runtime changes needed: none
Status: plan prepared; proof not executed.
```

## ST2-US-009

```text
Story ID: ST2-US-009
Proof goal: Проверить safe public Web Search plan shape: query -> candidate sources -> answer draft with source visibility.
Preconditions: Safe public query matrix exists; source-attribution rules are linked; runtime execution has separate approval if needed later.
Synthetic input: Safe public RU/EN query set from selected requirements.
Steps:
1. Select a public query with no customer/internal context.
2. Define expected candidate-source list fields.
3. Define answer draft shape with source links and uncertainty/no-results handling.
4. Check that the plan separates candidate discovery from final answer.
Expected result: Future proof can run a safe public query without changing rollout policy.
Pass signal: Query matrix contains public-only queries and output shape shows sources, uncertainty and no-results behavior.
Fail signal: Query contains private/internal context, assumes source safety, or treats Web Search rollout as approved.
What this proof does not prove: Production rollout, source trust, provider privacy, logging safety or cost policy.
Customer decisions required later: Rollout scope, allowed query classes, logs, cost policy, group defaults and provider stance.
Runtime changes needed: none
Status: plan prepared; proof not executed.
```

## ST2-US-011

```text
Story ID: ST2-US-011
Proof goal: Проверить минимальную форму usage analytics report: user, day/week, model, messages, tokens and approximate cost.
Preconditions: Synthetic usage rows exist; model/price catalog draft exists; runtime execution has separate approval if needed later.
Synthetic input: CSV/Markdown synthetic usage rows from selected requirements.
Steps:
1. Aggregate synthetic rows by user, day, week and model.
2. Calculate message and token totals.
3. Apply approximate cost formula from draft price catalog.
4. Mark limitations: not billing, not invoice parity, no hard budgets.
Expected result: Report shape that admin can review before runtime/native analytics proof.
Pass signal: Report includes user/day/week/model/messages/tokens/approx cost and explicit analytics-vs-billing limitation.
Fail signal: Report promises hard billing, hides token basis, uses real usage rows or omits privacy limitation.
What this proof does not prove: Native analytics sufficiency, provider invoice parity, hard budgets, group filters or manager visibility policy.
Customer decisions required later: Reporting granularity, visibility rules, accepted price catalog and hard billing/gateway decision.
Runtime changes needed: none
Status: plan prepared; proof not executed.
```

## ST2-US-013

```text
Story ID: ST2-US-013
Status: paused pending OCR / VL OCR infrastructure epic.
Proof goal: Подготовить OCR/VL OCR candidate shortlist and benchmark criteria for synthetic documents only.
Preconditions: Synthetic scan/table/document requirements exist; candidate classes are listed; runtime/provider execution has separate approval if needed later.
Synthetic input: Fake scan description, fake invoice/act description and fake table-like PDF description.
Steps:
1. List candidate classes: native extraction, open-source parser/OCR, cloud OCR/document AI and VL OCR.
2. Define benchmark fields: text extraction, table structure, uncertainty, latency, cost, privacy fit and failure reporting.
3. Define expected output table for candidate comparison.
4. Mark real customer pilot as blocked by samples and provider/data policy.
Expected result: Candidate-selection plan without running OCR or sending files to providers.
Pass signal: Shortlist criteria are explicit and synthetic-only boundary is visible.
Fail signal: Plan claims production OCR quality, uses real documents or sends data to an external provider.
What this proof does not prove: Quality on real scans, broker reports, tables, stamps, handwriting or customer document classes.
Customer decisions required later: Real samples, expected output, allowed provider class, data policy and pilot owner.
Runtime changes needed: none
Do not execute as proof until provider shortlist, contracts and benchmark plan are ready.
```

## Links

- [Stage 2 Selected User Stories](STAGE2_SELECTED_USER_STORIES.md)
- [Stage 2 Selected Stories Synthetic Data Requirements](../testdata/STAGE2_SELECTED_STORIES_SYNTHETIC_DATA_REQUIREMENTS.md)
- [Stage 2 Scenario Shortlist](STAGE2_SCENARIO_SHORTLIST.md)
- [Workspace Scenario User Stories](WORKSPACE_SCENARIO_USER_STORIES.md)
- [Acceptance Matrix](../acceptance/ACCEPTANCE_MATRIX.md)
