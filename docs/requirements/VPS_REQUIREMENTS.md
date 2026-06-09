# VPS Requirements

## Operating System

Ubuntu Server LTS. Current target expectation: Ubuntu 24.04 LTS.

## Recommended Baseline

- CPU: 2-4 vCPU.
- RAM: 4-8 GB.
- Disk: 50-60 GB SSD.
- Swap: required.
- Public IPv4: required.
- Public ports: `22/tcp`, `80/tcp`, `443/tcp`.
- SSH access: sudo-capable user.
- Runtime: Docker Engine and Docker Compose plugin.
- Ingress: Traefik as reverse proxy / ingress.
- Host hardening: UFW + fail2ban.

## Notes

OpenWebUI is self-hosted, but models are not local in PRD-0. The server must have outbound HTTPS access to OpenAI and Gemini APIs, either directly or through an operator-approved HTTP proxy bridge.

If provider APIs block the server region, PRD-0 may use a host-local HTTP-to-SOCKS bridge. The bridge must not publish a public port.

50 GB disk is acceptable as a lower bound for a short pilot if backups are kept under control. 60 GB remains the cleaner baseline.

## Out of Scope

This document does not authorize deployment, VPS access or old VPS changes. Actual bootstrap/deploy is a separate operator task.
