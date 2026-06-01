# ADR-0001: Project Scope

## Context

Hermes Corporate v1 must provide a practical demo stand for evaluating isolated Hermes usage without committing to the full corporate product architecture.

## Decision

Hermes Corporate v1 is a demonstration stand, not a full corporate Hermes implementation.

## Consequences

- The repository focuses on PRD/TZ context, requirements, decisions and placeholders.
- Live deployment is out of scope for the bootstrap task.
- Corporate controller and centralized corporate features remain deferred.

## Deferred Alternatives

- Full corporate controller.
- Centralized RBAC and audit.
- Multi-tenant Hermes runtime.
- Shared enterprise SSO integration.
