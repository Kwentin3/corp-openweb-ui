# Broker Reports — Goal 7: атомарный semantic-table release

Дата: 2026-07-22

Результат: `COMPLETED`

Release gate: `PASSED`

## Вывод

Новый production-маршрут выпущен не как отдельный VLM-проект, а как замена model-facing контракта внутри существующего контура. Модель возвращает только `description + rows`; код строит envelope, логическую таблицу, provenance, persistence и Gate 2 package.

Положительное решение Goal 5 применено только к ограниченному числовому профилю. Gemini включён как master, OpenAI по умолчанию не вызывается. Старый geometric/review path сохранён для чтения исторических артефактов и rollback, но не выбран новым default.

## Терминальный статус программы

| Goal | Статус |
|---|---|
| `GOAL_0_CONTRACT_AUTHORITY` | `COMPLETED` |
| `GOAL_1_GEMINI_MASTER_BOUNDARY` | `COMPLETED` |
| `GOAL_2_DETERMINISTIC_MATERIALIZATION` | `COMPLETED` |
| `GOAL_3_SEMANTIC_VALIDATOR` | `COMPLETED` |
| `GOAL_4_THREE_TABLE_HYPOTHESIS` | `COMPLETED` |
| `GOAL_5_ACTUAL_CORPUS_QUALIFICATION` | `COMPLETED` |
| `GOAL_6_DOWNSTREAM_MIGRATION` | `COMPLETED` |
| `GOAL_7_ATOMIC_RELEASE` | `COMPLETED` |

Подробное evidence каждого Goal находится в отдельном одноимённом отчёте этой директории. Скрытых `NOT_CLOSED` внутренних Goal нет.

## Release identity

| Объект | Identity |
|---|---|
| Release candidate | `54d5a6dc48a94e3ae0cb0d9b8814ff4561c48f4e` |
| Release id | `broker-reports-54d5a6dc48a9` |
| Atomic manifest SHA-256 | `78e1527447815c498f9c649fe25a80aec3e7b16a35b88eebf21ac66b668eb3ed` |
| Gate 1 bundle SHA-256 | `2e11148fb33d14a4c3ad29967298f4b3f4733eebaddbd4f383e703c00c026e87` |
| Gate 2 source bundle SHA-256 | `4325f0d31d11f30185ad8f685e516cb8469b4191dcb67834181aeadad5d21d92` |
| Gate 2 domain bundle SHA-256 | `aca592556f145b8af28f7a05cc8eaafb7c00e9105389e4fbbd06c854fc2b5eac` |
| Private-intake Action SHA-256 | `874a07129aa626e61807095b19e531972395934ce1a9aad72d378a3104530ae4` |
| Static loader SHA-256 | `28c5eadf6839d9aac5db4f125c31bda5ca6f08d9ce82723c832dd319126703b2` |
| Rollback identity SHA-256 | `16058ad82749748f8befaec504dbaeec3e41316ec590c896ba65fc6bfdc60410` |

Stage сохранил pinned image `corp-openwebui/openwebui:v0.9.6-native-web-stt-broker-intake-v2-8e6a71f`, image id `sha256:c862956b5a88f490de3a13829cb4176ce9a2e3fb3621ebf0198b059be65f8e83`, source revision `8e6a71f13cf4f9cec0e5be191fac924548050e48` и private-intake contract `server-authoritative-v2`. Image работал без restart.

## Semantic contract identity

| Поле | Значение |
|---|---|
| Prompt version | `broker_reports_semantic_table_transcription_prompt_v1` |
| Prompt SHA-256 | `9b54abe91313a87aacfe756ccec662b0c669188919b5db0bd0aab3bcee58dee2` |
| Schema version | `broker_reports_semantic_table_transcription_v1` |
| Canonical/OpenAI schema SHA-256 | `71584a0564b2175c4233ec8072873a72054a7a61e8fb81f6fd88e54690dbadc1` |
| Gemini adapted schema SHA-256 | `9c02cfdc757c4e202abe2e36dbc3d8e44ecff2e863e90fd490eb677c5c8cd93a` |
| Gemini schema transforms | `4` |
| Migration policy | `broker_reports_semantic_visual_table_migration_policy_v1` |
| Accepted profile | `broker_reports_semantic_visual_numeric_profile_v1` |
| Goal 5 qualification receipt | `96820ec84e1a4bfa167ac4c85090c0295f337ac24d2694d4f6fde0c535ed2ad7` |
| Goal 5 gate identity | `2860e0d181ae4a8137ec4db796b2f26070f2df32e4581f4438107410fc62adbb` |

Текущие visual model ids: Gemini `models/gemini-3.5-flash`, OpenAI `gpt-5.4-mini-2026-03-17`. Default provider policy — `pdf_semantic_vlm_provider_selection_v1`; OpenAI invocation policy — `disabled`.

Все 12 managed prompts прошли exact version/content/meta readback. Их content SHA-256:

| Prompt | SHA-256 |
|---|---|
| `broker_reports_document_metadata_passport_prompt_v0` | `1f9827ad62e1f20c5187f92aa3814f2c149f28148a61356b52850afc301f2de6` |
| `broker_reports_gate1_clarification_prompt_v0` | `7fd0b6dc935395bfb61aeabd24194941ed32b590ba58af03ff1581849dc2048a` |
| `broker_reports_gate2_cash_movement_prompt_v0` | `c9394d07189cd3aec476a27a2fd2f3cc4b3e7883e3abaa6d43066902060d7e0e` |
| `broker_reports_gate2_currency_fx_prompt_v0` | `917c1cae378223bdd2316dc8ec7d317352107943dd5988360e7572719e1bb715` |
| `broker_reports_gate2_document_summary_evidence_prompt_v0` | `9bad1a06bb8556e0fa62f1f47de73c7d7b1d41e57aa752de9206c0749133088d` |
| `broker_reports_gate2_fee_commission_prompt_v0` | `1d7b5c5e25f1e520d55ef8e9c84d323e6a27d73da392b428a74e95a0af6910fc` |
| `broker_reports_gate2_income_prompt_v0` | `af7fcd78f4533d0f5a1f8bcef58ad113f72f102e58f547f0c30f8810ddced187` |
| `broker_reports_gate2_position_snapshot_prompt_v0` | `b250663fc078782b28dfb530f10e99ee13f97789a12d4e67852938b3088c36fd` |
| `broker_reports_gate2_source_fact_prompt_v0` | `8ae7e4c49b987f8098540235b46381ae7c7ad7e021a417f975807ac1ea3083c9` |
| `broker_reports_gate2_trade_operation_prompt_v0` | `e819ded91b58bea3012e9bd9cde0444b63427d60120ef6712e33a4d8b515c0d1` |
| `broker_reports_gate2_unknown_source_row_prompt_v0` | `776a7574542cba7b77b2c5e7686af5990c652420823bbea9a78749ac12428aa1` |
| `broker_reports_gate2_withholding_tax_prompt_v0` | `e952e09ab395d21093102e9264effd0d8fce54e5b913b57c046538168d3eb228` |

## Активированные valves

- `pdf_table_intake_enabled=true`;
- `pdf_dual_vlm_enabled=true`;
- `pdf_semantic_visual_table_downstream_enabled=true`;
- `allow_standalone_semantic_visual_projections=true`;
- semantic migration policy и accepted profile зафиксированы exact identity;
- legacy hybrid/structural/guided/header shadows выключены;
- legacy automatic visual publication выключена;
- workload authority одинакова у трёх Functions: Gate 1 concurrency `1`, Gate 2 local maximum `2`.

Fresh class defaults остаются safe-off: production activation принадлежит persisted versioned release valves, а не неявному конструктору.

## Атомарность и rollback

1. Dry validation завершилась `validated`; stage не менялся, staging cleanup прошёл.
2. Apply изменил три Function в одной остановке/transaction boundary.
3. После candidate выполнен health/readback.
4. Rollback rehearsal восстановил предыдущее accepted состояние.
5. Candidate был повторно восстановлен и снова прошёл health/readback.
6. Всего прошло `3` health-check; `previous_state_restored=true`, `candidate_state_restored=true`.
7. Independent read-only verifier повторно подтвердил exact bundle hashes, revision, manifest, valves, prompts, Action, loader, image, rollback identity, quiescence и cleanup.

Mixed runtime не наблюдался: все три live Function содержат одну release revision и один manifest hash.

## Knowledge/RAG/vector и private intake

Atomic release сохранил counters без дельты:

| Counter | До | После | Delta |
|---|---:|---:|---:|
| OpenWebUI document rows | 0 | 0 | 0 |
| OpenWebUI file rows | 261 | 261 | 0 |
| Knowledge rows | 0 | 0 | 0 |
| Vector files | 595 | 595 | 0 |
| Vector bytes | 309808908 | 309808908 | 0 |

Отдельный synthetic-only private-intake smoke прошёл `PASSED`: native processing, Knowledge add/update, RAG, embeddings и vectorization для private source были отклонены. После cleanup file/document/knowledge/vector counters, vector collection count, vector bytes и ArtifactStore record count вернулись к исходным значениям. Customer documents не использовались.

## Paddle/local OCR

Production source scan не нашёл импортов `paddle`, `paddleocr`, `easyocr` или `torch`. Release manifest дополнительно фиксирует:

- `local_ocr_production_allowed=false`;
- `local_ocr_worker_pool_allowed=false`;
- `knowledge_rag_vectorization_allowed=false`;
- `native_openwebui_document_processing_allowed=false`;
- `whole_document_provider_upload_allowed=false`.

Independent verifier: `no_paddle_or_local_ocr_dependency=true`.

## Проверка repository

- Полный service suite: `1100 passed, 20 skipped`.
- Финальный focused architecture/release/bundle suite: `43 passed`.
- Semantic migration/materialization/downstream/VLM suite: `41 passed`.
- Atomic/delivery/bundle suite до финальной архитектурной синхронизации: `31 passed`.
- Ruff для изменённых Python-модулей и тестов: `passed` с сохранённым историческим `E402` исключением для script-import tests.
- Deterministic bundle regeneration: `passed`.
- `git diff --check`: `passed`.
- Worktrees: `1`.

## Граница доказанного

Default-on относится только к Goal 5-qualified numeric profile. Long-form prose, unreadable/obscured crops, cross-page continuations и неизвестные layout families не получают автоматическую Gate 2 публикацию и должны завершаться unsupported, review-required или fail-closed.

Это подтверждает исходную гипотезу программы: проблема была не в JSON как объектном формате, а в чрезмерной геометрической детализации model-facing контракта. Компактный semantic JSON сохраняет названия и суммы, а системную структуру безопасно и детерминированно достраивает код.
