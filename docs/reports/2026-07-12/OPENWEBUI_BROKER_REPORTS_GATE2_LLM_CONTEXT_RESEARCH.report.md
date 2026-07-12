# OpenWebUI Broker Reports Gate 2: исследование LLM-контекста

Дата: 2026-07-12

Контрольный документ: тот же шестистраничный PDF, case `customer_case_group_002_process_false_gate1_20260712145140`

Безопасность: в отчёте нет исходного текста клиента, значений, имён файлов, ключей и приватных путей.

## Итог

Причина 4,58 млн входных токенов была не в размере PDF. Основной объём создавали динамическая JSON Schema, повторяемая техническая оболочка domain package и повторная отправка одного и того же issue context.

Подтверждены `GATE2_LLM_CONTEXT_FORENSIC_RESEARCH_READY`, `GATE2_LLM_CONTEXT_COMPONENT_ACCOUNTING_PROVEN` и `GATE2_LLM_CONTEXT_DUPLICATION_DIAGNOSED`.

## Baseline

- 116 окон и 175 domain packages/provider calls;
- 4 584 773 provider-reported input tokens на 124 успешных вызовах;
- 55 принятых и 120 отклонённых packages;
- 51 Gemini HTTP 400, все в `document_summary_evidence`;
- 113 `source_fact_provenance_missing`;
- 2175 из 2489 refs не покрыты;
- один typed-owned ref.

## Состав контекста

Оценка токенов ниже получена как `compact JSON chars / 4`; provider-reported total остаётся главным фактом.

| Компонент | Символы | Оценочные токены |
|---|---:|---:|
| Dynamic strict JSON Schema | 5 274 194 | 1 318 604 |
| Policy и contract metadata | 2 939 710 | 734 979 |
| Source projection | 925 099 | 231 333 |
| Source value index | 876 485 | 219 212 |
| Candidate list | 609 881 | 152 558 |
| Candidate profile | 387 533 | 96 930 |
| Candidate relations | 200 405 | 50 157 |
| Coverage contract | 228 148 | 57 110 |
| Issue context | 127 050 | 31 850 |
| Header context | 88 812 | 22 290 |
| Document context | 55 825 | 14 025 |

Схема доминировала. Только `document_summary_evidence` создал 4 429 123 символа schema из-за повторения вариантов по каждому ref, candidate и semantic role.

## Дублирование и fan-out

- один issue ref был отправлен 175 раз: 174 повторные отправки;
- 13 source refs были отправлены двум sibling-доменам;
- шесть уникальных header contexts были отправлены 50 раз, максимум 36 повторов одного context;
- 175 source projections содержали 174 уникальные структуры;
- 62 из 175 packages относились к `document_summary_evidence`;
- любой text segment без точного business signal автоматически маршрутизировался в `document_summary_evidence`.

116 окон дали 175 calls из-за secondary-domain fan-out и ошибочного summary default. Это была архитектурная проблема applicability boundary, а не только слабость модели.

## Принятые и отклонённые packages

Форензика 175 packages: 55 accepted, 51 provider error, 36 provenance-missing packages, 4 required-role packages и 29 прочих rejected.

Главные причины:

1. `document_summary_evidence` использовал чрезмерную row/window schema и не имел корректной summary boundary.
2. Модель вызывалась, даже когда candidate inventory не мог заполнить required roles или relations.
3. LLM видел большой технический контейнер и часто выбирал неполные bindings.
4. Один полный issue register переносился во все packages.
5. Managed Prompt описывал legacy package fields, а не компактную карточку задачи.

## Граница рефакторинга

Не меняются Gate 1 normalized contracts, ArtifactStore, process=false intake, source-fact validator, candidate-bound values, issue carry-forward, deterministic stitch, provider metadata и OpenWebUI core.

Меняется только участок:

```text
normalized source unit
→ auditable domain applicability
→ domain package
→ compact LLM context v2
→ feasibility/budget guard
→ provider-compatible strict schema
→ production provider factory
```

OCR/VLM, Knowledge/RAG/vector, Gate 3, tax, declaration и XLS/XLSX не использовались.
