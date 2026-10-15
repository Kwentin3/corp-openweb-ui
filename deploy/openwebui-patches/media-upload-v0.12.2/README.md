# OpenWebUI v0.12.2 media upload adaptation

Port of the accepted four-file v0.11.4 media exception to official v0.12.2,
commit `6a18585ff4c2e5f6805f682222cfbc46dc669ef8`. This package contains a minimal
source transformer and review diff, not replacement upstream files or a copied
frontend build. Its source hashes reject another release, newline conversions,
mixed states and local edits before any write. Reapplying is harmless.

## Scope and existing owners

- Local uploads write/hash chunks of at most 1 MiB. Other storage providers
  retain their native `upload_file` behavior. Native size/extension checks stay
  in their existing route.
- The custom `accept_upload` handoff asks enabled Event Functions to claim an
  authenticated native File before default processing. An unclaimed file keeps
  native synchronous/background processing. Native `file.uploaded` dispatch
  starts the existing Event Function after a claimed upload.
- The native frontend status stream still owns waiting. When it completes,
  refresh the authoritative File, retain native warnings and expose a failed
  media-preparation state. Copy final filename/size into the normal attachment.

Media preparation, same-ID replacement, retries and source cleanup remain in
the existing `stage2_media_intake` Event Function. STT remains in the existing
Filter/sidecar and starts on Send. This package adds no queue, registry, route,
provider, lifecycle service module or custom frontend state machine.

v0.12.2 still has no synchronous upload-processing handoff; its Event dispatch
is asynchronous. Its default STT-on-upload/indexing and as-is video storage
do not implement the accepted prepare-before-Send workflow. The native status
stream returns status/error, not refreshed filename/size. Recheck these gaps on
the next upstream update and remove the corresponding changes when equivalent
native behavior has passed the same product checks.

## Required build metadata

`manifest.json` records pristine/patched hashes of the four affected files and
official `package.json`, `package-lock.json` and `Dockerfile` hashes.

- Upstream declares Node `>=18.13.0 <=22.x.x`, npm `>=6.0.0`; its Dockerfile
  selects `node:22-alpine3.20`. Qualify with **Node 22** and record the exact
  Node/npm versions and container digest. Upstream does not pin one npm patch
  version. Preserve its lockfile and `npm ci --force` command.
- Upstream's backend uses Python **3.11**; this package's installer/verifiers
  use only the Python 3.11 standard library. No OpenWebUI, database, ML, npm or
  provider import is needed for local backend checks.
- The native build script runs `npm run pyodide:fetch` before `vite build`.
  Preserve this script; it needs the normal upstream build-time network access.
- Resolve and pin the selected official v0.12.2 runtime image digest and the
  Node 22 image digest before building a release. A moving tag is not a receipt.

## Source preparation and local checks

Use a disposable exact upstream checkout with LF files (`core.autocrlf=false`),
not the corporate repository root. Verify its HEAD before patching:

```sh
git -c core.autocrlf=false clone --depth 1 --branch v0.12.2 https://github.com/open-webui/open-webui.git /work/openwebui-0122
git -C /work/openwebui-0122 rev-parse HEAD
# Must print 6a18585ff4c2e5f6805f682222cfbc46dc669ef8.

python /repo/deploy/openwebui-patches/media-upload-v0.12.2/verify_installer.py /work/openwebui-0122
python /repo/deploy/openwebui-patches/media-upload-v0.12.2/apply_media.py /work/openwebui-0122 --check
python /repo/deploy/openwebui-patches/media-upload-v0.12.2/apply_media.py /work/openwebui-0122
python /repo/deploy/openwebui-patches/media-upload-v0.12.2/verify_backend.py /work/openwebui-0122
node /repo/deploy/openwebui-patches/media-upload-v0.12.2/verify_frontend.mjs /work/openwebui-0122
```

The installer checks all four exact source hashes before mutation. A checked
source tree need not contain `.git` (for example, an extracted image); source
hashes establish this overlay's applicability. The release owner must separately
bind the full upstream checkout/image to the pinned commit/digest.

`verify_installer.py` exercises installation, idempotence, check-only mode,
whole-input rejection and backend-only installation in disposable directories.
`verify_backend.py` executes the actual extracted backend function bodies:
bounded writes/byte/hash fidelity, empty/interrupted/collision cleanup, native
non-local fallback, claimed/unclaimed File handoff, process=false/synchronous
fallback, extension checks and max-size cleanup. Native persistence/config,
extension-loading and background-task boundaries use fixtures. These checks
do not prove real authorization, conversion, DB migration or browser behavior.

## Build the frontend from the patched v0.12.2 checkout

Local native equivalent, from that exact patched checkout:

```sh
node --version
npm --version
npm ci --force
# Set APP_BUILD_HASH to the commit above and APP_BUILD_CHANNEL=stable.
npm run build
```

Alternatively use the supplied frontend recipe, which verifies source/lock
hashes before running the same upstream scripts. Set `NODE_IMAGE` to the resolved
Node 22 Alpine3.20 digest. The named context is only this overlay package:

```sh
docker buildx build --file /repo/deploy/openwebui-patches/media-upload-v0.12.2/frontend.Dockerfile \
  --build-context media_overlay=/repo/deploy/openwebui-patches/media-upload-v0.12.2 \
  --build-arg NODE_IMAGE="$NODE_IMAGE" --target export \
  --output type=local,dest=/work/media-0122-frontend /work/openwebui-0122
```

Exported assets are in `/work/media-0122-frontend/build`. Record the artifact
manifest/hash; install that complete build in `/app/build` of the same pinned
v0.12.2 runtime. Keep backend patching inside that image build:

```sh
python /media-overlay/apply_media.py /app --backend-only
python /media-overlay/verify_backend.py /app
```

The runtime root here is `/app`, containing `backend/open_webui/`. Do not layer
the v0.11.4 backend files, old frontend build, old minified composer installers
or legacy `open_webui.services.stage2_*` modules into v0.12.2. Other independent
overlays and runtime integration belong to the release's composition owner.

## Integration and acceptance boundary

Keep current production Function source/Valves and enabled state. In particular,
accepted STT Filter **0.2.6** (PR #559 / `c091819e`) scopes transcription to the
current user message and preserves an explicit task. Older branch copies with
Filter 0.2.5 must not replace that accepted source during this upgrade.

Use a fully separate database **and storage copy** for the trial. The Event's
startup reconciler can resume conversion/deletion for copied pending markers;
inspect these before first start or disable only that Event in the test copy
until its File/storage bindings are verified.

Qualification must cover ordinary-user MP3/M4A/MP4 upload, same File ID and
ownership, no STT before Send, pending Send, final filename/size, transcript
cache and reload, failure/recovery/source cleanup, next-turn explicit tasks,
and an unrelated document's unchanged native processing. Compare chats, File
metadata, stored bytes and skipped side effects; a visible MP3 card or passing
unit harness alone is insufficient.

The package author's initial evidence was limited to local installer/backend
checks. Subsequent integration built and qualified the exact frontend/runtime,
native migration and ordinary-user media workflow; see the
[accepted production release](../../../docs/infra-ops/openwebui-0122-cutover.md).

The concrete prepare-before-Send, same-ID attachment workflow was added to the
[existing upstream discussion](https://github.com/open-webui/open-webui/discussions/24239#discussioncomment-18949752).
It asks whether an existing native seam can replace this adaptation and explains
the distinction from text extraction or pre-storage rejection. This is a feature
discussion, not upstream agreement to merge the patch.

Sources: [official v0.12.2](https://github.com/open-webui/open-webui/tree/v0.12.2),
[Event behavior](https://docs.openwebui.com/features/extensibility/plugin/functions/event/),
[upstream upload-hook discussion](https://github.com/open-webui/open-webui/discussions/24239).
