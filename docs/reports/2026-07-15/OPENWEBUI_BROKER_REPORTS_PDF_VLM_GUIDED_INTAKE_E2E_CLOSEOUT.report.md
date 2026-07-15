DOES_NOT_WORK_ON_DEVELOPMENT_CORPUS
condition_1 target=drivewealth_p07 reason=development_positive_route_mismatch
condition_1 target=drivewealth_p09 reason=development_positive_route_mismatch
condition_1 target=drivewealth_p11 reason=development_positive_route_mismatch
condition_1 target=ibkr_midyear_p03 reason=development_positive_route_mismatch
condition_6 target=corpus reason=development_minimum_correct_acceptances_not_met observed=2 expected=4
condition_7 target=corpus reason=development_required_broker_acceptance_missing broker=drivewealth
condition_9 target=drivewealth_p07 reason=development_provider_accounting_invalid
condition_9 target=drivewealth_p09 reason=development_provider_accounting_invalid
condition_9 target=drivewealth_p11 reason=development_provider_accounting_invalid
condition_9 target=ibkr_midyear_p03 reason=development_provider_accounting_invalid
condition_10 target=drivewealth_p09 reason=development_terminal_or_intake_decisions_missing

# Broker Reports PDF VLM-guided intake: E2E closeout

## Короткий вывод

Новый guided-путь технически соединён и воспроизводимо запускается одной командой на development-корпусе, но его прикладной результат недостаточен. Из требуемых минимум четырёх реальных таблиц правильно приняты две. Для DriveWealth не принята ни одна таблица. Поэтому следующий этап не открыт.

Итоговый статус: `BROKER_REPORTS_PDF_VLM_GUIDED_INTAKE_E2E_NOT_WORKING`.

## Результат development gate

В прогоне было 29 случаев: 14 положительных и 15 отрицательных. Terminal
завершён со статусом `completed`, внутренних runner failures нет; шесть
уникальных PDF нормализованы один раз, остальные 23 случая использовали
детерминированный normalization cache.

| Проверка | Фактический результат |
|---|---:|
| Очевидный текст и другие отрицательные случаи корректно пропущены | 15/15 |
| Вызовы `countTokens` / `generate` на этих 15 случаях | 0 / 0 |
| Принятые регионы на этих 15 случаях | 0 |
| Правильно принятые реальные таблицы | 2 |
| Ложно принятые таблицы | 0 |
| Правильно принятые таблицы DriveWealth | 0 |
| Требуемый минимум правильных принятий | 4 |

Два доказанных правильных принятия:

- Betterment, страница 4: candidate-crop, точная структура `21 x 2`;
- Moomoo midyear, страница 10, `Lease Summary`: page-level регион, точная структура `4 x 2`.

Это полезный, но недостаточный результат. Фильтр больше не отсекает всё подряд, а отрицательные случаи не расходуют VLM-вызовы. Однако рабочее покрытие реальных таблиц пока не прошло установленный бинарный порог.

## Где именно блокируется цепочка

Терминальные причины сохранены отдельными кодами и не исчезли в общем `internal error`:

| Цель | Точная терминальная причина |
|---|---|
| DriveWealth p7 | `pdf_vlm_region_binding_parent_atom_crossing` |
| DriveWealth p9 | `pdf_vlm_guided_candidate_intake_proposal_missing`; дополнительно созданы два target-state payload, поэтому terminal cardinality не доказана |
| DriveWealth p11 | `pdf_vlm_region_binding_parent_atom_crossing` |
| IBKR midyear p3 | `pdf_visual_topology_atom_bbox_invalid`; блокировка произошла до provider, фактические вызовы `0 / 0` |
| IBKR annual p11 | `pdf_vlm_region_binding_atom_bbox_crosses_proposed_boundary` |
| Moomoo annual p9, p10, p11 | `pdf_vlm_region_binding_region_has_no_word_atoms` |
| Moomoo midyear p6, p8 | `pdf_vlm_region_binding_region_has_no_word_atoms` |
| Moomoo annual p14 | `pdf_vlm_region_binding_region_has_no_word_atoms`, `pdf_vlm_region_binding_assembly_not_uniquely_bound`, `pdf_vlm_region_binding_candidate_ownership_invalid` |
| Moomoo midyear p7 | `pdf_vlm_region_binding_atom_bbox_crosses_proposed_boundary` |
| Moomoo midyear p10 | первый регион принят; второй заблокирован с `pdf_vlm_region_binding_region_has_no_word_atoms` |

Для DriveWealth p7, p9 и p11 внешний wrapper зафиксировал по одному вызову `countTokens` и `generate`, но persisted journal сохранил `0 / 0` и пустые token/image/model-поля. Поэтому точный provider accounting не доказан.

## Что означает блокер Moomoo

Значимая часть таблиц Moomoo находится внутри растрового изображения. VLM видит форму таблицы, но в PDF-текстовом слое для соответствующего региона нет word atoms. Binder поэтому не может доказать происхождение значений из исходных слов и координат и правильно закрывается fail-closed.

Это не означает «таблицы нет». Это означает «структура визуально предложена, но источник ячеек не доказан». OCR в эту работу намеренно не входил, поэтому обходить блокировку недоказанными данными нельзя. Решение о добавлении OCR или другого авторитетного источника atoms должно быть отдельным заданием с отдельным контрактом доказательства.

## Граница текущего этапа

- Development corpus: `FAIL`.
- Fresh unseen holdout: `NOT_RUN`.
- Live canary: `NOT_RUN`.
- Production authority: `DISABLED`.
- Semantic header projection: `NOT_RUN`, потому что физический development gate не пройден.

Остановка после development failure является ожидаемым поведением gate, а не недоделанным запуском. До fresh holdout и live canary переходить нельзя.

## Воспроизводимые доказательства

Проверенный реальным E2E runtime commit:

`5d21074c70bd14583b022b2e4bca158818613a18`

Delivery branch: `codex/vlm-guided-intake-e2e`. В запечатанном terminal
зафиксировано `worktree_clean=true` для проверенного runtime commit.
Data-bearing checkout на `main` не изменялся: его существующие 80 unrelated
dirty entries сохранены, а `HEAD` и `origin/main` остались на
`6ed92eeb3674fcb5cf877568e78723a2f2833d07`.

Поздний commit `cff0c42233179e95ebc4dd1286f67e65b6614610` меняет только UTF-8 обработку stdout дочернего процесса Windows gate wrapper. Для него выполнен unit-регрессионный тест и полный service suite; он не выдаётся за повторно проверенный реальным provider-прогоном runtime.

Проверки текущей delivery-ветки:

- полный service suite: `596 passed`, пять прежних SWIG warnings;
- focused development runner/scorer suite: `15 passed`;
- Ruff и `py_compile` для изменённых Python-файлов: passed;
- повторная сборка Gate 1 bundle дала тот же SHA-256;
- repo-wide Ruff не выдаётся за зелёный: в базовой ветке остаются 148
  несвязанных ошибок вне этого slice.

| Артефакт | SHA-256 |
|---|---|
| Локальный bundle | `f054e037ab60544657c78ab2f783e62c332a24a9f3103730b0e49fff81a6831c` |
| Development manifest | `7adf4db32b79ac2c884fb71f3fcf01098861005840fa136e7b95b08c9c9c93af` |
| Reference file | `f6a2b3338798385fed85b95442affc2169d499344bb0539bbdd58995ddf1e9d1` |
| Terminal | `7cc1b47ad68556e9ecb6615ed611e5b976e732e15338313d28914984618bb932` |
| Score file | `4809f7e68f3ec44780e2292786a8c1c6ac78bbad7e2efd744660405f4a69a14f` |
| Embedded `score_checksum` | `d6e43e644e91ecddde6ec2fc21450bcf66f9b1d519f2e1f8962e013513dca9a0` |
| Safe process evidence | `f5d3eb46dc68c002cf652167d6564e49a18454a326fef78ad42b2567770d87b5` |
| Фактический live bundle | `4c5d5005bce561e41b2ca50df58b0d958a070b694c9c163471c66b22af1fb150` |

Development runner исполнял service modules из указанного commit. Bundle был
привязан к manifest по SHA-256 и повторно собран byte-for-byte, но не выдаётся
за отдельно исполненный live Function.

Локальный и live bundle не совпадают: `parity=false`. Деплой, live mutation и canary не выполнялись.

Raw terminal, reference, crops и приватная диагностика остаются только в локальном private-каталоге доказательств. В репозиторий их содержимое не переносится.

## Сохранённые жёсткие границы

- исходный PDF, parser atoms, координаты и source refs остались единственным источником точных значений;
- VLM получал только один ограниченный crop/page image и предлагал только структуру;
- значения не исправлялись, не нормализовались и не создавались моделью;
- принятие осталось детерминированным и fail-closed, неоднозначность не скрывалась;
- скрытых retry и provider failover не было;
- human reference был доступен только отдельному scorer после terminal seal;
- whole-PDF model input, OCR, Knowledge/RAG/vector, OpenWebUI Core patch и изменение production Gate 2 authority не выполнялись.

## Следующее минимальное действие

Не расширять intake ещё одной общей эвристикой. Сначала отдельными узкими исправлениями закрыть четыре уже доказанных класса отказа: пересечение parent atoms, отсутствие proposal/единственного terminal на DriveWealth p9, рассинхрон provider accounting и pre-provider invalid atom bbox. Для растровых таблиц Moomoo отдельно принять решение об OCR/source-atom authority.

После этого повторить тот же development gate без изменения reference. Переход к fresh holdout допустим только если одновременно выполнены все бинарные условия: минимум четыре точных принятия, хотя бы одно принятие DriveWealth, ноль ложных принятий, корректный provider accounting и ровно один terminal на каждый случай.
