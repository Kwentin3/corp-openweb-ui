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

`stage2_stt_data`:

- содержит STT ArtifactStore SQLite по `/data/stage2-stt/artifacts.sqlite3`;
- монтируется в `stage2-stt` как `/data/stage2-stt`;
- переживает recreation контейнера независимо от `openwebui_data`;
- должен входить в согласованный backup/restore вместе с проверкой SQLite;
- не является canonical Broker Reports storage authority.

Broker Reports canonical использует существующий namespace
`/app/backend/data/broker_reports_gate1` внутри `openwebui_data`. Metadata,
payload components, active pointers и receipts нельзя разносить по
несогласованным backup windows.

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
- archive or coordinated SQLite snapshot of `stage2_stt_data`;
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

Для Broker Reports дополнительно обязательны: SQLite `integrity_check=ok`,
16/16 active pointers/root hashes, ноль missing chunks и fail-closed tenant
read через `CanonicalReaderFactory`. Проверка на временном store не заменяет
target restore drill.
