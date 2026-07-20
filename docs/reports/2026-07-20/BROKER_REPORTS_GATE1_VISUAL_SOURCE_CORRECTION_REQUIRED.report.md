# Broker Reports Gate 1 visual source correction required

Date: 2026-07-20
Status: **NOT_CLOSED**

## Outcome

The last claimed material visual scope cannot be recovered from the currently
authorized source bytes. This is not an OCR, DPI, crop, rotation, renderer, or
table-profile failure. The normalized ArtifactStore render and the original PDF
page are independently proven byte-uniform.

The scope remains material as claimed. It was not removed from the denominator,
reclassified, or reconstructed from adjacent pages. Goal 3 therefore remains
10/11 and correctly deferred pending source-owner correction.

## Measured source evidence

| Check | Result |
| --- | ---: |
| Source identity records | 2 |
| Exact source binary copies | 2 |
| Unique source binary hashes | 1 |
| Target page | 8 of 19 |
| Normalized page renders | 2 |
| Normalized non-white channel values | 0 |
| PDF content streams / bytes | 0 / 0 |
| Text characters | 0 |
| Images / XObjects | 0 / 0 |
| Drawings / links / annotations | 0 / 0 / 0 |
| Contentful non-target pages | 18 |
| Other blank pages | 0 |

PyMuPDF and pypdf agree on the page structure. PyMuPDF renders at 72, 144,
288, and 300 DPI are uniformly white. MediaBox and CropBox rendering agree. An
alpha render contains zero visible pixels. Both normalized ArtifactStore page
renders are pixel-identical to the independent 144 DPI source render.

## Failed invariant and ownership

- Failed invariant: `VISUAL_SCOPES_CANONICAL = 11_OF_11`.
- Current evidence: 10 accepted scopes, one claimed material source page with no
  visible or structural PDF content.
- Owner: authorized source owner.
- Narrowest remaining action: confirm or replace the claimed material but
  byte-uniform page in an authorized source binary.

The replacement is accepted only after all of the following pass:

1. Replacement source identity is authorized.
2. The target page contains visible source evidence.
3. Source-hash and page-render lineage are rebuilt.
4. Bounded visual recovery replays identically twice.
5. The canonical-table validator passes.
6. The Gate 2 visual-package validator passes.

Inference from adjacent pages is forbidden because it would invent source
evidence. A model remains proposal-only and cannot make an empty page canonical.

## Safety

The proof used the maintained ArtifactStore factory and resolver, then matched
the original private PDF copies by their validated hash. ArtifactStore remained
unchanged. Provider calls, uploads, Knowledge/RAG use, vectorization, and model
canonical authority were zero.

The safe evidence contains no customer values, filenames, private paths, raw
hashes, or raw artifact/document/source identifiers:
`BROKER_REPORTS_GATE1_VISUAL_SOURCE_CORRECTION_REQUIRED.v1.safe.json`.
