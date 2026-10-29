# Final provider request debugging for OpenWebUI 0.12.2

Opt-in debugging of the exact UTF-8 request body prepared for dispatch by the native
OpenAI-compatible chat router. It records the model, system instructions,
history, tool schemas/results, images and opaque fields passed to the native
HTTP sender. It does not reconstruct or modify context.

The supported upstream commit is `6a18585ff4c2e5f6805f682222cfbc46dc669ef8`.
The installer accepts the pristine router or the exact accepted
[Responses context overlay](../tool-context-v0.12.2/README.md), applied first.
It checks complete input/output hashes and a unique final serialization point,
fails on unknown source, and is idempotent. Source hashes are in `apply_capture.py`.

## Observation boundary

The observer runs after model alias resolution, Workspace Model system/parameter
insertion, provider-prefix removal, Azure/Responses conversion and final native
serialization, immediately before the native HTTP sender. Request Filters run
earlier and cannot show all of those changes.

This one seam covers ordinary `/api/chat/completions`, native tool continuations
and community/native subagents routed through `generate_chat_completion`.
It adds no provider client, prompt assembler, tool loop or proxy.

Each captured `NNN.request.json` is the exact serialized body; its sibling
`NNN.receipt.json` contains SHA-256, size, time, scope/chat/message IDs, task,
child iteration, selected alias and the final outbound model, plus URL host/path.
No connection headers, cookies or API keys are accepted by the helper. Provider
response bodies and response model echoes are not captured.

## Prepare the diagnostic image

Build outside production on the exact accepted immutable image, preserving its
other overlays. The example intentionally requires an operator-supplied image:

```sh
docker build --build-arg OPENWEBUI_BASE_IMAGE="$accepted_image" \
  -f deploy/openwebui-patches/provider-context-v0.12.2/runtime.Dockerfile \
  -t local/openwebui-provider-debug:0.12.2 \
  deploy/openwebui-patches/provider-context-v0.12.2
```

Installation and verification run inside that image. Component CI builds the
actual ordinary runtime Dockerfile's `backend` target, including the existing
context/media overlays and this observer; no duplicate installation recipe is
maintained. The ordinary
0.12.2 runtime builder and its public context packager include this facility,
disabled by default, so later routine releases retain it. The command above
also supports adding it to an existing accepted image without rebuilding its
frontend or unrelated integrations. Preparing an image does not activate
recording or change the deployed image. Deploy through the existing Compose
owner, with the usual immutable identity and rollback record.

## Enable one bounded reproduction

Use a saved chat UUID, not an unsaved `local:` chat. Run the installed CLI inside
the diagnostic WebUI container as its runtime owner. Replace `webui_container`
with the exact intended container name:

```sh
docker exec "$webui_container" python -m open_webui.utils.provider_capture_control \
  enable --chat-id "$chat_id" --ttl-seconds 900 --max-requests 20 \
  --include-task sub_agent --include-native-subagents
docker exec "$webui_container" python -m open_webui.utils.provider_capture_control status
```

Without a protected `DATA_DIR/forensics/provider-context/capture.json`, capture
is off. The CLI writes that config atomically, creates a fresh run UUID, refuses
to replace an active run, and limits its lifetime to at most one hour. The helper
also refuses manually supplied expiries more than one hour in the future. Default
limits are 20 requests and 128 MiB of request bodies; maximum body storage is
256 MiB. Counts and body bytes share one locked budget across the whole run,
including parallel calls and child chats. Recording limits stop recording,
not model execution; bound the reproduction separately with native chat controls.

Main-chat requests are included by default. Tasks are excluded unless named by
`--include-task`; `sub_agent` admits the pinned community Sub Agent execution
loop. Its `sub_agent_summary` requests require a separate explicit task flag.
Title/tag/follow-up and other auxiliary tasks stay excluded by default.

The helper verifies the authenticated user's ownership with the native `Chats`
reader. `--include-native-subagents` additionally admits distinct saved child
chats only through native `meta.internal/type/parent_chat_id` lineage back to
the selected chat, checking every owner's ID and rejecting cycles or chains
over eight links. Parent lineage is not guessed from prompts or session strings.
Other chats and users are excluded.

The current community plugin shares parent chat/message IDs between parallel
children. Its existing metadata supplies the child task and iteration but no
unique sibling identity. Capture numbers identify requests; they must not be
presented as authoritative agent identities.

## Read and stop

`status` prints only scoped configuration, body counts/bytes and whitelisted
technical receipts. Read exact request bodies separately in the protected run
directory when diagnosing a specific reproduction. Those bodies can include
private conversation/document data and tool-returned credentials; keep them
outside Git, public reports and user-facing responses. The helper preserves
the actual body rather than redacting it into a misleading input.

```sh
docker exec "$webui_container" python -m open_webui.utils.provider_capture_control disable
docker exec "$webui_container" python -m open_webui.utils.provider_capture_control status
```

Disable removes only the active config and preserves evidence. The CLI and
writer share a control lock so a disabled/replaced config is checked again
after the asynchronous native ownership read. Files are mode 0600 and the
diagnostic/run directories mode 0700; unsafe existing permissions, symlinks,
invalid configuration or I/O/DB failures make the observer skip recording
without changing the model request. Remove retained runs through the normal
authorized evidence-retention procedure. The installed facility can remain
available with capture disabled; no background recorder or second WebUI is
needed. To roll back the image change, restore the saved accepted image through
Compose. Disabling capture is independent of rolling back the image.

## Limits of the evidence

- `selected_model` is the selected Workspace Model ID; `provider_model` comes
  from the actual outbound body. It proves the model requested, not a provider
  response's serving model or hidden provider internals.
  Classic Azure removes `model` from that body, so this field is null there;
  the deployment is present in the captured URL path.
- A request containing `previous_response_id` is marked `outbound_delta`.
  Provider-retained prior state is not present in those bytes. Inspect the
  preceding captured requests separately; do not claim a full state snapshot.
- Direct `/openai/responses`, generic OpenAI proxy routes, Ollama, external
  browser-direct connections and other processes have different senders and
  are outside this package's observation seam.
- Capture occurs before the native HTTP call. It proves what was prepared for
  dispatch; a failed connection or cancellation can prevent transmission.
  A captured request alone does not establish provider receipt, skill adequacy
  or correctness of the model's resulting document.

Remove this overlay when a pinned upstream release exposes an equivalent
supported final-request debugging seam and passes the same checks.
