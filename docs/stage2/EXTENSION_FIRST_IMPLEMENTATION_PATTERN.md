# Extension-First Implementation Pattern

## 1. Principle

New OpenWebUI-facing features should first be evaluated through OpenWebUI-native
extension mechanisms before considering a fork.

Preferred order:

1. Native OpenWebUI configuration / workspace / model / prompt / knowledge
   mechanisms.
2. OpenWebUI Functions / Actions / Tools / OpenAPI Tool Servers.
3. Thin static loader or minimal UI integration patch.
4. Private backend/domain sidecar.
5. Deep OpenWebUI fork only if all above are insufficient and a decision record
   approves it.

## 2. Why

- Preserves OpenWebUI updateability.
- Keeps users in native OpenWebUI UX.
- Keeps domain logic isolated.
- Avoids provider keys in browser.
- Allows admin-side configuration through valves/settings where possible.
- Reduces merge burden.

## 3. STT Reference Implementation

Stage 2 STT MVP confirms this pattern:

```text
static loader UX shim + Action Function + private sidecar + provider adapter
```

Implemented path:

```text
OpenWebUI media attachment
-> static loader Transcribe action
-> browser ffmpeg.wasm normalization when needed
-> OpenWebUI process=false prepared-audio upload
-> OpenWebUI Action Function
-> private stage2-stt sidecar
-> Lemonfox adapter
-> transcript returned to OpenWebUI composer/chat UX
```

Status:

```text
Stage 2 STT MVP: implemented/proven/current-stage closed.
Remaining STT work: testing/hardening, not architectural discovery.
```

## 4. What Belongs Where

OpenWebUI/static loader:

- visible UX affordance;
- browser-only preprocessing if needed;
- progress/status;
- calls OpenWebUI-native APIs.

Action Function:

- OpenWebUI context bridge;
- admin-configured valves;
- thin wrapper;
- calls sidecar.

Sidecar:

- provider keys;
- provider adapters;
- domain contracts;
- validation;
- storage/retention;
- job state;
- transcript/result normalization.

Provider:

- external service only.

## 5. Anti-Patterns

- Separate user-facing sidecar GUI for MVP.
- Direct browser-to-provider calls.
- Provider keys in frontend.
- Deep fork as first move.
- Hidden magic LLM trigger as only UX.
- Reading OpenWebUI private storage/database as an undocumented product
  contract.
- Broad rewrites of OpenWebUI UI when an Action/static loader hook is enough.

## 6. When A Fork May Be Acceptable

A deep OpenWebUI fork may be considered only when:

- native mechanisms fail;
- runtime proof shows the extension path is insufficient;
- the patch cannot remain thin;
- owner/ADR explicitly approves the fork.

Until then, future Stage 2 features should start from the extension-first order
above and keep backend/domain logic in isolated services or adapters.
