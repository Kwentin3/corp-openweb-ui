# Broker Reports DOC4 Semantic Comparison v1

Status: `CONTRACTED_INACTIVE_EXPERIMENT_ONLY`

Schema: `broker_reports_doc4_semantic_comparison_v1`

Owner: `PdfViewSemanticComparator.compare`.

RUN C receives only the two schema-valid sealed responses. It never reads PDF, Managed Document, LLM View, gold evidence, provider credentials, or model output beyond those responses and never invokes a model.

The comparator joins stable semantic keys and emits MATCH_EXACT, MATCH_NORMALIZED, PDF_ONLY_FACT, VIEW_ONLY_FACT, VALUE_CONFLICT, STATUS_CONFLICT, ORDER_CONFLICT, MISSING_POINTER, INVALID_POINTER, UNSUPPORTED_FACT, or UNCOMPARABLE. Values are represented in the comparison by hashes; private literals remain in the sealed arm outputs. Exact six-decimal critical and noncritical match rates are derived from integer counts. Both-wrong is never established or counted as a match by RUN C; source adjudication alone decides it.

The normative machine authority is [BROKER_REPORTS_DOC4_SEMANTIC_COMPARISON.v1.schema.json](./BROKER_REPORTS_DOC4_SEMANTIC_COMPARISON.v1.schema.json).
