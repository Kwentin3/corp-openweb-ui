# Broker Reports Goal 2 — Visual Review and Canonical Promotion

Date: 2026-07-21

Status: `COMPLETED`

Accepted base: `9e927a0c654329f8c4c648240726a21a88e923a0`

Implementation revision: `64d8f7325ef31d89624902b4a2b4bb22a24d717a`

## Verdict

The maintained dual-VLM runtime remains proposal-only.  A visual table becomes
canonical only through `PdfVisualTableReviewFactory.create`, with review
authority bound by server context, a valid bounded-crop lineage, a schema-valid
candidate, explicit region/cell accounting, an accepted review decision and a
mutation-sensitive seal.

Provider agreement is evidence only.  It cannot call the promotion boundary or
make a Gate 2 package.  Local OCR is neither evidence nor a fallback.  The
runtime and review route remain default-off until the later atomic stage-release
goal.

## Maintained boundary

The implementation preserves four ownership domains:

1. `pdf_dual_vlm_runtime.py` owns bounded Gemini/OpenAI proposals and keeps
   canonical output null.
2. `pdf_visual_table_review.py` owns authenticated review, exact correction
   accounting, receipt creation, sealing and projection creation.
3. `visual_table_review_contracts.py` owns the versioned receipt/seal/projection
   validators exposed through `gate1_public_contracts.py`.
4. `Gate2TablePackageFactory.create` remains the only normalized-table package
   entrypoint.  It accepts a reviewed visual projection only when the embedded
   receipt, accounting, projection integrity and seal all revalidate.

The receipt binds the source document hash, page, crop and exact image hash,
both provider proposal hashes, canonical candidate hash, reviewer identity and
type, validator version, decision, correction hashes, accounting hash, seal and
the existing private ArtifactStore lifecycle `private_ready`.

Supported decisions are:

- `accepted_without_correction`;
- `accepted_with_correction`;
- `rejected`;
- `unresolved`;
- `unsupported`.

Only the first two can produce a canonical projection.  Every other decision
produces a sealed terminal receipt and no packageable canonical result.

## Anti-bypass results

- A self-asserted PDF `canonical_validation=passed` without the deterministic
  neutral profile or the reviewed-visual contract is rejected at Gate 2.
- Provider consensus cannot create a review authority or canonical table.
- Accepted-with-correction requires an acknowledgement for every deterministic
  proposal/candidate diff and corrected action on affected retained cells.
- Every canonical cell has exactly one reviewer-supplied normalized image
  region and observed-text hash; non-table regions are accounted separately.
- Mutating a receipt, accounting region, private value, projection or seal makes
  validation fail.
- Gate 2 records upstream VLM/page-render provenance explicitly while its
  existing privacy flags remain scoped to Gate 2 package construction itself.
- Receipt and seal schemas are accepted by the existing immutable ArtifactStore
  as private payloads; no parallel store or lifecycle was introduced.

## Verification

- Focused review/promotion tests: `12 passed`.
- Full service suite: `989 passed, 20 skipped, 5 existing PyMuPDF SWIG
  deprecation warnings`.
- Focused Ruff over new and relevant clean production/test files: passed.
- Repository-wide Ruff is not claimed green; legacy files have pre-existing
  diagnostics outside this Goal's contract.  They were not opportunistically
  rewritten.
- Bundle build repeated with identical SHA-256 values:
  - Gate 1: `f9836a2bbcd0e2122bf4a11a1e317e880a750121d2dacefd57dd95594b5b4ec3`;
  - Gate 2 source: `44aa9187e333116708760e64a66d8241c1a168e198c347cf56742c4b814de6ed`;
  - Gate 2 domain: `788b9dd4a1853955d829f5c98b4625b04a790962d729ce10d9208d7e381bbdf3`.
- Heavy local OCR production imports: `0`.
- Stage mutations: `0`.

## Acceptance

```text
VISUAL_REVIEW_CONTRACT:
VERSIONED

REVIEW_RECEIPT:
SOURCE_BOUND_AND_SEALED

PROVIDER_CONSENSUS_AUTO_ACCEPTANCE:
ZERO

LOCAL_OCR_EVIDENCE:
ZERO

CANONICAL_PROMOTION_WITHOUT_REVIEW:
ZERO

ACCEPTED_VISUAL_TABLE_GATE2_HANDOFF:
PASSED

REJECTED_OR_UNRESOLVED_RESULT:
NOT_PACKAGEABLE_AS_CANONICAL
```

The safe receipt contains no customer documents, customer values, crop bytes,
raw provider output or private paths.  It does not claim customer acceptance.
