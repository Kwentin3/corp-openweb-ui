# Stage 2 Decisions

Architecture decisions for Stage 2 go here after research review.

Do not create ADRs to justify implementation already started. ADRs should be written before implementation when a domain crosses a boundary:

- native OpenWebUI configuration vs custom module;
- browser preprocessing vs server processing;
- native analytics vs gateway;
- OCR pilot vs production document pipeline;
- policy/audit/export vs custom chat retention/deletion patch.

Use [ADR_TEMPLATE.md](ADR_TEMPLATE.md).

Current proposed decision drafts:

- [ADR-0001 Data Policy by Provider Class](ADR-0001-data-policy-by-provider-class.md)
- [ADR-0002 Manager Visibility Policy](ADR-0002-manager-visibility-policy.md)
- [ADR-0003 Chat Deletion, Retention and Audit](ADR-0003-chat-deletion-retention-audit.md)

Planned next ADRs:

- ADR-0004 STT Proxy Boundary.
- ADR-0005 OCR / VL OCR Pilot Scope.
- ADR-0006 Provider Model Catalog.
- ADR-0007 Web-search Provider.
