# Canonical table financial-role mapping R&D

> Исправление от 2026-08-28: вывод ниже о том, что гипотеза опровергнута,
> больше не считается действующим. В frozen sample только один из 12 документов
> оказался реальным отчётом клиента; остальные были инструкциями, примерами,
> отчётностью самих брокеров, регуляторными формами или factsheet. Кроме того,
> часть расхождений впервые возникала в PDFPlumber до смысловой разметки.
> Актуальный аудит: [BROKER_REPORTS_CANONICAL_TABLE_PIPELINE_AUDIT.report.md](BROKER_REPORTS_CANONICAL_TABLE_PIPELINE_AUDIT.report.md).

Дата: 2026-08-28

Статус: **гипотеза опровергнута; production integration не рекомендована**

Research head: `e21547b06b17ab059f5803aaa79b82c5c64cfcfa`

Freeze: `fbe6f10c2da64e6f7004a046e8de12bb3210d9aebe933b4b70bb2a82fd8cdfbd`

## Итог

Один table-level model call остаётся перспективной формой, но проверенный KISS-кандидат не готов к production. На untouched holdout только 4 из 6 ответов прошли технический validator, а после независимой семантической проверки только 1 из 6 таблиц получила полный исполнимый контракт без ручной или документ-специфичной коррекции.

Fail-closed часть работает: invalid, aggregate и structurally incompatible таблицы не публикуют факты; все source stores сохранили byte identity. Но strict JSON действительно маскирует семантические ошибки: валидный T-Bank contract у выбранного варианта связал три разных явных валютных контекста с одной колонкой, а часть headerless tables была формально принята с первой финансовой строкой, ошибочно объявленной structural header.

## Археология production mapper

Текущий mapper ограничивает Canonical до 256 строк на таблицу и 12 000 cells, но model-facing surface показывает только первые 24 строки и не более 64 distinct values на колонку ([ordinary_trade_semantic_mapping.py](../../../services/broker-reports-gate1-proof/broker_reports_gate1/ordinary_trade_semantic_mapping.py)). Mapper и same-evidence critic получают этот же усечённый surface; полный Canonical остаётся только у детерминированного validator/dry-run. Неизвестный документ поэтому использует два вызова, а при rejected `COMPLETE` — третий adjudication call ([ordinary_trade_mapping_runtime.py](../../../services/broker-reports-gate1-proof/broker_reports_gate1/ordinary_trade_mapping_runtime.py)).

Предыдущий exhaustive per-row эксперимент был дешевле, но семантически смешивал tax-credit и dividend rows. Поэтому новый стенд проверял другую гипотезу: один контракт колонок на всю таблицу и детерминированное применение ко всем строкам.

## Стенд и корпус

Research-only стенд находится в:

- [canonical_financial_role_mapping_research.py](../../../services/broker-reports-gate1-proof/scripts/canonical_financial_role_mapping_research.py) — surface, strict schema, validator, all-row application;
- [live_canonical_financial_role_mapping_research.py](../../../services/broker-reports-gate1-proof/scripts/live_canonical_financial_role_mapping_research.py) — inventory, freeze, development, pre-holdout selection, holdout и safe receipts;
- [test_canonical_financial_role_mapping_research.py](../../../services/broker-reports-gate1-proof/tests/test_canonical_financial_role_mapping_research.py) — local contract и owned-provider-seam regressions.

Inventory содержит 43 документа, 288 Canonical TABLE nodes и 3418 строк. В frozen sample: 6 development и 6 untouched holdout tables с разными source hashes, плюс публичный квалифицированный T-Bank control (10 tables, 58 rows; целевая trade table — 15 × 34).

Ограничение покрытия существенно: только control является чистой исполнимой ordinary-trade таблицей. В sample также есть одна повреждённая trade table и десять aggregate, balance, reference или fragmented tables. Переносимость на неизвестные исполнимые dividend/tax/cash-operation schemas этим корпусом не доказана.

Никаких broker/year/filename routes, приватных prompt exceptions или production imports нет. Canonical не менялся. Model возвращала только refs/roles/bindings; source values, nodes и facts она не создавала.

## Сравнение KISS-вариантов

Все варианты использовали один prompt v2, одну response schema, `models/gemini-3.5-flash`, один call, без semantic retry, best-of-N и manual repair.

| Development surface | Valid / 6 | Input tokens | Total tokens | Sum latency | Approx. paid-list cost |
|---|---:|---:|---:|---:|---:|
| header only + 4 leading rows | 5 | 10 463 | 20 866 | 50.141 s | $0.109322 |
| header + profiles + rare row shapes | 6 | 28 734 | 41 534 | 58.875 s | $0.158301 |
| full table | 5 | 54 692 | 67 120 | 60.718 s | $0.193890 |

`header_plus_profiles` был заморожен до просмотра holdout (`selection_sha256=a339ddbb…`): это был единственный development-вариант с 6/6 технически валидными ответами, он стоил заметно меньше full-table и одинаково сохранил 5 T-Bank observations. Поздняя независимая проверка показала, что технический критерий выбора был недостаточен: profile/full contracts схлопнули четыре явных currency columns control в одну и связали обе комиссии с trade currency. Header-only сохранил соседние commission currencies корректнее, но не смог выразить continuation table без header.

Полный experimental spend: 24 live calls, 143 015 input tokens, 189 856 total tokens, 231.719 s summed provider latency. Approximate cost `$0.636092` рассчитан по standard paid-list `$1.50/M input` и `$9/M output including thinking`; actual account billing/free-tier status стенд не видел. Тариф: [официальная Gemini API pricing page](https://ai.google.dev/gemini-api/docs/pricing).

## Corpus matrix

`V` означает strict-valid, `F` — validator fail, `S` — семантически полный исполнимый contract после независимой проверки.

| Split / case | Наблюдаемая структура | Header | Profiles outcome | First divergence | S |
|---|---|---:|---|---|---:|
| dev public control | ordinary purchases, explicit price/trade/commission currencies | 1 | V, 5 observations | false currency-role exclusions and bindings | no |
| dev 019/24 | trade date + settlement date; type/qty/price merged in one cell | 2 | V, structurally incompatible | Canonical cell granularity | yes |
| dev 005/01 | pricing/reference header only | 2 | V, non-financial/reference | none | yes |
| dev 008/03 | mark-to-market aggregate; several metrics merged per cell | 3 | V, aggregate | role detail lost in Canonical cells | partial |
| dev 008/20 | continuation of aggregate without header | none | V only by treating row 1 as header | contract cannot express headerless node | no |
| dev 037/08 | two-row balance/offsetting header | 2 | V with header 1 | second header row treated as data | no |
| holdout 014/02 | balance-sheet rows without in-node header | none | F (`header_row=0`) | schema cannot express no header | no |
| holdout 041/02 | performance series without in-node header | none | F (`header_row=0`) | schema plus wrong structural terminal | no |
| holdout 024/06 | valuation-level aggregate | 1 | V, aggregate | descriptive role omitted, terminal safe | yes |
| holdout 027/04 | regulatory balance calculation, fragmented labels/amounts | none | V as structural with header 1 | data row treated as header | no |
| holdout 040/04 | top-holdings rows fragmented across changing columns | none | V as structural with header 1 | no stable column contract | no |
| holdout 060/05 | interest-income aggregate with two header rows and damaged text | 2 | V with header 1 | second header row treated as data | no |

В двух invalid holdouts model семантически попыталась вернуть `header_row=0`; Gemini schema projection не удержал enum, но runtime validator правильно остановил результат. Это полезный контрпример неудобному вопросу про strict JSON: structured output снижает синтаксический шум, но не доказывает ни semantic correctness, ни даже соблюдение исходной canonical enum после provider projection.

All-row application было выполнено для каждого валидного contract: control дал 15/15 accounted rows и 5 observations; aggregate/structural cases получили explicit terminal и ноль фактов. У двух validator-fail tables application намеренно не запускалось. `RELEVANT_UNMAPPED=0` здесь не является доказательством полноты: terminal table kind может остановить всю таблицу до row-level financial role assembly.

## Почему гипотеза опровергнута

Первое расхождение локализовано на границе `Canonical TABLE node -> table-level contract`, а не в количестве model calls:

1. Логическая шапка может находиться в другом table node либо отсутствовать в node полностью.
2. Один Canonical cell нередко содержит несколько логических колонок, а row-to-row fragmentation меняет физическое размещение одного значения.
3. Профили distinct values и row shapes обнаруживают аномалию, но не восстанавливают утраченный column addressability.
4. Полный ввод не помог: он был дороже, всё равно дал invalid `header_row=0` и иногда заменял ясный aggregate на structural terminal.
5. Strict schema не предотвращает правдоподобный, но неправильный currency binding.

Следовательно, сложная mapper/critic/adjudication цепочка действительно частично компенсирует плохой input surface, но её нельзя безопасно заменить проверенным single-call вариантом без более раннего структурного контракта.

## Production recommendation

Не интегрировать этот кандидат и не заменять им production mapper.

Следующий разрешённый KISS-R&D slice — не ещё один prompt и не broker dictionary, а один generic deterministic table-node assembly contract перед LLM:

- сохранить физические nodes неизменными;
- дать logical table view явный `header_rows: [] | [refs...]`, включая доказуемое отсутствие header внутри node;
- разрешить continuation links только из Canonical structural evidence;
- явно представить compound/fragmented cells как structural incompatibility, не притворяясь стабильной колонкой;
- повторить тот же frozen table-level mapping на новом development/untouched holdout с несколькими неизвестными, но исполнимыми operation tables.

До такого proof текущий результат — полноценный отрицательный R&D outcome. PR #316, production, CD и OpenWebUI не изменялись.

## Safe receipts

Публичный receipt: [BROKER_REPORTS_CANONICAL_TABLE_ROLE_MAPPING_RD.receipt.safe.json](BROKER_REPORTS_CANONICAL_TABLE_ROLE_MAPPING_RD.receipt.safe.json).

Safe evidence file SHA-256:

- inventory: `9e058cf2d0b1be686d5d79f5b727e995c53e9809aa33aa5af8681a4fabe64f7f`;
- freeze: `316388411099029c0bd8f4add488e2f7efe9efdbcf7d3cab9f286a3c10e84123`;
- development: `2a9a175edd9a1aa2903230222135669e09e0b4b4958771dcc1e59628e9b18ef8`;
- holdout: `4be23f84455fb1d4db22eae9cfb8921962448e8dbf3cc950f2ed0f7da3dfd2a2`.

Private model inputs/outputs и Canonical literals остаются только во внешнем evidence root; в Git их нет.

## Verification

- Focused research, gate architecture и Gate 1/2 bundle pack: `62 passed`.
- Ruff по стенду и тесту: PASS.
- JSON parse и `git diff --check`: PASS.
- Более широкий pack: `74 passed, 5 failed`. Все пять failures относятся к уже существующему drift между architecture policy/contracts и их assertions (presentation owner, новые case facts/call sites, authority wording и projection Decimal users). Research diff не меняет ни один из затронутых production/test files относительно base `7e4192d4feb3…`; поэтому они зафиксированы отдельно как unrelated baseline, без ложного общего green claim.
