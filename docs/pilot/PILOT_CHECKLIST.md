# Pilot Checklist

## Before pilot

- [ ] Домен открывается по HTTPS.
- [ ] Strict TLS check проходит без `curl -k`.
- [ ] UFW active.
- [ ] Fail2ban active, `sshd` jail enabled.
- [ ] `bash scripts/network-hardening-check.sh` не показывает unexplained warnings.
- [ ] Администратор входит.
- [ ] Имя инстанса отображается как `Alpha Soft AI Chat` или подтвержденное оператором имя.
- [ ] Warning banner виден пользователю и запрещает отправку секретов/закрытых персональных данных.
- [ ] OpenAI primary provider с `gpt-5.4-mini` подключен или готов по runbook.
- [ ] Gemini secondary provider с `gemini-3.5-flash` подключен через Admin UI или готов по runbook.
- [ ] Хотя бы один provider отвечает.
- [ ] Второй provider проверен или pending только по API key/quota/billing, не по выбору provider/model.
- [ ] Созданы 3-4 пользователя.
- [ ] Signup отключен или ограничен.
- [ ] Backup создан.
- [ ] `WEBUI_SECRET_KEY` и `.env` не попали в Git.
- [ ] Пользовательская инструкция выдана.

## During pilot

- [ ] Пользователи заходят повторно.
- [ ] Пользователи задают рабочие вопросы.
- [ ] Фиксируются полезные сценарии.
- [ ] Фиксируются проблемы интерфейса и качества ответов.
- [ ] Фиксируются фактические расходы/quota по OpenAI и Gemini.

## After 1-2 weeks

- [ ] Собраны 2-3 сценария использования.
- [ ] Понятно, стоит ли развивать OpenWebUI дальше.
- [ ] Принято решение: развивать, расширять только отдельным PRD или остановить.
