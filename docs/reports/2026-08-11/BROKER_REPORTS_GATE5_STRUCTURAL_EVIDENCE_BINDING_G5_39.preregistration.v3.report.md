# G5.39 Structural Evidence Binding Tournament — preregistration v3

Status: `FROZEN_BEFORE_V3_COMPARATIVE_INFERENCE`
Date: `2026-08-11`

This document restarts the tournament after the pre-H2 completeness audit. The earlier v2 source assignments were valid, but its experimental T-Bank and holdout projections contained adjudicated candidate rows rather than their complete structural spaces. H1/v2 SHA `99300b5d…` is invalidated and excluded from every comparison; no strategy had been selected.

## V3 frozen identities

- Corpus v3 safe manifest SHA-256: `dc9619eb446c01c82cbce538e01c70be7c170c25da95c4ef230efce217d61c2d`.
- Private complete-case oracle SHA-256: `d76ade254cfe2c323e0ab73daf0fcf83d598034022e096dba6c86173a65e6c85`.
- Common research baseline commit: `1fb05ed3e725ff27701d97b1136dcb7ca01aee7d`.
- Common research baseline tree: `8370cebde17bcf6f0c39ea10b2f03c2cf4512ae5`.
- Frozen config SHA-256: `78a838cc2164f449fe745b9fba74ac6ce051726c71de9691d8653e72df92c9f8`.
- G5.38C baseline receipt and implementation identities remain unchanged from preregistration v2.

The complete evidence spaces now contain:

| Sample | Tables | Rows | Cells | Full projection size |
|---|---:|---:|---:|---:|
| DEV T-Bank | 4 | 16 | 274 | 13,585 chars |
| HOLDOUT real | 12 | 212 | 1,927 | 525,510 chars |
| LARGE real | 65 page sections | 3,455 | 3,474 | 217,842 chars |
| Negative A/B | 2 | 4 | 18 | bounded |

No hypothesis receives an oracle-filtered document projection. H1 still receives exactly its anchor row by definition; H2 must reject a full space that exceeds budget; H3 derives its neighborhood from the full space; H4 starts from a compact map of the full space.

## Unchanged frozen rules

The H1–H4 definitions, model `gpt-5.4-mini-2026-03-17`, temperature `0`, JSON mode, total per-case budgets (`16,000` input chars, `1,800` output tokens, H4 at most `10,000` retrieved chars), retry/repair/best-of-N/merge prohibitions, hard invariants, metrics, lexicographic evaluation, winner rule and downstream freeze are exactly those in `BROKER_REPORTS_GATE5_STRUCTURAL_EVIDENCE_BINDING_G5_39.preregistration.report.md`.

The provider transport profile now includes the literal JSON-mode instruction required by the configured gateway. Two v2 HTTP `400` responses occurred before model inference and are transport diagnostics only; they are not semantic attempts and will not recur in v3.

Every V3 hypothesis branch starts directly from commit `1fb05ed3e725ff27701d97b1136dcb7ca01aee7d`. Any further completeness defect requires v4 and another full restart.
