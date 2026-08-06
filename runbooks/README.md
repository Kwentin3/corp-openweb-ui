# Runbooks

This directory contains placeholders for future operational runbooks.

The current repository bootstrap does not define live deployment procedures and does not authorize VPS access.

## DOC28 durable canonical deployment gate

The compose declaration provides one admissible storage candidate:
`openwebui_data:/app/backend/data`. The Broker Reports ArtifactStore defaults
place SQLite metadata and file payloads below that mount. This configuration
does not by itself prove an operational durable deployment.

As of 2026-08-05, the target OpenWebUI container and volume are not accessible
from the approved execution context. No restart, cross-process read, capacity,
metadata/payload consistency, active-pointer persistence, or restore drill has
been completed. DOC28 durable writes and all dependent migrations remain
blocked. Do not substitute a local or temporary volume for this proof.
