# Broker Reports DOC11 — minimal table context and plain-text structure test

Дата: 2026-08-03  
Статус: **DOC11 BLOCKED**

## Итог

Эксперимент не даёт права оценить гипотезу. Все четыре минимальных пакета были корректно собраны, визуально проверены и заморожены до вызовов. Из требуемых 16 provider slots только 2 завершились HTTP 200; процесс исполнения прервался после выдачи durable claims, поэтому 14 оставшихся слотов закрыты как `INTERRUPTED_AFTER_CLAIM` без повторной отправки.

Повтор этих слотов без нового явного разрешения был бы скрытым retry и нарушил бы frozen protocol. Два полученных ответа сохранены как диагностические наблюдения, но не используются для model-level или overall выводов.

## Замороженный вход

- Таблицы: 4; пакеты: 4; ровно одно изображение на пакет.
- Model-visible файлы каждого пакета: `table.png`, `parser_text.txt`, `prompt.txt`.
- Видимые ID/метки: 0; parser rows/columns/order/coordinates/JSON/anchors/DOC6 fields: 0.
- `parser_text.txt`: точный multiset фрагментов, дубликаты сохранены, строки отсортированы лексикографически и не несут visual order.
- Для двух исходных crop до freeze удалён только частично видимый материал после последней линии целевой таблицы; строки frozen gold и parser fragments не удалялись.
- Protocol: `d1b1cf283ca3a82ab262849c95fee2977c63f477bcab114946eed4791e33d13f`.

## Модели

| Роль | Exact model ID | Catalog status |
|---|---|---|
| cheap OpenAI | `gpt-5.4-mini-2026-03-17` | AVAILABLE |
| cheap Google | `models/gemini-3.5-flash-lite` | AVAILABLE |
| cheap Anthropic | `claude-haiku-4-5-20251001` | AVAILABLE |
| strong reference | `claude-opus-5` | AVAILABLE |

## Call accounting

| Показатель | Значение |
|---|---:|
| Frozen slots | 16 |
| Accounted slots | 16 |
| HTTP responses | 2 |
| `INTERRUPTED_AFTER_CLAIM` | 14 |
| Retry / fallback / repair | 0 / 0 / 0 |
| Исключённые failed tables | 0 |

Получены только два ответа на `doc11_table_01`: Google Flash-Lite прошёл normalizer и exact-text multiset conservation, но не дал exact table; OpenAI mini не прошёл exact-text multiset validation. Это недостаточная выборка и не является сравнением моделей.

## Решения

| Решение | Статус |
|---|---|
| `DOC11` | `BLOCKED` |
| `PLAIN_TEXT_CONTEXT_REDUCES_OVERLOAD` | `INCONCLUSIVE` |
| `PLAIN_TEXT_CONTEXT_IMPROVES_STRUCTURE` | `INCONCLUSIVE` |
| `BEST_CHEAP_MODEL` | `NONE` |
| `BEST_REFERENCE_MODEL` | `NONE` |
| `MINIMAL_CONTEXT_PROJECTION` | `INCONCLUSIVE` |

Исторический DOC10 прочитан только как baseline; повторных DOC10 вызовов не было. Сравнение запрещено до полного покрытия 4/4 таблиц хотя бы для одной модели.

## Граница остановки

Product pipeline, parser, DOC6, роли и финансовая интерпретация не менялись. Для нового запуска нужен отдельный выбор: либо явное разрешение на новые попытки для 14 неопределённых slots, либо новый полностью версионированный run. До такого решения вывод о minimal context не подтверждён и не опровергнут.
