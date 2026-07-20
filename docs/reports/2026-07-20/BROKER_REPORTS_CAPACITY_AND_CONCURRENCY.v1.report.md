# Broker Reports — capacity и concurrency envelope

Дата: 2026-07-20

Статус измерения: `passed`.

## Что измерено

На одном fixed revision выполнен реальный actual-corpus Gate 2 package-preparation
contour: сначала один worker, затем два одновременных fresh-process workers. Перед
каждой группой весь immutable ArtifactStore graph прочитан для одинакового OS-cache
состояния. Production workload не затрагивался; все raw outputs находятся в ignored
root.

| Показатель | 1 worker | 2 workers |
|---|---:|---:|
| Group wall | 54.497682 с | 59.865303 с |
| Worker wall | 53.731399 с | 58.768772 / 59.031550 с |
| Aggregate peak RSS | 4.011 GB | 8.018 GB |
| Минимум доступной host RAM | 7.645 GB | 3.940 GB |
| Max host CPU | 70.8% | 87.5% |
| Swap-in / swap-out delta | 0 / 0 | 0 / 0 |
| DB lock errors / retries / failures | 0 / 0 / 0 | 0 / 0 / 0 |

Два workers сохраняют 681/681 packages passed у каждого, 0 errors, 0 warnings,
0 provider calls и неизменный ArtifactStore. Per-worker wall degradation — 1.0808×,
а aggregate throughput — 1.8207× от одиночного worker.

## Рекомендованный envelope

| Класс нагрузки | Максимум на текущем 8-CPU / 34-GB host | RAM на worker | Container limit | Решение |
|---|---:|---:|---:|---|
| Gate 1 full actual normalization/proof | 1 | фактический peak 7.43 GB | 10 GiB | Очередь обязательна |
| Gate 2 package preparation | 2 | фактический peak 4.02 GB | 5 GiB | Допустимо 2; >2 через очередь |
| Visual recovery/OCR | 1 в отдельном pool | фактический parent peak 4.12 GB; OCR child отдельно | 6 GiB | Не смешивать с Gate 1 |

Два Gate 2 workers безопасны в измеренном состоянии, но оставляют только 3.94 GB
available host memory. Третий worker не запускался: его ожидаемые дополнительные
~4.01 GB устраняют запас для ОС, page cache и transient allocations. Поэтому он не
является ни безопасным, ни полезным экспериментом на этом host.

Gate 1 peak 7.43 GB и visual peak 4.12 GB взяты из пройденных actual-corpus
контуров. Для них не рекомендуется совместный запуск: Gate 1 удерживает крупный
payload/render graph, а visual использует отдельные OCR subprocesses. Отдельный
visual pool предотвращает конкуренцию за память и упрощает cleanup.

## Ограничения

- Portable sampler не предоставляет disk queue depth; зафиксированы host disk
  bytes/counts, wall degradation и отсутствие lock errors.
- Windows `swap_memory().percent` вырос при двух workers, но реальные swap-in/out
  byte counters остались нулевыми. Вывод о двух workers опирается на RSS и minimum
  available RAM, а не на неоднозначный percentage.
- Capacity limit — не timeout. Длинная задача должна стоять в очереди и завершаться
  terminal state, а не обрываться по произвольному времени.

Machine-readable evidence:
`BROKER_REPORTS_GATE2_CAPACITY.v1.safe.json`.
