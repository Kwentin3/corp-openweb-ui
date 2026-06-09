# Acceptance Criteria

OpenWebUI PRD-0 is accepted when all criteria below are satisfied in the target pilot environment.

- `https://gpt.alpha-soft.ru` is reachable over HTTPS.
- HTTP redirects to HTTPS.
- Strict TLS check passes without `curl -k`.
- OpenWebUI is exposed only through Traefik.
- UFW is active.
- Public perimeter is limited to `22/tcp`, `80/tcp`, `443/tcp`.
- Fail2ban is active.
- `sshd` jail is enabled.
- Admin can log in.
- Signup is disabled or restricted to pending users.
- 3-4 pilot users exist.
- A normal user can log in.
- UI shows `Alpha Soft AI Chat` or another operator-approved soft instance name.
- A warning banner is visible to the user.
- The warning banner forbids sending passwords, tokens, API keys, private SSH keys and closed personal data.
- OpenAI provider is connected or ready by runbook.
- Gemini provider is connected or ready by runbook.
- At least one provider returns an answer in chat.
- The second provider is checked or explicitly marked pending operator decision.
- Chat history persists after logout/login.
- Chat history persists after OpenWebUI container restart.
- Real `.env` is not committed.
- API keys, passwords, SSH endpoint and public IP are not committed.
- Backup is created and restore path is documented.
