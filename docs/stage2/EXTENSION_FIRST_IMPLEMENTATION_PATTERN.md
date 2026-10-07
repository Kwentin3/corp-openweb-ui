# Extension-First Implementation Pattern

## Principle and current authority

Use the simplest existing owner that preserves the agreed user outcome and
keeps OpenWebUI updates reproducible. The current upgrade scope and permissions
are defined by [issue #474](https://github.com/Kwentin3/corp-openweb-ui/issues/474),
revision 2026-10-02. Historical implementations are evidence, not instructions
to carry their patches into a new version.

This is a standing rule for new Tools, Functions, integrations and user features,
starting with the first design discussion, as agreed by the owner on 13 September
in #474. It does not authorize a mass rewrite of accepted integrations or grant
production, provider, patch or merge permissions for another task.

Evaluate solutions in this order:

1. Existing component and native OpenWebUI settings or capabilities.
2. Documented Tools, Functions, OpenAPI connections, events and server APIs,
   verified against the selected release.
3. A thin adapter to an existing domain service where a real gap requires it.
4. An existing external alternative when the native mechanism is insufficient.
5. New code only for the remaining demonstrated gap.

A loader, Function or sidecar name does not establish native compatibility.
DOM/fetch interception, compiled frontend changes, route replacement, modules
copied into the core and runtime dependency installation remain modifications
or internal dependencies. Do not conceal them inside an extension.

Distinguish a supported extension contract, an internal dependency such as a
native model/Storage import or direct table read, and a behavior patch such as
frontend interception or monkey-patching. A small file or separate directory
does not change that classification. Prefer a supported API and isolate any
necessary internal dependency in one version-specific adapter.

In the existing issue/PR, briefly connect the user outcome, extension seam,
domain owner, version dependencies, disablement and next-upgrade check. A few
sentences suffice for a simple integration; do not create a parallel registry
or ADR for every feature. Disabling a capability may remove that capability,
but must preserve ordinary chat, shared data, permissions and independent domains.

## Ownership and boundaries

OpenWebUI owns authentication, permissions, chats, files, attachments and the
model/tool loop. Use the context and access checks provided by the selected
version's native extension contract. Keep an internal Python dependency inside
one narrow adapter and state its supported versions.

Existing OfficeCLI, STT and Terminal services retain their domain work. Adapters
translate transport and representations; they do not duplicate document
semantics, provider dispatch, user registries or file storage. Prompts/Skills
carry reusable instructions. A normal Prompt is sufficient for the transcript
summary and meeting-minutes templates; do not add a catalog reader for them.

Do not introduce another agent loop, universal gateway or a service per small
operation. Compatible components need no rewrite for architectural appearance.

## Current STT reference and migration boundary

The accepted source workflow is documented in
[STT Native Media Transcription Runbook](operations/STT_NATIVE_MEDIA_TRANSCRIPTION_RUNBOOK.md):

```text
ordinary chat attachment
-> native File upload
-> server preparation of recognized media into MP3 before Send
-> wait for preparation when Send is pressed early
-> ordinary-chat audio Filter
-> existing STT service and Lemonfox provider
-> persisted transcript and ordinary chat result
```

This is a source contract; deployed identity and product acceptance must be
checked separately. Microphone dictation is a distinct workflow. The older
Transcribe Action and browser ffmpeg.wasm implementation are historical and
must not become the target specification.

The current media preparation uses version-specific core/frontend overlays.
For a new official image, first prove what its native mechanisms preserve:
preparation before Send, waiting, agreed retries and cleanup, persistent
attachments, cached transcription and recovery after interruption. A notification
after upload does not by itself prove that processing can be intercepted before
it happens. If a native replacement loses a guarantee, report the exact gap and
minimal options before changing the contract.

The accepted 0.11.4 release uses the approved four-file media exception and
`stage2_media_intake` Event Function, with Filter v0.2.5 consuming prepared audio
or its stored transcript. The Event Function is the only preparation/retry/
cleanup owner. This remains an exception requiring a custom image and internal
File/Storage compatibility checks; upstream publication or acceptance is not
claimed. Current acceptance and retained recovery assets are recorded in the
[backup/upgrade runbook](../ops/BACKUP_RESTORE_RUNBOOK.md).

## Changes requiring an owner decision

Issue #474 requires separate approval before introducing a new patch, including
on staging. Supply the demonstrated gap, tested alternatives, exact diff and
scope, pinned versions, Git history, reproducible application, test, rollback
and removal condition. An approved exception remains an exception.

For every controlled exception, retain its stable identifier, affected files
and behavior, owner decision, upstream version and exact commit/image digest.
Keep the patch, required dependencies and reproducible build recipe in Git.
Record focused checks, rollback and a concrete condition for removal alongside
the patch or in the existing PR, preserving adaptation history in Git.

Apply the patch to the pinned candidate during preparation/build. Unknown
versions, ambiguous signatures, partial application or a mismatched starting
state must stop preparation; never silently skip a patch or repair a running
container by hand. Reapplication must recognize the exact already-applied state
or fail without partial changes.

On every upgrade, first check whether a native replacement now preserves the
required outcome. Remove a redundant exception after a focused check; otherwise
explicitly qualify its necessity and compatibility on the isolated candidate.
An unchanged-scope transfer may be covered by an explicitly authorized upgrade,
but #474's separate-patch approval rule takes precedence for that task. Expanding
meaning or scope requires a new decision. A deep fork needs a separate owner
decision; approval of a narrow patch does not authorize one.

Keep domain semantics outside upstream files. Native integration is a means of
reducing maintenance, not a reason to build a large replacement subsystem merely
to avoid acknowledging a small justified exception.

Replace a historical path only after its replacement proves the same required
result. A temporary Terminal link or preview does not replace a permanent chat
attachment with permissions, download and continuation from the latest version.
Remove obsolete integration hooks while retaining historical files and data.
Retirement of historical data/runtime follows the owner's explicit selection;
the completed #474 retirement is recorded in the backup/upgrade runbook.

## Verification and updateability

Check a small complete slice through the ordinary user route and inspect its
actual result. Administrative HTTP success, mocks and green CI alone do not
qualify the user workflow. Respect auxiliary-task boundaries and the applicable
provider budget; do not substitute another model to obtain a PASS.

Pin the official image version and digest. Recreating that container and
installing only declared extensions must reproduce the accepted state. Check
that disabling an extension preserves ordinary chat and independent features.
State any remaining internal dependencies and approved exceptions explicitly.

Use the existing Compose/installers and deployment runbooks. Test restoration
before migrating copied data. Production downtime, merge/CD and cutover require
the release/window decision specified by #474. Keep the old compatible data
and runtime through the agreed rollback window; switching an image tag cannot
undo a schema migration. After the owner authorizes retirement, use the verified
retained recovery set and current source/build recipe. The removed 0.9.6 stack
is no longer a restart target. Preserve new writes before any recovery.
