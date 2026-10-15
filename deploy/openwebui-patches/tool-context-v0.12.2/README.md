# OpenWebUI v0.12.2 Responses context overlay

Exact upstream commit: `6a18585ff4c2e5f6805f682222cfbc46dc669ef8`.
This replaces the transport/reasoning portion of `tool-history-v0.11.4` for the
new release. The history-ordering fix #31593 is already native and is not patched.

The native `get_openai_connection(model['urlIdx'])` selects the actual connection
API type. For Responses, existing converter options preserve tool-result images
inside their result and carry encrypted reasoning at its original position. The
existing foreign-model guard also removes model-bound encrypted content. The
existing provider converter admits only API fields. Chat Completions and Ollama
keep their native image/reasoning representation. No prompt, provider client,
tool loop or storage owner is added.

The existing Responses converter projects call IDs longer than 64 characters to
the full SHA256 hex of their original UTF-8 value. It applies the same projection
to the call and its result only in the outgoing API representation. IDs up to
64 characters pass through unchanged. Original history, including Google IDs
that carry opaque thought signatures, stays intact for a return to that provider.
Distinct original IDs must remain distinct after projection, including collisions
with unchanged short IDs; incomplete long pairs and long-ID projection with
`previous_response_id` fail before sending. The converter copies its input dict
before consuming fields, so refusals also leave the caller input intact.
This adds no Chat Completions ID transformation and does not close all model-switch
routes. Preserve `ENABLE_RESPONSES_API_STATEFUL=false` for the candidate.

The middleware changes cover initial history reconstruction, pending approved
responses, approval resume, the stateful and stateless tool continuations, the
second reconstruction after native compaction, and code-interpreter continuation.

## Installation and verification

Copy this package into the exact v0.12.2 image, then run inside that image:

```sh
python /path/to/tool-context-v0.12.2/apply_context.py --check
python /path/to/tool-context-v0.12.2/apply_context.py
python /path/to/tool-context-v0.12.2/verify_context.py -v
```

Both scripts accept `--root /path/to/backend/open_webui`; the default is
`/app/backend/open_webui`. Installation preflights every input hash and unique
anchor before writing any file, validates the complete result hash and Python
syntax, and accepts an already-patched result unchanged. Unknown source fails
closed. `ORIGINAL` and `PATCHED` in the installer are the source manifest.
The preceding overlay's router hash is not an admitted input for this revision;
prepare a fresh exact-upstream source/image rather than patching that installed
result in place. The middleware and misc result hashes remain unchanged.

The verification executes pure functions extracted from the installed source,
including middleware reconstruction and actual Responses payload conversion.
It checks exact hashes, call/result order, parallel batches, stable prefix,
render-before-edit image position, unchanged user intent, opaque reasoning field
admission/order, cross-model stripping, non-Responses fallback, incomplete calls,
display-only exclusion, every middleware conversion call site, and installer
idempotence/drift rejection. Call-ID checks cover both native input shapes,
63/64/65-character boundaries, complete replay and Google reconstruction,
distinct long IDs sharing their first 64 characters, collision with an unchanged
native ID, incomplete pairs, stateful refusal, unchanged short stateful output
references, and preserved item IDs, UTF-8 arguments, images and user content.
No DB, server, network or provider is used by the
verification scripts. This is source-bound component evidence, not portal or
provider acceptance.

## Compaction acceptance constraint

v0.12.2 native `_find_compaction_boundary` can start the retained window directly
at an assistant tool-call message. A separate immediately preceding opaque
reasoning carrier can then fall into the summarized prefix while its call is
retained. The tested carrier shape is introduced by this preservation overlay;
pristine reconstruction already drops native opaque reasoning. This is a pure
boundary reproduction and a constraint on a preservation fix, not a separately
proven unmodified-server end-to-end defect. Passing options to the second
reconstruction prevents a separate
unconditional loss even with compaction disabled; it does not repair native
boundary selection when compaction actually occurs.

This package deliberately does not change `context_compaction.py`. The root
integration audit verified production `chat.context_compaction.enable=false`;
preserve that setting for the accepted production configuration. Active
compaction requires separate qualification before claiming that mode works.
Run the discriminating probe against the installed source:

```sh
python /path/to/tool-context-v0.12.2/repro_compaction_boundary.py
```

The probe exits 1 if the native two-round boundary drops `rs_second` while
retaining its `edit-2` call. It never enables compaction or generates a summary.
Stateful compatibility and provider replay still require normal-route acceptance;
this overlay neither enables the flag nor proves provider support.

Remove each change when the selected upstream release passes the same context
checks natively. Do not apply the old v0.11.4 overlay on top of this package.

## Delivery and upstream reports

The overlay is qualified in the
[accepted production release](../../../docs/infra-ops/openwebui-0122-cutover.md).
[Issue #32473](https://github.com/open-webui/open-webui/issues/32473) reports the
same-model reasoning loss, image provenance and qualified compaction constraint.
[Discussion #32474](https://github.com/open-webui/open-webui/discussions/32474)
asks for the supported cross-provider call-ID contract. Source-level reproductions
were rerun on the exact release and current `dev` on 2026-10-15; a full unmodified
`dev` server run and upstream acceptance are not claimed.
