# OpenWebUI PRD-0 Post-Acceptance Audit

Дата аудита: 2026-06-16
Репозиторий: `corp-openweb-ui`
Цель: зафиксировать baseline после приемки PRD-0 и подготовить контекст для обсуждения Stage 2.

## 1. Executive summary

PRD-0 принят заказчиком и в продуктовой логике закрыт. Этот аудит не спорит с приемкой. Он фиксирует, что именно есть в репозитории, какие факты подтверждены текущей проверкой, какие подтверждены historical deployment reports, а какие остаются operator actions перед дальнейшим развитием.

Короткий вывод: PRD-0 можно считать закрытым как нулевую фазу "дать 3-4 людям корпоративную точку входа в LLM-чат на OpenWebUI". Репозиторий содержит PRD, blueprint, compose, `.env.example`, runbooks, security/pilot docs и отчеты о deploy/proxy verification. Текущая внешняя проверка на 2026-06-16 подтвердила, что `gpt.alpha-soft.ru` резолвится, HTTP редиректит на HTTPS, HTTPS отвечает без `curl -k`.

При этом текущий аудит не выполнял SSH-вход на сервер и не перечитывал server-local `.env`. Поэтому состояние контейнеров, UFW, fail2ban, volume, backup artifacts, Gemini secondary provider и 3-4 pilot users сейчас классифицируются не как independently verified today, а как historical evidence / accepted / needs operator confirmation.

Scope PRD-0 в документах удержан консервативно: без LiteLLM, model gateway, routing, budget control, RAG, web search, document skills, plugins, fork OpenWebUI и custom frontend. Наличие research-документа по web search не расширяет PRD-0: сам документ помечает web search как non-goal и candidate for Stage 2.

## 2. Что было целью PRD-0

PRD-0 был фазой смотрин, а не финальной AI-платформой. Простыми словами: поднять OpenWebUI на домене `gpt.alpha-soft.ru`, подключить LLM-провайдеров через штатные механизмы OpenWebUI, создать небольшую пилотную группу и проверить, нужен ли сотрудникам единый корпоративный LLM-чат.

Целевой результат:

- OpenWebUI доступен по HTTPS;
- вход через домен `gpt.alpha-soft.ru`;
- Traefik отвечает за внешний HTTPS ingress;
- OpenAI выбран primary provider через server-local `.env`;
- Gemini выбран secondary provider через Admin UI;
- есть администратор и 3-4 пользователя;
- публичная регистрация закрыта или ограничена;
- история чатов сохраняется;
- есть warning banner о запрете отправки секретов и закрытых персональных данных;
- есть минимальный host hardening, backup, runbook, smoke и acceptance checks.

Важная граница: self-hosted OpenWebUI не означает локальные модели. Модели остаются внешними API-провайдерами.

## 3. Что фактически собрано в репозитории

### Git/repository state

Проверено локально 2026-06-16:

- ветка: `main`;
- upstream: `origin/main`;
- последний commit: `239a281 Document OpenWebUI web search provider research`;
- tracked worktree на момент проверки чистый;
- untracked files через `git ls-files --others --exclude-standard` не найдены;
- локальный `.env` присутствует на диске, но игнорируется `.gitignore` и в рамках аудита не читался;
- `local/` также игнорируется и предназначен для operator-only target details.

Локальная валидация:

- `git diff --check` прошел;
- `bash -n` для `scripts/preflight.sh`, `scripts/backup.sh`, `scripts/smoke-test.sh`, `scripts/network-hardening-check.sh` прошел через Git Bash;
- системный `bash` в Windows оказался WSL shim и не пригоден для проверки;
- локальный `docker compose` plugin отсутствует, поэтому текущий `docker compose config` в этом аудите не запускался;
- текстовый contract check compose подтвердил наличие `traefik`, `openwebui`, `80:80`, `443:443`, `openwebui_data`, `traefik_letsencrypt`, provider/env/security переменных.

### Canonical source of truth

Главные документы для PRD-0:

- `README.md` - входная навигация и короткий scope;
- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_0.md` - продуктовый scope и критерии готовности;
- `docs/blueprint/OPENWEBUI_PRD_0_BLUEPRINT.md` - инженерная рамка;
- `docs/blueprint/ARCHITECTURE_OVERVIEW.md` - текущие runtime/data/network boundaries;
- `docs/blueprint/SCOPE_AND_NON_GOALS.md` - явные non-goals;
- `docs/ops/DEPLOYMENT_DECISIONS.md` - закрытые решения, текущий deployment status и operator actions;
- `docs/infra/INFRA_TARGET.md` - sanitized deployment summary;
- `docs/ops/ACCEPTANCE_TESTS.md` - acceptance checklist.

Вторичные, но полезные документы:

- `docs/infra/*` - endpoint, compose, provider, env, storage details;
- `docs/ops/*` - runbooks и smoke/restore/update flows;
- `docs/security/*` - минимальный security baseline;
- `docs/pilot/*` - onboarding, pilot checklist, feedback form;
- `docs/requirements/*` - дополнительные критерии, синхронизированные с PRD-0;
- `docs/decisions/ADR-0004-traefik-ingress.md` - ADR по Traefik ingress;
- `docs/reports/2026-06-09/*` - historical evidence и chronology.

Документы, которые могут ввести в заблуждение перед Stage 2:

- `reports/REPO_PREFLIGHT.report.md` относится к `corp-hermes`, а не к текущему OpenWebUI PRD-0. Его нельзя использовать как источник истины для Stage 2 OpenWebUI.
- `deploy/hermes-corporate-v1/*` и root `runbooks/*_PLACEHOLDER.md` выглядят как остатки/placeholder другого контура. Они не должны смешиваться с OpenWebUI PRD-0 без отдельного решения.
- `docs/infra/WEB_SEARCH_PROVIDER_RESEARCH.md` актуален как research, но web search прямо оставлен вне PRD-0. Это candidate for Stage 2, не выполненная часть PRD-0.

## 4. Архитектура простыми словами

Текущая схема:

```text
Пользователь
  -> https://gpt.alpha-soft.ru
  -> Traefik
  -> OpenWebUI
  -> OpenAI API / Gemini OpenAI-compatible API
```

С учетом provider egress bridge из deployment report:

```text
OpenWebUI
  -> host-local HTTP proxy bridge
  -> SOCKS5 upstream
  -> OpenAI API / Gemini API
```

Что где находится:

- OpenWebUI работает в Docker container и обслуживает UI, локальных пользователей, чаты, настройки и provider connections.
- Traefik работает отдельным контейнером, принимает внешний HTTP/HTTPS, выпускает Let's Encrypt certificate и проксирует запросы внутрь Docker network к OpenWebUI.
- Self-hosted часть заканчивается на OpenWebUI и proxy/ingress. Сами модели не локальные, запросы уходят во внешние API.
- Persistent данные OpenWebUI лежат в named volume `openwebui_data`, не в bind mount репозитория.
- ACME/certificate state Traefik лежит в `traefik_letsencrypt`.
- Primary provider настраивается через server-local `.env`: `OPENAI_API_BASE_URL`, `OPENAI_API_KEY`, `DEFAULT_MODELS`.
- Secondary provider настраивается через OpenWebUI Admin UI и может попасть в persistent data.
- API keys должны жить только в server-local `.env`, password manager или Admin UI. Обычным пользователям они не передаются.
- PRD-0 не использует отдельный gateway, потому что в нулевой фазе не нужны routing, budgets, per-user limits и сложное управление моделями.

## 5. PRD-0 requirement coverage matrix

| Требование | Где описано | Артефакт в репозитории | Evidence level | Статус | Комментарий |
| --- | --- | --- | --- | --- | --- |
| OpenWebUI deployment | PRD, blueprint, compose | `compose/openwebui.compose.yml`, deployment reports | Historical runtime evidence | accepted / historical confirmed | 2026-06-09 report: container recreated and healthy. Current SSH/container state not checked in this audit. |
| Домен `gpt.alpha-soft.ru` | PRD, infra target, DNS requirements | README, `docs/infra/INFRA_TARGET.md` | Current external check | confirmed | 2026-06-16 DNS resolves; exact IP intentionally not recorded in report. |
| HTTP -> HTTPS | PRD, Traefik plan, acceptance | Traefik labels, smoke script | Current external check | confirmed | 2026-06-16 `http://gpt.alpha-soft.ru/` returned `308` to HTTPS. |
| Strict TLS without `curl -k` | PRD, smoke tests | `scripts/smoke-test.sh --strict-tls` | Current external check + historical evidence | confirmed | 2026-06-16 HTTPS returned `200` with normal certificate validation from workstation. |
| Traefik ingress | blueprint, ADR, compose | `compose/openwebui.compose.yml`, ADR-0004 | Repo + historical evidence | accepted | Compose publishes `80/443`; OpenWebUI has no direct published port. Current server listeners require SSH check. |
| Docker / Docker Compose | PRD, runbooks | `BOOTSTRAP_DOCKER_UBUNTU.md`, compose | Historical runtime evidence | accepted | 2026-06-09 deployment report says Docker/Compose were installed and compose config passed. Local machine lacks compose plugin. |
| Persistent volume | PRD, compose, storage docs | `openwebui_data`, `STORAGE_AND_VOLUMES.md` | Repo + historical evidence | accepted | Compose defines volume; current volume existence on server not checked today. |
| OpenAI provider | PRD, provider plan, decisions | `.env.example`, provider runbook | Historical runtime evidence | accepted | 2026-06-09 report: OpenAI `/models`, OpenWebUI `/api/models`, chat completion with `gpt-5.4-mini` returned HTTP 200. |
| Gemini provider | PRD, provider plan | Provider runbook, `.env.example` comments | Documented / operator action | needs operator confirmation | Gemini selected as secondary path, but reports keep it as operator action unless separately entered in Admin UI. |
| Model IDs | PRD, deployment decisions | `.env.example`, provider docs | Repo evidence | confirmed for docs | OpenAI `gpt-5.4-mini`; Gemini `gemini-3.5-flash`; preview `gemini-3-flash-preview` only if explicitly testing preview. |
| Create users | PRD, runbook, pilot docs | `DEPLOYMENT_RUNBOOK.md`, `PILOT_CHECKLIST.md` | Operator action | needs operator confirmation | PRD expects 3-4 users. Reports say pilot users remained operator work. Customer acceptance may cover it, but this audit did not verify UI users. |
| Disable public signup | PRD, security docs, compose | `.env.example`, compose | Repo evidence | documented / accepted | `ENABLE_SIGNUP=false`, `DEFAULT_USER_ROLE=pending`. Current UI config can be overridden by persistent config, so needs operator confirmation if critical. |
| Chat history persistence | PRD, acceptance tests, storage docs | `openwebui_data`, restore docs | Documented / operator check | needs operator confirmation | Volume and checks exist; this audit did not login/restart OpenWebUI to verify history. |
| Warning banner | PRD, env docs, security docs | `.env.example`, compose | Repo evidence + historical config evidence | accepted | Banner JSON is present; actual current UI display needs operator/browser confirmation. |
| `WEBUI_SECRET_KEY` | PRD, env docs, compose | `.env.example`, preflight | Repo evidence | documented / accepted | Required and validated by preflight. Real value was not read. |
| `CORS_ALLOW_ORIGIN` | PRD, env docs, compose | `.env.example`, preflight | Repo evidence | documented / accepted | Example restricts origin to `https://gpt.alpha-soft.ru`. Real server value not read. |
| UFW | PRD, hardening docs | `HOST_HARDENING_RUNBOOK.md`, `network-hardening-check.sh` | Historical runtime evidence | accepted / historical confirmed | 2026-06-09 reports say strict hardening passed. Current UFW state not checked today. |
| fail2ban | PRD, hardening docs | `FIREWALL_AND_FAIL2BAN.md`, script | Historical runtime evidence | accepted / historical confirmed | 2026-06-09 reports say fail2ban/sshd jail passed. Current state not checked today. |
| Backup / restore | PRD, storage docs, runbook | `backup.sh`, `BACKUP_RESTORE_RUNBOOK.md`, `restore.md` | Historical backup evidence + documented restore | accepted / partial evidence | 2026-06-09 backup passed. Full restore drill not proven in current audit. |
| Runbooks | PRD | `docs/ops/*` | Repo evidence | confirmed | Deployment, provider, hardening, backup/restore, smoke, troubleshooting, update/rollback are present. |
| User onboarding | PRD, pilot docs | `USER_ONBOARDING.md`, feedback form | Repo evidence | documented only | Useful for pilot, but not proof users received it. |
| Smoke/acceptance checks | PRD, ops docs | `smoke-test.sh`, `ACCEPTANCE_TESTS.md` | Repo + current external + historical | accepted | Current external DNS/TLS checked; server-side full smoke requires server context. |

## 6. Acceptance evidence

### Current checks performed in this audit

Performed on 2026-06-16 from the local workstation, read-only:

- `git status --short --branch`: clean tracked tree on `main...origin/main`;
- `git log -1 --decorate --oneline`: latest commit `239a281 Document OpenWebUI web search provider research`;
- `git ls-files --others --exclude-standard`: no untracked non-ignored files;
- `git check-ignore -v .env local`: `.env` and `local/` are ignored;
- obvious secret-pattern scan over committable files: no private key/API token style hits;
- file artifact check: local `.env` exists but is ignored; no backup/key archive files found except ignored `.env`;
- `git diff --check`: passed;
- shell syntax check via Git Bash: passed;
- external DNS check for `gpt.alpha-soft.ru`: resolves to an A record; exact IP not recorded here;
- external HTTP check: HTTP returns redirect to HTTPS;
- external HTTPS strict check: HTTPS returns `200` without `curl -k`.

### Historical deployment evidence from 2026-06-09 reports

The strongest historical runtime evidence is `docs/reports/2026-06-09/OPENWEBUI_PRD_0_SOCKS5_BRIDGE_DEPLOYMENT.report.md` and the follow-up docs sync report. They record:

- compose config passed on server;
- OpenWebUI container recreated and became healthy;
- Privoxy/HTTP-to-SOCKS bridge active;
- host and container provider egress reached OpenAI `/v1/models`;
- `gpt-5.4-mini` was present in model list;
- OpenWebUI admin signin returned HTTP 200;
- `/api/models` returned HTTP 200;
- `/api/chat/completions` with `gpt-5.4-mini` returned HTTP 200 and a short answer;
- `scripts/smoke-test.sh --strict-tls` passed with HTTP 301 / HTTPS 200 at that time;
- `scripts/network-hardening-check.sh --strict` passed with no unexpected public listeners;
- `scripts/backup.sh` passed and retention pruning executed.

### Accepted but not independently verified in this audit

These facts may be true operationally and may be covered by customer acceptance, but this audit did not verify them live through Admin UI or SSH:

- current Docker container status;
- current Docker networks and published ports;
- current UFW rules;
- current fail2ban service and `sshd` jail;
- current backup artifacts and volume existence;
- current OpenWebUI admin/user list;
- current signup setting after persistent config;
- current warning banner display in browser;
- current chat history persistence after restart;
- Gemini secondary provider save/test;
- final 3-4 pilot users and their access.

## 7. Runtime/deployment evidence

Current runtime evidence in this audit is limited to public endpoint checks from outside:

| Check | Result | Evidence level |
| --- | --- | --- |
| DNS for `gpt.alpha-soft.ru` | resolves to an A record | current external confirmed |
| HTTP endpoint | returns redirect to HTTPS | current external confirmed |
| HTTPS endpoint | returns HTTP 200 with strict TLS | current external confirmed |
| OpenWebUI UI reachable | inferred from HTTPS 200 HTML response | current external limited |
| Containers | not checked via server | needs operator confirmation |
| Docker networks | not checked via server | needs operator confirmation |
| Published ports | historical strict check only | accepted but not refreshed |
| UFW/fail2ban | historical strict check only | accepted but not refreshed |
| Volume/backup | historical report only | accepted but not refreshed |
| Provider chat completion | historical OpenAI evidence only | accepted but not refreshed |

No server state was changed. No secrets were read or printed. No production commands were executed beyond public read-only HTTP/DNS checks.

## 8. Security and secrets review

Positive findings:

- `.gitignore` ignores `.env`, `.env.*`, `local/`, secret/key file patterns, backup/temp/runtime directories and archives.
- `.env.example` contains placeholders for API key, admin password and `WEBUI_SECRET_KEY`.
- Gemini key is intentionally not represented as an active `.env.example` variable because PRD-0 uses Admin UI for secondary provider.
- `compose/openwebui.compose.yml` passes provider secrets via environment only from server-local env, not hardcoded values.
- `WEBUI_SECRET_KEY` and `CORS_ALLOW_ORIGIN` are explicitly part of compose/env/preflight.
- Backup docs correctly classify `.env` and `openwebui_data` backups as secret-bearing.
- The current obvious-pattern scan did not find private keys, OpenAI-style `sk-...`, GitHub PAT-style `ghp_...`, Slack token-style strings or Google API-key-style strings in committable files.

Notes and risks:

- `.env.example` contains a real Let's Encrypt contact email. This is not an API secret, but in a public repo it is still operator contact data. For Stage 2, consider using an operations alias if privacy/noise matters.
- `openwebui_data` can contain provider secrets entered through Admin UI. Any backup of this volume must be treated as sensitive.
- The local workspace contains an ignored `.env`; it was not read. If it ever leaves the server/workstation boundary, rotate contained secrets.
- Warning banner and onboarding reduce accidental leakage, but do not replace a corporate data policy, DLP, SIEM, SSO or user training.
- UFW/fail2ban are minimum hardening, not a corporate security audit.

## 9. Operations/runbook review

Runbooks are sufficient for PRD-0 operations:

- `DEPLOYMENT_RUNBOOK.md` gives deploy order from DNS through backup and deployment note.
- `BOOTSTRAP_DOCKER_UBUNTU.md` covers Docker Engine and Compose plugin on Ubuntu 24.04.
- `HOST_HARDENING_RUNBOOK.md` covers UFW/fail2ban and Docker/UFW caveat.
- `PROVIDER_SETUP_RUNBOOK.md` covers OpenAI primary and Gemini secondary via Admin UI.
- `BACKUP_RESTORE_RUNBOOK.md` and `scripts/restore.md` cover volume/env restore paths.
- `SMOKE_TESTS.md` and `scripts/smoke-test.sh` cover HTTP/HTTPS smoke and strict TLS mode.
- `ACCEPTANCE_TESTS.md` records acceptance criteria.
- `TROUBLESHOOTING.md` covers DNS, HTTPS, provider, proxy, banner, CORS, secret key and persistence issues.
- `UPDATE_ROLLBACK_RUNBOOK.md` records backup-before-update and pinned image rollback.
- `USER_ONBOARDING.md`, `PILOT_CHECKLIST.md`, `PILOT_FEEDBACK_FORM.md` support user handoff.

Operational gaps to discuss in Stage 2, not PRD-0 defects:

- no monitoring/alerting stack;
- no scheduled backup/restore drill policy;
- no formal access lifecycle process;
- no usage/cost accounting;
- no model governance/gateway;
- no corporate SSO/RBAC/audit policy;
- no current 2026-06-16 server-side recertification in this audit.

## 10. Что было вне scope

These items were intentionally excluded from PRD-0 and should not be counted as unfinished PRD-0 work:

- LiteLLM;
- model gateway;
- provider routing/fallback;
- budgets;
- per-user/per-team limits;
- large model catalog as a product feature;
- web search;
- corporate dashboard;
- manager access to subordinate chats;
- Word/PDF/Excel skills;
- transcription;
- complex RAG;
- memory/context layer;
- integrations with 1C, CRM and internal systems;
- white-label;
- OpenWebUI fork;
- frontend code changes;
- custom frontend;
- plugins/tools/functions;
- WAF/SIEM/DLP/corporate security audit.

This was not "не успели". It was deliberate scope control so the zero phase did not become a full AI platform.

## 11. Риски и открытые вопросы

| Риск / вопрос | Почему важно | Как проверить | Рекомендуемое действие |
| --- | --- | --- | --- |
| Gemini secondary may still be operator action | PRD selected Gemini, but reports leave save/test as pending | Admin UI Connections + test chat | Confirm or explicitly keep pending due key/quota/billing/region |
| Pilot users may not be independently verified | PRD expected 3-4 users | Admin UI users list | Confirm user creation/access without publishing names |
| Current UFW/fail2ban not refreshed | Hardening is public exposure control | SSH read-only `network-hardening-check.sh --strict` | Run read-only server recertification before Stage 2 |
| Backup restore not drilled | Backup without restore proof is partial | Restore to test window or maintenance drill | Add periodic restore check in Stage 2 ops |
| Web search research can be misread as PRD-0 scope | Latest commit is web-search research | Read `WEB_SEARCH_PROVIDER_RESEARCH.md` status section | Keep it as Stage 2 candidate only |
| Old Hermes placeholders remain in repo | They can confuse next-stage context | Identify `reports/REPO_PREFLIGHT.report.md`, `deploy/hermes-*`, root `runbooks/*_PLACEHOLDER.md` | Decide whether to archive/remove in a separate cleanup task |
| Provider egress depends on proxy bridge | Regional blocking already occurred | Server read-only provider smoke | Document ownership and rotation for bridge credentials |
| Secrets shared outside password manager may need rotation | Deployment report explicitly recommends rotation | Operator confirmation | Rotate after pilot stabilization |
| OpenWebUI image pinned to v0.9.6 | Good for PRD-0 stability, but update planning matters later | Check OpenWebUI release notes separately | Stage 2 should include update/rollback cadence |
| `.env.example` has real contact email | Not secret, but public metadata | Review repo visibility policy | Use ops alias if needed |

## 12. Stage 2 readiness notes

Do not design Stage 2 inside this audit. Reasonable discussion tracks are:

### A. Эксплуатационное развитие

- monitoring and uptime checks;
- regular backup/restore checks;
- OpenWebUI update cadence;
- access lifecycle and user offboarding;
- admin account/password/key rotation policy;
- periodic server-side hardening recertification.

### B. Управление моделями и стоимостью

- whether to add Claude or other providers;
- model selection rules for users;
- per-user/per-team limits;
- usage accounting;
- budget alerts;
- LiteLLM/model gateway only if governance becomes necessary.

### C. Корпоративные функции

- roles and groups;
- usage audit;
- reporting;
- data policy;
- administrator/manager visibility only after explicit privacy and security discussion.

### D. Работа с документами

- file upload scenarios;
- PDF/Word/Excel expectations;
- native OpenWebUI limitations;
- whether RAG is needed;
- whether a separate document pipeline is needed.

### E. Интеграции

- 1C;
- CRM;
- file storage;
- internal knowledge bases;
- transcription;
- external tools/functions.

### F. Продуктовая развилка

- continue with OpenWebUI as corporate chat;
- add gateway/governance around OpenWebUI;
- build a separate agentic layer;
- split Hermes/AgentBridge into another track if the real need is autonomous business-process execution rather than chat.

## 13. Вопросы заказчику перед Stage 2

1. Какие 2-3 рабочих сценария реально появились после PRD-0?
2. Кто будет владельцем эксплуатации: пользовательский администратор, IT, подрядчик или смешанная модель?
3. Нужен ли второй provider Gemini прямо сейчас, или достаточно OpenAI плюс будущий Claude/другие модели?
4. Нужно ли добавлять Claude как отдельного provider и какие модели считать default/economy/premium?
5. Нужны ли бюджеты, лимиты и usage reports уже в Stage 2?
6. Нужно ли руководителям видеть чаты сотрудников, или это запрещено/нежелательно по privacy policy?
7. Какие типы документов пользователи хотят загружать: PDF, Word, Excel, договоры, внутренние базы?
8. Должен ли web search стать частью Stage 2, и какой provider допустим с точки зрения стоимости и privacy?
9. Кто отвечает за backup restore drills, secret rotation и обновления OpenWebUI?
10. Stage 2 должен быть развитием OpenWebUI или отдельной задачей на агентный слой/интеграции?

## 14. Итоговый вердикт

1. Можно ли считать PRD-0 закрытым с инженерной точки зрения?
Да, как нулевую фазу и с учетом факта customer acceptance. Engineering package, deployment evidence и external endpoint checks достаточны для baseline. Не нужно задним числом включать в PRD-0 функции полноценной AI-платформы.

2. Какие факты подтверждены репозиторием?
Scope, non-goals, compose skeleton, env contract, provider plan, security minimum, runbooks, backup/restore docs, pilot docs, acceptance checklist, historical deployment reports.

3. Какие факты подтверждены runtime-проверками?
В этом аудите: DNS resolves, HTTP redirects to HTTPS, HTTPS returns 200 with strict TLS. Historical 2026-06-09 reports additionally confirm OpenWebUI healthy, OpenAI `gpt-5.4-mini` response, strict smoke, hardening check and backup.

4. Какие факты подтверждены только приемкой заказчика/операторским заявлением?
Gemini secondary final state, 3-4 users, current Admin UI settings, current banner visibility, current chat-history persistence and current server-side UFW/fail2ban/container/volume state.

5. Есть ли критические риски перед Stage 2?
Критических blockers по PRD-0 baseline не найдено. Есть normal Stage 2 risks: refresh server-side evidence, confirm users/Gemini, define ops owner, decide governance/cost controls.

6. Есть ли признаки, что PRD-0 был раздут за пределы исходного scope?
Нет для production path. Research по web search и Hermes placeholders существуют, но не включены в PRD-0 runtime path. Их нужно держать как separate/future context.

7. Какие вопросы нужно задать заказчику?
См. раздел 13. Главные: реальные сценарии, ownership, модельный набор, бюджеты, privacy, документы, web search, интеграции, ops responsibility.

8. Какой следующий документ лучше готовить?
Сначала `Stage 2 discovery` с вариантами и решениями заказчика. После него - либо `PRD-1`, если выбран продуктовый scope, либо technical roadmap/commercial proposal, если нужно согласовать бюджет и этапность.

Финальная формулировка: PRD-0 accepted; this audit records baseline and evidence level. Stage 2 should start from discovery, not from silent implementation.
