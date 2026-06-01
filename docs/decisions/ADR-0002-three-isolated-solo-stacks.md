# ADR-0002: Three Isolated Solo Stacks

## Context

The v1 stand must let users try Hermes in three independent environments while reducing the risk of data, auth or runtime mixing.

## Decision

Use three isolated Hermes solo stacks instead of one shared multi-tenant runtime.

## Consequences

- Each node has its own runtime, Compose project, data, configs, logs and secrets.
- Operational duplication is accepted for v1.
- Isolation is easier to reason about and validate.

## Deferred Alternatives

- One multi-tenant Hermes runtime.
- Shared data plane with tenant separation.
- Centralized lifecycle controller.
