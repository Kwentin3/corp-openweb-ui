# Broker Reports XLSX Canonical Profile v1

Status: current shadow/storage contract. Production product reads and Wave 2
cutover remain disabled.

## Authority

`CanonicalNormalizerFactory.create().build_xlsx_streaming()` is the only XLSX
normalization entrypoint. `CanonicalArtifactStoreFactory.create()` is the only
persistence entrypoint. The OpenWebUI retrieval loader is not canonical
authority.

The selected implementation is `DIRECT_OOXML_STREAMING`. This is the bounded
replacement path for the existing stdlib OOXML adapter, not an additional
product parser. It was selected after the exact OpenWebUI loader and
`openpyxl(read_only=True)` alternatives failed the required structural or
formula/cache contracts.

## Logical profile

The profile preserves workbook and sheet order, sheet visibility, source
coordinates, merged ranges, named ranges, table definitions, hyperlinks,
hidden rows/columns, formulas, cached values, formula attributes, shared
formula references, shared-string references, style references and number
format references.

Shared strings and styles are workbook dictionaries. Cells reference them by
stable IDs. Blank styled cells are retained as contiguous row runs; empty
declared ranges are never expanded into cell objects. Formula text and cached
value are separate fields. A missing cache is explicit and never calculated or
fabricated.

Unsupported features and inconsistent dimensions produce explicit
`UNSUPPORTED` or `PARTIAL` issues. Charts, drawings, pivots, macros, external
references and data connections are not silently interpreted.

## Streaming and persistence

Worksheets are parsed forward-only and emitted in fixed chunks of 256 source
rows. Memory is bounded by workbook dictionaries plus the current sheet/chunk.
The physical layout is `xlsx_row_chunked_v1`.

Each staged chunk is hash-sealed. Resume requires an exact match on source
hash, normalizer/profile/policy versions, tenant, document, source artifact,
MIME and chunk size. Drift or chunk tampering fails closed.

Publishing reserves a `CANDIDATE`, writes one bounded immutable component at a
time, validates the logical root incrementally, and finalizes the complete
component graph atomically. Activation is a separate compare-and-set step.
Failures before finalization purge only the unlinked candidate components; no
partial active pointer is permitted.

## Resource and oversized-workbook policy

Target jobs run with concurrency 1, 0.5 CPU, 1 GiB RAM with no additional swap,
128 PIDs and bounded block I/O. The current input cap is 16 MiB; ZIP part,
uncompressed-size, member-size and compression-ratio guards apply before row
streaming. Capacity and component-count checks run before publication.

Inputs outside the frozen limits are rejected explicitly. Operators must not
raise memory limits, expand empty dimensions, load all sheets into DataFrames,
or retry through the legacy XLSX adapter.

## Non-authority

This profile does not evaluate formulas, infer financial semantics, use
Knowledge/RAG, call providers, enable global canonical reads, migrate Wave 2,
remove the legacy handoff or start Gate 3.
