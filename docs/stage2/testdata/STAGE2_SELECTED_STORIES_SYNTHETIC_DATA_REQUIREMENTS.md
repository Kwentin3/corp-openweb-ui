# Stage 2 Selected Stories Synthetic Data Requirements

Дата: 2026-06-25

Статус: требования к искусственным тестовым данным для первого Stage 2
execution-пакета. Файлы synthetic data в этой задаче не создаются.

`Synthetic data` - искусственные тестовые данные без данных заказчика.
`Expected output shape` - ожидаемая форма результата, а не гарантия качества.
`VL OCR` - распознавание документа через зрительно-языковую модель.

## Общие правила

- Не использовать customer data, реальные имена, emails, телефоны, реквизиты,
  private URLs, credentials, tokens or secrets.
- Каждый будущий файл или строка данных должны содержать явный marker
  `SYNTHETIC TEST DATA`.
- Synthetic data доказывает только механику, форму результата и понятность
  ограничений.
- Synthetic data не доказывает качество на реальных документах, legal/tax
  correctness, production OCR quality, provider safety or final data policy.

## ST2-US-001

```text
Story ID: ST2-US-001
Story name: Краткое резюме рабочего текста
Synthetic data needed: synthetic working text with 5-8 short paragraphs about a fictional internal project.
Format: Markdown or TXT.
Purpose: Проверить форму краткого summary, key points and human-review warning.
What it proves: Prompt can produce structured summary on safe synthetic text.
What it does not prove: Quality on real customer documents, sensitive-data handling or final tone policy.
Required markers: SYNTHETIC TEST DATA; fictional company/project names; no real people, private URLs or financial details.
Expected output shape: 3-5 sentence summary, 3-7 key points, optional draft reply note, manual-review reminder.
Safety rules: Text must not include secrets, customer names, personal data, contracts, invoices or credentials.
Status: requirements only; file not created.
```

## ST2-US-002

```text
Story ID: ST2-US-002
Story name: Предупреждение о чувствительных данных
Synthetic data needed: allowed examples and forbidden/sensitive synthetic examples.
Format: Markdown or CSV table with columns: category, example, expected handling, safe rewrite.
Purpose: Подготовить warning text, forbidden categories and safe rewrite examples.
What it proves: Scenario can explain data boundaries and avoid promising automatic masking.
What it does not prove: Final customer data policy, DLP, runtime blocking or provider compliance.
Required markers: SYNTHETIC TEST DATA; examples must be obviously fake and redacted.
Expected output shape: Short warning, allowed/prohibited examples, safe rewrite suggestion, explicit "no automatic masking" note.
Safety rules: Use fake tokens like `sk-SYNTHETIC-DO-NOT-USE`, fake domains like `example.invalid`, fake IDs and fake names only.
Status: requirements only; examples not created.
```

## ST2-US-003

```text
Story ID: ST2-US-003
Story name: Резюме встречи и action items
Synthetic data needed: fake meeting transcript with synthetic speakers, decisions, open questions and tasks.
Format: Markdown or TXT transcript.
Purpose: Проверить post-transcription workflow after STT: summary, decisions, action items and unresolved questions.
What it proves: Prompt/output shape for transcript processing without running STT.
What it does not prove: STT quality, audio/video handling, consent, retention or transcript access policy.
Required markers: SYNTHETIC TEST DATA; fictional speakers; timestamps optional; explicit fake meeting title.
Expected output shape: Meeting summary, decisions table, action items with owner/date/status, open questions and manual-review warning.
Safety rules: No real meeting notes, no customer names, no personal data and no actual business commitments.
Status: requirements only; transcript not created.
```

## ST2-US-009

```text
Story ID: ST2-US-009
Story name: Публичное исследование с источниками
Synthetic data needed: safe public Web Search query set.
Format: Markdown or CSV table with columns: query, language, freshness need, source expectation, risk note.
Purpose: Подготовить safe public query matrix for future proof.
What it proves: Query wording, candidate source list shape and answer/source separation can be planned safely.
What it does not prove: Web Search production rollout, source safety, provider privacy or customer policy.
Required markers: SYNTHETIC TEST DATA; public-only topic; no customer/internal context.
Expected output shape: Candidate sources, answer draft, links, uncertainty/no-results behavior and source-attribution note.
Safety rules: Queries must be public, generic and non-sensitive; no private company names, internal URLs, customer facts or secrets.
Status: requirements only; query list not created.
```

## ST2-US-011

```text
Story ID: ST2-US-011
Story name: Отчет по использованию AI
Synthetic data needed: analytics sample prompts and synthetic usage rows.
Format: CSV or Markdown table with columns: user_id, date, week, model, messages, input_tokens, output_tokens, approx_cost, scenario.
Purpose: Проверить report shape for user/day/week/model/messages/tokens/approx cost.
What it proves: Minimum report fields and analytics-vs-billing boundary.
What it does not prove: Provider invoice parity, hard budgets, cost enforcement, group-filter behavior or privacy approval.
Required markers: SYNTHETIC TEST DATA; fake users like `stage2-user-a`; fake model IDs clearly marked as examples unless from approved catalog.
Expected output shape: Daily and weekly aggregate tables, per-model totals, token totals, approximate cost and limitation note.
Safety rules: No real user IDs, real usage exports, provider invoices, API keys or private model pricing from credentials.
Status: requirements only; rows not created.
```

## ST2-US-013

```text
Story ID: ST2-US-013
Story name: OCR/VL OCR candidate shortlist
Synthetic data needed: fake scan description, fake invoice/act description and fake table-like PDF description.
Format: Markdown requirements and later PDF/image files only after separate approval.
Purpose: Подготовить candidate benchmark requirements without sending real documents to OCR/VL OCR providers.
What it proves: Candidate taxonomy, benchmark criteria and expected result shape can be defined before customer samples.
What it does not prove: OCR quality on real scans, broker reports, stamps, signatures, tables or handwriting.
Required markers: SYNTHETIC TEST DATA; generated/fake text; visible synthetic watermark if files are later created.
Expected output shape: Candidate comparison table with extracted text, table structure, confidence/uncertainty, latency, cost and privacy notes.
Safety rules: Do not use real broker reports, real scans, real invoices, personal data, customer logos or provider calls in this task.
Status: requirements only; files and benchmark not created.
```

## Links

- [Stage 2 Selected User Stories](../implementation/STAGE2_SELECTED_USER_STORIES.md)
- [Stage 2 Selected Stories Proof Plans](../implementation/STAGE2_SELECTED_STORIES_PROOF_PLANS.md)
- [Synthetic Test Data Index](SYNTHETIC_TEST_DATA_INDEX.md)
- [Acceptance Matrix](../acceptance/ACCEPTANCE_MATRIX.md)
