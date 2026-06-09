# OpenWebUI PRD-0 REFINE-2: Providers And Host Hardening

Дата: 2026-06-09

## Что проверено

- PRD-0, blueprint, scope, requirements, infra/ops/security docs.
- `.env.example`, compose env contract, preflight and smoke scripts.
- OpenWebUI provider connection path for OpenAI-compatible APIs.
- Gemini OpenAI compatibility endpoint.
- OpenAI API endpoint contract.
- Ubuntu UFW and fail2ban operational commands.
- Placeholder and out-of-scope grep audit across repo.

Deploy в рамках REFINE-2 не выполнялся.

## Официальные источники

- OpenWebUI env reference: https://docs.openwebui.com/reference/env-configuration/
- OpenWebUI OpenAI-compatible connections: https://docs.openwebui.com/getting-started/quick-start/connect-a-provider/starting-with-openai-compatible/
- OpenWebUI Starting with OpenAI: https://docs.openwebui.com/getting-started/quick-start/starting-with-openai/
- Google Gemini OpenAI compatibility: https://ai.google.dev/gemini-api/docs/openai
- OpenAI API reference: https://platform.openai.com/docs/api-reference/chat/create
- Docker Engine on Ubuntu: https://docs.docker.com/engine/install/ubuntu/
- Ubuntu firewall docs: https://documentation.ubuntu.com/server/how-to/security/firewalls/
- Ubuntu UFW docs: https://help.ubuntu.com/community/UFW
- Ubuntu fail2ban-client manpage: https://manpages.ubuntu.com/manpages/jammy/man1/fail2ban-client.1.html
- Traefik Docker provider: https://doc.traefik.io/traefik/v3.3/providers/docker/
- Traefik ACME resolver: https://doc.traefik.io/traefik/v3.6/reference/install-configuration/tls/certificate-resolvers/acme/

## Provider decision

PRD-0 теперь фиксирует два provider:

- OpenAI: `https://api.openai.com/v1`;
- Gemini OpenAI compatibility: `https://generativelanguage.googleapis.com/v1beta/openai`.

Skeleton использует консервативный путь:

- primary provider через server-local `.env`;
- secondary provider через OpenWebUI Admin UI.

Multi-provider env через `OPENAI_API_BASE_URLS`/`OPENAI_API_KEYS` не выбран для skeleton PRD-0, потому что порядок URL/key становится скрытым контрактом, а часть OpenWebUI настроек сохраняется как persistent config. Это не нужно для фазы смотрин без routing/budgets/per-user limits.

Для Gemini runbook использует endpoint без trailing slash. Google SDK examples показывают slash в конце base URL, но для OpenWebUI connection в этом пакете оставлено одно нормализованное значение без альтернатив.

## Добавлено

- [../../infra/PROVIDER_CONNECTIONS_PLAN.md](../../infra/PROVIDER_CONNECTIONS_PLAN.md)
- [../../ops/PROVIDER_SETUP_RUNBOOK.md](../../ops/PROVIDER_SETUP_RUNBOOK.md)
- [../../security/FIREWALL_AND_FAIL2BAN.md](../../security/FIREWALL_AND_FAIL2BAN.md)
- [../../ops/HOST_HARDENING_RUNBOOK.md](../../ops/HOST_HARDENING_RUNBOOK.md)
- [../../../scripts/network-hardening-check.sh](../../../scripts/network-hardening-check.sh)

## Обновлено

- PRD и blueprint отражают OpenAI + Gemini без отдельного gateway.
- `.env.example` оставлен только для primary provider; secondary provider направлен в Admin UI.
- `DEPLOYMENT_DECISIONS.md` разделяет closed decisions и operator decisions.
- `DEPLOYMENT_RUNBOOK.md` получил порядок: DNS, SSH, Docker, host hardening, clone, `.env`, decisions, preflight, compose, strict TLS, admin/users, providers, LLM response, persistence, backup.
- Acceptance/smoke/security docs включают UFW, fail2ban, `sshd` jail, provider checks и non-blocker password rotation.
- Requirements docs переведены с прежнего контекста на OpenWebUI PRD-0.
- Backup/restore теперь учитывает, что provider secrets могут оказаться в `openwebui_data`, если secondary provider добавлен через Admin UI.

## Placeholders

Удалены или заменены:

- прежний sample chat domain;
- старые формулировки "один provider" в PRD-0 path;
- буквальный placeholder model id;
- прежние requirements в активных `docs/requirements/*`;
- противоречивый Gemini endpoint со slash в docs.

Оставлены осознанно:

- API keys: реальные значения должны быть только server-local/Admin UI;
- `WEBUI_SECRET_KEY`: генерируется оператором;
- admin email/password: требуются для bootstrap;
- Let's Encrypt email: operator decision;
- exact OpenAI/Gemini model ids: operator decision;
- backup retention: operator decision;
- SSH endpoint/public IP/operator IP: local-only, не для Git.

## Host hardening

Добавлен минимальный target:

- UFW active;
- default deny incoming / allow outgoing;
- allow `22/tcp`, `80/tcp`, `443/tcp`;
- fail2ban active;
- `sshd` jail active;
- команда unban для ошибочного fail2ban ban.

`scripts/network-hardening-check.sh` является read-only проверкой и не меняет firewall/fail2ban.

## Operator decisions remain

- Primary provider through `.env`: OpenAI or Gemini.
- Secondary provider through Admin UI.
- OpenAI API key.
- Gemini API key.
- Exact OpenAI model id.
- Exact Gemini model id.
- Let's Encrypt email.
- First admin email/password.
- Backup retention.
- Operator current public IP for fail2ban ignore list, if needed.

## Readiness

Пакет готов к отдельной задаче bootstrap/deploy после закрытия operator decisions и заполнения server-local `.env`.

Перед фактическим запуском нужно выполнить hardening runbook, preflight, provider setup runbook и acceptance checks. REFINE-2 не авторизует deploy.

## Валидация

- `git diff --check`: прошел без whitespace errors; Git показал только локальные CRLF warnings.
- `bash -n scripts/preflight.sh scripts/backup.sh scripts/smoke-test.sh scripts/network-hardening-check.sh`: прошел.
- YAML parse `compose/openwebui.compose.yml`: прошел, services `openwebui`, `traefik`.
- `scripts/smoke-test.sh --help`: прошел, usage показывает `--strict-tls`.
- `scripts/preflight.sh` на временной `.env`, созданной из `.env.example`: exit 1 только на placeholder values до Docker-check.
- `scripts/network-hardening-check.sh` локально в Git Bash: exit 0, expected warnings из-за отсутствия UFW/fail2ban/ss в Windows-среде.
- Secret scan по коммитимым файлам: реальных API keys/private keys/token/password assignments не найдено.
- Public endpoint scan: точный SSH endpoint/public IP не найден; найден только loopback range в fail2ban example.
- Старые placeholder scan: sample chat domain, literal model-id placeholder и Gemini slash endpoint в docs не найдены.
- Out-of-scope scan: в OpenWebUI PRD-0 path упоминания остались как Non-goals, closed decisions или future/deferred work. REFINE-3 удаляет устаревшие документы из репозитория.
