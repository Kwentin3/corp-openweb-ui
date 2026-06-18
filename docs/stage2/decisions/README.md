# Stage 2 Decisions

Architecture decisions for Stage 2 go here after research review.

Do not create ADRs to justify implementation already started. ADRs should be written before
implementation when a domain crosses a boundary:

- native OpenWebUI configuration vs custom module;
- browser preprocessing vs server processing;
- native analytics vs gateway;
- OCR pilot vs production document pipeline;
- policy/audit/export vs custom chat retention/deletion patch.

Use [ADR_TEMPLATE.md](ADR_TEMPLATE.md).

ADR registry order:

- [ADR-0001 Data Policy by Provider Class](ADR-0001-data-policy-by-provider-class.md)
- [ADR-0002 Manager Visibility Policy](ADR-0002-manager-visibility-policy.md)
- [ADR-0003 Chat Deletion, Retention and Audit](ADR-0003-chat-deletion-retention-audit.md)
- [ADR-0004 STT Proxy Boundary](ADR-0004-stt-proxy-boundary.md)
- [ADR-0005 OCR / VL OCR Pilot Scope](ADR-0005-ocr-vl-ocr-pilot-scope.md)
- [ADR-0006 Provider Model Catalog](ADR-0006-provider-model-catalog.md)
- [ADR-0007 Web-search Provider](ADR-0007-web-search-provider.md)
- [ADR-0008 Native Analytics vs Hard Billing](ADR-0008-native-analytics-vs-hard-billing.md)

Recommended execution / review order:

1. Data Policy by Provider Class.
2. STT Proxy Boundary.
3. Provider Model Catalog.
4. Web-search Provider.
5. Manager Visibility Policy.
6. Chat Deletion / Retention / Audit.
7. OCR / VL OCR Pilot Scope.
8. Native Analytics vs Hard Billing.

Numbers are the ADR registry order. Execution order reflects implementation
dependencies.

Implementation gates:

- [Stage 2 Implementation Gates](../IMPLEMENTATION_GATES.md)
