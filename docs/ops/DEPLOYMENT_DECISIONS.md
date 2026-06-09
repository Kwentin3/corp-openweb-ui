# Deployment Decisions

## Назначение

Перед bootstrap/deploy PRD-0 нужно явно закрыть операторские решения. До этого пакет готов как инженерный skeleton, но фактический запуск не должен начинаться.

## Closed decisions

| Decision | Status | Current value | Where applied |
| --- | --- | --- | --- |
| Domain | Decided | `gpt.alpha-soft.ru` | `.env`: `OPENWEBUI_HOST`, Traefik labels |
| API providers | Decided | OpenAI + Gemini | Provider runbook, Admin UI |
| Gateway | Decided | LiteLLM/model gateway не добавляется в PRD-0 | PRD, blueprint, compose |
| Provider setup path | Decided | Один provider через `.env`, второй через Admin UI | `.env.example`, provider runbook |
| Low-cost customization | Decided | Только env/Admin UI: `WEBUI_NAME`, `WEBUI_BANNERS`, signup/access settings | `.env.example`, compose, acceptance |
| Instance name | Decided | `Alpha Soft AI Chat` unless operator confirms another soft instance name | `.env`: `WEBUI_NAME` |
| Warning banner | Decided | Security warning banner, `type=warning`, `dismissible=true` | `.env`: `WEBUI_BANNERS` |
| No white-label/fork | Decided | No fork, logo change, custom frontend, plugins or tools/functions | PRD, blueprint |
| Host hardening | Decided | UFW + fail2ban | hardening runbook, acceptance |
| Public ports | Decided | `22/tcp`, `80/tcp`, `443/tcp` | firewall runbook |
| OpenWebUI image tag | Proposed | `ghcr.io/open-webui/open-webui:v0.9.6`; не `:main` для пилота. | `.env`: `OPENWEBUI_IMAGE` |
| Traefik image tag | Proposed | `traefik:v3.6`. | `.env`: `TRAEFIK_IMAGE` |
| Public repo personal data | Decided | Не хранить реальные имена, SSH endpoint, public IP, секреты. | docs and `.gitignore` |
| Post-bootstrap password rotation | Decided | Не blocker PRD-0; можно сделать после стабилизации пилота. | security minimum, acceptance |

## Operator decisions required

| Decision | Required value | Where applied | Notes |
| --- | --- | --- | --- |
| Primary provider via `.env` | `OpenAI` or `Gemini` | `.env`: `OPENAI_API_BASE_URL`, `OPENAI_API_KEY`, optional `DEFAULT_MODELS` | Recommendation for PRD-0 skeleton: OpenAI primary, Gemini secondary, unless operator prefers the reverse. |
| Secondary provider via Admin UI | Provider not used as primary | OpenWebUI Admin UI | Use [PROVIDER_SETUP_RUNBOOK.md](PROVIDER_SETUP_RUNBOOK.md). |
| OpenAI API key | Real server/operator secret | `.env` if OpenAI primary, otherwise Admin UI | Must not be committed. |
| Gemini API key | Real server/operator secret | `.env` if Gemini primary, otherwise Admin UI | Must not be committed. |
| Exact OpenAI model id | Operator-selected model id | `.env` optional `DEFAULT_MODELS` or Admin UI Model IDs | Check quota and model access first. |
| Exact Gemini model id | Operator-selected model id | `.env` optional `DEFAULT_MODELS` or Admin UI Model IDs | `gemini-2.5-flash` is a documented Google example, not a forced PRD-0 decision. |
| Let's Encrypt email | Technical email | `.env`: `LETSENCRYPT_EMAIL` | Avoid personal random address. |
| First administrator email | Work email | `.env`: `WEBUI_ADMIN_EMAIL` | Bootstrap works only on fresh DB. |
| First administrator password | Strong temporary password | `.env`: `WEBUI_ADMIN_PASSWORD` | Keep only server-local/password manager. |
| Backup retention | Days and location | server-local backup policy | Minimum 7-14 days is reasonable for pilot if no other policy exists. |
| Operator current public IP | IP or CIDR for fail2ban ignore list, if needed | `/etc/fail2ban/jail.d/sshd.local` | Keep local-only; do not commit. |

## Provider endpoints

| Provider | Base URL | Model id | Source |
| --- | --- | --- | --- |
| OpenAI | `https://api.openai.com/v1` | operator-selected exact id | OpenAI API docs and OpenWebUI OpenAI connection docs |
| Gemini OpenAI compatibility | `https://generativelanguage.googleapis.com/v1beta/openai` | operator-selected exact id | Gemini OpenAI compatibility docs |

## Stop condition

Если хотя бы одно required decision не закрыто, выполнять только документационные работы, preflight и read-only checks. Не запускать production-like deploy.
