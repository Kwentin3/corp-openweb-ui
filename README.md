# corp-hermes

`corp-hermes` is a project scaffold and PRD/TZ workspace for Hermes Corporate v1.

Hermes Corporate v1 is a demonstration stand with three isolated Hermes solo stacks on a new VPS and a new domain. The goal is to let users try Hermes in three independent environments, validate node isolation, collect feedback, and prepare requirements for a future corporate Hermes variant.

This repository does not contain a live deployment. The current task does not change any old VPS and does not prepare production code. Any existing old VPS with a solo Hermes stack is treated only as a reference environment and historical engineering context.

## Scope

In v1 each node has its own Web GUI, Hermes runtime/context, Docker Compose project, `STACK_ROOT`, data, configs, logs, secrets, Docker network, Authelia instance, auth/session context, and Traefik router/service/middleware names.

Only the Traefik ingress layer may be shared.

Corporate controller, centralized RBAC, centralized audit, billing, quotas, token accounting, self-service provisioning, LDAP/AD integration, shared corporate Authelia, and multi-tenant Hermes runtime are future scope.

## Documents

- PRD/TZ draft: [docs/prd/HERMES_CORPORATE_V1_PRD.md](docs/prd/HERMES_CORPORATE_V1_PRD.md)
- Architecture notes: [docs/architecture/HERMES_CORPORATE_V1_ARCHITECTURE.md](docs/architecture/HERMES_CORPORATE_V1_ARCHITECTURE.md)
- VPS requirements: [docs/requirements/VPS_REQUIREMENTS.md](docs/requirements/VPS_REQUIREMENTS.md)
- DNS requirements: [docs/requirements/DNS_REQUIREMENTS.md](docs/requirements/DNS_REQUIREMENTS.md)
- Security requirements: [docs/requirements/SECURITY_REQUIREMENTS.md](docs/requirements/SECURITY_REQUIREMENTS.md)
- Acceptance criteria: [docs/requirements/ACCEPTANCE_CRITERIA.md](docs/requirements/ACCEPTANCE_CRITERIA.md)
- Future corporate controller notes: [docs/future/FUTURE_CORPORATE_CONTROLLER.md](docs/future/FUTURE_CORPORATE_CONTROLLER.md)
- Deploy placeholder: [deploy/hermes-corporate-v1/README.md](deploy/hermes-corporate-v1/README.md)
- Preflight report: [reports/REPO_PREFLIGHT.report.md](reports/REPO_PREFLIGHT.report.md)

## Safety

Do not commit real IP addresses, passwords, tokens, OAuth secrets, private keys, password hashes, or server-local environment files. `example.com` names in this repository are placeholders until the real domain is approved.
