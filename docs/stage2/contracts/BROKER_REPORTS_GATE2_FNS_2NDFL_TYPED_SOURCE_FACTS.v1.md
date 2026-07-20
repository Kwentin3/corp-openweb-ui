# Broker Reports Gate 2 FNS 2-NDFL typed source facts v1

Status: maintained contract. Adapter id: `broker_reports_fns_2ndfl_source_facts_v1`.

## Boundary

Gate 1 remains format-neutral. It owns ordered XML events, existing node/value refs, source identity, checksums and structural completeness. It does not assign financial meaning.

Gate 2 consumes only the persisted neutral-event source unit through `Gate2Fns2NdflAdapterFactory.create`. It selects a period-specific schema profile, maps source-local fields to typed facts and validates every fact against the existing Gate 1 refs. It does not parse XML bytes, mint source refs, calculate tax, reconcile documents, make entitlement decisions or assemble Gate 3/Gate 4 outputs.

Unknown roots, periods, attributes, elements and vendor extensions fail closed. No LLM or provider fallback exists.

## Official lineage and period policy

The policy is historical, not “latest schema wins”:

- report years 2016–2017: FNS order 30.10.2015 № ММВ-7-11/485@, Appendix 3, electronic format 5.04;
- report year 2018: FNS order 02.10.2018 № ММВ-7-11/566@, Appendix 3; the order applies from 2019 to tax period 2018 and supersedes the 2015 order;
- report years 2019–2025: the maintained signed-certificate document-fragment profile used by the FNS personal-account PDF/XML/P7S export. This profile name deliberately does not claim that a fragment is a complete tax-authority submission envelope.

Primary FNS sources:

- <https://www.nalog.gov.ru/html/sites/www.rn31.nalog.ru/pril_prkz/prik_30102015_485%40.pdf>
- <https://www.nalog.gov.ru/rn77/about_fts/docs/7942386/>
- <https://www.nalog.gov.ru/rn77/news/activities_fts/7028292/>
- <https://www.nalog.gov.ru/rn77/taxation/taxes/ndfl/form_ndfl/>

The source `ОтчетГод` selects the profile. Missing, malformed, pre-2016 or post-2025 periods are unsupported until a separately reviewed profile is added.

## Typed output

Schema: `broker_reports_fns_2ndfl_source_facts_v1`.

Fact families:

- `source_certificate_identity`;
- `tax_agent_identity`;
- `recipient_identity`;
- `income_source_row`;
- `deduction_source_row`;
- `tax_summary_source_fact`;
- `certificate_metadata`.

Every fact carries a deterministic fact id, source document/package identity, adapter id/version, schema family/version, source checksum, original node/value refs, fields, validation status, restrictions and an integrity hash. Customer values exist only in the `private_case` typed payload. The safe report contains counts, opaque identities, refs and hashes only.

`СвСумДох` placeholders without `СумДоход` are not silently dropped and are not invented as financial rows. They are recorded under `non_fact_source_nodes` with source refs and the reason `income_row_without_amount_not_material_source_fact`.

Certificate identifiers and export/signature metadata remain separate from income, deduction and tax-summary facts.

## Canonical route and validation

```text
Gate1 neutral XML source unit
  -> Gate2InputReadinessFactory.create
  -> Gate2Fns2NdflAdapterFactory.create
  -> broker_reports_fns_2ndfl_source_facts_v1
  -> validate_fns_2ndfl_typed_output
```

`Gate2InputReadinessFactory` enables financial interpretation only after typed validation passes. A generic XML document stays blocked and exposes a deterministic error code with provider calls, tokens and cost all equal to zero.

The adapter is read-only. ArtifactStore identity before and after preparation must be equal. Resolver access, lifecycle, source-availability and purge rules remain authoritative.

## Restrictions

Every fact declares:

- source-local meaning only;
- no tax declaration calculation;
- no cross-document reconciliation;
- no tax entitlement decision;
- no Gate 3 or Gate 4 output;
- private-case values.

Safe outputs must never contain raw XML values, filenames, private paths, artifact ids or source refs that identify a customer record.
