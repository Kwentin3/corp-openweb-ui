# Repo Preflight Report

Date: 2026-06-01

## Repository Status

- Repository URL: `https://github.com/Kwentin3/corp-hermes`
- Local path: `d:\Users\Roman\Desktop\Проекты\corp-hermes`
- Current branch: `main`
- Remote: `origin`
- Clone result: empty repository warning from Git.
- Initial status before scaffold: no committed files in working tree.

## What Was Found

- No README was present.
- No `.gitignore` was present.
- No license file was present.
- No GitHub Actions were present.
- No existing docs, deploy scaffold or runbooks were present.
- No `.env` files or other sensitive project files were present.
- No binary files or large files were present.
- No Git LFS need was found at this stage.

## Created Structure

- `README.md`
- `.gitignore`
- `docs/prd/`
- `docs/architecture/`
- `docs/decisions/`
- `docs/requirements/`
- `docs/future/`
- `deploy/hermes-corporate-v1/`
- `deploy/hermes-corporate-v1/env/`
- `deploy/hermes-corporate-v1/authelia/`
- `deploy/hermes-corporate-v1/registry/`
- `runbooks/`
- `reports/`

## Created Documents

- `docs/prd/HERMES_CORPORATE_V1_PRD.md`
- `docs/architecture/HERMES_CORPORATE_V1_ARCHITECTURE.md`
- `docs/requirements/VPS_REQUIREMENTS.md`
- `docs/requirements/DNS_REQUIREMENTS.md`
- `docs/requirements/SECURITY_REQUIREMENTS.md`
- `docs/requirements/ACCEPTANCE_CRITERIA.md`
- `docs/future/FUTURE_CORPORATE_CONTROLLER.md`
- `docs/decisions/ADR-0001-project-scope.md`
- `docs/decisions/ADR-0002-three-isolated-solo-stacks.md`
- `docs/decisions/ADR-0003-per-node-authelia.md`
- `docs/decisions/ADR-0004-traefik-ingress.md`

## Decisions Captured

- v1 is a demonstration stand, not full corporate Hermes.
- v1 uses three isolated Hermes solo stacks.
- v1 uses separate Authelia per node.
- Traefik is the only shared ingress layer.

## Placeholders Left

- `deploy/hermes-corporate-v1/compose.node.yml.placeholder`
- `deploy/hermes-corporate-v1/env/*.env.example`
- `deploy/hermes-corporate-v1/authelia/*.template`
- `deploy/hermes-corporate-v1/registry/node-registry.example.yml`
- `runbooks/*_PLACEHOLDER.md`

## Missing Data

- Approved real domain.
- New VPS public IPv4.
- Exact Hermes solo stack baseline/version.
- Demo user model.
- Backup and retention expectations.
- Required observability depth.
- Final secret handling approach.

## Blockers Before PRD v1.0

- Approve real domain naming.
- Confirm target VPS provider and size.
- Confirm expected demo users and access model.
- Confirm source Hermes solo stack version and constraints.
- Confirm acceptance test procedure with stakeholders.

## Blockers Before Deployment Scaffold

- Approved VPS and DNS.
- Concrete Compose contract for Hermes solo stack.
- Concrete Authelia per-node configuration.
- Secret-generation and storage policy.
- TLS/certresolver decision.
- Backup/restore policy.
- Rollback procedure.

## What Was Not Performed

- No deployment.
- No connection to old VPS.
- No connection to new VPS.
- No changes to any VPS.
- No production Compose implementation.
- No real secrets, IP addresses or domains were added.
- No corporate controller was implemented.
