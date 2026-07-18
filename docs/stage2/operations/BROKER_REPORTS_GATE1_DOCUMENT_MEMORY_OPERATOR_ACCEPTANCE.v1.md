# Broker Reports Gate 1 document-memory operator acceptance v1

Status: required, not yet performed for the actual mixed-format pilot corpus

## Acceptance corpus

Use one approved stage case containing accessible actual source bytes for at
least:

- one supported CSV;
- one supported static HTML document with material text and a table;
- one supported text-layer PDF with page/layout provenance and a material
  table or an explicit table-review outcome.

Do not upload customer documents to Knowledge/RAG/vector storage. Use the
maintained `process=false` artifact intake and the Gate 1 factory path.

## Automated preconditions

- Repository tests and bundle tests are green at the delivered revision.
- Stage Gate 1, Gate 2 source and Gate 2 domain Function bundle SHA-256 values
  match the repository.
- Managed Prompt versions/hashes match where those prompts changed.
- Mixed case has one source-file identity and one logical-document identity per
  v1 source file.
- Every accepted document reports validator-passed accounting and
  zero-silent-loss.
- Gate 2 input readiness resolves only the DCP/document-memory public boundary.
- Wrong-context, source-delete and case-purge checks fail closed as contracted.

## Operator review

For each document, compare the original approved source with resolver-accessed
private memory and record pass/fail for:

1. document identity and obvious metadata;
2. beginning, middle and end order/context;
3. every declared sheet/page/table/section in the profile scope;
4. material table headers, row order, cell boundaries and source values;
5. PDF page provenance and readable table context;
6. explicit issues for anything unresolved, excluded or unreadable;
7. absence of a false `complete` state when material content is missing;
8. sufficiency of preserved context for later Gate 2 interpretation without
   reading the original container directly.

Record reviewer id/role, stage case id, run id, source document refs, bundle
hashes, timestamp, per-document verdict and a redacted reason for every failure.
Do not copy private source values into the operator report.

## Acceptance rule

Global Gate 1 may be product-accepted only when all automated preconditions pass
and the operator accepts every supported document in the representative case.
Synthetic fixtures may prove mechanics but cannot replace this actual-pool
acceptance.

