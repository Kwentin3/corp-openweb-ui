# OpenWebUI: самописец событий на хосте

Источник: `deploy/openwebui-flight-recorder/recorder.py`, Python 3.10+ standard library.
Сервис `openwebui-flight-recorder.service` работает вне контейнеров под systemd.
Он читает штатные Docker events/logs/inspect, cgroup v2 и kernel journal.
Установка не пересоздаёт OpenWebUI и не меняет его образ, данные или лимиты.

## Что сохраняется

- Каждые 10 секунд: память, swap, cumulative CPU time, memory pressure, OOM counters,
  до 10 PID с наибольшим RSS; доступная память хоста и boot ID. Снимки включают
  работающие контейнеры и наблюдаемые сервисы даже в остановленном состоянии.
- Docker: create/start/stop/restart/die/kill/oom/destroy/update/health_status для
  OpenWebUI, OfficeCLI и stage2-stt. Сохраняются ID, UTC/timeNano, exit code, signal.
- Kernel: факты OOM kill (PID, memory figures, host/cgroup), без произвольного текста.
- Из Docker logs сохраняются только распознанные HTTP access-записи: время,
  метод, нормализованный маршрут и статус; из ошибок — только тип из allowlist.
  Тела запросов/ответов, заголовки, query strings, пользовательские пути и аргументы
  процессов не сохраняются. Неизвестный HTTP-маршрут обозначается `other`.
- Остановка/ошибка/перезапуск самого сборщика отмечаются в истории; сбой отдельного
  опроса оставляет `sample_error`, а не фиктивный нулевой расход памяти.

Прямого обещания «этот tool вызвал OOM» нет. Access log обычно фиксирует HTTP-ответ,
не начало операции, и не всегда содержит chat/message ID или длительность. Корреляция
по времени не доказывает причинность, особенно при параллельных запросах. Для дальнейшей
детализации предусмотрен штатный OpenTelemetry, но он не включён этим изменением.

## Хранение и карточки

Данные root-only: `/var/lib/openwebui-flight-recorder/` (0700, файлы 0600).

| Путь | Назначение | Ограничение |
| --- | --- | --- |
| `history/*.jsonl` | События и снимки | до 7 дней / 256 МиБ |
| `incidents/*.json` | Самодостаточные карточки | до 30 дней / 64 МиБ |
| `cursors.json` | Позиции чтения источников | один небольшой файл |
| `last-resources.json` | Последний снимок для сравнения жизненного цикла | один файл |
| `status.json` | Время последнего завершённого цикла | один файл |

Действует более раннее ограничение: срок **или** объём. История ротируется сегментами
до 4 МиБ/часа; удаление по возрасту сегмента допускает погрешность до часа. Карточки
ограничены 2 МиБ данных timeline, плюс метаданные. Атомарная запись временно требует
места для ещё одной копии карточки. Эти лимиты относятся только к самописцу: исходные
Docker logs и системный journal имеют собственные правила хранения.

Каждое событие oom/die/kill/stop/restart и обнаруженная смена контейнера/запуска создаёт
карточку. Одна авария может дать несколько связанных карточек; связывать по container ID
и времени. Kernel OOM создаёт отдельную карточку уровня хоста; он может относиться
к другому контейнеру. Код 137 без OOM-события сохраняет причину `unknown`.

Окно: 10 минут до наблюдения триггера и 2 минуты после. `complete=true` означает,
что постокно завершилось, а не что причина установлена. `omitted_rows` и
`recent_buffer_full` показывают сокращение timeline при высокой нагрузке (буфер
12000 записей). Отсутствующие данные до установки или во время простоя не выдумываются.
История сохраняется с fsync, карточки и позиции чтения — через atomic replace.
После рестарта сборщик восстанавливает незаконченные карточки и последние 10 минут.
Источники читаются с перекрытием: повторные access-записи допустимы, использовать
`source_time`; Docker event идентифицируется по container ID/timeNano/action.
Docker хранит лишь последние 256 событий, поэтому длительный простой сборщика может
оставить пробел. Сравнение последних снимков дополнительно замечает смену запуска.

## Просмотр

```bash
systemctl status openwebui-flight-recorder --no-pager
cat /var/lib/openwebui-flight-recorder/status.json
ls -lt /var/lib/openwebui-flight-recorder/incidents/
python3 -m json.tool /var/lib/openwebui-flight-recorder/incidents/INCIDENT_ID.json
journalctl -u openwebui-flight-recorder --since '-1h' --no-pager
```

Проверять свежесть `status.json` (обычно до 20–30 секунд), наличие регулярных
`resources` и отсутствие повторяющихся `sample_error`/`stream_disconnected`.
Для расследования: сначала причина Docker/kernel, затем снимки памяти/PID и
соседние access/error-записи. `memory.current` включает cgroup accounting и может
отличаться от отображаемого Docker working set; `cpu.stat` содержит накопительные
микросекунды — нагрузку считать по разности двух снимков.

## Установка / обновление

Из проверенного checkout скопировать `recorder.py` и unit на хост. Проверить тесты
`python3 test_recorder.py` рядом с `recorder.py`, сохранить предыдущие два файла
при обновлении. Затем:

```bash
install -d -m 755 /opt/openwebui-flight-recorder
install -m 755 recorder.py /opt/openwebui-flight-recorder/recorder.py
install -m 644 openwebui-flight-recorder.service /etc/systemd/system/openwebui-flight-recorder.service
systemd-analyze verify /etc/systemd/system/openwebui-flight-recorder.service
systemctl daemon-reload
systemctl enable --now openwebui-flight-recorder
# При обновлении уже работающего сборщика:
systemctl restart openwebui-flight-recorder
```

Нужны Docker CLI, доступ к Docker socket и persistent kernel journal. Сервис root
для чтения этих источников; код вызывает только read-only Docker-команды. Ограничения
unit: 192 МиБ RAM, 10% одного CPU, 128 задач (включая Go threads Docker CLI),
read-only system/home/kernel и запись только в StateDirectory. Docker socket остаётся
привилегированным интерфейсом; код и unit должны быть доступны на запись только root.
Имена сервисов задаются `--targets`; после переименования sidecar обновить ExecStart
через systemd override и перезапустить только сборщик.

Откат: `systemctl disable --now openwebui-flight-recorder`. История остаётся на диске;
при остановленном сборщике retention не исполняется и новые данные не поступают.
Удалять сохранённые данные только отдельной осознанной операцией.

## Проверка

Unit tests проверяют фильтрацию секретов/путей, OOM vs exit 137, retention по сроку
и объёму, сохранение before/after timeline после повторного открытия хранилища.
Живая квалификация использует отдельный контейнер `openwebui-recorder-canary`:
без сети/томов приложения, с 64 МиБ RAM и без swap; отдельно проверяются ручной
restart и ограниченный OOM. Не выполнять OOM-тест на основном OpenWebUI.
Уведомления во внешние каналы и полноценная распределённая трассировка в этот этап
не входят. Задача текущего этапа — сохранять доказательства для расследования.

Первичные источники: [Docker events](https://docs.docker.com/reference/cli/docker/system/events/),
[Linux cgroup v2](https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html),
[OpenWebUI OTel](https://docs.openwebui.com/reference/monitoring/otel/).
