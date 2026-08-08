# G3.4C context and boundary examples

Status: `PRIVACY_SAFE_SUMMARY`

Date: 2026-08-07

Every request contained the same three model-visible parts in the same order:

1. the exact Managed Financial Label Dictionary v1 render;
2. the exact G3.4 instruction;
3. one structural chunk with its alias-free ancestor/table context and working
   target aliases.

Backend alias mappings, canonical identifiers and source evidence did not
become model-visible context. Each selected chunk injected the dictionary
exactly once.

For boundary review, a positive credited-interest case at the final row of one
large-CSV chunk and another at the first row of the following chunk both
received the expected label. A debit-interest row, an informational accrual
row and a return-of-capital row were correctly omitted. No reviewed example
required cross-chunk semantic merge.

The compact response used four known labels but returned four target aliases
with display brackets. The contract requires bare aliases, so code accepted
zero aliases and rejected the entire response. No brackets were stripped and
no second request was made.

Exact model inputs, raw outputs, validation records and restored annotations
remain in non-Git private evidence. This file intentionally contains no source
values, customer identifiers, document IDs, canonical IDs or raw provider
payloads.
