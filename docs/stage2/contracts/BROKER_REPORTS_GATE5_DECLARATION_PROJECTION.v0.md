# Broker Reports Gate 5 Declaration Projection v0

Status: `CURRENT SUPPORTING CONTRACT`

Goal status: `G5.12_CLOSED`

Product status: `INACTIVE PROOF`

## Purpose

This contract owns one narrow representation boundary:

```text
validated projection-proof input
+ validated Declaration Projection Spec
        -> deterministic declaration-shaped fragment
```

It proves only the 2025 3-NDFL Appendix 8 fragment for one securities-operation
category. It does not define Tax Model or Tax Methodology semantics and does
not generate a complete XML declaration.

## Public boundary

The sole construction entrypoint is:

```python
Gate5DeclarationProjectionRuntimeFactory.create(...)
```

`create` always loads the exact SHA-pinned repository evidence fixture and
loads the repository candidate unless another candidate is supplied for
authoring-time validation. It validates the candidate before returning the
projector. Case-time execution is only:

```python
runtime.project(proof_input=...)
```

No LLM, official-source download, XSD parse, Gate 4 read, Tax Methodology read,
storage or network operation is allowed in `project`.

## Exact declaration target

| Property | Value |
| --- | --- |
| tax period | `2025` |
| form / KND | `3-NDFL` / `1151020` |
| order | FNS `ED-7-11/913@`, 2025-10-20 |
| electronic format | `5.20` |
| XSD | `NO_NDFL3_1_033_00_05_20_01.xsd` |
| fragment | `File/Document/NDFL3/DohOperCB` (`Файл/Документ/НДФЛ3/ДохОперЦБ`) |
| cardinality | `0..unbounded`; the proof emits one logical occurrence |

The official form, filling procedure, electronic format and XSD are captured
by URL, locator and SHA-256 in the separate evidence resource. Raw official
documents are not copied into Git.

## Machine-readable artifacts

The candidate spec is the package resource:

```text
gate5_declaration_projection_spec.ru_3ndfl_2025_appendix8.v0.json
```

It contains only:

- exact declaration identity;
- a synthetic projection-proof input contract;
- target path and cardinality;
- one mapping per source concept;
- declaration-owned transform, requiredness and evidence references.

The captured evidence pack is:

```text
gate5_declaration_projection_evidence.ru_3ndfl_2025_appendix8.v0.json
```

It separately records why each mapping is accepted: official source hashes,
locators, XSD-derived target contract and bounded mapping claims. It is not a
runtime copy of the DOCX or XSD.

## Projection-proof input

`broker_reports_gate5_declaration_projection_proof_input_v0` is an inactive
consumer stub, not a production Tax Model. It requires exactly:

| Stable concept | Value kind |
| --- | --- |
| `operation_category` | stable enum |
| `operation_category_gross_income` | money |
| `related_expenses` | money |
| `allowable_expenses` | money |
| `loss_treatment` | stable enum |

The representative values are `organized_market_securities_outside_iis`,
`100.00 RUB`, `72.00 RUB`, `72.00 RUB` and `none`. Their declaration codes and
field names are absent from projector control flow.

## Candidate validation

Factory construction fails closed unless all of these hold:

1. spec and evidence pack have exact closed keys and version identities;
2. declaration identity and target cardinality match the evidence pack;
3. input concepts and mapping IDs are unique;
4. every mapped source concept is declared by the proof input contract;
5. every target attribute exists in captured XSD/format evidence;
6. all five proof-required mappings are present exactly once;
7. source value kind, transform and target datatype are compatible;
8. enum codes have an exact evidence-pack mapping claim;
9. every mapping carries the complete required evidence-reference set;
10. conflicting source or target mappings are rejected.

The validator contains no list of the five Russian attribute names or their
codes. Those live only in the machine-readable artifacts.

## Output

`broker_reports_gate5_declaration_projection_fragment_v0` contains:

- exact declaration identity;
- target path, element and one logical occurrence;
- projected attribute map;
- spec and evidence-pack SHA-256 bindings;
- mapping-level provenance;
- an explicit validation claim.

The validation claim is only:

```text
structurally_consistent_not_full_xml_validated
```

It must not be described as a complete XSD-valid declaration. Full XML
envelope and XSD validation remain outside G5.12.

## Ownership

| Knowledge / behavior | Owner |
| --- | --- |
| tax meaning | Tax Methodology |
| stable calculated value | future Tax Model |
| declaration code/path/cardinality | Declaration Projection Spec |
| official proof of mapping | evidence pack |
| mechanical mapping execution | deterministic projector |
| research/extraction | authoring-time LLM agent |

No responsibility is intentionally duplicated. The evidence pack states why a
mapping is credible; the projection spec states what an already validated
runtime executes.

## Non-goals

This proof does not create a production Tax Model, tax calculation, complete
3-NDFL XML/PDF, serializer, generic form engine, XSD-to-JSON generator,
publication workflow, database, GUI mapper, methodology editor, provider call
or product route. Gate 4 and G5.11 remain unchanged.
