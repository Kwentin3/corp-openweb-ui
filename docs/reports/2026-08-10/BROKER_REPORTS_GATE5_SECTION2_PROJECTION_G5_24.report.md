# Broker Reports Gate 5 Section 2 Projection — G5.24

Date: 2026-08-10

Status: `G5.24_CLOSED`

Outcome: `SECTION2_PROJECTED_WITH_EXISTING_CAPABILITY_FAMILY`

Product status: `INACTIVE PROOF`

## Ответ

Да. Уже доказанная G5.22 tax semantics отображается в официальную структуру
Section 2 через versioned PROJECT v1 и один минимальный evidence-bound
projection package. Новая capability family, declaration-specific Python
hardcode и программируемый Tax/XML Engine не понадобились.

Исторический PROJECT v0 оказался Appendix-8-shaped по input/output contract,
но не фундаментально по действию. Его versioned преемник принимает один
опубликованный projection ref и зарегистрированный stable semantic input;
Capability Contract по-прежнему содержит ровно пять action families.

## Expected versus observed до реализации

```text
expected
  validated G5.22 Tax Model
  + evidence-bound Section 2 mapping
  -> bounded Section 2 declaration fragment

observed
  PROJECT v0 accepted only Appendix 8 proof input
  and emitted only its flat Appendix 8 fragment contract
```

Это было contract/representation ограничение, а не отсутствие налоговой
формулы и не основание вводить новый base primitive.

## Backwards official evidence

Проверено 2026-08-10. [Страница приказа ФНС](https://www.nalog.gov.ru/rn77/about_fts/docs/16589324/)
публикует приказ № ЕД-7-11/913@ от 2025-10-20, форму КНД 1151020, порядок,
электронный формат и XSD для налогового периода 2025.

Для bounded Section 2 восстановлено:

- root `Файл/Документ/НДФЛ3/НалБаза`, required `ГрупДоход`;
- child `РасчНалБаза`, required `СумДох`, `СумДохНеНал`, `СумДохНал`,
  `СумНалВыч`, `СумРасх`, `НалБаза`;
- group code — двухзначная строка;
- все шесть сумм — decimal, `totalDigits=15`, `fractionDigits=2`;
- paragraphs 37-46 Порядка связывают group/lines 010-060;
- Appendix 4 связывает bounded resident non-IIS securities scenario с group
  `02` и supporting income type `003`.

Exact downloaded source hashes:

```text
form PDF          d751043f63af1f0095a14228a65a3831acf47fcd82c397e2eb38b0f9f8dc9565
procedure DOCX    7bc11cad8d0465c03c834c50c7832fb2edc7291d9b4b161ef5b2c6cabdcb0fdc
format DOCX       f5215c237a8af73dd7a251cee94a2e09aacd8540173fcde2904b4c311129e3c2
XSD               083128322833dbafb29be0bf919e33b7b362956244b422d34dd554c99a1e4484
```

Raw official bytes не добавлены в Git.

## Ownership and classification 02 / 003

Разделение сохранено:

```text
Tax Methodology  = налоговый смысл и расчёт
Tax Model        = полученные stable values
Projection       = form-version target, codes and representation
```

G5.22 Tax Model сохраняет stable semantic
`resident_securities_and_derivatives_non_iis`. Projection/evidence artifacts
владеют отображением этого смысла в form-specific `ГрупДоход=02`.

`003` — официальный классификационный qualifier, но не field bounded Section 2
fragment. Он явно записан как `evidence_only_not_section2_target` и не
выводится. Поэтому код не спрятан в projector для удобства.

Hardcode pressure test:

| Изменение | Меняющийся owner |
| --- | --- |
| ФНС меняет Section 2 fields/codes/structure | новая версия projection/evidence artifact |
| меняется налоговый расчёт | methodology/behavior и Tax Model, не PROJECT mechanic |
| меняется income classification | stable semantic owner и затронутое evidence-bound mapping; не branch в projector |
| другая декларация использует тот же Tax Model | другой published projection ref; calculation runtime не переписывается |

## Минимальная реализация

Добавлены два package resources:

```text
gate5_declaration_projection_spec.ru_3ndfl_2025_section2.v1.json
  sha256 1dbe4124295ac2539f92349d28a8bcc2b4038133639c399f613eeb0bfe9a1705

gate5_declaration_projection_evidence.ru_3ndfl_2025_section2.v1.json
  sha256 ff67f17ea76758312e3f32b586c83904c86794ef4073f0b1543f68ffe6fdfc38
```

Spec содержит только target из двух nodes, семь mappings и два закрытых
transform kind: enum-to-code и RUB money formatting. Условий, expressions,
loops, templates, caller paths и executable code нет.

`Gate5DeclarationProjectionRuntimeV1Factory.create` владеет статическим
двухэлементным registry: прежний Appendix 8 и новый Section 2. Перед mapping
он повторно валидирует Section 2 input через реальный G5.22 owner. Appendix 8
остаётся исполнимым через общий v1 fragment envelope.

Runtime Capability Contract v3:

```text
same five families
PROJECT member  project_validated_declaration_fragment_v1
input           projection_ref + registered_projection_input
output          broker_reports_gate5_declaration_projection_fragment_v1
resource SHA    34d3796054fc780b4c4937caf101b87224a64ed58b857ac9404a5c0b3438f438
```

v0/v1/v2 machine contracts и historical PROJECT v0 не изменены.

## Representative deterministic proof

Реальный G5.22 owner построил Tax Model, а PROJECT v1 дважды дал byte-semantic
equal result:

```text
НалБаза ГрупДоход=02
  РасчНалБаза
    СумДох       160.00
    СумДохНеНал    5.00
    СумДохНал    155.00
    СумНалВыч      3.00
    СумРасх       104.00
    НалБаза        48.00
```

Каждое значение сохраняет цепочку:

```text
source contract/concept/trace
  -> projection rule + official evidence refs
  -> target node/attribute
```

Result говорит только
`partial_section2_fragment_not_full_xml_validated`.

Fail-closed regressions подтверждают отказ без fragment для unknown ref,
tampered upstream Tax Model, missing или duplicate/ambiguous mapping,
classification mismatch, target/evidence incompatibility и package hash drift.

## History-free Declaration Definition replay

До inference были заморожены только current published inventory и Runtime
Capability Contract v3; authoring intent, official evidence, research policy,
system instructions и output schema остались прежними. Старые gap IDs и
ожидаемый следующий blocker модели не сообщались.

```text
trial             g5.24-history-free-replay-2026-08-10-001
payload bytes     28631
payload SHA-256   c69a096ad656ccb0c843930977f7ed12b0e148cd5467528dca06ea6fe08241f3
history/workspace none/empty
provider/model    openai_codex_cli / gpt-5.6-sol high
provider calls    1
retry/follow-up   0/0
terminal event    turn.completed
candidate bytes   7405
candidate SHA-256 c2efa5639a8d083ef6f7c9d9cef4f873a1027cdfbcc4d765b80c66555aa8c8c1
parser/schema     passed/passed
compiler          passed
manual repair     0
```

Итог: 5 requirements, 4 supported, 1 unsupported, 6 resolved compositions,
1 gap. Оба прежних gap отсутствуют. Первый новый blocker:

```text
complete_electronic_declaration_assembly_gap
```

Он не реализован.

## Candidate limitations preserved without repair

Exact model candidate — evidence, не authority. В нём замечены две неточности:

1. `semantic_outputs` Section 2 упоминает income type `003`, хотя runtime
   fragment содержит только group `02` и шесть денежных attributes;
2. unsupported full-document composition перечисляет два projection artifacts
   в одной PROJECT composition, хотя один runtime invocation принимает один
   `projection_ref`; compiler проверяет artifact identity/role, но не эту
   cardinality.

Retry, follow-up, cherry-pick и repair не выполнялись. Ограничения сохранены в
safe trial record и не повышены до runtime truth.

## Verification

Из `services/broker-reports-gate1-proof`:

```text
focused G5.24/G5.23 owners + architecture
  106 passed, 1 unrelated warning in 38.19s

all Gate 5 tests + architecture
  171 passed, 1 unrelated warning in 52.33s

authority successor LF hash pin
  1 passed in 1.35s

ruff on changed G5.24 modules/tests
  passed
```

Warning — прежний `DeprecationWarning` об escape sequence в DOC6 report
script; это не assertion failure и не относится к G5.24.

Exact candidate, compilation record, trial record и все новые machine resources
проходят JSON parse. UTF-8, package/resource hashes, local Markdown links,
privacy/secret-like scan и `git diff --check` также прошли. Git вывел только
ожидаемые line-ending warnings из-за Windows attributes; whitespace errors нет.

## KISS / architecture result

Результат ограничен одним versioned artifact pair, маленьким static registry,
одной общей two-node projection representation и честной versioned contract
коррекцией. Не созданы Projection DB/Service/ACL, новый ArtifactStore,
OpenWebUI workflow, sixth capability, calculation branch или DSL.

OpenWebUI не привлекался: это immutable repository publication и deterministic
runtime boundary; платформенная GUI/storage задача в G5.24 отсутствует.

## Scope stop

G5.24 закрыт. Не начаты:

- complete electronic declaration assembly/XSD validation;
- full XML, PDF, filing, GUI или workflow;
- tax rate/tax payable или новая формула;
- новая capability family;
- product activation.

Следующая declaration-discovered boundary —
`complete_electronic_declaration_assembly_gap`. Для неё нужен отдельный GOAL.
