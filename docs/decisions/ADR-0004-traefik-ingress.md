# ADR-0004: Traefik Ingress

## Context

The demo stand needs one public ingress point for routing HTTPS traffic to three isolated node stacks.

## Decision

Use Traefik as the base ingress/reverse proxy.

## Consequences

- Traefik is the only shared layer allowed in v1.
- Router, service and middleware names must be unique per node.
- Web GUI services are exposed through Traefik only.

## Deferred Alternatives

- Nginx reverse proxy.
- Per-node public ingress.
- Kubernetes ingress.
- Shared corporate gateway managed by a future controller.
