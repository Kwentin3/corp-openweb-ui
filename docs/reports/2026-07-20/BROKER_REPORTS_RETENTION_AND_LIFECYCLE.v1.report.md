# Broker Reports — retention и lifecycle audit

Дата: 2026-07-20

Итог: approved `expire_run` не выполняет global scan, но полный retention contract
имеет два незакрытых gap: API не context-bound и повторный expiry не строго
идемпотентен. Статус: `PASSED_WITH_CONTRACT_GAPS`.

## Измерение с 5000 unrelated records

На disposable SQLite ArtifactStore создано 5000 активных записей другого run и 10
expired записей target run. Через maintained factory выполнен реальный
`expire_run`.

| Показатель | Результат |
|---|---:|
| Target records examined | 10 |
| Target records changed | 10 |
| Unrelated records materialized | 0 |
| Unrelated records changed | 0 |
| SQL | 1 SELECT + 10 UPDATE |
| Execute wall | 0.001898 с |
| Полный operation wall | 0.008314 с |
| Transaction connections | 1 |

SQL использует `WHERE normalization_run_id = ?`, а индекс
`idx_artifact_run(normalization_run_id)` ограничивает выборку. Исправленный live
smoke вызывает именно `expire_run(probe_result.normalization_run_id)`, где run id
получен из server-side normalizer result, а не из клиентского поля. Поэтому прежний
global-expiry stall в approved flow устранён.

## Изоляция и context gap

Пустой run id отклоняется `artifact_scope_unverified`, но store API принимает только
строку `normalization_run_id`; `ArtifactAccessContext`, user/case/tenant и
соответствующие SQL predicates отсутствуют. Approved pipe сейчас безопаснее API,
поскольку сам создаёт probe run, однако storage contract не доказывает cross-case
изоляцию при ошибке caller или коллизии/повторном использовании run identity.

Узкая коррекция: `expire_run(context, now)` либо `expire_run(run_id, trusted_context,
now)` с обязательным совпадением `user_id`, `case_id` и run id в одном SQL predicate.
Клиентские scope поля нельзя передавать напрямую.

## Idempotence и concurrency

- Два concurrent callers завершились без lock error за 0.012551 с; все 20 records
  получили terminal `expired`.
- Оба caller вернули по 20 ids: операция повторяет работу.
- Повторный последовательный expiry снова вернул 10 ids и переписал `updated_at`
  у всех 10 records. Terminal state идемпотентен, audit state — нет.

Нужен predicate `lifecycle_status NOT IN ('expired', 'purged')` и аналогичный
`purge_status`, после чего второй вызов должен вернуть пустой set и не менять audit
timestamps. Это P1 lifecycle/observability debt, а не причина текущего global stall.

## Purge, source deletion и failure semantics

- `purge_run` выбирает records по run, но выполняет отдельные transactions на
  transition/delete/status для каждого record; atomic all-or-nothing cleanup не
  обеспечен.
- Реальная filesystem failure (payload ref указывает на directory) была
  проброшена вызывающему коду; ложный terminal success не возвращён, record остался
  в recoverable `purge_pending`.
- Purged/tombstoned resolver denial и source/case deletion функционально покрыты
  существующими ArtifactStore tests.
- `purge_case`, `purge_chat` и `mark_source_file_deleted` используют
  `_active_records()` и тем самым материализуют все активные records до фильтрации.
  Это оставшиеся global scans, хотя они не участвуют в approved expiry smoke.
- Публичный `expire_artifacts` всё ещё предоставляет global expiry API; maintained
  Broker flow его не вызывает.

## Приоритеты

1. P1: context-bound run/case/user expiry contract и composite index.
2. P1: strict idempotence для expired records.
3. P1 before scale: заменить global active scans в case/chat/source cleanup на
   indexed SQL predicates.
4. P2: batched/transactional purge state updates с resumable purge_pending ledger.
5. P3: метрики records examined/changed, transaction and lock duration в safe
   operational telemetry.

## Статус требований

- Run-bounded approved expiry: proven.
- Global expiry scan in approved flow: absent.
- Thousands of unrelated records untouched: proven.
- Single expiry transaction: proven.
- Concurrent terminal state: proven.
- Cleanup failure cannot report success: proven.
- Strict repeated idempotence: failed, exact gap recorded.
- Store-level trusted case/tenant context: not proven, exact gap recorded.
- All lifecycle paths free of global scans: failed for case/chat/source deletion.

Machine-readable evidence:
`BROKER_REPORTS_RETENTION_RUN_SCOPE.v1.safe.json`.
