# Broker Reports PDF Structural Repair Consensus v2

Status: default-disabled, non-authoritative Gate 1 shadow. Production Gate 2 selection, hybrid authority and OpenWebUI core are unchanged.

## Outcome

This contract replaces the parser-seeded table-grid path for the new research slice. The parser no longer hands a ready row/column grid to the visual model.

The slice has four explicit domains:

| Domain | Owns | Must not own |
|---|---|---|
| Raw parser values | Exact PDF word atoms, immutable visible values, source refs, checksums, bboxes and source order | Rows, columns, headers or a preferred grid |
| Raw parser geometry | Vector-line and rectangle-edge observations in table-normalized coordinates | Values, candidate groups or table semantics |
| Visual topology | Crop plus anonymous atom ids/bboxes/order; proposed rows, columns, headers, spans and alternatives | Source values, parser grid, reference answers or authority |
| Deterministic assembly and consensus | Geometry calibration, span adjudication, atom placement, constraint evaluation, uniqueness and typed terminals | Value repair, score-based ranking, provider calls or reference scoring |

The existing v1 dual-oracle contract remains the baseline for typed terminals, continuation and generic solver constraints. This v2 contract defines the independent observation and deterministic assembly path that was missing in v1.

## Factory entrypoints

The research path is factory-routed:

- `PdfDualOracleContractFactory` builds and validates raw-word parser observations;
- `PdfParserGeometryFactory` observes raw vector/rectangle geometry;
- `PdfStructuralRowWindowFactory` plans value-free vertical atom windows and stitches attempt-local topology;
- `PdfVisualTopologyFactory` builds the anonymous model package and validates topology responses;
- `PdfTopologyAssemblyFactory` assembles topology and raw atoms into binding hypotheses;
- `PdfDualOracleConsensusFactory` performs final deterministic constraint evaluation;
- `PdfHybridMaterializationFactory` resolves accepted candidate ids back to exact source values.

Direct runtime construction is rejected. The Gate 1 Pipe and its closed-world bundle import this path behind a default-disabled valve. The result stays private/non-authoritative and does not change Gate 2 selection.

## Raw parser value contract

Schema: `broker_reports_pdf_parser_observation_v1`.

The eligible construction lineage is `raw_word_atoms`. Every candidate owns exact word atoms and records:

- candidate identity and exact visible value;
- source value, word, bbox and text-checksum refs;
- union bbox and reading order;
- duplicate-value ambiguity;
- candidate and envelope checksums.

Validation recomputes value, bbox, refs, order and accounting. A candidate cannot be invented, omitted, duplicated or silently reassigned.

Legacy compact-ledger groups remain supported only by the old replay path. They are not input to the v2 visual-topology route.

## Raw parser geometry contract

Schema: `broker_reports_pdf_parser_geometry_observation_v2`.

The geometry observer reads only table-local raw vector lines and rectangle bounds from the PDF projection. It is forbidden from reading:

- legacy cells or a ready grid;
- row/column counts;
- header depth;
- candidate values or reference answers.

Signals use table-normalized coordinates. Vector lines may certify boundaries and span separators. Rectangle edges are diagnostic only because fills and decorative rectangles are not reliable table separators.

The observation is canonically checksummed. Persisted v1 observations may cross the boundary only through `upgrade_v1_observation`, which verifies the sealed v1 checksum/configuration, changes identity fields to canonical v2 and proves that all semantic fields are unchanged. This is serialization canonicalization, not a new parser run.

## Anonymous visual-topology contract

The model receives exactly one bounded crop and anonymous atoms:

```text
atom_id + normalized bbox + source order
```

The model does not receive:

- visible values;
- candidate/source/word refs;
- parser rows, columns, cells or header depth;
- the legacy grid;
- the provisional human reference.

A private exactly-once map binds anonymous atom ids to raw parser candidate ids after the model response. JSON object insertion order is never authority: the explicit atom order and parser `candidate_order` are authoritative, while dictionaries are validated as exact key sets plus exact per-candidate content.

The topology response is closed-shape and package-bound. It can propose:

- row and column boundaries;
- header-row count;
- non-degenerate spans;
- header hierarchy;
- explicit alternatives, continuation need and uncertainty codes.

Rows mean physical bands separated by visible horizontal separators, not individual text baselines. One-cell spans are invalid model claims.

## Deterministic assembly

Assembly has no provider call and cannot mutate values.

### Boundary calibration

Visual boundaries are proposals. Parser vector geometry calibrates them only when the expected `N + 1` strong line clusters are present and each certified line has sufficient table coverage. A missing or extra strong boundary is a typed regional block.

Candidate placement uses bbox bands, not nearest-cell fallback. A bbox center on a boundary or a bbox crossing a certified separator blocks the affected hypothesis.

### Span adjudication

Every proposed span is checked against vector-line coverage at its internal separators:

- coverage at or above `0.80` means a real separator;
- coverage at or below `0.10` means a supported gap;
- intermediate coverage is ambiguous and produces a typed regional block.

A span that overreaches a certified separator is trimmed to the nearest certified gap. If that reduces it to one cell, it is dropped as a no-op. The adjustment journal records the operation and fixes `source_value_change_allowed=false`.

This rule repaired the grouped-header development case without consulting cell values or the reference. It is geometry policy, not an exception for one table.

An empty geometry-certified merged region is currently projected to explicit empty cells because the existing binding schema requires a non-empty span anchor. That projection is journaled and is a known contract limitation.

### Binding invariants

An assembled hypothesis must prove:

- complete rectangular rows and explicit empty cells;
- every atom bound exactly once;
- no unknown, missing or duplicated candidate id;
- stable source order;
- no value mutation;
- no nearest-cell fallback;
- package, crop, dictionary and raw-response checksum integrity.

Ambiguous geometry returns `regional_retry_required`; it is not guessed into an accepted grid.

## Final consensus

The existing bounded finite-domain solver remains the final auditor. It checks each assembled hypothesis against exact parser evidence and returns one terminal:

- `accepted_unique_consensus`;
- `ambiguous_multiple_consensus`;
- `parser_vlm_conflict`;
- `no_valid_consensus`;
- `human_review_required`;
- `unsupported`.

There is no numeric optimizer, majority vote, oracle preference or “best-looking” response. Acceptance requires one complete, unique, constraint-valid canonical grid and a passing repeatability record.

Before materialization, the solver revalidates the accepted witness and the private dictionary against parser evidence. Dictionary insertion order is not semantic; exact candidate key membership and the explicit parser order are checked separately.

## Replay and reference isolation

Sealed replay has three processes:

1. `prepare` reads the historical private/safe evidence, strictly parses provider JSON, verifies six attempt identities and writes a checksummed whitelist-only replay input without paths, scores, old terminals or reference material.
2. `solve` accepts only that replay input. It has no reference argument and performs no network/provider call. It writes an immutable terminal artifact.
3. `score` starts after the solver process exits. It re-reads and validates the terminal file, then opens the provisional reference and computes diagnostics only.

The terminal seal includes the replay-input SHA plus, for every table:

- consensus result checksum and SHA;
- parser and geometry observation SHAs;
- both assembly result SHAs;
- hypothesis-set and repeatability SHAs;
- accepted binding and materialization SHAs.

The scoring process re-reads the terminal file after scoring and rejects any byte or semantic change.

## Evidence proved on 2026-07-14

### Historical sealed replay

Six already-sealed visual provider responses were replayed without new provider calls. Assembly v4 produced one repeatable canonical grid per development table:

| Case | Grid | Terminal | Diagnostic exact cells |
|---|---:|---|---:|
| simple control | `10 x 3` | `accepted_unique_consensus` | `30/30` |
| grouped/merged header | `7 x 11` | `accepted_unique_consensus` | `77/77` |
| tax summary | `5 x 8` | `accepted_unique_consensus` | `40/40` |

The replay bound `178/178` candidates exactly once, matched `147/147` diagnostic cells, invented no values and repeated the same post-assembly checksum for all three tables. This remains post-hoc development evidence, not proof of generalization.

### Fresh holdout v1

The first certification-eligible public holdout executed all six planned provider generate calls for three targets. It terminated `FRESH_HOLDOUT_COMPLETED_WITH_TYPED_NONACCEPTANCE`:

- accepted unique consensus: `0/3`;
- `no_valid_consensus`: `3/3`;
- hidden retries and failovers: `0`;
- invented values: `0`.

Two responses violated the row-boundary contract; the third violated the unsupported-response contract. The prompt was then clarified to require boundary endpoints `0.0` and `1.0` and a non-empty uncertainty code for `unsupported`. The v1 terminal remains immutable and is not reinterpreted after that change.

### Development regression after the prompt amendment

The exposed `157`, `330` and `72` atom targets are non-certifying regression cases. Before windowing, the `157` and `72` atom targets reached deterministic assembly and blocked on parser/visual boundary-count conflict. The `330` atom target passed the local `1000` atom cap but actual provider `countTokens` exceeded `20,000`; generation remained zero. This proved that raising only the atom cap was insufficient.

## Bounded vertical atom windows

Tables are now routed before provider calls:

- `1..192` atoms: the original whole-table path, exactly two `countTokens` and two generate calls;
- `193..1000` atoms: deterministic full-width vertical atom windows, at most `192` owner atoms per window;
- more than `1000` atoms or no safe cut: typed block.

Window owner sets are disjoint and their ordered union must equal the full parser candidate order. A cut may not cross an atom bbox. The full-table package is a sealed assembly ledger with `provider_input_allowed=false`; only per-window packages are sent to the provider. Each window keeps the unchanged `48 KiB`, `18,000` static-token, `20,000` counted-token and `8,192` output-token guards.

For `W` windows, the runtime performs exactly `2W` `countTokens` calls and `2W` generate calls. It first stitches all windows from attempt 1, then all windows from attempt 2. Attempts cannot be mixed. Column disagreement, an unsupported shared cut, a span crossing the cut, incomplete ownership or excessive alternative combinations blocks the result. Existing global assembly, consensus and materialization run only after an attempt-local stitch succeeds.

## Wide tables and continuation

Local tests cover a `3 x 12` wide table with multiline content and exact atom ownership. This proves the bounded implementation path, not public-corpus generalization.

Continuation discovery is parser/geometry-only and currently accepts exactly two adjacent page fragments with a compatible column model. Each fragment must independently reach accepted unique consensus. The join:

- adds zero provider calls;
- preserves fragment row order and subtotals;
- forbids duplicate boundary rows unless the sealed repeated-header policy authorizes removal;
- offsets headers and spans deterministically;
- revalidates exact ownership, provenance and zero invention.

A failed fragment cannot be hidden by a successful first page. Three-page chains and ambiguous continuation candidates remain typed manual-review cases.

## Durable repeat history and user-visible failure context

Repeat history is append-only inside the exact parser/crop/model/runtime/window/solver scope. Event sequence is monotonic; `ever_conflicted=true` cannot be erased by later agreement; checksum or scope tampering blocks execution. The ledger remains non-authoritative production evidence.

Every processed file now receives one closed safe outcome with stage, reason, retryability, next action and a plain user message. The same safe structural outcome is included in the LLM passport package, so the model can explain what failed. Raw exceptions, provider payloads, paths and customer values stay in private diagnostics. A counted-token budget block records the safe observed token count and still performs zero generate calls.

## Final fresh and live evidence on 2026-07-14

The final certification-eligible `fresh_holdout_v4` used seven official public broker PDFs whose SHA-256 hashes were disjoint from every earlier development and holdout corpus. Parser-only pre-registration selected three Edward Jones table crops before any provider or reference access.

The sealed run completed the exact call schedule:

- `countTokens`: `6/6`;
- provider generate calls: `6/6`;
- hidden retries and failovers: `0`;
- invented values: `0`;
- accepted unique consensus: `0/3`.

Only after the terminal seal was written, all three crops were human-reviewed as supported tables. The independent scorer remained bound to the unchanged terminal and reported `0/3` available bindings and `0/3` exact topologies. This is a valid execution and safe-abstention result, but it is not an accuracy pass.

The final non-certifying development regression exercised `157`, `330` and `72` atom targets after windowing. It completed exactly `8/8` `countTokens` and `8/8` generate calls, including two stitched observations for the `330` atom target. All three still ended `no_valid_consensus`; no value was invented. During this run the terminal validator exposed and then received a tested fix for a legal attempt-2-only window stitch.

The live OpenWebUI canary passed with the repository Gate 1 bundle:

- two synthetic adjacent-page fragments each reached accepted unique consensus;
- the fragment path made exactly four `countTokens` and four generate calls in total;
- continuation discovery joined the fragments into `8 x 3` with zero new provider calls;
- exact candidate ownership and zero invention were revalidated;
- no Knowledge/RAG/vector rows changed;
- the synthetic upload was removed by id and alias;
- the structural shadow valves were restored exactly to disabled.

Repository/live SHA parity then passed for Gate 1, Gate 2 source-fact and Gate 2 domain bundles, together with all twelve managed prompts. Gate 2 selection remains unchanged: the domain live smoke recorded `candidate_binding_enabled=false` while accepting all nine synthetic domain packages.

## Current readiness boundary

The bounded implementation and live default-disabled shadow are complete. Production accuracy and production Gate 2 authority are not approved because the independent fresh holdout accepted `0/3` supported tables.

The remaining limitations are explicit:

- only two adjacent continuation fragments are supported;
- tables above `1000` atoms, unsafe vertical cuts and per-window provider-budget excesses block with typed outcomes;
- wide/multiline and continuation have synthetic/live proof, but not fresh public generalization proof;
- a completely empty merged region without a source anchor still requires explicit projection or review;
- the shadow remains default-disabled and non-authoritative.

Production Gate 2 selection must remain unchanged until a new source-frozen, previously unseen holdout proves the agreed accuracy bar without hidden retries, value invention or reference leakage.
