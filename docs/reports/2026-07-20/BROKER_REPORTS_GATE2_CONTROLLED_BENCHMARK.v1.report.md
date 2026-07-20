# Broker Reports — контролируемый benchmark Gate 2

Дата: 2026-07-20

Revision: `1f36c70cba25b96b2ea178744c33d4f81b72f1ea`

Статус: `no_regression_measurement_noise`

## Вывод

Регрессия относительно 53.146799 с не подтверждена. Медиана шести
неинструментированных прогонов составила 53.287363 с, отношение к историческому
ориентиру — 1.002645. Разница 0.26% находится внутри измерительного шума. Позднее
значение около 112 с было получено с line tracing и function wrappers и не является
задержкой продуктового пути.

## Методика

- Один commit, Python 3.11.9, SQLite 3.45.1, Windows, 8 logical CPU и 34.04 GB RAM.
- Один workload fingerprint `6827eea…0651`, 1531 record и 1.463 GB входного графа.
- Три fresh-process прогона и три fresh-process прогона после полного chunked
  prewarm OS cache; конкурирующие диагностические нагрузки не запускались.
- Ещё три warm instrumented прогона использованы только для фазовой атрибуции.
- Каждый результат: 681/681 package passed для 75 source-ready документов,
  0 errors, 0 warnings, 0 provider calls, ArtifactStore не изменён.
- Raw profiles остались в ignored private evidence root; в Git помещён только
  агрегат без source refs, customer values и private paths.

## Результаты

| Контур | N | Медиана wall | Диапазон wall | Медиана peak RSS |
|---|---:|---:|---:|---:|
| Fresh process | 3 | 53.326727 с | 53.247568–53.354346 с | 4.0117 GB |
| Warm OS cache | 3 | 53.279008 с | 53.200649–53.295719 с | 4.0118 GB |
| Instrumented warm | 3 | 109.639739 с | 109.553120–109.772349 с | 4.0114 GB |

Baseline CPU: около 50.14 с user и 3.04 с system. На каждый baseline процесс
приходится 1.374875 GB disk reads и 11.10 MB disk writes. Warm pre-read почти не
влияет на wall time: путь CPU-heavy, а не storage-latency-heavy.

## Корректная фазовая атрибуция

Первоначальный audit harness обнаружил собственный дефект: фазовые границы были
заданы устаревшими номерами строк. До фикса это ошибочно переносило почти всё время
в package construction. Отдельный commit заменил номера строк на проверяемые
уникальные source markers и добавил regression test, требующий присутствия всех
границ в текущем orchestrator.

Медианы instrumented-прогонов:

| Фаза | Медиана |
|---|---:|
| Private artifact discovery/validation | 65.893316 с |
| Package enumeration/construction/validation | 40.247032 с |
| Scope readiness reconciliation | 1.100843 с |
| Catalog + DCP resolution | 0.827250 с |
| Store immutability guard | 0.827161 с |
| Coverage/parity aggregation | 0.370397 с |
| Safe report rendering | 0.231831 с |
| Остальные boundary phases вместе | <0.08 с |

Главный cost center — не reconciliation, а private artifact discovery и полная
валидация неизменившихся source units. Функциональный probe показывает 861 вызов
`validate_full_source_unit` (~37.15 с inclusive), 861 проверку provenance
(~36.91 с), 667 валидаций source-fact packages (~27.01 с), 667 разрешений source
values (~19.87 с) и 667 package constructions (~10.60 с). Inclusive времена
перекрываются и не должны суммироваться.

## Operation counts и узкие цели

- 935 SQLite queries, cumulative SQLite time 0.228 с: SQLite не является главным
  bottleneck.
- 933 resolver calls и 933 unique payload reads; duplicate payload reads = 0.
- Прочитано 1.324 GB payload bytes; 869 из 933 payloads — normalized source units.
- 45 полных PDF parent validations и 532 cache hits.
- 219,654 PDF checksum и 365,989 provenance checksum operations внутри
  instrumented пути указывают на CPU-стоимость строгой повторной валидации.

Самая узкая безопасная следующая оптимизация для Gate 2: не ослабляя контракты,
измерить и затем устранить повторное вычисление immutable validation/checksum для
одного и того же sealed scope внутри одного audit call. Кэш должен быть
run/context-bound, неперсистентным и ключеваться integrity identity; глобальный или
unscoped cache недопустим.

## Ограничения сравнения

Полная runtime identity исторического 53.146799-секундного прогона не сохранена.
Поэтому доказано отсутствие наблюдаемой регрессии текущего пути относительно числа,
но не побитовое равенство двух исторических окружений. Текущая контролируемая серия
сама по себе стабильна и достаточна, чтобы отклонить гипотезу о текущей задержке
112 с без instrumentation.

Machine-readable evidence:
`BROKER_REPORTS_GATE2_CONTROLLED_BENCHMARK.v1.safe.json`.
