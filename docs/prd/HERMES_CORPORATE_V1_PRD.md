# Hermes Corporate v1 PRD/TZ Draft

## Цель стенда

Подготовить демонстрационный стенд Hermes Corporate v1 из трех независимых изолированных Hermes solo stack на новом VPS и новом домене.

Стенд нужен, чтобы пользователи могли попробовать Hermes в трех независимых средах, проверить модель изоляции нод, собрать обратную связь и подготовить требования к будущему корпоративному Hermes.

## Краткое описание решения

Hermes Corporate v1 строится как набор из трех отдельных нод:

- `node1.example.com`
- `node2.example.com`
- `node3.example.com`

Каждая нода является отдельным Hermes solo stack со своими данными, конфигурацией, логами, секретами, Docker Compose project, Docker-сетью, Authelia и auth/session context.

Общим допускается только ingress-слой Traefik, который принимает внешний HTTPS-трафик и маршрутизирует его на нужную ноду.

## Границы v1

v1 является демонстрационным стендом, а не полноценным корпоративным Hermes.

В рамках v1 не выполняются live deployment, подключение к старому VPS, изменение старого VPS, реализация corporate controller или подготовка финального production-кода.

## Что входит

- Три независимые Hermes-ноды.
- Отдельный Web GUI на каждую ноду.
- Отдельный Hermes runtime/context на каждую ноду.
- Отдельный Docker Compose project на каждую ноду.
- Отдельный `STACK_ROOT` на каждую ноду.
- Отдельные данные, конфиги, логи и secrets.
- Отдельная внутренняя Docker-сеть на каждую ноду.
- Отдельная Authelia на каждую ноду.
- Отдельные auth/session context.
- Отдельные Traefik router/service/middleware names.
- Общий Traefik только как ingress/reverse proxy.

## Что не входит

- Corporate controller.
- Админская панель.
- Backend controller.
- Frontend controller.
- Централизованный RBAC.
- Централизованный аудит.
- Биллинг.
- Квоты.
- Учет токенов.
- Self-service provisioning.
- LDAP/AD integration.
- Общая корпоративная Authelia.
- Мульти-тенантный Hermes runtime.

## Целевая архитектура

Целевая схема v1:

1. Пользователь открывает домен конкретной ноды по HTTPS.
2. Traefik принимает внешний трафик на 80/443.
3. Traefik маршрутизирует запрос в изолированный stack выбранной ноды.
4. Authelia конкретной ноды выполняет авторизацию.
5. После авторизации пользователь работает только с выбранной нодой.

Сессия, данные и secrets одной ноды не должны давать доступ к другой ноде.

## Описание трех нод

Каждая нода должна иметь собственный идентификатор:

- `node1`
- `node2`
- `node3`

Для каждой ноды должны быть разнесены:

- домен Web GUI;
- auth-домен Authelia;
- Compose project name;
- `STACK_ROOT`;
- Docker network;
- volumes;
- logs;
- server-local secrets;
- Traefik labels and names.

## Требования к VPS

Предполагаемый провайдер: JustHost.

ОС: Ubuntu Server LTS.

Рекомендуемый baseline:

- 4 vCPU;
- 8 GB RAM;
- 60 GB SSD;
- swap enabled;
- public IPv4;
- доступные извне порты 80/443;
- SSH-доступ root или sudo-пользователь;
- Docker and Docker Compose;
- Traefik как reverse proxy / ingress.

50 GB disk may be treated only as a lower bound for a short demo, not as the recommended baseline.

## Требования к домену и DNS

Wildcard DNS не требуется и не должен быть обязательным требованием.

Нужно шесть DNS A-записей:

- `node1.example.com -> VPS_PUBLIC_IP`
- `node2.example.com -> VPS_PUBLIC_IP`
- `node3.example.com -> VPS_PUBLIC_IP`
- `auth-node1.example.com -> VPS_PUBLIC_IP`
- `auth-node2.example.com -> VPS_PUBLIC_IP`
- `auth-node3.example.com -> VPS_PUBLIC_IP`

`example.com` is a placeholder. The real domain must be substituted only after approval.

## Требования к Traefik / ingress

- Public ingress exposes only HTTP/HTTPS entrypoints needed for certificate issuance and HTTPS access.
- Web GUI services are not exposed directly to the public network.
- Traefik router/service/middleware names must be unique per node.
- Traefik must not erase node isolation by sharing auth/session state.

## Требования к отдельной Authelia

- Each node uses its own Authelia instance.
- Each Authelia has its own auth host.
- Session storage and provider secret files are not shared between nodes.
- A login session for one node must not grant access to another node.

## Требования к изоляции

- Data, logs, configs and secrets are isolated per node.
- Docker Compose projects are isolated per node.
- Internal Docker networks are isolated per node.
- Restarting or stopping one node must not break other nodes.
- Node-specific names must avoid accidental Traefik or Docker collisions.

## Требования к безопасности

- HTTPS only for Web GUI access.
- No direct public ports for Web GUI.
- Secrets are server-local and are not committed.
- Real `.env` files are not committed.
- Password hashes, API keys, OAuth secrets and private keys are not committed.
- Docker socket is not mounted unless a separate decision explicitly approves it.
- YOLO/off approval mode is not enabled without a separate decision.

## Требования к эксплуатации

- Each node must be operable independently.
- Start, stop, update, rollback and backup/restore procedures must be documented before live deployment.
- Placeholder deploy files in this repository are not production deployment instructions.
- The old VPS is not part of the target environment.

## Требования к минимальной наблюдаемости

- Logs are separated per node.
- Health checks or smoke checks should distinguish node state independently.
- A future deployment scaffold must define where Traefik, Authelia and Hermes logs are stored.

## Критерии приемки

See [../requirements/ACCEPTANCE_CRITERIA.md](../requirements/ACCEPTANCE_CRITERIA.md).

## Открытые вопросы

- What real domain will replace `example.com`?
- What user groups should be allowed into each demo node?
- How many demo users are expected concurrently?
- What Hermes solo stack version should be used as the source baseline?
- What backup retention is expected for the demo stand?
- What observability depth is required for the first demo?

## Future Scope: Corporate Controller

Corporate controller is future scope and is not implemented in v1. See [../future/FUTURE_CORPORATE_CONTROLLER.md](../future/FUTURE_CORPORATE_CONTROLLER.md).
