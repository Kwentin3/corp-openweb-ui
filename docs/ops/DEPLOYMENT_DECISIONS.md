# Deployment Decisions

## Назначение

Документ фиксирует закрытые решения PRD-0, текущий deployment status и оставшиеся operator actions. Реальные secrets, SSH endpoints, public IP и пользовательские данные не коммитятся.

## Current deployment status

Актуально на 2026-06-09:

- target `gpt.alpha-soft.ru` поднят;
- Traefik и OpenWebUI запущены;
- OpenWebUI healthy;
- strict TLS smoke проходит;
- UFW/fail2ban hardening проходит в strict mode;
- OpenAI primary через `gpt-5.4-mini` отвечает через OpenWebUI API;
- direct provider egress с сервера блокировался provider region policy, поэтому включен HTTP-to-SOCKS bridge;
- backup script отработал.

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
| OpenWebUI image tag | Decided | `ghcr.io/open-webui/open-webui:v0.9.6`; не `:main` для пилота. | `.env`: `OPENWEBUI_IMAGE` |
| Traefik image tag | Decided | `traefik:v3.6`. | `.env`: `TRAEFIK_IMAGE` |
| Provider outbound proxy | Decided | OpenWebUI получает HTTP proxy env; SOCKS5 используется только за host-local HTTP-to-SOCKS bridge | `.env`, provider runbook |
| Public repo personal data | Decided | Не хранить реальные имена, SSH endpoint, public IP, секреты. | docs and `.gitignore` |
| Let's Encrypt email | Decided | `kwentin3@mail.ru` | `.env`: `LETSENCRYPT_EMAIL` |
| Backup retention | Decided | `BACKUP_RETENTION_DAYS=7`; allowed pilot choices are `1`, `7`, `30` days | `.env.example`, backup runbook |
| Post-bootstrap password rotation | Decided | Не blocker PRD-0; можно сделать после стабилизации пилота. | security minimum, acceptance |

## Operator actions and secret ownership

| Item | Status | Where applied | Notes |
| --- | --- | --- | --- |
| OpenAI API key | Configured server-local secret | `.env`: `OPENAI_API_KEY` | Must not be committed; rotate if it was exposed outside password manager. |
| SOCKS5 upstream credentials | Configured server-local secret | `.env`: `OPENWEBUI_SOCKS5_UPSTREAM`, Privoxy config | Must not be committed; rotate if they were exposed outside password manager. |
| Gemini API key | Pending operator action | OpenWebUI Admin UI secondary connection | Must not be committed. |
| First administrator email/password | Configured server-local secret | `.env`: `WEBUI_ADMIN_EMAIL`, `WEBUI_ADMIN_PASSWORD` | Password rotation after bootstrap is recommended after stabilization. |
| Pilot users | Pending operator action | OpenWebUI Admin UI | Create or activate 3-4 users before full pilot acceptance. |
| Operator current public IP | Optional local-only decision | `/etc/fail2ban/jail.d/sshd.local` | Keep local-only; do not commit. |

## Provider endpoints

| Provider | Base URL | Model id | Source |
| --- | --- | --- | --- |
| OpenAI | `https://api.openai.com/v1` | `gpt-5.4-mini` | OpenAI API docs and OpenWebUI OpenAI connection docs |
| Gemini OpenAI compatibility | `https://generativelanguage.googleapis.com/v1beta/openai` | `gemini-3.5-flash` | Gemini model docs and Gemini OpenAI compatibility docs |

## Stop condition

Не считать PRD-0 полностью принятым для пилота, пока не закрыты:

- 3-4 pilot users;
- Gemini secondary provider или явное решение оставить его pending из-за API key/quota/billing/region;
- post-chat/password-manager rotation для секретов, которые передавались вне защищенного канала.
