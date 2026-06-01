# Future Corporate Controller

The corporate controller is future scope and is not implemented in Hermes Corporate v1.

## Candidate Capabilities

- Unified admin panel.
- Node lifecycle management.
- User management.
- RBAC.
- Quotas.
- Token usage accounting.
- Centralized audit.
- Health aggregation.
- Shared Authelia or enterprise SSO.
- LDAP/AD integration.
- Self-service provisioning.
- Backup policy.
- Node registry.

## Guardrail

Do not backport controller assumptions into v1 deployment placeholders. v1 should remain three isolated solo stacks with shared Traefik ingress only.
