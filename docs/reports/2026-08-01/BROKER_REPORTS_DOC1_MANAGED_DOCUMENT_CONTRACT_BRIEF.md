# Broker Reports DOC1 Managed Document Contract Brief

Status: `PASSED`

Date: 2026-08-01

DOC1 defines one universal inactive document artifact for PDF, HTML, CSV,
XLSX, XLS, and unknown sources. The document is an ordered `blocks[]` reading
stream supplemented by explicit relations, typed provenance, status-bearing
metadata, and a fail-closed quality/loss ledger.

Key decisions:

- unknown content remains an `UNKNOWN` block rather than being dropped;
- unknown or conflicting metadata is explicit and never guessed;
- `MODEL_PROPOSED` can never masquerade as `SOURCE_EXPLICIT`;
- the current `description + rows` table core is nested inside `TABLE` blocks;
- logical cell annotations distinguish `EMPTY` from `UNREADABLE`;
- physical table geometry is not canonical truth;
- canonical serialization is UTF-8 sorted JSON with SHA-256 integrity;
- `unaccounted_context_loss_total` must equal zero.

Coverage and proof:

```text
DOC0 facets = 53 total, 51 represented, 2 explicit unknown, 0 unaccounted
safe fixtures = 6 (PDF 3, HTML 1, CSV 1, XLSX 1)
exact merged-main suite = 2336 passed, 5 historical skips, 0 failed/errors
focused DOC1 = 30 passed
generated bundle diff = 0
provider calls = 0
live changes = 0
new skips = 0
```

Delivery:

- base: `7cbb62f39915fd1499aeb009aac6a41bab0accb0`;
- implementation: `c81d6d0d40e2f95e2eb9ca8020544744c9b717cf`;
- implementation PR: `#247`;
- implementation merge: `c4fa86d8229bc8afdd88bfd0371a96d260790942`;
- evidence merge: reported in the terminal response due to self-reference.

The fixtures are safe synthetic expressiveness evidence. They are not proof of
a real PDF normalizer; `REAL_CORPUS_GAP = TRUE`. DOC2, DOC3, DOC6, parser work,
LLM rendering, model qualification, and product activation remain not started.
