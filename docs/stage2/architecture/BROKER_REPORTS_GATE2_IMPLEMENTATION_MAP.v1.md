# Broker Reports Gate 2 Implementation Map v1

Status: `CURRENT`

Date: 2026-08-06

This map binds architecture to maintained code. Paths are relative to
`services/broker-reports-gate1-proof/` unless noted otherwise.

## Execution map

| Architecture entity | Authoritative implementation | Input | Output | Forbidden dependency |
| --- | --- | --- | --- | --- |
| authenticated source custody | `broker_reports_gate1.artifact_store.ArtifactStoreFactory` and `artifact_resolver.ArtifactResolver` | trusted `ArtifactAccessContext`, source ref | authorized source record/bytes | caller-supplied tenant authority, public payload paths |
| bounded Full Evidence extraction | `full_source.FullSourceArtifactFactory.create` | source bytes, detected format, budgets | private source payloads/units and coverage summary | public schema ownership, financial meaning, Knowledge/RAG |
| PDF Document AI boundary | `pdf_document_ai.PdfDocumentExtractor` selected by `PdfDocumentExtractorFactory.create` | custody-bound PDF bytes after preflight | typed `PDF_DOCUMENT_AI_NOT_CONFIGURED`, or a future qualified provider-neutral envelope | provider/model response knowledge, local extraction, fallback, caller injection |
| format routing | `canonical_artifact.CanonicalNormalizer.build` | Gate 1 document plus extracted units | one adapter call | downstream format branching |
| future PDF representation handoff | `FullSourceArtifactBuilder.build_document_extraction` | validated `PdfDocumentExtraction` | byte-exact generic text representation for existing downstream | Markdown semantic parsing, table reconstruction, second Canonical owner |
| HTML assembly | `CanonicalNormalizer._adapt_html` | visible canonical blocks | common document/section nodes | script/style/hidden content as visible truth |
| CSV assembly | `CanonicalNormalizer._adapt_csv` | parsed rows and dialect evidence | common dataset/table cells | inferred financial roles |
| XLSX assembly | `CanonicalNormalizer._adapt_xlsx` or `build_xlsx_streaming` -> `xlsx_streaming.XlsxStreamingCanonicalAdapter` | workbook source or bounded extracted sheets | common workbook/sheet/table nodes | workbook DOM, unbounded range expansion, formula/value conflation |
| public schema validation | `canonical_artifact.validate_canonical_artifact` | candidate or reconstructed artifact | validation result | best-effort repair or unknown-version fallback |
| completeness | `canonical_artifact.assess_canonical_completeness` | common logical artifact | counts-only pass/fail reasons | activation of non-empty zero-node artifacts |
| immutable publication | `canonical_store.CanonicalArtifactStoreFactory.create().put_candidate` | validated artifact and trusted context | immutable version/component graph | alternate store, mutable version overwrite |
| physical persistence | existing `artifact_store.ArtifactStore` canonical methods | version/component descriptors | SQLite metadata plus private payload records | business reads of SQLite or payload paths |
| activation/rollback | `ArtifactStore.activate_canonical_version` through `CanonicalReader.activate/rollback` | validated version and expected pointer | atomic CAS receipt | pointer movement before graph validation |
| public read | `canonical_store.CanonicalReaderFactory.create` | manifest ref or document ID plus trusted context | revalidated `CanonicalArtifactV1` | layout-specific consumer API, legacy fallback |
| neutral projection diagnostic | `canonical_consumer_migration.render_neutral_canonical_projection` | reader-returned artifact | non-persisted format-neutral text | private evidence, source resolver, providers, financial semantics |
| consumer compatibility | factories in `canonical_consumer_migration` | canonical reader envelope | versioned legacy-compatible response/status | direct storage reads or global cutover |
| Wave 2 diagnostic | `canonical_wave2_shadow.CanonicalWave2ShadowFactory` | active reader envelope | side-effect-free compatibility telemetry | product writes, provider calls, fallback, cutover |

## Public and private surfaces

The public logical surface is the schema plus `CanonicalReader`. Physical
layouts (`single_payload`, `chunked`, `xlsx_row_chunked_v1`) are private behind
the reader. Full Evidence remains private behind resolver/access checks. The
neutral renderer is diagnostic tooling; no product runtime imports it today.

## Runtime and deployment requirements

- run from the closed service package and pinned dependency set; generated
  OpenWebUI bundles must exactly match their maintained sources;
- store SQLite metadata and private payloads below the existing
  `openwebui_data:/app/backend/data` mount through `ArtifactStoreFactory`;
- obtain tenant/case identity only from trusted `ArtifactAccessContext`;
- keep global canonical product reads disabled until a separate cutover;
- freeze capacity/resource limits and prove restart plus isolated restore for
  the exact target before an authorized migration;
- never depend on workspace-only imports, developer paths, historical reports,
  private fixtures or one-shot proof scripts at runtime.

The package also contains legacy-named `gate2_*` financial-semantic modules and
historical PDF experiment modules. They are `LEGACY_PRODUCT_COMPATIBILITY` or
`RESEARCH_PROTOTYPE`, not the current canonical engine. DOC34 does not remove
legacy product behavior; the do-not-break guard prevents these modules from
becoming dependencies of the canonical authority.

## Do-not-break invariants and focused checks

| Invariant | Primary check |
| --- | --- |
| `ONE_PUBLIC_SCHEMA` | `test_broker_reports_doc34_repository_contract.py` plus `test_broker_reports_canonical_artifact_v1.py` |
| `ONE_PUBLIC_READER` | repository contract test plus `test_broker_reports_canonical_storage_lifecycle_v1.py` |
| `ALL_FORMATS_CONFORM` | `test_broker_reports_canonical_multiformat.py` |
| `DOWNSTREAM_FORMAT_OPACITY` | `test_broker_reports_canonical_machine_projection.py` |
| `EVIDENCE_BOUNDARY` / `LLM_PROJECTION_BOUNDARY` | repository contract and canonical pipeline tests |
| `COMPLETENESS_FAIL_CLOSED` / `PROVENANCE_RESOLVES` | canonical artifact and PDF round-trip tests |
| `IMMUTABLE_VERSIONING` / `ATOMIC_ACTIVATION` | canonical storage lifecycle tests |
| `DURABLE_ROUNDTRIP` | PDF round-trip and XLSX streaming tests |
| `NO_SILENT_FALLBACK` | canonical consumer compatibility/pipeline tests |
| cross-format table semantics | canonical multiformat and machine projection tests |

Any violation blocks merge. A historical receipt or generated bundle is not a
substitute for the terminal behavioral test.
