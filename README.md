# corp-hermes

`corp-hermes` - проектный репозиторий для Hermes Corporate v1: документации, PRD/ТЗ, требований и scaffold-материалов для демонстрационного стенда.

Hermes Corporate v1 - это демонстрационный стенд из трех изолированных Hermes solo stack на новом VPS и новом домене. Цель стенда - дать пользователям попробовать Hermes в независимых средах, проверить изоляцию нод, собрать обратную связь и подготовить требования к будущей корпоративной версии Hermes.

Этот репозиторий не содержит live deployment и production-код. Старый VPS с существующим solo Hermes stack не является площадкой для стенда и используется только как инженерный reference context.

## Область v1

В v1 каждая нода имеет свой Web GUI, Hermes runtime/context, Docker Compose project, `STACK_ROOT`, данные, конфиги, логи, secrets, Docker-сеть, Authelia, auth/session context и имена Traefik router/service/middleware.

Общим допускается только ingress-слой Traefik.

Corporate controller, централизованный RBAC, централизованный аудит, биллинг, квоты, учет токенов, self-service provisioning, LDAP/AD integration, общая корпоративная Authelia и multi-tenant Hermes runtime относятся к future scope.

## Навигация

Клиентские документы:

- ТЗ для заказчика: [docs/customer/HERMES_CORPORATE_V1_CUSTOMER_TZ.md](docs/customer/HERMES_CORPORATE_V1_CUSTOMER_TZ.md)
- Почему Hermes: [docs/customer/HERMES_CORPORATE_V1_WHY_HERMES.md](docs/customer/HERMES_CORPORATE_V1_WHY_HERMES.md)

Внутренняя проектная документация:

- PRD/ТЗ draft: [docs/prd/HERMES_CORPORATE_V1_PRD.md](docs/prd/HERMES_CORPORATE_V1_PRD.md)
- Архитектура: [docs/architecture/HERMES_CORPORATE_V1_ARCHITECTURE.md](docs/architecture/HERMES_CORPORATE_V1_ARCHITECTURE.md)
- Требования к VPS: [docs/requirements/VPS_REQUIREMENTS.md](docs/requirements/VPS_REQUIREMENTS.md)
- Требования к DNS: [docs/requirements/DNS_REQUIREMENTS.md](docs/requirements/DNS_REQUIREMENTS.md)
- Требования к безопасности: [docs/requirements/SECURITY_REQUIREMENTS.md](docs/requirements/SECURITY_REQUIREMENTS.md)
- Критерии приемки: [docs/requirements/ACCEPTANCE_CRITERIA.md](docs/requirements/ACCEPTANCE_CRITERIA.md)
- Future scope corporate controller: [docs/future/FUTURE_CORPORATE_CONTROLLER.md](docs/future/FUTURE_CORPORATE_CONTROLLER.md)
- Deploy placeholder: [deploy/hermes-corporate-v1/README.md](deploy/hermes-corporate-v1/README.md)
- Repo preflight report: [reports/REPO_PREFLIGHT.report.md](reports/REPO_PREFLIGHT.report.md)

## Безопасность

Не коммитить реальные IP-адреса, пароли, токены, OAuth secrets, private keys, password hashes или server-local env-файлы.

Домены `example.com` в документах используются только как placeholders до утверждения реального домена.
