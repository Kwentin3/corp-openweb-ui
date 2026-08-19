# Broker Reports Gate 5 G5.16 — Declaration Definition Authoring

Date: 2026-08-10 (Europe/Moscow)

Status: **PARTIALLY PROVEN / G5.16 NOT CLOSED at the requested anti-bias
strength**.

## Ответ

На требуемой строгости — пока **нет**.

Текущая LLM-assisted сессия сформировала небольшой machine-readable
Declaration Definition candidate, а ordinary-code validator подтвердил его
evidence/capability/artifact/I/O consistency. Candidate честно выделяет два
условно исполнимых declaration units и два разных gap.

Но критерий независимого discovery не доказан: основной агент видел полный
G5.16 addendum с ожидаемыми примерами до построения exact payload, а отдельный
clean-context model call в этой сессии не выполнялся. Поэтому stored candidate
явно содержит:

```text
trial_independence = structural_prompt_only_not_blind_to_governance_goal
```

Это reasoning/evaluation boundary, а не недостаток official evidence, output
schema или deterministic validator. Объявлять G5.16 закрытым было бы сильнее
полученного доказательства.

## Что реально получено

Добавлены:

- exact SHA-pinned six-section authoring context;
- bounded inventory из четырёх published tax/projection artifacts;
- one LLM-authored candidate data resource;
- one static validator/analyzer;
- focused negative tests;
- versioned contract и authority-map entries.

G5.15 Runtime Capability Contract не менялся. Новые capability, calculation
behavior, human input type и case-time research seam не добавлялись.

## Official research

Primary authority — [приказ ФНС России от 20.10.2025 №
ЕД-7-11/913@](https://www.nalog.gov.ru/rn77/about_fts/docs/16589324/).
Страница подтверждает КНД `1151020`, три утверждённых приложения и применение
формы начиная с декларации за налоговый период 2025.

На 2026-08-10 live bytes четырёх официальных attachments повторно скачаны в
memory и сверены с captured evidence:

| Official attachment | Bytes | SHA-256 | Used evidence |
| --- | ---: | --- | --- |
| [form PDF](https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/16589324_1.pdf) | 438,785 | `d751043f63af1f0095a14228a65a3831acf47fcd82c397e2eb38b0f9f8dc9565` | Appendix 8 fields; Section 2 fields |
| [filling procedure](https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/16589324_2.docx) | 106,008 | `7bc11cad8d0465c03c834c50c7832fb2edc7291d9b4b161ef5b2c6cabdcb0fdc` | paragraphs 37–46, 97–98; appendices 4 and 8 |
| [electronic format](https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/16589324_3.docx) | 148,677 | `f5215c237a8af73dd7a251cee94a2e09aacd8540173fcde2904b4c311129e3c2` | table 4.46 and Section 2 structure |
| [XSD 5.20](https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/xsd/NO_NDFL3_1_033_00_05_20_01.xsd) | 178,427 | `083128322833dbafb29be0bf919e33b7b362956244b422d34dd554c99a1e4484` | `ДохОперЦБ` and tax-base structures |

Previous G5 reports were navigation/repository context only and do not appear
as normative evidence in the model payload.

## Exact model-visible payload

The payload is built by
`Gate5DeclarationDefinitionAuthoringFactory.create().model_payload()` and has
exactly:

```text
SYSTEM INSTRUCTIONS
RESEARCH POLICY
RUNTIME CAPABILITIES
PUBLISHED ARTIFACT INVENTORY
OFFICIAL EVIDENCE
OUTPUT SCHEMA
```

The system/research sections contain only the high-level intent to audit the
current 2025 securities-disposal declaration surface. They do not name Section
2, line 060, group tax base or a roadmap gap. Official evidence does contain
the actual downstream form requirements, because deleting them would itself
bias the result.

No model-visible section contains Python owner names, repository paths,
ArtifactStore/SQL details, prior Gate reports or case-time browser tools.

### Context measurement

Bytes are canonical UTF-8 JSON. Tokens are measured with local `tiktoken
0.12.0`, encoding `o200k_base`; this is an explicit tokenizer proxy, not a
claim about an unspecified provider model's exact billing tokenizer.

| Section | UTF-8 bytes | `o200k_base` tokens |
| --- | ---: | ---: |
| system instructions | 832 | 149 |
| research policy | 593 | 111 |
| runtime capabilities | 6,775 | 1,353 |
| published artifact inventory | 1,785 | 396 |
| official evidence | 4,528 | 1,233 |
| output schema | 1,097 | 226 |
| exact enveloped payload | 15,747 | 3,490 |

Architectural warning: none at this representative scale. The payload is
bounded and dominated by the existing capability contract plus official
evidence, not repository history. Larger declaration coverage still requires
fresh measurement rather than extrapolation.

## Published artifact inventory finding

The inventory exposed exact identities/versions and semantic runtime relations,
not repository internals:

| Artifact | Published behavior / role | Public capability relation |
| --- | --- | --- |
| `ru-ndfl-securities-proof@2026.0-experimental` | `security_disposal_net_result_v0` | executable by `execute_published_calculation_behavior_v0` |
| `ru-ndfl-securities-tax-model-proof@2026.0-experimental` | single-operation Tax Model behavior | no public capability relation |
| `ru-ndfl-securities-tax-model-proof@2026.1-experimental` | operation-model behavior/member binding | accepted by aggregation, but no public producer capability |
| `ru-3ndfl-2025-appendix8-securities-proof@2026.0-proof` | validated projection | direct projection and nested aggregation output |

This exposed an important mismatch in the suggested happy path:
`execute_published_calculation_behavior_v0` only executes the old G5.7
`security_disposal_net_result_v0` contract. Its output is not an operation-model
member accepted by G5.14. Therefore the Definition cannot truthfully compose
`resolve -> execute -> aggregate -> project` as one compatible chain.

## Definition candidate

Candidate:
[gate5_declaration_definition_candidate.ru_3ndfl_2025_securities.v0.json](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_declaration_definition_candidate.ru_3ndfl_2025_securities.v0.json)

Authoring context:
[gate5_declaration_definition_authoring_context.v0.json](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_declaration_definition_authoring_context.v0.json)

Contract:
[Broker Reports Gate 5 Declaration Definition Authoring v0](../../stage2/contracts/BROKER_REPORTS_GATE5_DECLARATION_DEFINITION_AUTHORING.v0.md)

The candidate has no executable `action`, `steps`, expression, formula, code,
command or tool field. Each compilable unit references exactly one published
capability and explicitly declares its boundary inputs.

## Compilation Report

| Declaration requirement | Needed semantic output | Planned capability/artifact | Status | Gap |
| --- | --- | --- | --- | --- |
| substantiate Appendix 8 aggregate meanings with operation members | compatible source-tagged operation-model members | none; `2026.1` methodology exists but has no public producer | `NOT_COMPILABLE` | `missing_runtime_capability` |
| complete Appendix 8 category aggregation | complete category aggregation/result with exact completeness binding | `aggregate_complete_category_scope_v0`; operation methodology + validated projection | `COMPILABLE` with declared boundary inputs | none inside this unit |
| project complete five-concept semantics | Appendix 8 declaration fragment | `project_validated_declaration_fragment_v0`; validated projection | `COMPILABLE` with declared boundary input | none inside this unit |
| derive the next official income-group-bound tax base | group-level tax base | no compatible published behavior; calculation capability is only a related existing primitive | `NOT_COMPILABLE` | `missing_published_behavior` |

`COMPILABLE` is deliberately conditional: it proves exact capability/artifact
and I/O compatibility when declared inputs already exist. It does not claim an
end-to-end Financial Case route.

## First Missing Capability / first downstream gap

First runtime composition gap, in user-pain terms:

> The runtime cannot turn current case evidence into the operation-model
> members required by category aggregation through any published capability.

First unsupported downstream declaration requirement after the conditional
Appendix 8 fragment:

> The runtime cannot deterministically derive the declaration-required
> group-level tax base from complete income-group inputs with a reviewed
> published behavior.

The second gap is classified as `missing_published_behavior`, not a fabricated
new capability. No behavior or methodology was generated to hide it.

## Static validation proof

The ordinary-code validator checks:

- closed root/requirement/gap schemas;
- exact target/evidence identity;
- resolvable official evidence refs;
- known `proven` + `case_time` capability IDs through the G5.15 resolver;
- declared input and output contract compatibility;
- artifact identity and capability-role compatibility through existing owners;
- unresolved requirement/gap bidirectional consistency;
- gap-type-specific invariants;
- absence of free-form execution fields.

Negative tests prove rejection of unknown capability, wrong input/output
contract, unknown/incompatible artifact, target drift, orphan gap, inconsistent
gap type and free-form `action`.

## Verification

| Check | Terminal result |
| --- | --- |
| focused G5.16 | `11 passed` |
| G5.12–G5.16 relevant contour | `43 passed` |
| all Gate 5 tests + architecture suite | `100 passed` |
| authority-sensitive canonical/Gate 3/Gate 4/KT1 suite | initial `95 passed, 1 failed`; exact two-module allowlist repair; replay `96 passed, 1 warning` |
| Ruff check for new module/test | passed |
| Ruff format check | passed after deterministic formatting |
| package-only closed-world import/resource validation | passed: staged module path only, both resource hashes exact, payload `15,747` bytes, status `partially_compilable`, gaps `2` |

The initial authority-sensitive failure was the historical exact package-module
allowlist rejecting the new G5.15 and G5.16 owners. Only those two literal paths
were added; the assertion and CI-suite checks were not weakened. The remaining
warning is a pre-existing invalid escape sequence in the DOC6 local report
script and is unrelated to G5.16.

## GUI / chat-as-authoring-surface

The result supports only the narrow interface hypothesis:

```text
high-level user request
-> official research evidence
-> candidate JSON + compilation diff + typed gaps
-> deterministic validation
-> human review
```

This can be presented through chat without a specialized flow-builder GUI.
However, G5.16 does not yet prove that a clean-context model independently
finds the same requirement/gaps, and it does not replace artifact publication
or human review. Therefore “chat is sufficient as the authoring surface”
remains plausible but not closed.

## KISS and stop

Added one validator module, two small JSON resources, one focused test module,
one contract, this report and authority-map rows. No runner, DSL, plugin system,
DB, CMS, XML/PDF path, GUI or product activation was created.

No next engineering slice was started. G5.16 stops here with a valid partial
candidate and an explicit blind-authoring evidence boundary.
