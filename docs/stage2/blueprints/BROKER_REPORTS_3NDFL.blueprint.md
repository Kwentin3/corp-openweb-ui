# Broker Reports 3NDFL Blueprint

## 1. Purpose

Спланировать рабочий сценарий анализа брокерских отчетов и подготовки черновых материалов для 3-НДФЛ.

## 2. PRD-1 requirements covered

- Приоритетный сценарий заказчика.
- Есть текущая рабочая схема в Claude по брокерским счетам.
- Использовать Claude API / Claude models, not Claude Code.
- Результат ИИ - черновик and analytical help.
- Не налоговая консультация and not automatic filing.

## 3. Current known context

PRD-1 требует test documents and example of good result. Broker scenario depends on documents/OCR, providers, prompts, data policy.

## 4. Target user workflow

Пользователь выбирает workspace "Брокерские отчеты / 3-НДФЛ", загружает report, применяет approved prompt/template, получает structured draft, видит warnings and uncertain places, передает результат человеку на проверку.

## 5. Native OpenWebUI first path

- Workspace Model.
- Shared prompts/templates.
- Knowledge with approved methodology.
- File upload for basic docs.
- Group-based access.

## 6. Integration / custom implementation path

- Parser/tool path for precise XLSX/PDF table extraction.
- OCR pilot for scanned/complex PDFs.
- Structured intermediate JSON/CSV if needed.
- Export/template generation only after separate decision.

## 7. Data and security notes

Broker reports can contain personal, tax and financial data. Foreign provider use requires strict policy. Manual anonymization may be required until future masking subsystem exists.

## 8. Dependencies

- [DOCUMENTS_OCR_EXCEL](DOCUMENTS_OCR_EXCEL.blueprint.md)
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

Blocked by customer test documents and good-result examples.
