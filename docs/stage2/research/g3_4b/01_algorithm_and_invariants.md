# G3.4B structural chunking: algorithm and invariants

Status: `IMPLEMENTED_INACTIVE`

The only entrypoint is `Gate3StructuralChunkFactory.create(document_id,
context)`. It reads one active canonical version through the existing
`Gate3ProjectionFactory` render plan. The projection factory remains the sole
Markdown renderer and alias owner.

The v1 bound is exact Python `len(model_view.content)` with a default maximum
of 60,000 characters, including the context-only wrapper. It is deliberately
not a token estimate and introduces no tokenizer or provider dependency.

Algorithm:

1. Return the exact G3.2 projection as one chunk when it fits.
2. Otherwise traverse existing structural units in canonical order.
3. Keep a table whole when it fits.
4. Split only an oversized table into the largest fitting contiguous groups of
   whole rows.
5. Repeat existing headings, table/grid headers and attached notes as
   alias-free context only.
6. Carry alias-free sheet/page breaks and empty containers into the next
   target-bearing unit instead of creating empty working requests.
7. Fail closed when one indivisible row/block plus required context cannot fit.

Terminal validation requires one document/version binding, consecutive chunk
ordinals, deterministic identities, exact target order, no missing or repeated
working aliases, and zero row overlap/gaps. Chunks are returned in memory and
are not an ArtifactStore domain.

No empty-cell aliases were removed. G3.2 currently assigns an addressable
target to every canonical cell; changing that rule would be a target-contract
redesign rather than structural chunking.
