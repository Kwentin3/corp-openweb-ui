# Scoped final-provider request capture

For the accepted 0.12.2 runtime use
[provider-context-v0.12.2](../provider-context-v0.12.2/README.md).
This installer remains version-specific and must not be applied to 0.12.2.

Temporary diagnostic overlay for the exact deployed OpenWebUI 0.11.4 router.
It observes the serialized request immediately before the native HTTP sender.
The existing flight recorder covers resources, container events and sanitized
logs; native ASGI audit logging observes incoming requests. Neither supplies
this final provider body after the tool loop and provider conversion.

Build on the exact accepted local WebUI image with `OPENWEBUI_BASE_IMAGE`.
The installer checks full original/result router hashes and rejects drift.
Four image checks cover disabled/scope behavior, exact request bytes, private
file modes, expiry/count/volume limits and failure isolation. No provider is
called during qualification. The ordinary production image excludes this overlay.

Recording is disabled unless `DATA_DIR/forensics/provider-context/capture.json`
exists. An operator explicitly scopes it to one authorized saved chat:

```json
{
  "chat_id": "authorized-chat-id",
  "run_id": "a-fresh-uuid",
  "expires_at": 1792014000,
  "max_requests": 12,
  "max_bytes": 134217728
}
```

Use a future Unix expiry, directory mode `0700` and config mode `0600`.
Auxiliary tasks and other chats are excluded. Maximum accepted limits are
20 requests and 256 MiB. These limits stop recording, **not model execution**;
bound the actual test separately and stop it through native chat controls.

The run directory retains exact `NNN.request.json` bytes and a small receipt
with SHA-256, size, time, chat/message identity and URL host/path. Files use
`0600`, the run directory `0700`. No headers, cookies or credentials from the
connection are passed to the helper. Bodies can contain private customer data;
retain them only in the protected forensic location, outside Git and public PRs.

After the test, remove the active config (retaining it with private evidence),
confirm no native tasks remain, and restore the accepted production image through
the existing Compose owner. Preserve all other runtime configuration and volumes.
Remove this overlay when upstream supplies equivalent final-request diagnostics.
