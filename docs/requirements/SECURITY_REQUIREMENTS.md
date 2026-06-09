# Security Requirements

## Required Controls

- Use HTTPS only for Web GUI access.
- Expose OpenWebUI only through Traefik.
- Do not expose direct public OpenWebUI ports.
- Keep public perimeter limited to `22/tcp`, `80/tcp`, `443/tcp`.
- Enable UFW with default deny incoming and default allow outgoing.
- Enable fail2ban with `sshd` jail.
- Keep secrets server-local or in OpenWebUI Admin UI.
- Do not commit real `.env` files.
- Do not commit password hashes.
- Do not commit API keys.
- Do not commit OAuth secrets.
- Do not commit private keys.
- Keep exact SSH endpoint, public IP, operator IPs and real pilot participant names out of Git.
- Keep `WEBUI_SECRET_KEY` stable across container recreates.
- Restrict `CORS_ALLOW_ORIGIN` to `https://gpt.alpha-soft.ru`.
- Show a warning banner that reminds users not to submit secrets or closed personal data.
- Keep customization low-cost and reversible: env/Admin UI only.

## Provider Requirements

- OpenAI and Gemini are the only PRD-0 providers.
- LiteLLM/model gateway is not required and must not be added in PRD-0.
- One provider is configured through server-local `.env`.
- The second provider is configured through OpenWebUI Admin UI.
- API keys must not be visible to normal users.

## Customization Requirements

- `WEBUI_NAME` may set a soft instance name.
- `WEBUI_BANNERS` may set a warning banner.
- Fork, white-label, logo replacement, custom frontend, plugins and tools/functions are not allowed in PRD-0.

## Repository Safety

Only sanitized examples and templates may be committed. Any deployment-specific values must remain outside the repository until a secret-management approach is approved.
