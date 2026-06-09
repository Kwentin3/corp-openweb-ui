# OpenWebUI PRD-0 Docs Workspace/GitHub Sync Report

Date: 2026-06-09

## Purpose

Bring Workspace and GitHub documentation in line with the current PRD-0 deployment state after the SOCKS5 egress work.

## Current deployment facts reflected

- `gpt.alpha-soft.ru` target is deployed.
- Traefik and OpenWebUI are running.
- OpenWebUI is healthy.
- Strict TLS smoke passed.
- UFW/fail2ban hardening passed in strict mode.
- Public listeners are limited to `22/tcp`, `80/tcp`, `443/tcp`.
- OpenAI primary with `gpt-5.4-mini` works through OpenWebUI API.
- Direct provider egress was blocked by provider region policy.
- Provider egress now uses OpenWebUI HTTP proxy env and a host-local HTTP-to-SOCKS bridge.
- Bridge port is not public and is allowed only from Docker subnet to Docker gateway.
- Backup script passed.

## Documents updated

- `docs/infra/INFRA_TARGET.md`
- `docs/infra/ENVIRONMENT_VARIABLES.md`
- `docs/blueprint/ARCHITECTURE_OVERVIEW.md`
- `docs/blueprint/OPENWEBUI_PRD_0_BLUEPRINT.md`
- `docs/ops/DEPLOYMENT_DECISIONS.md`
- `docs/ops/ACCEPTANCE_TESTS.md`
- `docs/ops/SMOKE_TESTS.md`
- `docs/security/FIREWALL_AND_FAIL2BAN.md`
- `docs/ops/HOST_HARDENING_RUNBOOK.md`
- `docs/ops/TROUBLESHOOTING.md`
- `docs/infra/PROVIDER_CONNECTIONS_PLAN.md`
- `docs/requirements/VPS_REQUIREMENTS.md`

## Decisions and scope

The docs now distinguish:

- closed deployment decisions;
- configured server-local secrets;
- pending operator actions.

PRD-0 scope was not expanded. No fork, white-labeling, logo replacement, frontend patch, plugin, RAG, web search, LiteLLM or model gateway was added.

## Remaining operator actions

- Add Gemini secondary provider through OpenWebUI Admin UI or explicitly keep it pending due API key/quota/billing/region.
- Create or activate 3-4 pilot users.
- Rotate secrets that were shared outside a password manager.

## Verification used

- Workspace git tree was clean before the docs sync.
- Server checkout was already on the latest pushed commit before this sync.
- Current server evidence from the previous deployment verification was incorporated without committing secrets, public IP, SSH endpoint, API keys or proxy credentials.
