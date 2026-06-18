# Stage 2 Implementation Gates

## 1. Purpose

Implementation gates защищают проект от начала кодинга до того, как закрыты
policy, backend boundaries, runtime proof and customer test data.

Документ не запускает реализацию. Он фиксирует минимальные условия, после
которых можно переходить к implementation planning and slices.

## 2. Gates

### Gate 1. Data Policy approved

- ADR-0001 approved or accepted as interim policy.
- Provider data classes defined.
- Warnings for sensitive scenarios defined.

### Gate 2. STT Proxy Boundary approved

- ADR-0004 approved.
- Existing ffmpeg workflow contract inspected.
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

| Gate | Status | Owner | Blocking items | Related docs |
| ---- | ------ | ----- | -------------- | ------------ |
| Gate 1. Data Policy approved | proposed | Customer / security / engineering | Approval and examples | ADR-0001; Security blueprint |
| Gate 2. STT Proxy Boundary approved | blocked by ADR | Engineering | ADR-0004 and ffmpeg artifact | ADR-0004; STT blueprint |
| Gate 3. Provider Model Catalog approved | blocked by ADR | Engineering / admin | Exact model IDs and accounts | ADR-0006; Provider blueprint |
| Gate 4. Web-search Provider approved | blocked by ADR | Engineering / admin / customer | Provider and cost/privacy approval | ADR-0007; Web-search blueprint |
| Gate 5. Manager Visibility and Retention approved | blocked by customer input | Customer / admin / engineering | Matrix, retention, no-delete proof | ADR-0002; ADR-0003 |
| Gate 6. OCR / VL OCR pilot scope approved | blocked by customer input | Customer / engineering | Test documents and data approval | ADR-0005; VL OCR research |
| Gate 7. Runtime proof complete | blocked by runtime proof | Engineering / admin | Deployed/staging checks | Acceptance matrix; Backlog |
| Gate 8. Customer test data package received | blocked by customer input | Customer | Reports, media, OCR, XLSX, matrix | Test data requirements |
| Gate 9. Implementation slices approved | planned | Engineering / customer | Gates 1-8 and slice acceptance | Backlog; Roadmap |

No gate is marked completed without runtime/customer evidence.
