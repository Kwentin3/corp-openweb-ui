# OpenWebUI PRD-0 Operator Inputs, Model IDs and Backup Retention Report

Дата: 2026-06-09
Статус: local changes prepared, not committed

## Summary

По операторскому вводу обновлены `.env.example`, deployment/runbook docs, acceptance docs и backup/preflight scripts.

Зафиксированы решения:

- Let's Encrypt email: `kwentin3@mail.ru`;
- primary provider через `.env`: OpenAI;
- primary OpenAI model id: `gpt-5.4-mini`;
- secondary provider через OpenWebUI Admin UI: Gemini;
- secondary Gemini stable model id: `gemini-3.5-flash`;
- если оператор намеренно тестирует Gemini 3 Flash Preview, точный model id: `gemini-3-flash-preview`;
- backup retention default: `BACKUP_RETENTION_DAYS=7`;
- допустимые pilot retention values: `1`, `7`, `30` days.

Scope PRD-0 не расширен: fork, white-label, frontend patches, plugins, tools/functions, LiteLLM, model gateway, RAG и web search не добавлены.

## User Inputs Applied

| Input | Applied decision | Location |
| --- | --- | --- |
| Let's Encrypt email | `kwentin3@mail.ru` | `.env.example`, deployment decisions/runbook |
| Primary provider API key | Added explicit `.env.example` section with placeholder `OPENAI_API_KEY=replace-with-openai-api-key` | `.env.example` |
| OpenAI model name | `gpt-5.4-mini` | `.env.example`, provider docs, acceptance docs |
| Gemini model name | `gemini-3.5-flash` stable for PRD-0 secondary; `gemini-3-flash-preview` documented as preview exact id | provider docs/runbook |
| Secondary provider confusion | Clarified that OpenAI + Gemini are selected; Admin UI is only the second provider configuration path | provider docs/runbook |
| Backup retention | `BACKUP_RETENTION_DAYS=7`, allowed `1`, `7`, `30` | `.env.example`, backup runbook, backup script |

## Official Model Verification

OpenAI:

- Checked official OpenAI API model page: `https://developers.openai.com/api/docs/models/gpt-5.4-mini`.
- The model page names the model `GPT-5.4 mini`.
- The model alias/snapshot section lists `gpt-5.4-mini` and `gpt-5.4-mini-2026-03-17`.
- Applied PRD-0 primary model id: `gpt-5.4-mini`.

Gemini:

- Checked official Google AI Gemini models page: `https://ai.google.dev/gemini-api/docs/models`.
- Checked official Gemini 3.5 Flash page: `https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash`.
- Google lists model code `gemini-3.5-flash` as stable.
- The same page lists preview variant `gemini-3-flash-preview`.
- Checked Gemini OpenAI compatibility docs: `https://ai.google.dev/gemini-api/docs/openai`.
- Google OpenAI-compatible examples use base URL `https://generativelanguage.googleapis.com/v1beta/openai/` and model `gemini-3.5-flash`.

Conclusion:

- `gpt-5.4-mini` is the correct OpenAI API model id for the user's "GPT 5.4 mini" input.
- `gemini-3-flash` is not used as the exact PRD-0 model id.
- Stable Gemini choice for PRD-0 is `gemini-3.5-flash`.
- Exact preview code for "Gemini 3 Flash" is `gemini-3-flash-preview`.

## `.env.example` Changes

Added clear sections:

- public endpoint / TLS;
- image tags;
- low-cost built-in customization;
- primary provider through `.env`: OpenAI;
- secondary provider through Admin UI: Gemini;
- server secrets;
- admin bootstrap;
- PRD-0 access defaults;
- backup.

Active provider values:

```env
OPENAI_API_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=replace-with-openai-api-key
DEFAULT_MODELS=gpt-5.4-mini
```

Secondary provider is documented but not active in `.env.example`:

```env
# Admin UI base URL: https://generativelanguage.googleapis.com/v1beta/openai
# Admin UI model id: gemini-3.5-flash
# If testing Gemini 3 Flash Preview specifically: gemini-3-flash-preview
```

This keeps real Gemini API key out of Git and avoids multi-value env ordering.

Backup values:

```env
BACKUP_DIR=/opt/backups/openwebui-prd0
BACKUP_RETENTION_DAYS=7
```

## Secondary Provider Explanation

The "secondary provider via Admin UI" point is not a blocker and not an undecided provider choice.

Selected provider set:

- OpenAI;
- Gemini.

Selected configuration path:

- OpenAI primary is configured through server-local `.env`;
- Gemini secondary is configured in OpenWebUI Admin UI after admin login.

Reason:

- PRD-0 does not need provider routing, gateway, budgets or per-user provider rules.
- Multi-provider env variables such as `OPENAI_API_BASE_URLS` and `OPENAI_API_KEYS` create an ordering contract between URLs and keys.
- OpenWebUI stores part of provider configuration as persistent config; Admin UI is the clearer path for the second connection in this pilot.
- This keeps the skeleton simple, reversible and aligned with the no-fork/no-code-customization rule.

## Backup Retention Implementation

Updated `scripts/backup.sh`:

- reads `BACKUP_DIR` and `BACKUP_RETENTION_DAYS` from process environment or server-local `.env`;
- validates that `BACKUP_RETENTION_DAYS` is numeric and `>= 1`;
- creates backups with `umask 077`;
- prunes only known backup artifacts in `BACKUP_DIR`:
  - `openwebui_data-*.tgz`;
  - `traefik_letsencrypt-*.tgz`;
  - `env-*.backup`.

No scheduler was added. Operator can run backup manually or wire the existing script into cron/systemd outside PRD-0 skeleton.

Updated `scripts/preflight.sh`:

- validates `BACKUP_RETENTION_DAYS` when present;
- reports accepted retention value.

## Documentation Updated

Changed files:

- `.env.example`;
- `scripts/backup.sh`;
- `scripts/preflight.sh`;
- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_0.md`;
- `docs/blueprint/OPENWEBUI_PRD_0_BLUEPRINT.md`;
- `docs/infra/ENVIRONMENT_VARIABLES.md`;
- `docs/infra/PROVIDER_CONNECTIONS_PLAN.md`;
- `docs/ops/DEPLOYMENT_DECISIONS.md`;
- `docs/ops/DEPLOYMENT_RUNBOOK.md`;
- `docs/ops/PROVIDER_SETUP_RUNBOOK.md`;
- `docs/ops/BACKUP_RESTORE_RUNBOOK.md`;
- `docs/ops/ACCEPTANCE_TESTS.md`;
- `docs/pilot/PILOT_CHECKLIST.md`;
- `docs/requirements/ACCEPTANCE_CRITERIA.md`.

Main documentation effects:

- PRD now states OpenAI primary and Gemini secondary.
- Blueprint now states concrete model ids and backup retention.
- Provider docs explain why Gemini is configured through Admin UI.
- Deployment decisions no longer list primary/secondary provider or exact model ids as open questions.
- Acceptance docs no longer treat the second provider as pending because of undecided model choice.
- Backup restore runbook now documents `1`, `7`, `30` retention choices.

## Verification

Commands run locally:

```powershell
& "$env:TEMP\docker-compose-standalone.exe" --env-file .env.example -f compose/openwebui.compose.yml config
```

Result: passed.

Important rendered values:

- Traefik ACME email: `kwentin3@mail.ru`;
- OpenWebUI `DEFAULT_MODELS`: `gpt-5.4-mini`;
- OpenWebUI `WEBUI_BANNERS`: valid JSON string rendered correctly;
- `WEBUI_NAME`: `Alpha Soft AI Chat`.

```powershell
$banner = $map['WEBUI_BANNERS'] | ConvertFrom-Json
```

Result: passed.

Validated:

- `WEBUI_BANNERS` parses as JSON;
- first banner type is `warning`;
- first banner is `dismissible=true`;
- `DEFAULT_MODELS=gpt-5.4-mini`;
- `BACKUP_RETENTION_DAYS=7`.

```powershell
& 'C:\Program Files\Git\bin\bash.exe' -n scripts/preflight.sh scripts/backup.sh scripts/smoke-test.sh scripts/network-hardening-check.sh
```

Result: passed.

```powershell
git diff --check
```

Result: passed. Git printed CRLF warnings only; no whitespace errors.

## Environment Notes

Local `docker compose` plugin is not available:

```text
docker: 'compose' is not a docker command.
```

Standalone Docker Compose was available and used:

```text
Docker Compose version v5.1.4
```

System `C:\Windows\System32\bash.exe` is a WSL shim and failed in this environment. Git Bash was available and used for `bash -n`.

## Not Verified Yet

These checks require real secrets, server-local `.env` or live provider access:

- actual OpenAI API request with `gpt-5.4-mini`;
- actual Gemini API request with `gemini-3.5-flash`;
- full `scripts/preflight.sh` against real `.env`;
- full deployment compose up on server;
- OpenWebUI Admin UI secondary provider save/test;
- backup script end-to-end against real Docker volumes.

## Remaining Operator Inputs

Still required before production-like start:

- real `OPENAI_API_KEY` in server-local `.env`;
- real Gemini API key in OpenWebUI Admin UI;
- generated `WEBUI_SECRET_KEY`;
- first admin email;
- first admin password;
- billing/quota/region confirmation for OpenAI;
- billing/quota/region confirmation for Gemini;
- operator public IP or CIDR only if fail2ban ignore list is needed.

The committed example still intentionally contains placeholders for secrets and admin bootstrap values.

## Security Notes

- No real provider API key was added to Git.
- No admin password was added to Git.
- `.env.example` now contains the provided Let's Encrypt email. It is not an API secret, but it is still a real contact address in a public repository. Replace it with an operations alias before commit if that address should not be public.
- Gemini API key is intentionally not represented as an active `.env.example` variable because PRD-0 uses Admin UI for the secondary connection.
- Backup artifacts remain secret-bearing because they can include `.env` and OpenWebUI persistent provider configuration.

## Scope Control

No additional product/platform scope was added.

Not added:

- fork OpenWebUI;
- logo replacement;
- white-label;
- frontend code changes;
- custom frontend;
- plugins;
- tools/functions;
- document skills;
- Hermes;
- LiteLLM;
- model gateway;
- RAG;
- web search.

The customization path remains low-cost, built-in and reversible: env/Admin UI only.
