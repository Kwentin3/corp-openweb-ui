# Broker Reports — Gate 2 Source/Domain: фиксация доказательств и археология

Дата: 2026-07-25  
Ветка исследования: `codex/broker-reports-gate2-source-domain-secretary-contract-audit-v1`  
База исследования: `a40a51853290c868f3b070ed4827f388c4b1881f`

## Решение

Текущая система содержит не один source/domain-контракт, а три разные линии:

1. production source по умолчанию просит модель вернуть полный `broker_reports_source_facts_v0`;
2. production domain по умолчанию также просит полный legacy-объект; облегчённые `source_fact_selection_v3` и `candidate_binding_output_v0` существуют, но выключены;
3. economy qualification проверяла отдельные synthetic contracts. Поэтому её `0/5` нельзя переносить ни на production legacy path, ни на модель вообще.

Главная гипотеза подтверждена. Legacy source/domain output заставляет модель повторять системные идентификаторы, provenance, audit, coverage, внутренние paths, relation IDs и техническую оценочную метаинформацию. Это существенно шире bounded semantic matching.

## Замороженная цепочка доказательств

Все выводы ниже относятся к точным revision/contract bundle.

| Объект | Точная идентичность |
|---|---|
| Research base | `a40a51853290c868f3b070ed4827f388c4b1881f` |
| Source qualification execution | `943a496dcc33937404ee2d066cd71cf9b1b541ba`, PR 115 |
| Source manifest | canonical SHA-256 `830c78a7ae14175fde882a30ebcc1ee08c9715a230531c5cd5a73185a139ee81` |
| Source output / prompt | `broker_reports_gate2_source_economy_qualification_output_v1` / `broker_reports_gate2_source_economy_qualification_prompt_v1` |
| Source comparator | `broker_reports_gate2_secretary_benchmark_result_v1:b024c679f447e28389479555c68494992582acc5c837f70156760466355b5f58` |
| Source canonical/adapted schemas | `4d820214...d4e9` / `74f2519b...5de4` |
| Domain qualification execution | `0fe1c4b9d43ce6def9703b7bf7972556521a4571`, PR 119 |
| Domain manifest | semantic identity `edfba61488378154f7e6d37b6c532f2891a3339436d3fa107cce7ce3ba3678ca` |
| Domain output / prompt | `broker_reports_candidate_binding_output_v0` / `broker_reports_gate2_domain_economy_qualification_prompt_v1` |
| Domain comparator | `broker_reports_gate2_domain_qualification_comparator_v1:c52a2da4d26f667b5daa841b1fd219e211e387eb6b8194f1909e47d006cffaba` |
| Gemini provider route | `997bc0306756ddc127bf7d87b2a8e495af88f6fe03814414d1bf289eacdeeeba` |
| Financial-evidence reference | GPT-5.4 Nano, `QUALIFIED 4/4`, receipt SHA-256 `37ca8d73b35768f9235cbe127d4bc6694f753d0cb1cfd33e01a99a66251e5c61` |
| Checksum reference | Haiku 4.5, `QUALIFIED 3/3`, receipt SHA-256 `f0c58d8a94265745443c888337cb716ab242f7ea1ffc2161e447f3e01b47162b` |

Ключевые Git blobs на research base:

| Компонент | Git blob | SHA-256 файла |
|---|---|---|
| `gate2_source_fact_contracts.py` | `613dd24e19a0c07d6c5eb24957864e4b5b9c412b` | `6215bb39...84a1` |
| `gate2_source_fact_selection.py` | `8f731306d1018ab0b63a800e149b8952ecedc30e` | `81c2ef51...4486` |
| `gate2_source_fact_runtime.py` | `090a18496b4f238f69f7092a6f167db82ad60a44` | `7e52f324...01b5` |
| `gate2_domain_routing.py` | `45d56bd60dac35b51212f19c8b7e0ccabc4da785` | `34a54d65...c127` |
| `gate2_domain_packages.py` | `b42ff1323aee340d6465a33dc5dd6bc74f3fc8ea` | `9012fedd...6241` |
| `gate2_candidate_binding.py` | `f383185251562df3b5feaf678ed8f455c419da3a` | `aec7a2bb...e32c` |
| `gate2_candidate_binding_runtime.py` | `39e9af57b48687debed904936b849bd81ea09fff` | `8f39fead...5aee` |
| `gate2_domain_runtime.py` | `176bf0e8f08f920736454498dc985586cb7d8f4e` | `761cbc1b...f168` |
| `gate2_provider_adapters.py` | `4db8662345829b4bc0b56cc15b9c88c226517eb1` | `890c6215...cf0` |
| `gate2_financial_evidence_decision.py` | `7d14090b774c291b5d1c653006b3b29ecd2ff808` | `747d8355...b5be` |
| `gate2_financial_evidence_production_runtime.py` | `bfcf427c56d9a647cd331929b0b60f964f7b87fa` | `8a6bae36...067c` |

Подтверждающие исходники: source legacy schema — `gate2_source_fact_contracts.py:331-538`; compact source selection — `gate2_source_fact_selection.py:96-445`; deterministic router/package builder — `gate2_domain_routing.py:49-176`, `gate2_domain_packages.py:45-215`; candidate binding — `gate2_candidate_binding_runtime.py:59-201`; financial decision — `gate2_financial_evidence_decision.py:17-168,210-372`.

## Хронология

| Revision | Событие |
|---|---|
| `78cf831723e79babc5553c78c10581d9c88324cd` | исходный full source/domain runtime |
| `12e59d52e62f8b33f1de383df8f876bc677d016e` | compact source semantic selection |
| `bb094b21...`, `c3d23df2...`, `18274d32...` | enum binding, упрощение, positional coverage |
| `ba1eb134...` | domain semantic selection |
| `d14bb700...` | containment после регрессии coverage |
| `9378dd92a0bed45931d739f9d9b91761567bccba` | secretary benchmark research |
| `3e90011c6d004e3d50b38e4930b034904a77cf54` | source qualification harness |
| `7997d7c67b8bf3d0fdccf7a8348f26cbbc2fb75a` | domain qualification harness |
| `ba5fedbc...`, `4add5cdb...` | persistence и manifest identity corrections |
| `943a496d...`, `0fe1c4b9...` | terminal source/domain qualification evidence |

Изоляция revision соблюдена: source и domain результаты анализируются только с собственными manifest/output/prompt/adapter/comparator identities.

## Production source: фактический pipeline

```text
Gate 1 normalized source package
  → source runtime package binding
  → managed prompt + package-specific strict JSON schema
  → model returns full source_facts_v0
  → parser
  → canonical validator
  → persisted raw/validation/source-facts artifacts
  → stitch/context consumers
```

По умолчанию `semantic_selection_enabled=False`. Значит production модель должна вернуть:

- 14 root fields;
- каждый fact с 26 обязательными fields;
- source location, normalized/original values, typed date/amount/currency/quantity/instrument;
- issue impact, downstream restrictions, extraction audit;
- coverage, validation placeholders и system IDs.

Provider schema связывает многие значения через `const`/`enum`, однако ответственность всё равно оставлена модели: она обязана воспроизвести уже известные данные. Parser лишь принимает JSON, validator сравнивает его с package authority.

Compact `source_fact_selection_v3` значительно лучше: модель возвращает только `decision_type` и `value_bindings[{field,source_value_ref}]`; код восстанавливает legacy fact. Но production route намеренно недостижим после observed coverage regression: accepted packages снизились с 35/41 до 21/41, uncovered refs выросли с 7 до 42. Этот контракт нельзя просто включить обратно.

Его остающиеся дефекты:

- ownership привязан к позиции decision, а не к явному package-bound scope;
- `decision_type` смешивает type и no-fact reason;
- `field` привязан к legacy normalized path, а не к Registry role ID;
- нет прямого соответствия принятым четырём financial dispositions.

## Production domain: фактический pipeline

```text
Gate 1 package
  → deterministic source-unit router
  → deterministic domain package builder
  → managed domain prompt + strict schema
  → model
     ├─ default: full source_facts_v0
     └─ experimental: candidate_binding_output_v0
  → parser / candidate validator
  → deterministic finalizer
  → source-fact validator
  → stitch → persisted run/context artifacts
```

Router уже детерминированно назначает до двух candidate domains по видимым hints/headers и сохраняет unknown (`gate2_domain_routing.py:178-220`). Package builder уже знает source refs, source-value refs, fact-type allowlist, evidence refs и coverage (`gate2_domain_packages.py:63-190`).

`candidate_binding_enabled=False` по умолчанию. В experimental mode модель возвращает:

- шесть root identity/hash fields;
- `source_ref`, `fact_type`;
- на каждый binding одновременно `candidate_id`, `semantic_role`, `fact_field_path`;
- relation IDs и их cardinality;
- subtype, confidence, completeness, free-string uncertainty codes;
- ambiguity-resolution refs;
- no-fact outcome.

Candidate graph и relation graph при этом уже построены кодом. `semantic_role → fact_field_path` уже задан deterministic profile. Следовательно, модель повторяет три представления одного выбора и техническую структуру системы.

## Qualification source: отдельный контракт

Source qualification использовала `broker_reports_gate2_source_economy_qualification_output_v1`, а не production `source_facts_v0` и не `source_fact_selection_v3`.

Обе Gemini:

- provider schema acceptance 5/5;
- literal accuracy 1.0;
- source binding accuracy 1.0;
- inventions/duplicates/truncations 0;
- exact comparator 0/5 с единым `expected_value_mismatch`.

Value-free receipt не сохранил mismatch paths. Поэтому semantic cause четырёх из пяти cases доказать нельзя. В полностью singleton-constrained `syn_classification_no_fact` после Gemini projection единственным свободным scalar остаётся code-owned `schema_version`: adapter удаляет `const`, а prompt/package не сообщает нужный literal. Это прямой системный дефект benchmark contract, не доказательство слабости модели.

## Qualification domain: отдельный experimental contract

Domain qualification явно включала `candidate_binding_output_v0`, хотя production default выключен.

Обе Gemini показали одинаковый профиль:

- package valid 5/5;
- canonical selection valid 3/5;
- exact expected 0/5;
- no cross-row/forbidden/invented/duplicate bindings;
- один expected candidate mismatch.

Три cases материализовались и прошли canonical validation, но были отклонены exact comparator из-за лишнего binding или иной relation cardinality. Два отклонены за fact path/subtype или confidence/completeness/uncertainty — поля, которые target должен убрать из model authority.

## Downstream и persisted artifacts

Legacy path сохраняет package, raw output, validation, source facts, domain wrappers, stitch result, run summary и context refs. Downstream consumers читают итоговые факты/financial inputs, source bindings, provenance и coverage; они не нуждаются в model-authored candidate graph topology, confidence wording или exact relation count.

Financial-evidence production runtime уже:

- извлекает authoritative literal values из domain package (`gate2_financial_evidence_production_runtime.py:800-938`);
- строит package-bound candidates;
- передаёт модели только Registry types, role specs и source values (`:952-1005`);
- принимает четыре disposition и bindings;
- детерминированно materializes artifact (`:547-580`).

Это уже реализованный образец целевого распределения ответственности.

## Границы доказанного

Доказано:

- production, source qualification и domain qualification — разные contract bundles;
- legacy contracts перегружены системными полями;
- exact comparator отклоняет валидные materializations;
- отдельный deterministic router уже существует;
- financial-evidence decision уже выражает нужный bounded semantic choice.

Не доказано без нового model output:

- точный mismatch path в четырёх source cases;
- является ли один lost fee candidate в domain case реальной потерей product data или допустимой альтернативой.

Эти gaps не требуют provider call в данном research PR и не меняют архитектурный вывод.

## Терминальные статусы

- `GOAL_0_EVIDENCE_FREEZE: COMPLETED`
- `GOAL_1_ARCHAEOLOGY: COMPLETED`
- `EVIDENCE_CHAIN: COMPLETE`
- `CONTRACT_REVISIONS: PINNED`
- `STALE_RECEIPTS: ZERO`
- `MIXED_REVISION_CONCLUSIONS: ZERO`
- `SOURCE_PIPELINE: FULLY_MAPPED`
- `DOMAIN_PIPELINE: FULLY_MAPPED`
- `MODEL_OUTPUT_FIELDS: FULLY_INVENTORIED`
- `HIDDEN_MODEL_RESPONSIBILITIES: IDENTIFIED`
