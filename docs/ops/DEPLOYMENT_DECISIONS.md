# Deployment Decisions

## Назначение

Перед bootstrap/deploy PRD-0 нужно явно закрыть операторские решения. До этого пакет готов как инженерный skeleton, но фактический запуск не должен начинаться.

## Closed decisions

| Decision | Status | Current value | Where applied |
| --- | --- | --- | --- |
| Domain | Decided | `gpt.alpha-soft.ru` | `.env`: `OPENWEBUI_HOST`, Traefik labels |
| API providers | Decided | OpenAI + Gemini | Provider runbook, Admin UI |
| Gateway | Decided | LiteLLM/model gateway не добавляется в PRD-0 | PRD, blueprint, compose |
| Provider setup path | Decided | OpenAI primary через `.env`, Gemini secondary через Admin UI | `.env.example`, provider runbook |
| OpenAI model id | Decided | `gpt-5.4-mini` | `.env`: `DEFAULT_MODELS` |
| Gemini model id | Decided | `gemini-3.5-flash` for secondary Admin UI; use `gemini-3-flash-preview` only for explicit Gemini 3 Flash Preview testing | provider runbook |
| Low-cost customization | Decided | Только env/Admin UI: `WEBUI_NAME`, `WEBUI_BANNERS`, signup/access settings | `.env.example`, compose, acceptance |
| Instance name | Decided | `Alpha Soft AI Chat` unless operator confirms another soft instance name | `.env`: `WEBUI_NAME` |
| Warning banner | Decided | Security warning banner, `type=warning`, `dismissible=true` | `.env`: `WEBUI_BANNERS` |
| No white-label/fork | Decided | No fork, logo change, custom frontend, plugins or tools/functions | PRD, blueprint |
| Host hardening | Decided | UFW + fail2ban | hardening runbook, acceptance |
| Public ports | Decided | `22/tcp`, `80/tcp`, `443/tcp` | firewall runbook |
| OpenWebUI image tag | Proposed | `ghcr.io/open-webui/open-webui:v0.9.6`; не `:main` для пилота. | `.env`: `OPENWEBUI_IMAGE` |
| Traefik image tag | Proposed | `traefik:v3.6`. | `.env`: `TRAEFIK_IMAGE` |
| Public repo personal data | Decided | Не хранить реальные имена, SSH endpoint, public IP, секреты. | docs and `.gitignore` |
| Let's Encrypt email | Decided | `kwentin3@mail.ru` | `.env`: `LETSENCRYPT_EMAIL` |
| Backup retention | Decided | `BACKUP_RETENTION_DAYS=7`; allowed pilot choices are `1`, `7`, `30` days | `.env.example`, backup runbook |
| Post-bootstrap password rotation | Decided | Не blocker PRD-0; можно сделать после стабилизации пилота. | security minimum, acceptance |

## Operator decisions required

| Decision | Required value | Where applied | Notes |
| --- | --- | --- | --- |
| OpenAI API key | Real server/operator secret | `.env`: `OPENAI_API_KEY` | Must not be committed. |
| Gemini API key | Real server/operator secret | OpenWebUI Admin UI secondary connection | Must not be committed. |
| First administrator email | Work email | `.env`: `WEBUI_ADMIN_EMAIL` | Bootstrap works only on fresh DB. |
| First administrator password | Strong temporary password | `.env`: `WEBUI_ADMIN_PASSWORD` | Keep only server-local/password manager. |
| Operator current public IP | IP or CIDR for fail2ban ignore list, if needed | `/etc/fail2ban/jail.d/sshd.local` | Keep local-only; do not commit. |

## Provider endpoints

| Provider | Base URL | Model id | Source |
| --- | --- | --- | --- |
| OpenAI | `https://api.openai.com/v1` | `gpt-5.4-mini` | OpenAI API docs and OpenWebUI OpenAI connection docs |
| Gemini OpenAI compatibility | `https://generativelanguage.googleapis.com/v1beta/openai` | `gemini-3.5-flash` | Gemini model docs and Gemini OpenAI compatibility docs |

## Stop condition

Если API keys, первый admin email/password или local-only operator IP decision не закрыты, выполнять только документационные работы, preflight и read-only checks. Не запускать production-like deploy.
