# Security Requirements

## Required Controls

- Use HTTPS only for Web GUI access.
- Expose Web GUI only through Traefik.
- Do not expose direct public Web GUI ports.
- Use a separate Authelia instance for each node.
- Keep secrets server-local.
- Do not commit real `.env` files.
- Do not commit password hashes.
- Do not commit API keys.
- Do not commit OAuth secrets.
- Do not commit private keys.
- Do not mount the Docker socket unless separately approved.
- Do not use shared session storage across nodes.
- Do not use a shared provider secret file across nodes.
- Do not enable YOLO/off approval mode without a separate decision.

## Repository Safety

Only sanitized examples and templates may be committed. Any deployment-specific values must remain outside the repository until a secret-management approach is approved.
