# Goal #391: Native PDF upload compatibility-seam audit

Date: 2026-09-06

Scope: the one frontend bundle patch that makes ordinary OpenWebUI chat upload
safe for the private NDFL document route. This is an architecture decision,
not a product-pass receipt.

## Decision

Keep the narrowly scoped compatibility seam for the pinned OpenWebUI `v0.9.6`
image. Do not expand it and do not describe it as a native OpenWebUI feature.

The patch changes only the request default for PDF uploads while exactly one of
the two NDFL entry models is selected:

```text
standard chat upload UI
  -> native POST /api/v1/files/?process=false
  -> native owner-scoped file custody
  -> Gate 1 Pipe / ArtifactStore
```

All other models and non-PDF uploads retain upstream behavior.

## Why it remains necessary

In the pinned upstream build, chat upload defaults `process=true`. Processing
can extract source content and create native vector/RAG material before the
Pipe sees the source reference. The earlier runtime incident demonstrated that
an empty Knowledge collection did not mean that raw customer uploads avoided
vectorization.

The backend already offers the appropriate native request contract,
`process=false`, but the ordinary chat UI does not expose a model-scoped way to
select it. Setting `file_context=false` was tested and did not stop processing
on this route. A Pipe runs too late to alter the upload request.

## Boundary and safeguards

- Owner: OpenWebUI continues to own login, selected-model state, upload API,
  file ownership and chat UX.
- The Pipe continues to own document workflow orchestration, not browser
  state or upload authorization.
- `apply_native_broker_pdf_upload_patch.py` makes one textual change in the
  pinned build bundle; it is fail-fast if its exact upstream signature changes
  or appears more than once.
- `test_openwebui_native_broker_pdf_upload_patch.py` verifies model scope,
  PDF scope, idempotence, ambiguity rejection and Dockerfile ordering.
- It neither adds a second upload endpoint nor sends a document to a browser
  sidecar, a second provider, or a second storage owner.

This is a compatibility seam in image assembly, not an application-core fork:
the upstream image remains the base and a drift fails the image build. It is
nevertheless the only deliberately retained non-native seam for this route and
must remain visible in release review.

## Removal condition

Remove this patch only after an upstream-supported per-model chat-upload
configuration can make the ordinary selected-model route send
`process=false`, and a synthetic browser proof shows all of the following:

1. ordinary user upload succeeds through the standard chat UI;
2. the Pipe receives the native source reference;
3. no document/Knowledge/vector delta is created for the source case;
4. owner-scoped source purge still works; and
5. the product model does not regress for any other upload type.

Until then, removing it would restore a known confidentiality and operational
failure mode. Keeping it does not by itself prove the Goal #391 product
outcome: that still requires a complete, admissible control document and the
private user receipt from final Canonical through the right-bank read.
