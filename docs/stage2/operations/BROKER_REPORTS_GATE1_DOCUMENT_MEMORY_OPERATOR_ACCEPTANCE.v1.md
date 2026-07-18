# Broker Reports Gate 1 document-memory operator acceptance v1

Status: performed and passed for the actual approved pilot corpus on 2026-07-18

Reviewer role: `agent_operated_technical_reviewer`

Human customer acceptance: `not_performed`

## Accepted corpus

The operator review used the recovered, hash-reconciled private customer corpus
outside Git. The executed Gate 1 graph contained:

- 56 required top-level inputs;
- 24 bounded ZIP containers;
- 48 promoted PDF/XML members and 24 accounted P7S sidecars;
- 104 source records;
- 80 logical documents.

The full source corpus, extracted members, normalized values, local registry,
ArtifactStore and proof workspace stayed in the private local corpus root.
Nothing was uploaded to Knowledge/RAG/vector storage.

## Automated preconditions

| Check | Result |
| --- | --- |
| Authoritative source, private copy and safe registry hash reconciliation | passed, 63/63 |
| Required top-level pool | passed, 56 |
| Gate 1 package validation | passed |
| Terminal state for every source record | passed, 104/104 |
| Accounting and zero silent loss for accepted records | passed, 104/104 |
| ZIP safety/member accounting | passed, 24/24 containers and 72/72 members |
| Public DCP/document-memory boundary | passed |
| ArtifactStore unchanged by public boundary audit | passed |
| Knowledge/RAG/vector guard | passed |
| Repository tests | 903 passed, 5 dependency deprecation warnings |
| Stage Function/Prompt parity | passed, 3/3 Functions and 12/12 Prompts |
| Stage synthetic mixed-format execution | passed |

## Review contract

Every required source record received an automated per-document verdict. The
agent directly compared source containers with resolver-accessed normalized
private memory for:

1. SHA/size identity and material metadata;
2. beginning, middle and end ordering;
3. declared pages, tables, sections and archive members;
4. material table headers, row order, cells and source values;
5. PDF page/text/layout/visual provenance;
6. HTML DOM text/table order and embedded-media checksums;
7. XML ordered neutral-event coverage;
8. ZIP parent/member index, size, disposition and promoted lineage;
9. explicit restrictions for unresolved or non-canonical scopes;
10. absence of false `complete` states;
11. parser-independent sufficiency of accepted memory for Gate 2.

All 78 `review_required` documents were reviewed. The 26 `complete` records
received the same automated identity/accounting/source comparison; material
CSV and ZIP scope received direct structural checks. There were no `partial`,
`blocked`, `unsupported` or `unreadable` records in the required pool.

## Findings and repairs

The first actual run found nine honest `partial` records:

- PDF text/layout variants without an explicit accepted fallback;
- four HTML documents with embedded data images.

The implementation added bounded PDF visual memory and bounded HTML visual
media. A subsequent full reviewer caught one additional real defect: HTML
values were present, but outside text and tables were grouped rather than
preserving global DOM order. Production extraction was repaired to emit
ordered content blocks, a real-corpus four-document regression was added, and
the full proof was repeated.

The final run produced:

- 26 `complete`;
- 78 `review_required`;
- 0 other terminal states;
- 104/104 operator verdicts passed;
- 104/104 accounting and zero-silent-loss passed.

## Meaning of acceptance

This acceptance proves technical document memory, lineage, accounting,
resolver access and public handoff for the supported pilot profile. It does not
claim that every unresolved table is canonical, that duplicate source copies
have been canonically selected, that Gate 3 tax logic is complete, or that a
human customer approved financial interpretation.

Safe per-document evidence is stored in:
`docs/reports/2026-07-18/BROKER_REPORTS_GATE1_ACTUAL_CUSTOMER_CORPUS_ACCEPTANCE.v1.safe.json`.
