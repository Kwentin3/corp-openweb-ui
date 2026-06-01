# Hermes Corporate v1 Architecture

## Architecture Intent

Hermes Corporate v1 favors explicit isolation over shared runtime efficiency. The v1 architecture uses three independent solo stacks to reduce tenant-mixing risk and keep the demo stand understandable.

## Domains and Ownership

- Ingress: shared Traefik layer, public 80/443 entrypoints, TLS routing.
- Node runtime: one Hermes runtime/context per node.
- Authentication: one Authelia instance per node.
- Node storage: per-node data, configs, logs and secrets.
- Operations: future runbooks for deployment, update, rollback, backup/restore and node removal.

## Boundary Contracts

Node boundary:

- `HERMES_NODE_ID`
- `COMPOSE_PROJECT_NAME`
- `STACK_ROOT`
- `HERMES_NODE_DOMAIN`
- `AUTHELIA_AUTH_HOST`
- `TRAEFIK_NETWORK`
- `TRAEFIK_HTTP_ENTRYPOINT`
- `TRAEFIK_HTTPS_ENTRYPOINT`
- `TRAEFIK_CERTRESOLVER`

Ingress boundary:

- unique Traefik router names per node;
- unique Traefik service names per node;
- unique middleware names per node;
- no shared auth/session state between nodes.

## Deployment Shape

This repository currently contains only placeholders. A later deployment scaffold should define:

- concrete Compose files;
- server-local secret layout;
- per-node `STACK_ROOT` paths;
- Traefik static/dynamic config split;
- Authelia storage and session configuration;
- backup and restore procedures.

## Non-Goals

The v1 architecture does not introduce a shared corporate controller, shared corporate Authelia, centralized RBAC, centralized audit, shared session storage or multi-tenant Hermes runtime.

## Validation Surface

The architecture is accepted only if sessions, secrets, data, logs, Compose projects and Docker networks remain separated across `node1`, `node2` and `node3`.
