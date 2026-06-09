# Acceptance Tests

## Минимальные критерии готовности

PRD-0 готов к пилоту, если:

- `https://gpt.alpha-soft.ru` открывается в браузере;
- OpenWebUI доступен только через HTTPS;
- `bash scripts/smoke-test.sh --strict-tls` проходит без отключения проверки сертификата;
- UFW включен;
- публичный perimeter ограничен ожидаемыми портами `22/tcp`, `80/tcp`, `443/tcp`;
- Docker не публикует наружу ничего, кроме Traefik `80/443`; OpenWebUI не имеет прямого public port;
- если используется provider proxy bridge, bridge port не открыт публично и доступен только с Docker subnet на Docker gateway;
- fail2ban установлен и active;
- `sshd` jail active;
- `bash scripts/network-hardening-check.sh --strict` проходит после deploy;
- администратор может войти;
- публичная самостоятельная регистрация отключена или ограничена;
- созданы 3-4 пользователя;
- пользователь может войти;
- в интерфейсе отображается имя инстанса `Alpha Soft AI Chat` или подтвержденное оператором имя;
- пользователь видит warning banner при входе или в интерфейсе;
- warning banner содержит запрет на отправку паролей, токенов, API-ключей, приватных SSH-ключей и закрытых персональных данных;
- OpenAI primary provider с model id `gpt-5.4-mini` подключен или готов к подключению по [PROVIDER_SETUP_RUNBOOK.md](PROVIDER_SETUP_RUNBOOK.md);
- Gemini secondary provider с model id `gemini-3.5-flash` подключен через Admin UI или готов к подключению по [PROVIDER_SETUP_RUNBOOK.md](PROVIDER_SETUP_RUNBOOK.md);
- если прямой egress к provider API блокируется, OpenWebUI provider path проверен через HTTP proxy bridge, а не direct SOCKS env;
- пользователь может задать вопрос модели;
- ответ хотя бы от одного provider приходит;
- второй provider проверен или явно отмечен как pending из-за отсутствия API key/quota/billing, а не из-за незакрытого выбора provider/model;
- история чата сохраняется после выхода и входа;
- история чата сохраняется после restart контейнера;
- API-ключи не видны пользователям;
- `WEBUI_SECRET_KEY` задан в `.env`, стабилен и не коммитится;
- `CORS_ALLOW_ORIGIN=https://gpt.alpha-soft.ru`;
- реальный `.env` не попал в Git;
- backup создается;
- restore path согласован с backup для `openwebui_data`, `.env` и `traefik_letsencrypt`;
- есть runbook для повторного разворачивания.

## Not blockers

- Post-bootstrap password rotation не является blocker PRD-0. После стабилизации пилота администратор может сменить первичный пароль через UI и убрать bootstrap password из активного server-local `.env`.
- Второй provider может быть pending только если нет API key, quota/billing или региональный доступ блокирует запрос. Provider/model choice уже закрыт: Gemini secondary, `gemini-3.5-flash`.

## Docker/UFW caveat

Docker может управлять iptables и публиковать порты в обход ожидаемой UFW-модели. Поэтому UFW не считается единственной границей защиты. В PRD-0 запрещено публиковать наружу что-либо, кроме Traefik `80/443` и SSH `22`. После `docker compose up -d` обязательна проверка реальных listeners через `ss` и `bash scripts/network-hardening-check.sh --strict`.

## Evidence

Для приемки сохранить в приватном рабочем отчете:

- дату проверки;
- кто проверял;
- результат smoke;
- результат `network-hardening-check.sh --strict`;
- факт входа admin;
- отображаемое имя инстанса;
- факт отображения warning banner и его текст без секретов;
- primary/secondary provider без секретов;
- выбранные model ids;
- факт тестового запроса к OpenAI или Gemini;
- статус второго provider;
- факт restart и сохранения истории;
- путь к backup на сервере.

Не прикладывать API-ключи, пароли, точные SSH endpoints, public IP, операторские IP и пользовательские приватные данные.
