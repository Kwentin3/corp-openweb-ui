# G3.4C frozen plan and invariants

Status: `EXECUTED_ONCE`

Date: 2026-08-07

This live reproof used the already implemented Gate 3 boundaries without
changing their meanings:

- `Gate3ProjectionFactory.create` remained the projection owner;
- `Gate3StructuralChunkFactory.create` remained the structural chunk owner;
- `Gate3FinancialLabelDictionaryFactory.create` loaded the exact
  `broker-reports-financial-labels@1.0.0` dictionary;
- `Gate3BoundedLabelingFactory.create_from_chunk` reused the exact G3.4
  instruction, provider route and fail-closed response validator;
- `Gate3ChunkBatchLabelingFactory.create` owned only sequential selection,
  terminal outcome accounting and deterministic in-memory concatenation.

The G3.4B module hash was frozen before execution as
`203477af5d239c6a358dd3468c6727890fd94d9df8ac718b30fb0aef5edae0ba`.
Its `60000` character bound, structural boundaries, zero row overlap, context
envelope, aliases and row groups were not changed.

The request plan was frozen before the first call: one compact document in
full, all six chunks of the large CSV, and five structurally selected chunks
from the 76-chunk REPO document. Selection used only chunk kind, table
identity, row range and size; it did not inspect financial meaning or expected
labels.

Execution was sequential. Each selected chunk had at most one provider
submission. Retry, response repair, fallback, parallel classification,
dictionary mutation, persistence and product activation were all zero.
