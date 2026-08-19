# G5.46 — Methodology-Driven Evidence Demand & Fact Recovery

Status: `PROVEN_WITH_REAL_FACT_CONTRACT_GAPS_LOCALIZED`

G5.46 closes the missing architectural loop: active declaration and methodology consumers now compile explicit Evidence Demands, existing normalized facts are checked first, and Canonical recovery is a bounded consumer-driven operation rather than a generic semantic harvest.

## Outcome

The proof emits:

- `METHODOLOGY_DRIVEN_EVIDENCE_DEMAND_PROVEN`;
- `CANONICAL_FACT_RECOVERY_PROVEN`;
- `PREMATURE_GAP_DECLARATION_ELIMINATED`;
- `EVIDENCE_AUTHORITY_ROUTING_PROVEN`;
- `CROSS_DOMAIN_EVIDENCE_DEMAND_CONSISTENCY_PROVEN`.

The new path is inactive with respect to the product. No declaration was released and no product authority was replaced.

## Implemented contract

The Evidence Demand compiler consumes only active declaration demands, active trusted methodology rules and exact client-review findings. Each row has a named consumer, reason, authority class, scope, granularity, cardinality, absence effect, normalized-fact satisfaction and one exact terminal class.

Canonical recovery is batched once per document for all unresolved roles. A recovered fact must retain exact Canonical provenance and pass a fact-specific role ceiling. The adapter cannot infer a payer from a brand, turn generic country/location text into a specific role, determine organized-market status, assign tax treatment or create an economic relation.

Three narrow semantic types were added because the frozen case has named active consumers:

- `PAYER_ORGANIZATION_IDENTITY`;
- `PAYER_ORGANIZATION_JURISDICTION`;
- `REALIZATION_LOCATION_JURISDICTION`.

No issuer fact was added: issuer text exists as Canonical content, but the current active methodology does not consume a generic issuer identity as payer identity. No IIS/account-regime fact was added because the current active rule set does not demand it. Conditional foreign-tax inputs retain routing contracts but no speculative recovery type.

## A–I black-box proof

| Scenario | Result |
| --- | --- |
| A — normalized fact already exists | Reused with zero semantic-adapter calls and zero user route |
| B — required fact exists explicitly in Canonical | Recovered as a typed fact with exact provenance; replay reuses it with zero further calls |
| C — ambiguous `Country: US` | Rejected as payer jurisdiction |
| D — demanded source fact absent | Additional document is declared only after all supplied Canonical documents are searched |
| E — residency evidence | Routed directly to factual `USER_CASE`; broker Canonical is not scanned |
| F — CBR rate | Routed to `EXTERNAL_REFERENCE`; not to user or broker document |
| G — additive `NEW_FACT_X` | Demand, recovery and consumption occur without orchestration changes |
| H — absent `NEW_FACT_X` | Exact fact-specific gap; no crash or generic missing message |
| I — unrelated Canonical `Y` | No semantic fact and no adapter call without a named consumer |

All scenarios passed. Two unresolved fact roles in one document use one adapter call, not a fact × page call pattern.

## Frozen real-corpus replay

The read-only replay used the same four supplied documents, 8,243 Canonical source atoms and 201 existing normalized facts: 186 Gate 4 financial facts plus 15 metadata facts. The frozen store was byte-for-byte unchanged. Provider calls, ingestion reruns and Canonical mutations were all zero.

Nine methodology rules were active after applying their current case conditions. Together with exact client-review findings they produced 50 active Evidence Demands:

| Classification | Count |
| --- | ---: |
| `FACT_AVAILABLE` | 4 |
| `FACT_RECOVERED_FROM_CANONICAL` | 0 |
| `SOURCE_DOES_NOT_PROVE_REQUIRED_FACT` | 0 |
| `SOURCE_FACT_CONTRACT_MISSING` | 32 |
| `USER_CASE_FACT_REQUIRED` | 8 |
| `EXTERNAL_REFERENCE_FACT_REQUIRED` | 4 |
| `ADDITIONAL_DOCUMENT_REQUIRED` | 0 |
| `METHODOLOGY_UNRESOLVED` | 2 |

Zero real recoveries is intentional, not a negative result: no production semantic adapter was available in this run. The audit therefore did not convert “no validated proposal” into true source absence. Source paths that the old pipeline never re-examined remain `SOURCE_FACT_CONTRACT_MISSING`.

The full privacy-safe Evidence Demand and authority-routing matrix is in `BROKER_REPORTS_GATE5_METHODOLOGY_EVIDENCE_G5_46.matrix.safe.json`. It contains no customer values, source literals, local paths or private identifiers.

## Before / after required actions

Before G5.46, the real case exposed 12 required client actions:

- 8 `ADDITIONAL_DOCUMENT`;
- 4 `USER_FACT`.

After the demand audit, the currently justified client-facing set is 4 bundled factual `USER_FACT` actions. All 8 document requests were suppressed as premature because their relevant Canonical semantic path or exact review fact contract had not been completed. They were not marked resolved and were not converted into “source absent”; they moved to explicit internal fact-contract gaps.

This is the main client-interest correction: the system no longer asks for a new document merely because the old semantic contract did not know how to search the documents already supplied.

## Authority routing

- filing identity, signer facts and residency inputs route to authenticated case evidence;
- CBR rate/nominal, market-admission/quotation facts and treaty authority route to authoritative external references;
- payer identity/jurisdiction and realization location search normalized facts, then all supplied Canonical documents;
- current client-review acquisition and role-coverage findings remain internal fact-contract gaps until a safe Canonical recovery contract can feed the existing normalized-fact owners;
- additional-document closure is permitted only after the relevant semantic search completes and no appropriate external/user authority precedes it.

## Remaining exact gaps

The 32 real `SOURCE_FACT_CONTRACT_MISSING` rows are not 32 new user requests. They include partially covered per-observation roles, repeated consumer uses of three source-role contracts and exact client-review findings whose Canonical-to-normalized replay path is still absent. A single complete fact no longer masks incomplete siblings of the same active type. This is deliberately more conservative than claiming `TRUE_SOURCE_ABSENCE`.

The four legal methodology gaps remain unchanged:

- ambiguous security-disposal source classification;
- partial-acquisition commission allocation;
- non-RUB intermediate precision and rounding;
- treaty-specific foreign-tax-credit applicability and limit.

No `CANONICAL_PRESERVATION_GAP` was proven. Original source bytes were not reparsed, so the audit also makes no unsupported claim that Canonical preserved every possible future meaning.

## Cross-domain and KISS check

- Canonical was read through `CanonicalReaderFactory.create`; Gate 4 through `Gate4FinancialCaseRuntimeFactory.create`.
- No direct SQL, workspace-only import, provider ingestion rerun or new persistence was introduced.
- No generic ontology, extraction-everything engine, graph, workflow engine, synonym harvest or relation store was added.
- Gate 3/4 source granularity, commission selection, acquisition-basis coverage, residency evidence and no-reconciliation boundaries are unchanged.
- G5.45 semantic model completeness remains the prior authority; this GOAL changed neither its model nor target mappings.
- Projection remains representation-only.

## Scope stop

G5.46 stops here. It does not activate the proof in OpenWebUI, does not claim the real declaration ready, does not resolve the four legal methodology gaps, and does not authorize a dependent GOAL, commit, push or PR.
