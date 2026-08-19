# Broker Reports Gate 5 Declaration Projection v1

Status: `CURRENT SUPPORTING CONTRACT`

Goal status: `G5.24_CLOSED`

Product status: `INACTIVE PROOF`

Date: 2026-08-10

## Purpose

This contract version-replaces v0 as the current PROJECT boundary. It proves
that one exact repository-published projection definition can map an already
validated stable Tax Model into a bounded declaration-shaped fragment without
recalculating tax.

v1 supports two immutable artifacts through one closed runtime:

- the historical 2025 Appendix 8 projection;
- the 2025 Section 2 income-group/tax-base projection added by G5.24.

It does not assemble or validate a complete electronic declaration.

## Public boundary

The construction and execution entrypoints are:

```python
runtime = Gate5DeclarationProjectionRuntimeV1Factory.create()
runtime.project(
    projection_ref=...,
    declaration_semantics=...,
)
```

`projection_ref` uses
`broker_reports_gate5_declaration_projection_ref_v1`. The runtime resolves
only a static closed registry of exact ID/version pairs. There is no dynamic
import, caller path, caller schema, alias, fallback or discovery.

Before mapping, the Section 2 branch delegates the supplied
`broker_reports_gate5_income_group_tax_base_model_v0` to
`DeclarationSemanticsIncomeGroupRuntimeFactory.create`. That Declaration
Semantics owner revalidates the upstream Tax Model and returns only the closed
values/traces contract. PROJECT imports no Tax Model implementation, reproduces
no G5.22 formula and infers no missing value.

## Section 2 artifacts

Projection definition:

```text
gate5_declaration_projection_spec.ru_3ndfl_2025_section2.v1.json
sha256  1dbe4124295ac2539f92349d28a8bcc2b4038133639c399f613eeb0bfe9a1705
```

Official-evidence pack:

```text
gate5_declaration_projection_evidence.ru_3ndfl_2025_section2.v1.json
sha256  ff67f17ea76758312e3f32b586c83904c86794ef4073f0b1543f68ffe6fdfc38
```

Identity:

```text
projection_id       ru-3ndfl-2025-section2-securities-income-group-proof
projection_version  2026.0-proof
input contract      broker_reports_gate5_income_group_tax_base_model_v0
```

The spec is mapping data, not an executable DSL. It contains a two-node target,
seven exact source-to-attribute mappings and only the two reviewed transforms
`enum_code` and `money_amount`. It has no conditions, expressions, loops,
templates, caller paths or executable code.

## Backwards-derived official target

The [FNS order page](https://www.nalog.gov.ru/rn77/about_fts/docs/16589324/)
publishes Order ED-7-11/913@ of 2025-10-20, form KND 1151020, its filling
procedure, electronic format and XSD for tax period 2025.

For this bounded proof the official sources establish:

| Node | Required attributes |
| --- | --- |
| `Файл/Документ/НДФЛ3/НалБаза` | `ГрупДоход` |
| `Файл/Документ/НДФЛ3/НалБаза/РасчНалБаза` | `СумДох`, `СумДохНеНал`, `СумДохНал`, `СумНалВыч`, `СумРасх`, `НалБаза` |

The group value is a two-digit string. Each monetary value is a decimal with
at most 15 total digits and two fractional digits. Procedure paragraphs 37-46
bind group 001 and lines 010-060 to the same stable semantics already produced
by G5.22.

The evidence resource records exact primary-source byte hashes:

```text
form PDF          d751043f63af1f0095a14228a65a3831acf47fcd82c397e2eb38b0f9f8dc9565
procedure DOCX    7bc11cad8d0465c03c834c50c7832fb2edc7291d9b4b161ef5b2c6cabdcb0fdc
format DOCX       f5215c237a8af73dd7a251cee94a2e09aacd8540173fcde2904b4c311129e3c2
XSD               083128322833dbafb29be0bf919e33b7b362956244b422d34dd554c99a1e4484
```

Raw official documents remain outside Git.

## Classification ownership

The stable Tax Model owns:

```text
resident_securities_and_derivatives_non_iis
```

The versioned projection/evidence artifacts own its form-specific mapping to
income group `02`. Official income type `003` supports that classification but
is not an attribute of the bounded Section 2 target, so it is recorded as
`evidence_only_not_section2_target` and is not emitted.

Consequently:

- a form field/code/structure change versions the projection artifact;
- a change to stable tax meaning versions methodology/Tax Model behavior;
- a classification change updates its semantic owner and the affected
  evidence-bound mapping, rather than projector control flow;
- another declaration may consume the same stable Tax Model through another
  published projection without changing calculation runtime.

## Output and provenance

`broker_reports_gate5_declaration_projection_fragment_v1` returns a bounded
node tree, exact projection/spec/evidence and source-input bindings, validation
claims, and one provenance record per mapped value:

```text
Tax Model contract/concept/trace
  -> projection rule and official evidence refs
  -> target node/attribute
```

The representative result is `НалБаза ГрупДоход="02"` with one
`РасчНалБаза` child containing `160.00`, `5.00`, `155.00`, `3.00`, `104.00`
and `48.00` in the six mapped fields. It explicitly claims only
`partial_section2_fragment_not_full_xml_validated`.

## Fail-closed boundary

Construction or projection stops on unknown/stale ref, package hash drift,
invalid spec/evidence shape, missing/duplicate/ambiguous mapping, unsupported
target/code/representation, classification mismatch, incompatible input
contract, or an invalid/incomplete upstream model. No fragment is returned.

## Versioning and compatibility

v0 bytes and factory remain immutable replay evidence. v1 adapts the published
Appendix 8 artifact into the common v1 fragment envelope and proves it remains
executable. The capability action remains PROJECT, but its public input/output
contract changed, so Runtime Capability Contract v3 replaces only the PROJECT
member ID with `project_validated_declaration_fragment_v1`.

## Scope stop

This proof adds no tax formula, rate, tax payable, case discovery, persistence,
XML serializer, full-document assembler, XSD validator, PDF, filing, GUI,
workflow, generic form engine, projection DSL, sixth capability or product
route.
