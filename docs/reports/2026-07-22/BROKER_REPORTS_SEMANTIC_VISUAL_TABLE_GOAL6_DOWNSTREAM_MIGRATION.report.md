# Broker Reports — Goal 6: downstream migration и legacy compatibility

Дата: 2026-07-22

Результат: `COMPLETED`

Gate 6: `PASSED`

Release/default activation: отложены до атомарного Goal 7. Source actions изменены, live stage и committed bundles не менялись.

## Вывод

Новый semantic visual-table контракт встроен в поддерживаемый контур Gate 1 → ArtifactStore → Gate 2 без переопределения старых артефактов. Модель по-прежнему возвращает только `description + rows`; системный envelope, логическая сетка, идентификаторы, provenance и Gate 2 projection строятся кодом.

Для semantic-таблиц введены отдельные origin и version. Legacy geometric proposals остаются под исходными контрактами и не проходят auto-upgrade. Принятая по Goal 5 числовая таблица может стать отдельным Gate 2 input без обязательного ручного review, но только через явный versioned boundary.

## Боль

До этой интеграции semantic VLM decision заканчивался внутри результата Gate 1. Решение и provider evidence существовали, однако production handoff не материализовал и не сохранял новый semantic envelope, а Gate 2 выбирал table projection только тогда, когда соответствующий text-layer source unit уже был признан канонической таблицей.

Для raster-таблицы это замкнутый круг: visual route нужен именно тогда, когда PDF text layer не даёт надёжной табличной структуры. Простое включение semantic projection в старый selector либо ничего бы не дало, либо создало бы опасный неявный auto-upgrade старого visual-контракта.

## Решение

1. Добавлен отдельный migration policy `broker_reports_semantic_visual_table_migration_policy_v1` и принятый профиль `broker_reports_semantic_visual_numeric_profile_v1`.
2. Gate 1 action передаёт только новые semantic decisions в единственную factory-границу. Legacy schema получает disposition `legacy_retained_under_original_contract` и не материализуется.
3. Поддержанный decision детерминированно превращается в:
   - private envelope `broker_reports_semantic_visual_table_envelope_v1`;
   - совместимый Gate 2 projection с `table_origin = semantic_vlm_transcription` и `canonical_profile_id = semantic_visual_logical_table_v1`.
4. ArtifactStore сохраняет envelope отдельно от старых receipts, seals и projections. Raw provider response и literal values остаются только в private payload; safe metadata содержит лишь идентичности, hashes, origin, provider/model и флаг отсутствия geometry claim.
5. Перед первой записью выполняется preflight: проверяются envelope hash/provenance, projection validator, document scope и уникальность envelope/projection identity. Дубли завершают операцию fail-closed до появления частичного набора записей.
6. Gate 2 получил отдельный default-off параметр `allow_standalone_semantic_visual_projections`. При `false` новый projection только хранится. При `true` он добавляется как самостоятельный package, не заменяя и не удаляя maintained full source units.
7. Gate 2 domain runtime и source action прокидывают тот же параметр. Его default остаётся `false` до Goal 7, где source, bundles, valves и live stage должны быть выпущены одной ревизией.

## Граница принятого профиля

Автоматический downstream route ограничен числовыми таблицами Goal 5:

- от 2 до 64 строк;
- не более 4 колонок;
- не более 256 символов в ячейке;
- есть хотя бы одна видимая сумма и одна текстовая метка;
- decision terminally valid, provider contract valid, merge/repair отсутствуют;
- description не сообщает `ambiguous`, `cropped`, `incomplete`, `long-form prose`, `obscured` или `unreadable`.

Этот фильтр не является новым доказательством literal fidelity. Он только ограничивает runtime route профилем, для которого Goal 5 дал qualification receipt `96820ec84e1a4bfa167ac4c85090c0295f337ac24d2694d4f6fde0c535ed2ad7` и gate identity `2860e0d181ae4a8137ec4db796b2f26070f2df32e4581f4438107410fc62adbb`. Неподдержанная prose/uncertain таблица остаётся review-required или unsupported.

## Совместимость

| Условие | Результат |
|---|---|
| Legacy artifact readability | Сохранена; старые artifact types, receipts и seals не менялись |
| New semantic origin | Явный: `semantic_vlm_transcription` |
| Ambiguous auto-migration | 0 |
| Duplicate package identities | 0; preflight fail-closed |
| Source scope loss | 0; semantic package добавляется к maintained source units |
| CSV/XML/FNS/text-layer flows | Без изменения default-поведения |
| Gate 2 package validation | Passed |
| Mandatory human review для accepted profile | Не требуется |
| Default activation | `false` до Goal 7 |

Существующий reviewed visual path, его receipt/seal authority и старые canonical projections не переопределены. Новая ветка определяется одновременно origin, semantic profile и explicit Gate 2 flag; совпадения только по общему table projection schema недостаточно.

## Проверка

- Focused semantic migration/materialization/downstream/Gate 2 readiness: `23 passed`.
- Legacy receipts/seals, table projections, CSV, XML/FNS и Gate 2 domain runtime: `81 passed`.
- Source и существующий bundled Gate 1 action: `22 passed`.
- Полный service suite: `1100 passed, 20 skipped`.
- Ruff checks Goal 6 core/action/test modules: `passed`.
- `git diff --check`: `passed`.

Интеграционный тест подтверждает обе стороны boundary на одном persisted run:

- default-off Gate 2 не создаёт semantic package;
- explicit-on Gate 2 создаёт ровно один `semantic_visual_logical_table` package;
- исходный full source package остаётся доступен;
- duplicate semantic projection отклоняется до первой ArtifactStore record.

## Предположение и следующий шаг

Предположение Goal 6 подтверждено: semantic JSON полезен не как готовая системная структура, а как компактная смысловая транскрипция, которую код безопасно достраивает и версионирует. Это снимает с модели геометрию и одновременно сохраняет объектное хранение, проверяемый provenance и совместимость с Gate 2.

Оставшийся риск — переносимость qualification за пределы восьми подтверждённых числовых actual-corpus таблиц. Поэтому long-form prose, визуальная неопределённость, неизвестные layout families и иные профили не должны автоматически попадать в Gate 2.

Следующий шаг — Goal 7: атомарно пересобрать affected bundles, согласовать versioned valves с положительным решением Goal 5, проверить repository/live parity и rollback, затем выполнить stage cleanup. До этого новая ветка считается реализованной и проверенной в repository, но не выпущенной в live runtime.
