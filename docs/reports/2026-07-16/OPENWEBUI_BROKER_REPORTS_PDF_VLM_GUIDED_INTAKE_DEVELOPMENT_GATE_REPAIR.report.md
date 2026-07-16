DOES_NOT_WORK_ON_DEVELOPMENT_CORPUS
condition=6 target=corpus reason=development_minimum_correct_acceptances_not_met expected=4 observed=1
condition=7 target=corpus broker=betterment reason=development_required_broker_acceptance_missing
condition=7 target=corpus broker=drivewealth reason=development_required_broker_acceptance_missing
condition=7 target=corpus route=candidate_crop reason=development_required_route_acceptance_missing
condition=8 target=betterment_p04 reason=development_incorrect_structure_accepted
condition=8 target=drivewealth_p09 reason=development_incorrect_structure_accepted
condition=8 target=ibkr_annual_p11 reason=development_incorrect_structure_accepted
condition=8 target=moomoo_annual_p14 reason=development_incorrect_structure_accepted

# Broker Reports PDF VLM-Guided Intake: ремонт development gate

Дата: 2026-07-16

## Решение

Механические контракты intake отремонтированы, но продукт на development-корпусе не работает. Из требуемых четырёх корректно принята одна реальная таблица; одновременно валидатор пропустил четыре неверные структуры. Поэтому нельзя объявлять готовность, запускать unseen holdout или live canary.

Единственная корректная приёмка — регион `r1` цели `moomoo_midyear_p10`, route `page_level`, структура `4 x 2`. Всего runtime принял пять регионов: один корректный и четыре ложных.

## Проверенная граница

- Ветка: `codex/vlm-guided-intake-development-gate-repair`.
- Base: `origin/main` на `aade3c989bc99201152af33a2177c7e128f29fa4`.
- Проверенный runtime commit: `b31c80fb48c1117bc00602e0dcae7e14e4563f5d`.
- Предшествующий repair commit: `9bd18dd975914a774b4faa5b8106e68d568a8976`.
- При запуске gate source worktree был чистым: `source_worktree_clean=true`.
- Воспроизводимый bundle: `services/broker-reports-gate1-proof/openwebui_actions/broker_reports_gate1_pipe_bundled.py`.
- SHA-256 bundle: `6842e7bf529b9f952e417405249bd21c1d25b66d0cb87730ffd76ceb0b9c3f8d`.
- Manifest: `local/stage2/broker_reports_pdf_vlm_guided_intake_e2e_2026-07-15/private/development.repair-b31c80f.manifest.private.json`.
- SHA-256 manifest: `7144b80af9b7ca7600f39c889a61764587c2e97a849df33276245eb1b4f74953`.
- Reference: `local/stage2/broker_reports_pdf_vlm_guided_intake_e2e_2026-07-15/private/development.repair-b31c80f.reference.private.json`.
- SHA-256 reference file: `5ea28daf72115402ae07db13721c6d28ce582f87cd8fc2b11cfc3ac97af28af3`.
- Sealed reference checksum: `54229d3222f4ada51e57f4205b03660b7d01dccf63a4ae0d8a9c5bcb374946ea`.

Проекции исходного gate не менялись:

- manifest cases: `ffc0e2a1a1d92d0e9df6ceb308e67e9951c59ad9759ebb2f48166c6312925524`;
- provider contract: `e91f72d8849dc3ab08cb42ef3ef0f8b32b1b74235dfdf78ae5c48de8697a3d26`;
- reference cases: `eec2c894cc3c7b8465f75aa65d1b6edd5a58830ef23f10904822301607656d0f`;
- acceptance `{minimum_correct_acceptances, required_brokers}`: `91f4ead4a13c1269577cb0958bc05a69ff67f476569298562c8f9015138b4a54`.

## Что отремонтировано

1. Candidate-parent bbox теперь проходит через один factory-owned binder. Он может завершить только границу уже принадлежащего source atom, сохраняет исходный и согласованный bbox, причину и forcing atoms, заново рендерит точный crop и пересчитывает ownership из source atoms.
2. После completion проверяется соседняя неприсвоенная полоса. Близкие unowned atoms блокируют цель кодом `pdf_vlm_region_binding_parent_scope_incomplete_adjacent_unowned_band`; произвольное расширение не разрешается.
3. Для proposal, binding, terminal, detection, processability и holdout введена точная cardinality. Конфликтующие payloads блокируются, а не выбираются молча.
4. Provider journal, persisted state, terminal и scorer сверяются по числу вызовов, model/package/request identity и token fields. Реальный вызов больше не может сохраниться как `0 / 0`.
5. Pre-provider geometry различает невалидный bbox, transform/normalization defect, выход за source region, package defect и малую числовую погрешность. Clamp не используется.
6. Structural-adjustment evidence пересчитывается и сверяется по union/count/geometry; подделанная или пропущенная adjustment запись блокируется.
7. Bundle-тест сравнивает AST встроенных модулей с source, поэтому stale embedded runtime теперь обнаруживается.

## До и после по ранее проблемным целям

| Цель | До: run4 | После: run5 | Итог |
|---|---|---|---|
| `betterment_p04` | `accepted_physical_structure`, единственная корректная приёмка run4 | `accepted_physical_structure`, фактически `21 x 3` вместо reference `21 x 2` | Регрессия: ложная приёмка; отдельный столбец образован знаками валюты |
| `drivewealth_p07` | `validation_blocked`: `pdf_vlm_region_binding_assembly_not_uniquely_bound`, `pdf_vlm_region_binding_candidate_ownership_invalid`, `pdf_vlm_region_binding_proposal_repair_forbidden` | `validation_blocked`; дополнительно точные `pdf_topology_assembly_internal_boundary_source_gap_not_unique` и `pdf_topology_assembly_span_atom_outside_selected_region` | Безопасно заблокировано, корректной приёмки нет |
| `drivewealth_p09` | `guided_upstream_blocked`: `pdf_visual_topology_continuation_unsupported`; scorer condition 1 route mismatch | `accepted_physical_structure`, но `4 x 3` вместо `4 x 2` | Route/cardinality исправлены, структура принята ложно |
| `drivewealth_p11` | `accepted_physical_structure`, ложная приёмка | `validation_blocked`: `pdf_vlm_region_binding_parent_scope_incomplete_adjacent_unowned_band` | Предыдущая ложная приёмка закрыта fail-closed |
| `ibkr_annual_p11` | `validation_blocked`: `pdf_vlm_region_binding_atom_bbox_crosses_proposed_boundary` | `accepted_physical_structure`, размеры `2 x 3`, как в reference, но exact cells не совпали из-за разбиения исходных glyph/word atoms | Ложная приёмка |
| `ibkr_midyear_p03` | `guided_upstream_blocked`: `coordinate_bbox_outside_owned_bbox`; ошибочные `0 / 0`, scorer condition 1 и condition 9 | Дошёл до provider `1 / 1`, затем `validation_blocked`: `pdf_vlm_region_binding_parent_scope_incomplete_adjacent_unowned_band` | Geometry route и accounting исправлены; приёмки нет |
| `moomoo_annual_p09` | `validation_blocked`: `pdf_vlm_region_binding_region_has_no_word_atoms` | Тот же точный fail-closed terminal | Embedded raster доказан; без OCR остаётся unsupported |
| `moomoo_annual_p10` | `validation_blocked`: `pdf_vlm_region_binding_region_has_no_word_atoms` | Тот же точный fail-closed terminal | Embedded raster доказан; без OCR остаётся unsupported |
| `moomoo_annual_p11` | `validation_blocked`: `pdf_vlm_region_binding_region_has_no_word_atoms` | Тот же точный fail-closed terminal | Embedded raster доказан; без OCR остаётся unsupported |
| `moomoo_annual_p14` | Оба региона `validation_blocked`: boundary crossing и `region_has_no_word_atoms` | `partially_validated`: `r1` no-word, `r2` принят как `2 x 2` | `r2` не равен двум reference-структурам `4 x 2` и `11 x 3`; ложная приёмка |
| `moomoo_midyear_p06` | `validation_blocked`: `pdf_vlm_region_binding_region_has_no_word_atoms` | Тот же точный fail-closed terminal | Embedded raster доказан; без OCR остаётся unsupported |
| `moomoo_midyear_p07` | `validation_blocked`: `pdf_vlm_region_binding_atom_bbox_crosses_proposed_boundary` | `validation_blocked`: `pdf_topology_assembly_internal_boundary_source_gap_not_unique`, `pdf_vlm_region_binding_assembly_not_uniquely_bound`, `pdf_vlm_region_binding_candidate_ownership_invalid` | Boundary accounting исправлен; unique assembly не доказан, приёмки нет |
| `moomoo_midyear_p08` | `validation_blocked`: `pdf_vlm_region_binding_region_has_no_word_atoms` | Тот же точный fail-closed terminal | Embedded raster доказан; без OCR остаётся unsupported |
| `moomoo_midyear_p10` | Оба региона `validation_blocked`: boundary crossing и `region_has_no_word_atoms` | `partially_validated`: `r1` корректный `4 x 2`, `r2` no-word | Единственная корректная приёмка run5; вторая таблица `7 x 2` не восстановлена |

На уровне scorer:

- condition 1: было `FAIL`, стало `PASS`;
- condition 9: было `FAIL`, стало `PASS`;
- condition 6: осталось `FAIL`, `1 < 4`;
- condition 7: осталось `FAIL`; теперь отсутствуют корректные Betterment, DriveWealth и `candidate_crop` acceptance;
- condition 8: ухудшилось с одной ложной приёмки (`drivewealth_p11`) до четырёх других ложных приёмок.

## Точная bbox reconciliation

Все три показательных candidate пути используют общий код `complete_routed_candidate_source_atom_boundary`; broker- или reference-specific координат в policy нет.

### `drivewealth_p09`

- original parent bbox: `[65.88, 429.06, 557.58, 480.57]`;
- reconciled parent bbox: `[65.88, 429.06, 557.58, 481.9685]`;
- adjustment: нижняя граница `480.57 -> 481.9685`, forcing atoms: 3, max adjacent gap: `10.98 pt`;
- owned atoms: 17; до completion 5 owned refs не помещались полностью;
- после reconciliation: `included=17 + excluded=0 + crossing=0 = all_parent=17`;
- adjacent unowned atoms: 0; `candidate_parent_scope_complete=true`;
- evidence checksum: `ea9f96930f93bae38e6f8f383d624d453c887a3a3e2e449b91748e5eca76d802`;
- exact re-rendered crop SHA-256: `bfe305553531b89c4149127641fbbfa0f68dbc4a60d8a8d1d31934f040d74655`.

Reconciliation корректна механически, но полученная VLM topology `4 x 3` не равна exact reference `4 x 2`; безопасный structural validator пока это не отсекает.

### `drivewealth_p11`

- original parent bbox: `[54.48, 100.2, 553.98, 125.52]`;
- reconciled parent bbox: `[54.48, 100.2, 553.98, 126.7485]`;
- adjustment: нижняя граница `125.52 -> 126.7485`, forcing atoms: 2, max adjacent gap: `10.98 pt`;
- после reconciliation: `included=14 + excluded=0 + crossing=0 = all_parent=14`;
- сразу ниже обнаружены 7 unowned atoms с gap `1.8 pt`;
- `candidate_parent_scope_complete=false`;
- evidence checksum: `0ebbfcd33349199d2f2ed4dc8a67de1e8ce8e07a5c7c4ecad82359a322c85ec6`;
- exact re-rendered crop SHA-256: `e438f5764470a39a0c53d1d2e5784a570119fd28ad51e41ea72a2a4fb3a9b05e`.

Completion не превратился в произвольное расширение: соседняя полоса привела к точному fail-closed terminal.

### `ibkr_midyear_p03`

- original parent bbox: `[36.0, 73.4167, 576.0, 167.52]`;
- reconciled parent bbox: `[36.0, 73.4167, 576.0, 167.5243]`;
- adjustment: нижняя граница `167.52 -> 167.5243`, то есть погрешность `0.0043 pt`, forcing atoms: 6;
- parent scope: 23 owned atoms, 0 crossing atoms;
- предложенный после provider subregion: `included=10 + excluded=13 + crossing=0 = all_parent=23`;
- ниже parent bbox обнаружены 7 unowned atoms с gap `4.98 pt`, допустимый поиск до `10.02 pt`;
- `candidate_parent_scope_complete=false`;
- evidence checksum: `4c0f24d2fef637ab401bc4b7e4723ed3f8fa95a5a53f8c9bb5af60b1653ec177`;
- exact re-rendered crop SHA-256: `382499b7bd9f9f666f81171783cd9d9d90a9a190a660b2fd2c3954526a36cb24`.

Погрешность `0.0043 pt` признана безопасной и цель дошла до intended provider route. Соседняя source-полоса не была присвоена proposal, поэтому принятие правильно заблокировано.

Регрессии отдельно доказывают обратную границу: overshoot `0.0043 pt` согласуется и журналируется, genuinely invalid bbox даёт `pdf_visual_topology_atom_bbox_invalid`, atom за пределом precision envelope блокируется до provider с `countTokens=0`, `generate=0`. Невалидные координаты не clamp-ятся.

## Provider accounting: run4 и run5

Во всех строках run5 transport journal, persisted target, terminal и scorer совпали. Общий requested/resolved model: `models/gemini-3.5-flash`; hidden retry и failover: `false`.

| Цель | run4 `count/generate`, tokens | run5 `count/generate`, tokens | Cross-view run5 |
|---|---:|---:|---|
| `betterment_p04` | `1/1`, `8294=8294` | `1/1`, `8393=8393` | verified |
| `drivewealth_p07` | `1/1`, `7149=7149` | `1/1`, `7404=7404` | verified |
| `drivewealth_p09` | `1/1`, `2394=2394` | `1/1`, `2915=2915` | verified |
| `drivewealth_p11` | `1/1`, `2402=2402` | `1/1`, `2578=2578` | verified |
| `ibkr_annual_p11` | `1/1`, `9743=9743` | `1/1`, `9843=9843` | verified |
| `ibkr_midyear_p03` | `0/0`, tokens/model/request отсутствовали, unverified | `1/1`, `3276=3276` | verified |
| `moomoo_annual_p14` | `1/1`, `1633=1633` | `1/1`, `1734=1734` | verified |
| `moomoo_midyear_p10` | `1/1`, `1631=1631` | `1/1`, `1734=1734` | verified |

Scorer condition 9 прошёл для всех 29 целей. Pre-provider negatives сохранили точные `0 / 0`; post-provider block больше не может выдать себя за pre-provider `0 / 0`.

## Terminal cardinality

Для всех 29 целей run5:

- proposal outcomes: ровно `1`;
- binding outcomes: ровно `1`;
- terminal payloads: ровно `1`;
- detection decisions: ровно `1`;
- processability decisions: ровно `1`;
- holdout decisions: ровно `1`;
- `terminal_cardinality_verified=true`: 29 из 29;
- cardinality failure codes: 0.

DriveWealth p9 больше не теряет proposal и не создаёт конкурирующие target states. Дубли и конфликтующие terminal views покрыты fail-closed тестами.

## Диагноз `pdf_vlm_region_binding_region_has_no_word_atoms`

Для каждой строки bbox VLM приведён сначала в normalized page space, затем в exact source-space points. `intersecting=0` означает одновременно `contained=0` и `crossing=0`; все остальные page atoms учтены как excluded.

| Цель / регион | Proposed normalized bbox -> source bbox | Crop SHA-256 | Page atoms; intersecting; contained | Exact transform |
|---|---|---|---:|---|
| `moomoo_annual_p09/r1` | `[0.282353,0.343636,0.724706,0.427273]` -> `[172.800036,272.159712,443.520072,338.400216]` | `5728ed89d2987727155d5f7ecefa04def0d7fb3fecc3c15624f799a465e9b12d` | `521; 0; 0` | `sx=2.083333056, sy=2.083317482, tx=-172.800036, ty=-272.159712` |
| `moomoo_annual_p10/r1` | `[0.170667,0.808182,0.832,0.898182]` -> `[104.448204,640.080144,509.184,711.360144]` | `1a346e1c753bc6be2bd0f79b6af21831738987a9b27403c60a6432602fd7d24c` | `484; 0; 0` | `sx=2.085310981, sy=2.090347924, tx=-104.448204, ty=-640.080144` |
| `moomoo_annual_p11/fixed_assets_region` | `[0.164706,0.156364,0.847059,0.407273]` -> `[100.800072,123.840288,518.400108,322.560216]` | `b11f2f3d542e303570d8b282f90c34129733edd0166f60fceba591740109d793` | `354; 0; 0` | `sx=2.083333154, sy=2.083334088, tx=-100.800072, ty=-123.840288` |
| `moomoo_annual_p14/r1` | `[0.228,0.312,0.732,0.535]` -> `[139.536,247.104,447.984,423.72]` | `b4e4b83d7f77cbe4bba3926dd28f62299ed9ac1db4fdb3661f79a0dfeac46f65` | `262; 0; 0` | `sx=2.087872186, sy=2.089278435, tx=-139.536, ty=-247.104` |
| `moomoo_midyear_p06/r0` | `[0.285333,0.348148,0.717333,0.448148]` -> `[174.623796,275.733216,439.007796,354.933216]` | `1ee3957600884ffbee0a7a5a37ec3049f91567ee6b582dee23ef965dc21608a1` | `514; 0; 0` | `sx=2.087872186, sy=2.095959596, tx=-174.623796, ty=-275.733216` |
| `moomoo_midyear_p08/fixed_assets_region` | `[0.182667,0.164545,0.808,0.431818]` -> `[111.792204,130.31964,494.496,341.999856]` | `6f77e8c330749a46e4a715093087b3d1af4a824ef77e29abba3c48793304fe67` | `332; 0; 0` | `sx=2.087776522, sy=2.088055315, tx=-111.792204, ty=-130.31964` |
| `moomoo_midyear_p10/r2` | `[0.32,0.398,0.678,0.528]` -> `[195.84,315.216,414.936,418.176]` | `e8da98cc27c8626ad4fa0e6569c7ea0752204196149219f0340d2c6f0fabd454` | `307; 0; 0` | `sx=2.085843648, sy=2.097902098, tx=-195.84, ty=-315.216` |

Для всех семи регионов дополнительно доказано:

- `original_source_bbox == source_bbox == declared_table_bbox == rendered_bbox`;
- `page_rotation=0`, `applied_rotation=0`, `silent_resize_performed=false`;
- parent accounting замкнут: `contained + crossing + excluded = page_atoms_total`;
- source PDF перепроверены по SHA-256: annual `bad1e5fa045f0735f02487aca14236d84037f82fd2b1230ee3c56ba3420aee67`, midyear `766448b2bf8b9ebe9172e4a07b0392134787a3b642288a93fbe6c0f9999ed0d3`;
- каждый crop повторно отрендерен factory-equivalent PyMuPDF `1.26.5` policy при `150 dpi`; все семь PNG byte-for-byte совпали с sealed crop SHA-256 из таблицы;
- визуальная проверка этих exact hash-matched crops подтвердила, что bbox содержит именно целевую таблицу, поэтому случай 1 исключён;
- PDF object inventory внутри crop показывает embedded image, 0 PDF words и 0 overlapping vector drawings;
- provider выполнил ровно `1 / 1`, после чего повторный выбор source atoms вернул 0.

Embedded-image evidence по цели (`xref`; доля площади crop, покрытая union embedded images):

- `moomoo_annual_p09/r1`: `130`; `0.993351`;
- `moomoo_annual_p10/r1`: `134`; `0.976208`;
- `moomoo_annual_p11/fixed_assets_region`: `138,139,140`; `0.989131`;
- `moomoo_annual_p14/r1`: `150,151`; `0.988327`;
- `moomoo_midyear_p06/r0`: `18`; `0.965575`;
- `moomoo_midyear_p08/fixed_assets_region`: `26`; `1.000000`;
- `moomoo_midyear_p10/r2`: `34`; `0.994797`.

Итоговая классификация для всех семи — **случай 4: таблица действительно raster/image-only**. Случаи 1–3 исключены exact crop inspection, воспроизводимым transform и полным reselection accounting. В этих регионах нет авторитетных text-layer values; без OCR они остаются явно unsupported и не считаются обычной ошибкой reconstruction. OCR в этом goal не добавлялся и не запускался.

## Результат того же sealed development gate

- Run: `local/stage2/broker_reports_pdf_vlm_guided_intake_e2e_2026-07-15/run5-repair-gate`.
- Corpus cases: 29 из 29; runner failures: 0; `run_status=completed`.
- Terminal SHA-256: `f802cd25252c6ebccfed3fff055a877569189108cb29da069c1a871dce8690ed`.
- Runner и scorer были отдельными процессами с разными PID.
- Terminal был запечатан до старта scorer и не изменился во время scoring.
- Runner не получал reference и `reference_accessed=false`; scorer получил reference только после seal.
- Runner return code: `0`; scorer return code: `1`, что соответствует проваленному binary gate.
- Процессных blocker codes: 0.
- Принято регионов: 5.
- Корректно принято: 1.
- Ложно принято: 4 (`betterment_p04`, `drivewealth_p09`, `ibkr_annual_p11`, `moomoo_annual_p14`).
- Failed conditions: 6, 7, 8.
- Failed contracts: 8, перечислены в начале и в финальном статусе отчёта.

## Сохранённые границы безопасности

- exact values берутся только из original PDF/parser source refs;
- VLM предлагает только структуру;
- invented/mutated/repaired financial values: 0;
- accepted atom ownership остаётся exact и однократным;
- hidden retry: false;
- provider failover: false;
- whole-PDF model request не выполнялся;
- OCR: false;
- Knowledge/RAG/vector: false;
- production authority: false;
- production Gate 2 selection changed: false;
- reference до terminal seal не читался;
- максимальный counted input в показанных маршрутах `9843`, ниже лимита `20000`.

## Проверки кода

- Полный service suite: `744 passed, 5 warnings in 53.60s`.
- Targeted topology/assembly suite: `48 passed`.
- Bundle parity suite: `3 passed`, включая AST source/bundle parity.
- Независимый re-audit проверил подделку и пропуск structural adjustments; обе формы блокируются `pdf_topology_assembly_structural_adjustment_invalid`.
- `ruff`, `py_compile`, `git diff --check`: passed.

Fresh unseen holdout: **НЕ ЗАПУСКАЛСЯ**.

Live canary: **НЕ ЗАПУСКАЛСЯ**.

## Финальный статус

BROKER_REPORTS_PDF_VLM_GUIDED_INTAKE_E2E_NOT_WORKING
condition=6 target=corpus reason=development_minimum_correct_acceptances_not_met expected=4 observed=1
condition=7 target=corpus broker=betterment reason=development_required_broker_acceptance_missing
condition=7 target=corpus broker=drivewealth reason=development_required_broker_acceptance_missing
condition=7 target=corpus route=candidate_crop reason=development_required_route_acceptance_missing
condition=8 target=betterment_p04 reason=development_incorrect_structure_accepted
condition=8 target=drivewealth_p09 reason=development_incorrect_structure_accepted
condition=8 target=ibkr_annual_p11 reason=development_incorrect_structure_accepted
condition=8 target=moomoo_annual_p14 reason=development_incorrect_structure_accepted
