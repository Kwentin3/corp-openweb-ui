# Deployment Decisions

## Назначение

Перед bootstrap/deploy PRD-0 нужно явно закрыть операторские решения. До этого пакет готов как инженерный skeleton, но фактический запуск не должен начинаться.

## Decisions

| Decision | Status | Current recommendation | Where applied |
| --- | --- | --- | --- |
| API provider | Operator decision required | Выбрать OpenAI-compatible provider. Для Gemini использовать официальный OpenAI-compatible endpoint только после проверки quota/region. | `.env`: `OPENAI_API_BASE_URL`, `OPENAI_API_KEY` |
| Default model id | Operator decision required | Оставить `DEFAULT_MODELS=` пустым до выбора точного model id. | `.env`: `DEFAULT_MODELS` |
| Let's Encrypt email | Operator decision required | Использовать рабочий технический email, не личный случайный адрес. | `.env`: `LETSENCRYPT_EMAIL` |
| OpenWebUI image tag | Proposed | `ghcr.io/open-webui/open-webui:v0.9.6`; не `:main` для пилота. | `.env`: `OPENWEBUI_IMAGE` |
| Traefik image tag | Proposed | `traefik:v3.6`. | `.env`: `TRAEFIK_IMAGE` |
| Public repo personal data | Decided | Не хранить реальные имена, SSH endpoint, public IP, секреты. | docs and `.gitignore` |
| Backup retention | Operator decision required | Минимум 7-14 дней для пилота, если нет другой политики. | server-local backup policy |
| First administrator | Operator decision required | Указать рабочий email администратора. Bootstrap работает только на fresh DB. | `.env`: `WEBUI_ADMIN_EMAIL`, `WEBUI_ADMIN_PASSWORD` |

## Provider examples

| Provider | Base URL | Example model id | Source |
| --- | --- | --- | --- |
| OpenAI-compatible default | `https://api.openai.com/v1` | operator-selected | OpenWebUI env reference default |
| Gemini OpenAI compatibility | `https://generativelanguage.googleapis.com/v1beta/openai/` | `gemini-2.5-flash` | Google Gemini OpenAI compatibility docs |

## Stop condition

Если хотя бы одно required decision не закрыто, выполнять только документационные работы и preflight. Не запускать production-like deploy.
