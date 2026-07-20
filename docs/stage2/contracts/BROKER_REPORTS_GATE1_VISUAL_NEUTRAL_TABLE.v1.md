# Broker Reports Gate 1 Visual Neutral Table Contract v1

Status: implemented contract for restricted, visual-only source recovery.

## Boundary

This contour recovers source-faithful neutral tables from an explicitly declared
page region. It does not calculate tax, infer financial meaning, merge source
identities, or write customer material to knowledge/RAG storage.

`Gate1VisualNeutralTableFactory.create()` is the sole canonical promotion
entrypoint. Local OCR, geometry detectors, table-recognition models, and an
approved bounded visual-model adapter may only produce an observation proposal.
They never have canonical authority.

The runtime module has no PaddleOCR, OpenCV, provider SDK, or filesystem
dependency. Such tools belong to a local private observation adapter. This keeps
the production bundle closed-world and lets the validator replay an observation
without the proposing model.

## Required source scope

Every request binds all of the following before recovery:

- visual source-unit reference, document reference, and one-based page number;
- source image SHA-256 and verified private media bytes;
- opaque access-scope reference from the already-authorized artifact resolution;
- oriented image dimensions and one declared bounding box;
- renderer, preprocessing, OCR engine/model, validator, and recovery-policy
  identities.

A mismatch is terminal. Whole-document provider upload is forbidden. The
default provider policy is disabled and customer-data transfer is unapproved.

## Observation requirements

The sealed private observation records:

- image blankness statistics and orientation;
- every OCR line, bounding box, confidence, text checksum, and repeat checksum;
- every table boundary, cell boundary, span, source OCR-line reference, and
  source text;
- exact OCR-line accounting between table cells and out-of-table content;
- independent grid evidence and checksums for cell boxes and boundaries;
- header rows, header hierarchy, row roles, merge evidence, and totals/subtotals;
- uncertainty entries and their explicit resolution;
- declared continuation relationships between pages;
- zero or explicit provider accounting.

Missing coverage, duplicated line use, invented text, OCR substitution, decimal
separator drift, reordered columns, false boundaries, unsupported merges,
incorrect totals, wrong continuation, source-image drift, and access-scope drift
fail closed.

## Promotion states

- `canonical_table_accepted_deterministic`: repeated OCR checksums are exact,
  confidence is within policy, uncertainty is empty, and structural validation
  passes.
- `canonical_table_accepted_reviewed_visual`: structural validation passes and a
  sealed technical-operator review resolves every recorded uncertainty.
- `unresolved_visual_requires_review`: evidence is missing, ambiguous, blank, or
  a provider proposal is not authorized.
- `unsupported_visual_layout`: the declared layout is outside the bounded
  recovery profile.

An accepted state must contain canonical tables; an unresolved or unsupported
state must not. A model proposal alone cannot select an accepted state.

## Operator review

Review is scoped to one sealed observation and the checksums of its proposed
canonical tables. The operator confirms source-to-table mapping and resolves the
named uncertainty references. The review contract explicitly records that no
financial meaning was assigned and no model authority was used.

## Continuations

Continuation is either `not_applicable` or a declared page sequence with one
group reference and adjacent previous/next page numbers. Cross-document groups,
gaps, and broken links fail validation. Continuation does not authorize merging
cells or values across pages.

## Privacy-safe proof

The safe projection contains only opaque proof identity, terminal state,
aggregate table/row/column/cell counts, uncertainty count, operator-review
status, provider accounting, and validator status. It excludes source refs,
customer values, OCR text, paths, filenames, and private image hashes.

Actual-corpus proof remains a separate private execution. Passing synthetic
tests establishes contract integrity only; it does not establish corpus
coverage, generalization, release readiness, or customer acceptance.
