Make one bounded Gate 2 Financial Domain matching decision.

Apply only the managed Financial Domain Skill
`broker-reports-financial-domain-matching` version `1.0.0`. Load the complete
Financial Semantic Pack only through the managed
`broker_reports_financial_semantic_pack.load_financial_semantic_pack` Tool and
require Pack semantic version `1.0.0` with integrity SHA-256
`ab0b5aaaa4cd8133ab26d7dce8e501770c2d14f2c1bd2205cbad3fa2c6e0e7f8`.

Use the whole bounded source context below. The bounded input owns structural
eligibility and allowed role/ref combinations. The Pack alone owns financial
meaning. Do not use general knowledge, RAG, Knowledge, embeddings, vector
search, Python predicates, regex, or the wording of this Prompt as another
financial semantic authority.

Return one strict
`broker_reports_gate2_financial_evidence_decision_v1` JSON object and nothing
else. Use exactly one of `typed_input`, `unclassified_financial_input`,
`no_financial_input`, or `unsupported`. Prefer
`unclassified_financial_input` whenever source-stated financial values are
ambiguous. Preserve exact source values and permitted refs. Never invent,
calculate, aggregate, transform, normalize, repair, or fill missing data.

{{financial_semantic_matching_input_json}}
