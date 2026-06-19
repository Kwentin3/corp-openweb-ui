# Stage 2 Implementation Gates

## 1. Purpose

Implementation gates защищают проект от начала кодинга до того, как закрыты
policy, backend boundaries, runtime proof and customer test data.

Документ не запускает реализацию. Он фиксирует минимальные условия, после
которых можно переходить к implementation planning and slices.

Related boundary map: [CONTRACT_BOUNDARIES.md](CONTRACT_BOUNDARIES.md).

Stage 2 custom capabilities must be isolated behind explicit backend contracts.
OpenWebUI remains the upstream product shell; frontend must not own security,
provider keys, data policy, retention, manager visibility or usage accounting.

## 2. Gates

### Gate 1. Data Policy approved

- ADR-0001 approved or accepted as interim policy.
- Provider data classes defined.
- Warnings for sensitive scenarios defined.

### Gate 2. STT Proxy Boundary approved

- ADR-0004 approved.
- Existing browser ffmpeg workflow contract inspected.
- Operator manual proof captured as manual evidence for mobile/large-file
  scenarios.
- Lightweight proof matrix captured before implementation acceptance.
- Opus default candidate compatibility with Lemonfox accepted, revised or
  explicitly deferred.
- MP3 compatibility fallback accepted.
- `LemonfoxSttAdapter` first-adapter config accepted.
- STT env/config contract reviewed.
- Self-hosted ffmpeg production asset path accepted.
- S3/object storage and prepared-audio retention accepted.
- Prepared audio >100 MB behavior accepted.
- Cancel UX expectations accepted, revised or explicitly deferred.
- STT proxy input/output agreed.
- No API keys in browser.

### Gate 3. Provider Model Catalog approved

- ADR-0006 approved.
- Exact model IDs selected.
- Production/pilot/research providers marked.

### Gate 4. Web-search Provider approved

- ADR-0007 approved.
- Provider selected.
- Result count/concurrency/cost policy defined.

### Gate 5. Manager Visibility and Retention policy approved

- ADR-0002 and ADR-0003 approved.
- Manager visibility matrix defined.
- No-delete vs retention/audit clarified.

### Gate 6. OCR / VL OCR pilot scope approved

- ADR-0005 approved.
- Test data selected.
- Acceptance per document class defined.

### Gate 7. Runtime proof complete

- OpenWebUI deployed/staging capabilities checked.
- RBAC/groups checked.
- no-delete UI/API checked.
- analytics checked.
- web-search smoke checked.
- STT proxy smoke plan ready.

### Gate 8. Customer test data package received

- broker reports;
- good Claude result;
- audio/video;
- scanned PDF;
- PDF with tables;
- XLSX;
- group/role matrix;
- provider/data policy examples.

### Gate 9. Implementation slices approved

- implementation backlog split by slices;
- each slice has acceptance;
- optional/future items not included silently.

## 3. Current status

### Gate 1. Data Policy approved

Status:

- proposed.

Owner:

- Customer / security / engineering.

Blocking items:

- approval and examples.

Related docs:

- ADR-0001;
- Security blueprint.

### Gate 2. STT Proxy Boundary approved

Status:

- reviewable; not completed until human ADR review, lightweight proof matrix,
  Opus/Lemonfox compatibility proof, Lemonfox adapter config, self-hosted asset
  path, S3/object storage config, prepared-audio retention and production
  dependency decisions are complete.

Owner:

- Engineering.

Blocking items:

- ADR-0004 human review;
- lightweight proof matrix with device/browser/file metadata and selected output
  profile;
- output profile decision: Opus candidate default pending Lemonfox proof, MP3
  compatibility fallback;
- Lemonfox adapter config decision;
- STT env/config contract review;
- self-hosted ffmpeg asset path decision;
- S3/object storage env decision;
- prepared audio retention decision;
- prepared audio >100 MB behavior;
- cancel lifecycle expectations for preprocessing, upload and STT job;
- licensing/ops review for MP3 / `libmp3lame` and ffmpeg core assets;
- browser 1 GB input limit and Lemonfox 100 MB direct upload limit proof;
- production duration limits;
- [CONTRACT_BOUNDARIES.md](CONTRACT_BOUNDARIES.md).

Related docs:

- ADR-0004;
- STT env contract;
- FFMPEG workflow artifact inspection;
- STT blueprint.

### Gate 3. Provider Model Catalog approved

Status:

- blocked by ADR.

Owner:

- Engineering / admin.

Blocking items:

- exact model IDs and accounts.

Related docs:

- ADR-0006;
- Provider blueprint.

### Gate 4. Web-search Provider approved

Status:

- blocked by ADR.

Owner:

- Engineering / admin / customer.

Blocking items:

- provider and cost/privacy approval.

Related docs:

- ADR-0007;
- Web-search blueprint.

### Gate 5. Manager Visibility and Retention approved

Status:

- blocked by customer input.

Owner:

- Customer / admin / engineering.

Blocking items:

- matrix;
- retention;
- no-delete proof.

Related docs:

- ADR-0002;
- ADR-0003.

### Gate 6. OCR / VL OCR pilot scope approved

Status:

- blocked by customer input.

Owner:

- Customer / engineering.

Blocking items:

- test documents;
- data approval.

Related docs:

- ADR-0005;
- VL OCR research.

### Gate 7. Runtime proof complete

Status:

- blocked by runtime proof.

Owner:

- Engineering / admin.

Blocking items:

- deployed/staging checks.

Related docs:

- Acceptance matrix;
- Backlog.

### Gate 8. Customer test data package received

Status:

- blocked by customer input.

Owner:

- Customer.

Blocking items:

- reports;
- media;
- OCR;
- XLSX;
- matrix.

Related docs:

- Test data requirements.

### Gate 9. Implementation slices approved

Status:

- planned.

Owner:

- Engineering / customer.

Blocking items:

- Gates 1-8;
- slice acceptance.

Related docs:

- Backlog;
- Roadmap.

No gate is marked completed without runtime/customer evidence.
