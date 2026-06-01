# ADR-0003: Per-Node Authelia

## Context

Authentication must preserve node isolation. A shared Authelia would introduce shared session and configuration concerns that are not needed for the v1 demo.

## Decision

Use a separate Authelia instance for each node in v1.

## Consequences

- Each node has its own auth host.
- Session state must not be shared between nodes.
- User provisioning may be duplicated in v1.

## Deferred Alternatives

- Shared corporate Authelia.
- Enterprise SSO.
- LDAP/AD integration.
- Centralized user management.
