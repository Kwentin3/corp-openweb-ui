# Acceptance Tests

## Минимальные критерии готовности

PRD-0 готов к пилоту, если:

- `https://gpt.alpha-soft.ru` открывается в браузере;
- OpenWebUI доступен только через HTTPS;
- `bash scripts/smoke-test.sh --strict-tls` проходит без отключения проверки сертификата;
- UFW включен;
- публичный perimeter ограничен ожидаемыми портами `22/tcp`, `80/tcp`, `443/tcp`;
- fail2ban установлен и active;
- `sshd` jail active;
- `bash scripts/network-hardening-check.sh` не показывает unexplained warnings после deploy;
- администратор может войти;
- публичная самостоятельная регистрация отключена или ограничена;
- созданы 3-4 пользователя;
- пользователь может войти;
- в интерфейсе отображается имя инстанса `Alpha Soft AI Chat` или подтвержденное оператором имя;
- пользователь видит warning banner при входе или в интерфейсе;
- warning banner содержит запрет на отправку паролей, токенов, API-ключей, приватных SSH-ключей и закрытых персональных данных;
- OpenAI provider подключен или готов к подключению по [PROVIDER_SETUP_RUNBOOK.md](PROVIDER_SETUP_RUNBOOK.md);
- Gemini provider подключен или готов к подключению по [PROVIDER_SETUP_RUNBOOK.md](PROVIDER_SETUP_RUNBOOK.md);
- пользователь может задать вопрос модели;
- ответ хотя бы от одного provider приходит;
- второй provider проверен или явно отмечен как pending operator decision;
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
- Второй provider может быть pending operator decision, если нет API key, quota/billing или exact model id. Это должно быть явно зафиксировано до пилота.

## Evidence

Для приемки сохранить в приватном рабочем отчете:

- дату проверки;
- кто проверял;
- результат smoke;
- результат `network-hardening-check.sh`;
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
