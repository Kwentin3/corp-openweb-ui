# Broker Reports Goal 2 - Server-Authoritative Private Intake

Status: `COMPLETED`

Evidence date: `2026-07-21`

Repository: `Kwentin3/corp-openweb-ui`

Delivery PR: `#3`

Branch: `codex/broker-reports-private-intake-v1`

Runtime image source revision: `8e6a71f13cf4f9cec0e5be191fac924548050e48`

Terminal delivery-tooling revision before this receipt:
`e6255bffb20fe2e8b25295e327d0d636cc17c608`

## Terminal outcome

Broker Reports now owns a separate authenticated source-intake route. Eligible
sources are persisted with a server-owned receipt and cannot enter native
OpenWebUI document processing, Knowledge, RAG, embeddings or vector storage.
The protected Action accepts only a short-lived server-signed attestation
derived from authenticated-user-owned persisted receipts.

The runtime image is intentionally labelled with `8e6a71f`. The later
`e6255bf` commit changes only external delivery/proof readiness handling and is
not copied into the image. The Action source itself is unchanged across those
commits and has exact repository/live parity at the terminal repository head.

Goal 3 was not started as part of this branch.

## Contract review and recovery disposition

The recovery implementation at `0f9c950` was reviewed before selective reuse.
Its useful boundaries were retained:

- a dedicated `/api/v1/broker-reports/intake` route;
- deterministic owner-and-idempotency-key source identity;
- receipt persistence on the OpenWebUI file row;
- byte-integrity verification and compensating storage deletion;
- single and batch retrieval guards;
- Action receipt resolution through the authenticated request transaction.

The recovery Action contract was not accepted unchanged. Its shape-only
attestation was client-forgeable. The production contract is v2 and adds:

- an HMAC key derived from the authenticated OpenWebUI server secret;
- exact action-id and authenticated-user binding;
- a 60-second lifetime and unique nonce;
- exact source, receipt and schema identities;
- canonical serialization and constant-time signature comparison;
- fail-closed handling for missing, expired, cross-user, altered or
  shape-compatible forged attestations.

No browser `process` flag, body field, file metadata claim or Action payload is
accepted as authority.

## Prevention boundaries

The image patcher is signature-based and pinned to OpenWebUI v0.9.6. It fails
the image build if a required upstream signature is missing, duplicated or
partially patched. The deployed image contains these explicit choke points:

| Boundary | Server behavior for an eligible source |
| --- | --- |
| private intake query override | rejects `process`, `process_in_background`, `knowledge_id` and `collection_name` |
| retrieval single-file processing | rejects before the upstream processing `try` block |
| retrieval batch processing | validates the database row, not the client `FileModel` |
| file content update/reprocess | rejects before the broad upstream exception handler |
| Knowledge single add | rejects before native-data and vector processing |
| Knowledge single update | rejects before vector deletion or reprocessing |
| Knowledge batch add | rejects the whole batch before association or processing |
| protected Action dispatch | replaces client claims with a signed database-backed attestation |
| protected Action runtime | verifies signature, user, action, lifetime and exact receipts |

An eligible row has a reserved server-generated id, empty native `data`, an
authenticated owner and a receipt whose hash, size, storage path, creation
time and prohibition flags agree with the persisted row. Receipt validation
also rejects native data/meta keys. Cleanup remains compensating defence in
depth; the primary guarantee is rejection before native mutation.

The repository and storage adapters are created only through the maintained
feature factory and receive the request-scoped `AsyncSession`. No client
tenant identity or workspace-only runtime import was introduced.

## Idempotency and alternative-client behavior

The source id is a deterministic UUID scoped by schema version,
authenticated owner and validated `Idempotency-Key`. A retry with identical
bytes returns the same source and receipt with `replayed=true`. The same key
with different bytes returns conflict. Receipt reload uses the authenticated
owner predicate. Direct API clients and alternative browser flows hit the
same server boundary and cannot opt into processing through query parameters.

Generic, missing, cross-owner and ordinarily uploaded file references cannot
be resolved as Broker Reports receipts. A client-supplied signed-attestation
field is removed and replaced only after database verification.

## Test receipt

Final focused verification covered the private-intake service, signed Action,
upstream patch atomicity/idempotency, delivery assets, architecture and
repository privacy:

`30 passed, 0 skipped, 0 failed`.

The complete qualified Broker Reports suite was run from the service root:

- `947 passed`;
- `20 skipped`;
- `0 failed`;
- `5` known PyMuPDF/SWIG deprecation warnings.

All 20 skips retain the documented reason that the offline private benchmark
reference is required and deliberately absent from Git. The first root-level
pytest command was not a product test result: collection stopped because the
service package was outside root `sys.path`. The qualified service-root
command then collected and executed the complete suite. No expectation,
timeout or validator was weakened.

The built image also passed:

- patcher second-run result `already_patched`;
- `py_compile` for the intake contract, intake router, `main.py`, retrieval,
  files, Knowledge and Action utility modules;
- exact OCI revision and private-intake contract label readback.

## Deterministic bundle receipt

Goal 2 does not add private intake to Gate 1 or Gate 2 bundles. Two consecutive
maintained `--target all` generations produced identical bytes and no semantic
Git diff:

| Bundle | SHA-256 |
| --- | --- |
| Gate 1 | `de9709e78c7503f4a7277c5fad8285a79e3413b2005201a0d890f410c6b442ab` |
| Gate 2 source | `ffeff3c84d3c2a23ad3d6cfcb084d2072f752a5edce5551ffeb407a4efba4488` |
| Gate 2 domain | `9dc6ce4dc22ca0c810b36b1c77761f45b24e7cda7cd6a072738374ade0ec80ca` |

## Stage delivery receipt

The final stage container is running with restart count zero:

| Item | Identity |
| --- | --- |
| configured image | `corp-openwebui/openwebui:v0.9.6-native-web-stt-broker-intake-v2-8e6a71f` |
| running image id | `sha256:c862956b5a88f490de3a13829cb4176ce9a2e3fb3621ebf0198b059be65f8e83` |
| pinned base digest | `sha256:90eae5b419e40b4c3dd684582b2c83440b36f9ae2f6532c09639b2ba4ee65158` |
| OCI revision | `8e6a71f13cf4f9cec0e5be191fac924548050e48` |
| intake contract label | `server-authoritative-v2` |
| protected Action SHA-256 | `874a07129aa626e61807095b19e531972395934ce1a9aad72d378a3104530ae4` |

The Action is type `action`, active, not global, manifest version `2.0.0`, and
its repository/live hashes are identical. Final Action readback was performed
from repository revision `e6255bf`.

The maintained image switch validates labels and image identity, changes only
the `openwebui` compose service, waits for internal health, application auth
route and external ingress readiness, then atomically persists the selected
image. On failure it recreates the previous image and waits for the same
readiness envelope.

Rollback identities remain available:

- pre-Goal-2 image
  `corp-openwebui/openwebui:v0.9.6-native-web-stt-v1`,
  id `sha256:8dbfafc61b79cfdf6bbe7c08da6b65ad6d91ca249c801175f77092ccf0210175`;
- immediate proven predecessor
  `corp-openwebui/openwebui:v0.9.6-native-web-stt-broker-intake-v2-5c52b18`,
  id `sha256:e382d49ed3d074e79e40afa04cb4d9f9b554a31d48aca5e3a7734586e2d04d21`.

Existing Broker Reports Functions were not changed by Goal 2 delivery:

| Live Function | SHA-256 | State |
| --- | --- | --- |
| Gate 1 | `9b3895b521d8ec82b486edfba7a3b29cbeb913217fa73aff18783915126bb1df` | active, not global |
| Gate 2 source | `168a3095ca488f13736ea4655c54df5ec136ebf196c6ab7fa4e1e98f121a3f96` | active, not global |
| Gate 2 domain | `eb1a98515743e8adda5fa57dfbe5c2f7a57753966fd1b0902f35300ab903a54e` | active, not global |

## Live invariant proof

The final synthetic-only smoke used no customer document. It proved:

- initial intake eligible with all five native sink flags false;
- same-key same-byte retry and receipt reload return the same identities;
- same-key different-byte replay returns `409`;
- client `process=true` override returns `400`;
- generic file Action use returns `400`;
- native single processing returns `409`;
- content update/reprocess returns `409`;
- native batch returns an explicit terminal per-file rejection and no success;
- Knowledge single add, update and batch add each return `409`;
- protected private Action returns `200` and `receipt_verified` without
  disclosing the source id;
- the persisted source has empty native data, a valid receipt and zero
  forbidden native keys;
- source-specific Knowledge links, RAG documents, vector metadata and
  embedding queue references remain zero.

During the protected attempts, deltas were exactly zero for Knowledge rows,
RAG document rows, vector collections, vector directories, vector files and
vector bytes. After cleanup, all initial counters were restored exactly:

| Counter | Before | After cleanup |
| --- | ---: | ---: |
| OpenWebUI file rows | 261 | 261 |
| document rows | 0 | 0 |
| Knowledge rows | 0 | 0 |
| vector collections | 146 | 146 |
| vector directories | 146 | 146 |
| vector files | 595 | 595 |
| vector bytes | 309808908 | 309808908 |

Terminal readback found zero synthetic file rows, zero synthetic Knowledge
rows, zero private Knowledge links, zero storage objects and zero
source-specific vector or queue references.

## Failed-attempt attribution

No failed attempt is counted as acceptance evidence:

- the local Windows Docker 19.03 client stalled before producing an image;
  the exact build was moved to the stage Docker 29.5 host;
- one remote build used an incorrect base-image override and failed at GHCR
  metadata authorization before project steps;
- the first correct remote build failed closed because an upstream Knowledge
  comment anchor occurred twice; the selector was narrowed to the exact update
  sequence and the next image build passed;
- the first post-restart Action call saw an ingress `404` while OpenWebUI was
  still completing startup dependencies; readiness was extended through the
  real auth route and external ingress;
- the first live smoke's temporary Knowledge cleanup used the broad upstream
  DELETE route, which scanned 153 model records and exceeded the client
  timeout. The DELETE eventually completed. The two remaining synthetic files
  were then deleted explicitly, and readback proved zero rows, storage objects,
  Knowledge links and vector refs. The maintained proof now uses one exact
  authenticated-owner fixture row and independent cleanup operations. Two
  subsequent complete smokes passed, including the final image.

## Privacy and cleanup

Repository privacy guards passed in the focused and full suites. Only fixed
synthetic bytes and aggregate counters were used in live proof. No customer
document, customer value, raw provider response, credential, receipt id,
source id, storage path or private evidence path is committed in this report.

All four isolated remote build-context directories were removed. The
intermediate validation-only image was removed; the current and two explicit
rollback images remain. The canonical repository tree is clean before this
documentation-only receipt.

## Acceptance

`BROKER_REPORTS_PRIVATE_INTAKE: SERVER_AUTHORITATIVE`

`NATIVE_PROCESSING_FOR_ELIGIBLE_SOURCE: PROVEN_IMPOSSIBLE`

`KNOWLEDGE_DELTA: ZERO`

`RAG_DELTA: ZERO`

`VECTOR_AND_EMBEDDING_DELTA: ZERO`

`CLIENT_OVERRIDE: DENIED`

`GENERIC_NATIVE_FILE_REF: REJECTED_OR_INELIGIBLE`

`RETRY_AND_RELOAD: IDEMPOTENT_AND_SAFE`

`PRIVATE_INTAKE_STAGE_DELIVERY: PROVEN`

`GOAL_2_PRIVATE_INTAKE: COMPLETED`

Goals 3-6 are not claimed by this receipt. Sber customer acceptance remains an
external, default-off release gate.
