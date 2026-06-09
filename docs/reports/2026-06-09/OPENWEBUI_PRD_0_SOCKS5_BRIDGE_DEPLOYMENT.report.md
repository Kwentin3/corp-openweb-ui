# OpenWebUI PRD-0 SOCKS5 Bridge Deployment Report

Date: 2026-06-09

## Context

OpenAI provider access from the server's direct egress was blocked by provider-side regional restrictions. The operator provided a SOCKS5 upstream for provider egress.

PRD-0 scope is unchanged: no fork, no frontend changes, no plugins, no LiteLLM, no gateway.

## Env changes

Workspace `.env` and server-local `.env` now contain the outbound proxy section:

```env
OPENWEBUI_OUTBOUND_PROXY=http://172.18.0.1:8118
OPENWEBUI_SOCKS5_UPSTREAM=<server-local-socks5-upstream>
OPENWEBUI_NO_PROXY=localhost,127.0.0.1,::1,openwebui,traefik,openwebui-traefik,gpt.alpha-soft.ru
```

Secrets are stored only in ignored/server-local `.env`. The SOCKS5 upstream value is not committed.

## Implementation

Direct `socks5h://` in OpenWebUI proxy env was not used for the provider path. OpenWebUI's OpenAI-compatible route uses an `aiohttp` path with `trust_env=True`, which worked with an HTTP proxy and failed with direct SOCKS.

Implemented host-local HTTP-to-SOCKS bridge:

- Privoxy installed on the server;
- bridge listens on loopback and Docker gateway `172.18.0.1:8118`;
- Privoxy forwards to the server-local SOCKS5 upstream from `.env`;
- `/etc/privoxy/config` is readable only by the `privoxy` user;
- UFW allows `8118/tcp` only from Docker subnet `172.18.0.0/16` to Docker gateway `172.18.0.1`;
- `8118/tcp` is not public.

## Verification

Server and compose:

- `docker compose --env-file .env -f compose/openwebui.compose.yml config`: passed.
- OpenWebUI container recreated and became healthy.
- Privoxy service active.

Proxy path:

- host HTTP bridge egress resolved through proxy location;
- host OpenAI `/v1/models` through bridge returned HTTP `200`;
- container TCP connect to `172.18.0.1:8118` succeeded;
- container `aiohttp` with `trust_env=True` reached OpenAI `/v1/models` with HTTP `200`;
- `gpt-5.4-mini` was present in the model list.

OpenWebUI API:

- admin signin returned HTTP `200`;
- `/api/models` returned HTTP `200`;
- OpenWebUI model list included `gpt-5.4-mini`;
- `/api/chat/completions` with `gpt-5.4-mini` returned HTTP `200` and a short `OK` response.

Hardening and backup:

- `bash scripts/smoke-test.sh --strict-tls`: passed (`http_status=301`, `https_status=200`);
- `bash scripts/network-hardening-check.sh --strict`: passed, no unexpected public listeners;
- `bash scripts/backup.sh`: passed, backup artifacts created and retention pruning executed.

## Remaining operator work

- Gemini secondary provider still requires Gemini API key entry through Admin UI.
- Pilot users still require the operator-provided user list or manual creation through Admin UI.
- Credentials that were shared outside a password manager should be rotated after pilot stabilization.

## Scope control

No OpenWebUI fork, white-labeling, logo replacement, frontend patch, plugin, tool/function, RAG, web search, LiteLLM or model gateway was added.
