# Broker Reports 3NDFL Blueprint

Date: 2026-07-11

Status: bounded technical contour implemented and deployed with repo/live
parity; PDF Table Intake Gate 1 is implemented with region-only VLM detection
and deterministic `8 %` page-relative crop padding, with formal closure pending
its dated stage operator proof; the full customer pilot remains a separate gate.

## 1. Purpose

Спланировать рабочий сценарий анализа брокерских отчетов и подготовки черновых материалов для
3-НДФЛ.

## 2. PRD-1 requirements covered

- Приоритетный сценарий заказчика.
- Текущая рабочая схема в Claude по брокерским счетам остаётся примером
  пользовательского процесса, а не обязательной runtime-привязкой.
- Выбирать только разрешённый профиль модели через общий provider factory;
  Claude API / Claude models and Claude Code are different products.
- Результат ИИ - черновик and analytical help.
- Не налоговая консультация and not automatic filing.

## 3. Current known context

PRD-1 требует methodology, representative test documents and example of good
result для полного клиентского пилота. Bounded synthetic/local proof не требует
customer documents. Broker scenario depends on supported document
normalization, approved strict-output provider profile, managed Prompts and data
policy. OCR is a separate path for scanned/image-only input, not the default PDF
path.

## 4. Target user workflow

Пользователь выбирает workspace "Брокерские отчеты / 3-НДФЛ", загружает report, применяет approved
prompt/template, получает structured draft, видит warnings and uncertain places, передает результат
человеку на проверку.

## 5. Native OpenWebUI first path

- Workspace Model.
- Shared prompts/templates.
- Knowledge with approved methodology only, not raw broker reports.
- File upload for basic docs.
- Group-based access.

## 6. Integration / custom implementation path

- Supported PDF Table Intake Gate 1 through the native OpenWebUI Function:
  page rasterization, configured VLM region detection, strict validation and
  deterministic private PNG candidates. See the
  [versioned contract](../contracts/BROKER_REPORTS_PDF_TABLE_INTAKE_GATE1.v1.md).
- Deterministic normalized-table projection for supported native tables and
  mechanically accepted PDF text-layer candidates.
- Bounded candidate/value relations, narrow domain binding and strict
  validator-controlled acceptance.
- Shared provider factory with approved/probe-required/unsupported capability
  states and no automatic failover.
- Separate OCR pilot for scanned/image-only PDFs.
- Private structured intermediate artifacts with original row/cell value refs.
- Export/template generation only after separate decision.

## 7. Data and security notes

Broker reports can contain personal, tax and financial data. Foreign provider use requires strict
policy. Manual anonymization may be required until future masking subsystem exists.

## 8. Dependencies

- [PDF Table Intake Gate 1](../contracts/BROKER_REPORTS_PDF_TABLE_INTAKE_GATE1.v1.md)
- [DOCUMENTS_OCR_EXCEL](DOCUMENTS_OCR_EXCEL.blueprint.md)
- [Gate 2 source-fact extraction](BROKER_REPORTS_GATE2_SOURCE_FACT_EXTRACTION.blueprint.md)
- [Normalized table projection](../contracts/BROKER_REPORTS_NORMALIZED_TABLE_PROJECTION.v0.md)
- [Candidate-binding output](../contracts/BROKER_REPORTS_GATE2_CANDIDATE_BINDING_OUTPUT.v0.md)
- [PROVIDERS_MODEL_CATALOG](PROVIDERS_MODEL_CATALOG.blueprint.md)
- [SECURITY_DATA_POLICY](SECURITY_DATA_POLICY.blueprint.md)
- Customer test reports.

## 9. Risks and constraints

- False tax advice.
- Missing data in scanned PDFs.
- Excel formula/table extraction errors.
- Overpromising automation.

## 10. Open questions

- What current Claude workflow is considered good?
- Which report formats are common?
- What fields must be extracted?
- Which providers are allowed for these data?

## 11. Research links

- [DOCUMENTS_OCR_EXCEL_RESEARCH](../research/DOCUMENTS_OCR_EXCEL_RESEARCH.md)
- [PROVIDERS_YANDEX_GIGACHAT_DEEPSEEK_CLAUDE_RESEARCH](../research/PROVIDERS_YANDEX_GIGACHAT_DEEPSEEK_CLAUDE_RESEARCH.md)
- [DATA_MASKING_FUTURE_RESEARCH](../research/DATA_MASKING_FUTURE_RESEARCH.md)

## 12. Acceptance signals

- Test report produces structured draft.
- Output clearly says manual review required.
- System highlights uncertain places/questions.
- No automatic 3-НДФЛ filing is implied.

## 13. Implementation readiness

The bounded normalization, candidate-binding, strict-validation and provider
factory contour is implemented and locally verified. The current bundle passed
bounded synthetic semantic acceptance for `gpt-5.6-sol` and
`models/gemini-3.5-flash`. Deployment/Prompt parity, zero storage deltas and
cleanup are proven. The current native/PDF customer rerun was not performed
because the controlled case had no active source records or DCP.

Customer test documents, methodology, expected output and approved data policy
still gate broad customer-pilot acceptance. They do not retroactively block the
already completed synthetic/local technical work.
