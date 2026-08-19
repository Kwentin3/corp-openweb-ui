# Broker Reports G5.34 Full-target 3-NDFL XML Projection Report

Date: `2026-08-11`
Goal: `G5.34`
Verdict: `FULL_TARGET_XML_VALID`
Blockers: `0`
Scope: inactive bounded synthetic proof only

## Result

One exact trusted full-target Projection Definition now consumes the sealed
G5.33 Declaration Semantic Input and produces a complete 3-NDFL XML document
for the supplied synthetic case. The runtime constructs the tree first,
serializes it without adding meaning, validates the serialized bytes against
the exact official FNS XSD, and emits one hash-chain receipt.

The representative safe receipt is
[`BROKER_REPORTS_GATE5_FULL_TARGET_XML_PROJECTION_G5_34.receipt.safe.json`](./BROKER_REPORTS_GATE5_FULL_TARGET_XML_PROJECTION_G5_34.receipt.safe.json).
No raw XML, taxpayer value, source-party value or other synthetic identity value
is present in the report evidence.

## Official target authority

Verified on `2026-08-11`:

- FNS Order No. ED-7-11/913@ of 20 October 2025 approves the 3-NDFL form,
  filling procedure and electronic format and applies from declarations for tax
  period 2025:
  `https://www.nalog.gov.ru/rn77/about_fts/docs/16589324/`;
- the current FNS 3-NDFL forms page routes the 2025 period to that order:
  `https://www.nalog.gov.ru/rn77/taxation/taxes/ndfl/form_ndfl/`;
- official filling procedure DOCX SHA-256:
  `7bc11cad8d0465c03c834c50c7832fb2edc7291d9b4b161ef5b2c6cabdcb0fdc`;
- official electronic-format DOCX SHA-256:
  `f5215c237a8af73dd7a251cee94a2e09aacd8540173fcde2904b4c311129e3c2`;
- official `NO_NDFL3_1_033_00_05_20_01.xsd` decoded bytes: `178427`;
- official XSD SHA-256:
  `083128322833dbafb29be0bf919e33b7b362956244b422d34dd554c99a1e4484`;
- the current FNS KBK page confirms `18210102030011000110` for payment of
  personal income tax received under Tax Code article 228:
  `https://www.nalog.gov.ru/rn77/taxation/kbk/fl/ndfl/`.

The order publishes an XSD for this target and no separate Schematron artifact;
the exact conformance contract is therefore XSD-only and records
`schematron = null`.

## Autonomous blocker closure

The first full-target pass exposed five ordinary projection blockers. All were
local losses of meanings already required by the unchanged trusted Full
Declaration Definition, so no strategic stop and no Definition revision were
needed.

| Blocker | Closure | Replayed owner |
| --- | --- | --- |
| filing component retained references but not XML-required declaration date, authority code, legal taxpayer identity or declarant category | restored the exact supplied synthetic values and validation | `Gate5FilingAndPartyIdentityRuntimeFactory.create` |
| income-source component retained a source ref but not source-party identity or OKTMO | restored exact organization identity semantics and domestic/foreign obligation outcomes | `Gate5DeclarationIncomeSourcesRuntimeFactory.create` |
| budget component retained allocation refs but not KBK, OKTMO or simplified-procedure returned/credited amount | restored exact supplied-case budget meanings | `Gate5DeclarationBudgetOutcomeRuntimeFactory.create` |
| G5.33 view omitted existing non-taxable-income and tax-deduction values | selected those existing semantic values without exposing the input snapshot | `Gate5DeclarationSemanticInputRuntimeFactory.create` |
| a resolved source domain did not expose per-obligation domestic/foreign state | retained exact per-obligation resolution in the component and semantic view | source component plus G5.33 view |

The replay order was component creation and validation, scope/package assembly,
sealed Package validation, G5.33 semantic-input compilation, full-target tree
projection, serialization and XSD validation.

## Projection Definition and runtime

```text
Projection Definition
  id       ru_3ndfl_2025_full_target_supplied_case
  version  2026-08-11.0-proof
  sha256   48109cc6b3de6fd4d242346648660d99b40863310e622ab2cec44dc641ec7b26

Official XSD
  name     NO_NDFL3_1_033_00_05_20_01.xsd
  sha256   083128322833dbafb29be0bf919e33b7b362956244b422d34dd554c99a1e4484
```

All target elements, attributes, ordering, source paths, repeat paths,
constants, enum codes, currency/amount representations, output encoding,
domain-state profile and evidence refs live in that Definition. The Python
runtime is a generic tree mapper and contains no 3-NDFL element names, KND,
format version, taxpayer/income/operation code map or target encoding literal.

The prior fragment projector remains historical bounded evidence and is not
imported or composed by the G5.34 runtime.

## Semantic mapping proof

```text
Definition obligations                      25
activated and projected obligations          8
terminal non-projected obligations           17
unaccounted obligations                       0
mapping ids                                  49
mapping occurrences                          49
mapping proof status                     passed
mapping proof sha256
  c8bc9f1b5d900881efe65783b708157231c14f5ebca1756aea8df74672ee3449
```

Every activated obligation has a non-empty target-path binding. Every omitted
optional target domain has the exact non-activated terminal state required by
the Projection Definition. The proof stores hashes of source and rendered
values, not the values themselves.

## Conformance and determinism proof

```text
tree built before serializer              yes
serializer representation-only            yes
serialized encoding              windows-1251
well-formed XML                         passed
official XSD validation                 passed
Schematron                                null
same input + Definition + serializer
  -> byte-identical XML                    yes
xml bytes                                1112
xml sha256
  07d2a96d89776d71877bdd1f30ce142a4c6b6f905e09d3e8bcfe238195a8ef2a
terminal                       FULL_TARGET_XML_VALID
```

The negative proof separately keeps a valid semantic mapping result and makes
the serialized XML violate `ВерсФорм`; the official XSD rejects it. Thus a
mapping success cannot masquerade as target conformance.

The representative final receipt binds:

```text
xml sha256
  -> Projection Definition sha256
  -> Declaration Semantic Input sha256
  -> Full Declaration Definition sha256
  -> sealed Package sha256
```

## Fail-closed evidence

Focused negative tests prove rejection of:

- Projection Definition byte drift;
- official XSD byte drift;
- an unmapped changed semantic enum;
- a missing semantic value without defaulting;
- a non-integral tax amount without rounding;
- a changed domain-state profile that would silently omit an activated domain;
- serialized XML rejected by the official XSD.

No retry, best-of-N, provider call, manual XML repair, expected XML injection or
placeholder fallback exists.

## Verification

```text
focused G5.34 suite
  10 passed

full Gate 5 replay
  233 passed

architecture stabilization
  18 passed, 1 pre-existing DeprecationWarning

ruff over changed Python/test surfaces
  passed

pip dependency check
  no broken requirements
```

The closed-world test executes from a cwd outside the repository and still
resolves only packaged definition/XSD resources through the factory. `lxml` is
declared and pinned in `requirements-ci.txt`.

Product bundle SHA-256 values remain unchanged:

```text
Gate 1 bundle
  a0f919c4957cf64c21603e1e9599b171ee3472cfc8076a480c904926d2b64fcd
Gate 2 source bundle
  3ab3d64fa0598167e3c15a00b203fbf8587399f9d767eeee593875487ec0c616
Gate 2 domain bundle
  29cd51c8568ebcaaebc3c597f1741fc62795bdd5fb28613edae1f8c3df2e4add
```

## KISS check

One trusted Definition, one factory-routed runtime, one recursive tree mapper,
one representation-only serializer and one official XSD validator were added.
There is no second Declaration Model, target registry, rules engine, form
framework, database, workflow or projection fragment composition.

The upstream correction reused the existing five component/view owners. It did
not introduce parallel readers or semantic authorities.

## Limitations and stop

- This is supplied-case completeness, not real-world taxpayer tax completeness.
- XSD validity proves official schema conformance, not filing acceptance,
  cross-reference validation by FNS services or legal correctness of a real
  taxpayer declaration.
- Identity and monetary data are synthetic proof values.
- No XML file was committed as an output artifact; only a privacy-safe receipt
  was retained.
- No PDF, filing/submission, product activation, push, PR or dependent Gate goal
  was performed.

G5.34 stops here.
