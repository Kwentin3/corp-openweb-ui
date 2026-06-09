# Storage And Volumes

## Volumes

`openwebui_data`:

- содержит данные OpenWebUI;
- монтируется в `/app/backend/data`;
- должен попадать в backup.

`traefik_letsencrypt`:

- содержит ACME данные Traefik;
- монтируется в `/letsencrypt`;
- должен попадать в backup при production-like использовании.

## Что не хранить в volume

Не хранить в Git или repo bind mounts:

- реальные `.env`;
- API-ключи;
- пароли;
- приватные SSH-ключи;
- backup-архивы.

## Backup unit

Минимальный backup PRD-0:

- archive of `openwebui_data`;
- copy of `.env` в защищенной server-local backup directory;
- optionally archive of `traefik_letsencrypt`.

`.env` содержит `WEBUI_SECRET_KEY`, API key и admin bootstrap password, поэтому backup `.env` считается secret-bearing artifact.

## Restore expectation

Restore считается успешным, если после восстановления:

- OpenWebUI стартует;
- администратор входит;
- старые чаты видны;
- пользователь может получить новый ответ модели.
- strict TLS check проходит.
