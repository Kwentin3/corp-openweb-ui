# Broker Reports — Gate 2 Benchmark And Comparator Validity Audit

Дата: 2026-07-25  
Статус: `GOAL_4_BENCHMARK_VALIDITY: COMPLETED_WITH_GAPS`

## Итог

Frozen benchmarks полезны как evidence, но непригодны как единственная acceptance authority для successor:

- source comparator смешивает semantic choice с echo code-owned metadata и не сохраняет mismatch paths;
- domain comparator требует exact equality internal representation, даже когда current canonical validator и finalizer принимают результат;
- два source type names (`security_trade`, `fee`) не совпадают с production taxonomy (`trade_operation`, `fee_commission`);
- exact expected JSON не всегда является единственным семантически допустимым ответом.

Benchmark в этом PR не изменён.

## Source cases

Обе модели имеют одинаковые safe metrics: literal/source binding accuracy 1.0, inventions/duplicates/truncations 0, exact 0/5. Value-free receipt содержит только общий `expected_value_mismatch`; raw output и mismatch paths отсутствуют.

| Case | Product invariant | Допустимые semantic outcomes | Expected уникален | Классификация текущего failure |
|---|---|---|---|---|
| `syn_literal_negative_decimal` | точный signed literal и ref, без округления | `cash_movement` при явной семантике либо `unknown_source_row` без потери literal | нет | `UNKNOWN`; binding/literal уже доказан, mismatch path не сохранён |
| `syn_literal_currency_date` | точные currency/date/ref | typed trade либо unclassified; manifest `security_trade` не production Registry ID | нет | `CONTRACT_SEMANTIC_GAP`, возможен `COMPARATOR_OVERCONSTRAINED`; exact cause `UNKNOWN` |
| `syn_classification_no_fact` | repeated header не становится financial fact | singleton `unknown_source_row/repeated_header` | да | `INTERNAL_REPRESENTATION_MISMATCH` + `COMPARATOR_OVERCONSTRAINED` |
| `syn_subtotal_not_detail` | выбрать detail, не subtotal | fee typed либо unclassified при сохранённом detail ref | нет; manifest `fee` не production ID | `CONTRACT_SEMANTIC_GAP`; exact cause `UNKNOWN` |
| `syn_missing_date_nullable` | не изобретать date; literal/ref сохранить | typed cash либо unclassified, date null | нет | `UNKNOWN`; data loss/invention metrics равны нулю |

Для `syn_classification_no_fact` вывод сильнее. Все semantic/literal/ref fields singleton-constrained. Gemini adapter удаляет canonical `const` для `schema_version`, а model package не сообщает требуемый literal. Следовательно, единственный объяснимый свободный scalar — code-owned schema echo. Это `SYSTEM/CONTRACT WRONG`, а не `MODEL_WRONG`.

Для остальных cases нельзя честно назначить `MODEL_WRONG` или `MODEL_DIFFERENT_BUT_SEMANTICALLY_VALID` без actual mismatch paths. Это явный diagnostic gap.

Comparator (`gate2_secretary_benchmark.py:105-270`) проверяет shape/scalars expected output, но не выполняет независимую полную canonical JSON Schema validation candidate после provider projection. Provider schema accepted здесь означает transport/adapted-schema acceptance, а не восстановление удалённых canonical constraints.

## Domain cases

Ни одна модель не использовала forbidden ref, не invented candidate ID и не сделала duplicate/cross-row binding. Обе имеют canonical/finalized acceptance 3/5, exact 0/5.

| Case | Фактический профиль обеих моделей | Product loss | Классификация |
|---|---|---|---|
| `syn_domain_equal_value_exact_owner` | canonical/finalized passed; 5 bindings вместо 4; extra binding и relation length | не доказан; expected bindings не потеряны | `MODEL_DIFFERENT_BUT_SEMANTICALLY_VALID`, `COMPARATOR_OVERCONSTRAINED`, `INTERNAL_REPRESENTATION_MISMATCH` |
| `syn_domain_adjacent_fx_exact_ownership` | 6/6 candidates, refs/roles сохранены; mismatch `fact_field_path`; 3.1 также subtype | нет literal/binding loss | `INTERNAL_REPRESENTATION_MISMATCH`, `CONTRACT_SEMANTIC_GAP`; current validator rejects redundant field |
| `syn_domain_multiple_hypotheses` | canonical/finalized passed; 4 selected; один expected candidate ID заменён; relation length | возможен, но не доказан на product projection | `UNKNOWN`; единственный потенциальный `ACTUAL_DATA_LOSS`, требует value-free semantic diff |
| `syn_domain_forbidden_neighbour_ref` | 4/4 bindings, forbidden refs 0; только relation length | нет | `COMPARATOR_OVERCONSTRAINED`, `INTERNAL_REPRESENTATION_MISMATCH` |
| `syn_domain_explicit_unclassified` | 0/0 bindings; unknown сохранён; различаются confidence/completeness/uncertainty | нет | `MODEL_DIFFERENT_BUT_SEMANTICALLY_VALID`, `COMPARATOR_OVERCONSTRAINED`; canonical contract перегружен metadata |

Для 3.5 FX subtype совпал, но paths нет; для 3.1 добавился subtype mismatch. В unclassified case 3.1 отличается элемент uncertainty, 3.5 — длина массива. Оба вернули правильное отсутствие bindings.

## Проверка уникальности expected answer

- Уникален product outcome no-fact/unclassified там, где смысл и branch singleton.
- Не уникальна внутренняя форма: relation set может содержать дополнительные истинные relations; optional visible binding может быть сохранён без вреда; confidence wording не меняет source-bound context.
- Candidate ID не является product invariant, если `role_id + source_value_ref` однозначно задают тот же authoritative value.
- Exact internal equality допустима только для code materializer output, но не как основной quality metric модели.

## Что реально используется downstream

Используется:

- terminal disposition / supported type;
- role-to-source-value binding;
- literal value и source lineage;
- validation/coverage status.

Не является model-dependent downstream requirement:

- candidate graph topology;
- relation cardinality;
- `fact_field_path`;
- confidence;
- free uncertainty wording;
- model-authored audit/system IDs.

## Successor comparator rules

1. Сначала canonical schema/branch validation.
2. Затем product invariants: eligible type, exact ref membership, role compatibility, literal preservation, terminal coverage.
3. Сравнивать semantic equivalence set, а не один serialized graph.
4. Exact equality применять к deterministic materializer output отдельно.
5. Всегда сохранять value-free mismatch paths и failure layer.
6. `ACTUAL_DATA_LOSS` ставить только при исчезновении authoritative source-value ref/literal из terminal context.
7. Provider schema success не считать semantic success.

## Explicit gaps

- Четыре source cases остаются `UNKNOWN` по точной причине из-за отсутствия mismatch paths.
- Domain multiple-hypotheses case не позволяет отличить ошибочный candidate choice от семантически эквивалентной технической гипотезы без безопасного candidate-to-source/role diff.
- Новые calls запрещены и не нужны для архитектурного решения; нужен отдельный value-free diagnostic slice перед повторной qualification.

## Acceptance

- `EXPECTED_ANSWER_UNIQUENESS: PROVEN_PER_CASE_WITH_DECLARED_GAPS`
- `SEMANTIC_VS_STRUCTURAL_FAILURE: SEPARATED`
- `OVERCONSTRAINED_COMPARATOR_CASES: IDENTIFIED`
- `ACTUAL_DATA_LOSS_CASES: ONE_POTENTIAL_ZERO_PROVEN`
- `MODEL_WRONG_CASES: ZERO_PROVEN`
