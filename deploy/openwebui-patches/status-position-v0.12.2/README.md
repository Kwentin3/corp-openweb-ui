# Optional native status placement for OpenWebUI 0.12.2

This one-file frontend overlay adds `data.position = "after_content"` to the
existing `status` event. Only that exact value selects the region after the
answer (including its citations/code results), before native message controls.
Missing or unknown positions retain the existing upper status region.

```python
await __event_emitter__({
    "type": "status",
    "data": {"description": "Response $0.01 / Chat $0.02", "done": True,
             "position": "after_content"},
})
```

The values above only illustrate presentation. This patch contains no billing
calculation, provider invocation, content mutation, tool, iframe or new ledger.
It partitions each message's actual status history by position and reuses the
unchanged native StatusHistory/StatusItem renderer in both regions. Each region
keeps its own latest-status/hidden/history behavior, so progress above the answer
does not move when a lower status arrives. Both regions use the existing model
`status_updates` capability guard and preserve native edit/read-only/compact
preview visibility. Cursor visibility considers the latest status in either
region; default-only histories and the legacy status-only cursor path keep their
previous result. An empty filtered history removes that region's renderer output.

## Exact source and application

Pinned upstream commit: `6a18585ff4c2e5f6805f682222cfbc46dc669ef8`.
The manifest binds package/lock identity, original/candidate component bytes and
the reviewable patch. The installer requires exact UTF-8/LF inputs, changes only
`src/lib/components/chat/Messages/ResponseMessage.svelte`, rejects drift before
writing, and accepts an exact already-patched file without changing it.

```text
python deploy/openwebui-patches/status-position-v0.12.2/apply_status.py SOURCE_ROOT --check
python deploy/openwebui-patches/status-position-v0.12.2/verify_installer.py PRISTINE_SOURCE_ROOT
python deploy/openwebui-patches/status-position-v0.12.2/apply_status.py SOURCE_ROOT
node deploy/openwebui-patches/status-position-v0.12.2/verify_frontend.mjs SOURCE_ROOT
```

Apply before the existing native frontend build. The current
`media-upload-v0.12.2` overlay changes different files, so either application
order is compatible. Backend status-event persistence already accepts the
payload as a dictionary (`socket/main.py` and `models/chats.py`); no backend or
other type/schema change is needed. The frontend event consumer stores the
unchanged data in statusHistory. The component's local history-entry type gains
the optional string field; unknown strings are intentionally accepted/defaulted.

## Verification boundary and removal

The focused checks prove exact application/rejection, idempotence, source
identity, actual component status projection on mixed/default/hidden/disabled
inputs, non-mutation, and render-site ordering. They do not prove a Svelte build,
persist/reload behavior or ordinary-user GUI acceptance. Those remain required
before deployment. No production changes, full frontend build or model calls
are part of this source candidate.

Retire the overlay when the pinned upstream version supports this status
position contract natively; planned upstream issue/PR reference: #31897. Recheck
the exact upstream implementation before removing or rebasing. No CSS/DOM
position workaround is used. Removing the overlay restores native upper-only
display; existing persisted position fields remain harmless metadata.
