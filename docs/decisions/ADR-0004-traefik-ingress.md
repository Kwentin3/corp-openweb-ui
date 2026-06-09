# ADR-0004: Traefik Ingress For OpenWebUI PRD-0

## Context

OpenWebUI PRD-0 needs one public HTTPS entrypoint for `gpt.alpha-soft.ru`.

## Decision

Use Traefik as the reverse proxy and ACME HTTP challenge client.

## Consequences

- Traefik is the only public HTTP/HTTPS entrypoint.
- OpenWebUI is not exposed directly to the public network.
- Public ports are limited to `22/tcp`, `80/tcp`, `443/tcp`.
- Route is `Host(gpt.alpha-soft.ru) -> openwebui:8080`.

## Deferred Alternatives

- Nginx reverse proxy.
- Kubernetes ingress.
- Managed cloud load balancer.
