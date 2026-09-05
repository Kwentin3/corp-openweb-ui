# Deployment Runbook

Current target note (2026-08-05): the deployed Compose project is `compose`
under `/opt/openwebui-prd0`; `openwebui` and `stage2-stt` use named volumes.
Exact SSH endpoint remains local and must not enter Git.

Gate 2 canonical backfill remains stopped after a terminal resource-limit
failure. DOC34 does not authorize retry, a larger limit, service restart,
backfill continuation or product cutover. Any later authorized attempt must
follow the one-document fail-closed sequence in
[BROKER_REPORTS_RESOURCE_BOUNDED_BACKFILL_RUNBOOK.md](BROKER_REPORTS_RESOURCE_BOUNDED_BACKFILL_RUNBOOK.md).
Never use `compose down -v` or remove the persistent volumes during recovery.

## 1. Проверить DNS

Проверить, что `gpt.alpha-soft.ru` указывает на целевой public IPv4:

```bash
dig +short gpt.alpha-soft.ru
```

Точный public IP не коммитить в Git.

## 2. Зайти на сервер

```bash
ssh <deploy-user>@<server>
```

Точный endpoint хранить локально, не в Git.

## 3. Установить Docker

Если Docker отсутствует, выполнить [BOOTSTRAP_DOCKER_UBUNTU.md](BOOTSTRAP_DOCKER_UBUNTU.md). Для текущего target preflight показал Ubuntu 24.04 LTS и отсутствие Docker/Compose.

Проверить:

```bash
docker --version
docker compose version
```

## 4. Настроить firewall/fail2ban

Выполнить [HOST_HARDENING_RUNBOOK.md](HOST_HARDENING_RUNBOOK.md):

- UFW default deny incoming / allow outgoing;
- allow `22/tcp`, `80/tcp`, `443/tcp`;
- fail2ban active;
- `sshd` jail active.

Не включать firewall до проверки SSH allow. После включения UFW открыть вторую SSH-сессию и убедиться, что доступ работает.

Docker может управлять iptables и публиковать порты в обход ожидаемой UFW-модели. UFW не считается единственной границей защиты: в PRD-0 наружу разрешены только SSH `22` и Traefik `80/443`; OpenWebUI не должен иметь прямой public port.

## 5. Склонировать репозиторий

```bash
mkdir -p /opt/openwebui-prd0
cd /opt/openwebui-prd0
git clone https://github.com/Kwentin3/corp-openweb-ui.git .
```

## 6. Создать `.env`

```bash
cp .env.example .env
chmod 600 .env
vi .env
```

Заполнить реальные значения. Не коммитить `.env`.

Сгенерировать стабильный `WEBUI_SECRET_KEY`:

```bash
openssl rand -hex 32
```

Primary provider задается в `.env`. Secondary provider добавляется позже через Admin UI по [PROVIDER_SETUP_RUNBOOK.md](PROVIDER_SETUP_RUNBOOK.md).

Для текущего PRD-0 `.env.example` уже отражает закрытые operator decisions:

- Let's Encrypt email: `kwentin3@mail.ru`;
- primary provider: OpenAI;
- primary model id: `gpt-5.4-mini`;
- Gemini secondary model id для Admin UI: `gemini-3.5-flash`;
- backup retention default: `BACKUP_RETENTION_DAYS=7`.

Если provider API блокирует регион исходящего IP, добавить в server-local `.env` `OPENWEBUI_OUTBOUND_PROXY` и `OPENWEBUI_NO_PROXY`. OpenWebUI provider route ожидает HTTP proxy; для SOCKS5 нужен local HTTP-to-SOCKS bridge, например Privoxy, а SOCKS5 upstream хранится отдельно. Реальные proxy credentials не коммитить.

## 7. Закрыть deployment decisions

До запуска должны быть приняты решения из [DEPLOYMENT_DECISIONS.md](DEPLOYMENT_DECISIONS.md):

- OpenAI API key для primary provider;
- Gemini API key для secondary provider через Admin UI;
- подтверждение имени инстанса `Alpha Soft AI Chat` или другого мягкого имени;
- первый admin email/password;
- operator current public IP, если нужно добавить fail2ban ignore list.

## 8. Синхронизировать browser config и выполнить preflight

```bash
bash scripts/render-stage2-stt-browser-config.sh
bash scripts/preflight.sh
bash scripts/network-hardening-check.sh
```

`network-hardening-check.sh` предупреждает, но не меняет firewall. До запуска Traefik warning по `80/443` может быть нормальным; после compose up эти порты должны слушаться.

## 9. Поднять compose

```bash
docker compose --env-file .env -f compose/openwebui.compose.yml pull
docker compose --env-file .env -f compose/openwebui.compose.yml up -d
```

Если `.env` менялся между preflight и запуском compose, повторить
`bash scripts/render-stage2-stt-browser-config.sh` перед `up -d`.

## 10. Проверить strict TLS

```bash
curl -I http://gpt.alpha-soft.ru
bash scripts/smoke-test.sh --strict-tls
bash scripts/network-hardening-check.sh --strict
```

Ожидаемо: HTTP редиректит на HTTPS, HTTPS проходит без `curl -k`, `80/443` слушаются Traefik, unexpected public listeners отсутствуют.

## 11. Создать администратора и пользователей

Если база свежая и заданы `WEBUI_ADMIN_EMAIL` и `WEBUI_ADMIN_PASSWORD`, OpenWebUI создает admin на первом запуске и отключает signup. Если admin bootstrap не сработал или база уже содержит пользователей, создать первого администратора через UI/recovery-процедуру OpenWebUI и зафиксировать это в deployment notes.

После входа администратора создать или активировать 3-4 пользователей через Admin UI. Оставить signup отключенным или `DEFAULT_USER_ROLE=pending`.

Post-bootstrap password rotation не blocker PRD-0. После стабилизации пилота администратор может сменить первичный пароль через UI и убрать bootstrap password из активного server-local `.env`.

## 12. Проверить low-cost customization

Проверить в UI:

- имя инстанса отображается как `Alpha Soft AI Chat` или подтвержденное оператором имя;
- warning banner виден пользователю;
- warning banner содержит запрет отправлять пароли, токены, API-ключи, приватные SSH-ключи и закрытые персональные данные;
- OpenWebUI logo/branding не скрывались и не заменялись.

Если имя или баннер не применились после restart, проверить Admin UI -> Settings -> General. Не делать fork и не менять frontend-код.

## 13. Настроить Gemini/OpenAI providers

Выполнить [PROVIDER_SETUP_RUNBOOK.md](PROVIDER_SETUP_RUNBOOK.md):

- проверить primary provider из `.env`;
- добавить secondary provider через Admin UI;
- указать base URL без альтернатив;
- проверить API key, quota, region/billing и exact model id;
- сохранить результат без секретов в приватном deployment note.

### Gate активации Mistral OCR для PDF

Не включать Mistral OCR в рамках обычного deployment. Значение
`CONTENT_EXTRACTION_ENGINE=mistral_ocr` действует глобально: все новые PDF,
обрабатываемые штатным OpenWebUI Knowledge/RAG, могут быть отправлены в
Mistral. `MISTRAL_OCR_API_KEY` хранить только через Admin UI в native persistent
config OpenWebUI; не добавлять ключ в Git, Broker Reports valves или другие
копии конфигурации. Активация и любые live-вызовы разрешены только после
отдельного одобрения владельца и отдельной квалификации. Текущий статический
релиз дополнительно закрыт кодовым gate
`PDF_DOCUMENT_AI_LIVE_QUALIFIED = False`: наличие native-настроек само по себе
не открывает сеть. Смена gate должна идти отдельным review после live-квалификации.

До ввода ключа проверить qualification plan из чистого exact HEAD с зелёным
`broker-reports-ci`. HEAD должен быть либо точной вершиной открытого non-draft
PR, либо точной текущей вершиной default branch после merge:

```bash
python services/broker-reports-gate1-proof/scripts/live_pdf_document_ai_qualification.py --preflight-only
```

Ожидается ровно два pinned SHA-256 и нули для config/key reads, provider calls,
external sends, retry, fallback, repair и activation. Скрипт не принимает путь
к PDF, URL, key, model или hash. Live-режим запускается только после отдельного
разрешения владельца через закрытый admin-only режим существующего
`broker_reports_gate1_pipe`; он не является вторым product route и не создаёт
adapter напрямую. Перед публикацией Function его valve
`pdf_document_ai_qualification_repository_head` должен быть равен точному
merged HEAD, для которого прошёл `broker-reports-ci`.

Для разрешённой квалификации:

1. Открыть изолированное maintenance window и запретить параллельные PDF upload.
2. Записать прежнее значение `CONTENT_EXTRACTION_ENGINE` вне Git.
3. Ввести URL/key только в native Admin configuration и временно выбрать
   `mistral_ocr`.
4. В одном admin-чате существующего Broker Reports Pipe приложить точные
   DriveWealth и Fidelity fixtures и отправить точную команду
   `PDF Document AI live qualification`. Произвольный файл, другой набор,
   не-admin пользователь или незаданный exact HEAD блокируются до расхода slot.
5. Pipe расходует два durable slots, по одному на каждый pinned SHA-256, и
   проводит каждый PDF через тот же Normalizer, factory, adapter и ArtifactStore.
   Ошибка или timeout расходует текущий slot без retry.
6. Для каждого PDF закрытый runner через private ArtifactResolver повторно
   показывает проверяющему точный исходный PDF, execution binding, приватный
   Full Source Markdown и связанные изображения. Проверяющий сверяет страницы,
   таблицы, заголовки, периоды, продолжения, соседние таблицы, буквальные числа,
   изображения и административный шум. Только положительный verdict создаёт
   safe OCR 4.1 baseline candidate; затем `purge_run` доказывает отказ повторного
   чтения. Внешний координатор не получает PDF или provider payload.
7. Qualification uploads удалить штатным OpenWebUI source-deletion lifecycle.
8. В `finally` восстановить прежний engine даже после первой ошибки.

На всём шаге `PDF_DOCUMENT_AI_LIVE_QUALIFIED = False`. Успех квалификации не
разрешает production activation: для смены gate нужен отдельный owner-approved
review.

## 14. Проверить LLM-ответ

Администратор или тестовый пользователь задает простой рабочий вопрос.

Ожидаемо:

- ответ приходит хотя бы от одного provider;
- второй provider проверен или pending только по API key/quota/billing/region;
- ответ сохраняется в истории.

## 15. Проверить persistence

```bash
docker compose --env-file .env -f compose/openwebui.compose.yml restart openwebui
bash scripts/smoke-test.sh --strict-tls
```

После restart войти снова и проверить, что история чата сохранилась.

## 16. Сделать backup

```bash
bash scripts/backup.sh
```

Retention управляется `BACKUP_RETENTION_DAYS` в `.env`: `1`, `7` или `30`; default в `.env.example` - `7`.

Проверить restore path по [BACKUP_RESTORE_RUNBOOK.md](BACKUP_RESTORE_RUNBOOK.md).

## 17. Обновить deployment note/report

В приватном deployment note указать:

- дату запуска;
- кто выполнял;
- результат hardening check;
- имя инстанса и факт warning banner;
- primary/secondary provider;
- model ids без API keys;
- результат strict TLS;
- результат LLM и persistence checks;
- путь к backup на сервере.
