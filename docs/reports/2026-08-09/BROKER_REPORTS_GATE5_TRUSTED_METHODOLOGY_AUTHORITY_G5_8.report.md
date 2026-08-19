# Broker Reports Gate 5 — Trusted Tax Methodology Authority (G5.8)

Date: 2026-08-09

Goal status: `G5.8_CLOSED`

Proof outcome: `PROVEN`

Product status: `INACTIVE`

## Verdict

Да. Gate 5 может отличить trusted methodology от contract-valid arbitrary
caller JSON без Methodology Platform.

Минимальный seam:

```text
closed caller reference
-> repository-versioned, raw-SHA-pinned package resource
-> unchanged G5.7 calculation
-> resource/projection/identity-bound wrapper result
```

Новая persistence infrastructure не понадобилась.

## Research boundary

Проверены repository truth и закреплённый OpenWebUI `v0.9.6`:

- existing Gate 3 Financial Label Dictionary и Role Pack package-resource
  loaders;
- existing managed financial asset manifests/projections;
- existing ArtifactStore immutability, case scope и G5.3 use;
- existing OpenWebUI-backed managed Prompt resolver и access checks;
- upstream OpenWebUI Prompt, Skill и Tool storage shapes;
- G5.7 contract, runtime, result binding и fail-closed behavior.

G5.7 calculator уже корректно связывал результат с exact projection hash, но
его public input позволял caller передать сами methodology bytes. G5.8 не
меняет этот низкоуровневый calculation contract; он ставит trusted resolution
перед ним.

## Рассмотренные варианты

| Вариант | Решение | Repository finding |
| --- | --- | --- |
| versioned repository package resource | выбран | Gate 3 уже доказывает factory load, exact file SHA, closed-world resource и tamper failure |
| OpenWebUI Prompt | отклонён для proof | access/history полезны, но current row mutable; это prompt owner, а не опубликованная Tax Methodology |
| OpenWebUI Skill/Tool | отклонён для proof | access-controlled GUI surfaces, но у pinned version нет полного immutable version/readback lifecycle |
| ArtifactStore | отклонён как authority | immutable artifact IDs подходят case state, но writer/scope semantics принадлежат user/case artifacts, не system tax meaning |
| новая DB/config service | отклонён | добавила бы storage, ACL, CRUD и lifecycle без необходимости одного immutable published version |

Выбранный вариант не маскирует methodology в Python: налоговое содержание
находится в отдельном JSON resource. Python содержит только closed published
identity-to-resource/hash binding и обычную validation/composition boundary.

## Authority contract

Physical owner:

```text
broker_reports_gate1/
  gate5_tax_methodology.ru_ndfl_securities_proof.v0.json
```

Stable identity:

```text
methodology_id      = ru-ndfl-securities-proof
methodology_version = 2026.0-experimental
```

Runtime owner:

```text
Gate5TrustedMethodologyAuthorityFactory.create
```

Trusted composition:

```text
Gate5TrustedMethodologyCalculationRuntimeFactory(...).create()
```

Caller input содержит только:

```json
{
  "schema_version": "broker_reports_gate5_trusted_methodology_ref_v0",
  "methodology_id": "ru-ndfl-securities-proof",
  "methodology_version": "2026.0-experimental"
}
```

Caller не передаёт JSON methodology, path, hash, rule, behavior, requirements
или bindings.

## Integrity и authority

Разделение стало явным:

```text
authority:
  registered identity -> system package resource

resource integrity:
  raw resource SHA-256 == pinned expected SHA-256

calculation integrity:
  canonical projection SHA-256 == G5.7 result projection SHA-256
```

Raw hash защищает exact stored bytes. Canonical projection hash связывает
decoded methodology с G5.7 result. Wrapper независимо требует равенства
trusted `id/version/projection_sha256` и nested calculation result.

Package resource возвращается как copy. Caller mutation этой copy не меняет
следующее trusted resolution.

Threat boundary ограничен runtime caller. G5.8 не утверждает защиту от лица,
которое уже авторизовано изменить и развернуть application repository.

## Representative replay

Trusted owner разрешил ту же experimental methodology, что использовалась в
G5.7:

```text
Financial Case:
  proceeds = 100.00 RUB

Supplemental Facts:
  acquisition_cost = 70.00 RUB
  transaction_expense = 2.00 RUB
```

Unchanged G5.7 вернул:

```text
recognized_expense = 72.00 RUB
net_result          = 28.00 RUB
```

G5.8 wrapper сохранил:

- `authority_owner = repository_versioned_package_resource`;
- exact methodology id/version;
- exact raw resource SHA-256;
- exact canonical projection SHA-256;
- полный неизменённый G5.7 result с rule/behavior/input provenance.

Новый ArtifactStore и новый runtime повторно разрешили resource и вернули
полностью идентичный wrapper result. Financial Case до/после равен;
Supplemental Facts не изменились; write operation отсутствует.

## Fail-closed proof

Доказано:

- caller payload с дополнительным полем `methodology` отклоняется как
  `gate5_trusted_methodology_ref_invalid`;
- неизвестная identity/version отклоняется как
  `gate5_trusted_methodology_not_published`;
- изменённый package resource при прежнем identity/hash pin отклоняется как
  `gate5_trusted_methodology_resource_hash_mismatch`;
- caller mutation ранее прочитанной copy не влияет на replay;
- существующий G5.7 `gate5_calculation_behavior_unsupported` проходит через
  trusted wrapper без fallback;
- ни один failure path не создаёт artifacts или calculation result.

Также контракт закрывает missing resource, invalid JSON, resource identity
mismatch и trusted/result binding mismatch.

## Immutability finding

Одна published identity в closed map связана с одним raw resource hash.
File-only mutation немедленно fail-closed.

Published map объявлен append-only: новая методология получает новую version,
resource и hash binding. Изменить старые bytes и pin можно только явным
repository diff/deployment, что нарушит контракт и не является silent runtime
overwrite. Старый calculation result всё равно сохраняет прежний projection
hash.

Это минимальная достаточная immutability для одного proof; lifecycle state
machine не понадобилась.

## Независимость от calculator implementation

Новая methodology version с тем же поддержанным `behavior_id` требует только:

```text
new JSON resource
+ new authority identity/hash registration
```

G5.7 calculator менять не нужно. Если methodology требует новую арифметику,
существующий G5.7 unknown-behavior guard продолжает требовать отдельную
reviewed implementation. G5.8 не добавлял behavior.

## Architecture finding

```text
[ Trusted Methodology Owner ]
  Gate5TrustedMethodologyAuthorityFactory.create
  repository package resource + exact raw SHA-256
          |
          | exact methodology id/version/projection
          v
[ G5.7 calculation boundary ]
  Gate5MethodologyCalculationRuntimeFactory.create
          |
          | unchanged deterministic result
          v
[ calculation result ]
  authority owner/resource hash
  + G5.7 methodology/rule/behavior/provenance/output binding
```

Ответы на обязательные вопросы:

1. Authority owner — `Gate5TrustedMethodologyAuthorityFactory.create`.
2. Methodology физически находится в versioned JSON package resource.
3. Stable identity — `(methodology_id, methodology_version)`.
4. Content integrity — pinned raw SHA-256 плюс G5.7 canonical projection
   SHA-256.
5. Silent mutation — file-only change fail-closed; published identities
   append-only; новый content требует новой version.
6. Caller всё ещё выбирает опубликованный reference и передаёт existing trusted
   case context.
7. Caller больше не контролирует bytes, path, hash, rule, behavior,
   requirements или bindings.
8. Новая persistence infrastructure не понадобилась.
9. Repository resource проще alternatives: existing proven pattern, no DB,
   ACL, CRUD, workflow или mutable GUI lifecycle.

## KISS review

Добавлены:

- один JSON package resource;
- один маленький authority + composition module;
- один closed reference/result contract;
- focused replay/tamper/anti-drift tests;
- authority/CI routing и этот report.

Не добавлены Methodology CRUD, lifecycle states, approval roles, selector по
tax period/residency/effective date, DB/table, registry service, Tax Case, Tax
Engine, DSL, LLM, новый calculation behavior или product activation.

Factory/anti-drift и closed-world guardrails сохранили один путь: trusted
wrapper -> unchanged G5.7 -> existing G5.5. Tests проверяют observable result,
real SQLite ArtifactStore и copied-package tamper, не mock calculator.

## Verification

```text
Focused G5.7 + G5.8: 8 passed
G5.2-G5.8 contour: 23 passed
Extended bundles/ArtifactStore/lifecycle/architecture/Gate 3 owners/Gate 4/G5.2-G5.8/privacy: 138 passed
Managed generator checks: 10 passed
Generated OpenWebUI bundles: byte-stable, no G5.8 product activation
Closed-world copied-package load and tamper rejection: passed
```

## Evidence files

- [G5.8 contract](../../stage2/contracts/BROKER_REPORTS_GATE5_TRUSTED_METHODOLOGY_AUTHORITY.v0.md)
- [trusted authority/runtime](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_trusted_methodology.py)
- [trusted methodology resource](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_tax_methodology.ru_ndfl_securities_proof.v0.json)
- [G5.8 tests](../../../services/broker-reports-gate1-proof/tests/test_broker_reports_gate5_trusted_methodology.py)
- [unchanged G5.7 contract](../../stage2/contracts/BROKER_REPORTS_GATE5_METHODOLOGY_CALCULATION.v0.md)
- [Architecture authorities](../../stage2/contracts/BROKER_REPORTS_ARCHITECTURE_AUTHORITIES.md)
- [OpenWebUI Prompt model at pinned v0.9.6](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/models/prompts.py)
- [OpenWebUI Skill model at pinned v0.9.6](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/models/skills.py)
- [OpenWebUI Tool model at pinned v0.9.6](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/models/tools.py)

## Stop condition

`G5.8_CLOSED`, result `PROVEN`, product status `INACTIVE`.

Tax-period/residency/effective-date selection, authoring, approval and
methodology lifecycle remain separate future uncertainties. Следующий Gate 5
slice не начат.
