# Broker Reports G5.78 — SOURCE HAS IT Owner-Aware Routing Fix

Status: `COMPLETE`

Date: 2026-08-16

## Outcome

G5.78 исправил только маршрутизацию внутренних source-fact defects. Сами 13
role bindings и 3 decimal values не исправлялись. Новый router/framework не
создавался.

```text
SOURCE_HAS_IT_OWNER_AWARE_ROUTING_PROVEN
ROLE_BINDING_DEFECTS_ROUTED_UPSTREAM
DECIMAL_NORMALIZATION_DEFECTS_ROUTED_TO_OWNER
FALSE_ADDITIONAL_DOCUMENT_ACTIONS_ZERO
EVIDENCE_HORIZON_EXTERNAL_DEMANDS_PRESERVED
USER_CASE_ROUTING_UNCHANGED
FINANCIAL_GENERALIZATION_PRESERVED
READY_TO_REPAIR_13_ROLE_AND_3_DECIMAL_DEFECTS
```

## Baseline и первый неверный owner

Frozen real-case replay до изменения снова дал:

| Reason | Findings | Неверный action |
| --- | ---: | --- |
| `gate5_source_fact_required_role_missing` | 13 | `ADDITIONAL_DOCUMENT / document_submission` |
| `gate5_source_fact_decimal_invalid` | 3 | `ADDITIONAL_DOCUMENT / document_submission` |

Первое неверное решение находилось в
`Gate5ClientEvidenceReview._source_blocker_finding`: любой required blocker,
кроме двух специальных ветвей, default'ился в `ADDITIONAL_DOCUMENT`.
`Gate5HumanGapClosure._source_requests` затем материализовал уже неверную
closure как просьбу принести документ.

## Минимальный fix

Существующий finding получил один встроенный `routing` block; существующий gap
request переносит его без нового routing owner.

| Source state | Route | Owner | User request |
| --- | --- | --- | --- |
| `SOURCE_HAS_IT_ROLE_BINDING_LOST` | `UPSTREAM_SOURCE_FACT_PRODUCTION_REVIEW` | Gate 3 public demand port -> Gate 4 materializer | запрещён |
| `SOURCE_HAS_IT_NORMALIZATION_FAILED` | `NORMALIZATION_OWNER_REVIEW` | `Gate4FinancialCaseMaterializerFactory.create` | запрещён |
| `SOURCE_ABSENT_WITHIN_SUPPLIED_EVIDENCE_HORIZON` | `EVIDENCE_HORIZON_EXTERNAL_DEMAND` | existing HumanGapClosure/new-document replay | разрешён |
| unknown | `OWNER_UNRESOLVED` | unresolved | запрещён |

HumanGapClosure теперь явно публикует
`user_facing_required_actions` и `internal_owner_required_actions`. В dialog
adapter входят только `USER_FACT` и `ADDITIONAL_DOCUMENT`.

## Current-case replay

После fix:

- 13 role defects -> один internal owner action с 13 findings;
- 3 decimal defects -> один internal normalization action с 3 findings;
- false `ADDITIONAL_DOCUMENT` от 13+3: `0`;
- четыре реальные acquisition evidence-horizon gaps остались четырьмя
  `ADDITIONAL_DOCUMENT` actions;
- methodology gap остался `METHODOLOGY_RESEARCH` у existing trusted-methodology
  owner;
- required actions разделены: user-facing `9`, internal-owner `3`;
- четыре USER/CASE actions не изменили semantics: before/after semantic hash
  `e2c6bc2f90d9219b5a5c6d0e1a1a119b6ae8f23cabb0f877ab31e994d1a6ad4b`.

Safe evidence:

- `BROKER_REPORTS_SOURCE_HAS_IT_OWNER_ROUTING_G5_78.baseline.safe.json`
- `BROKER_REPORTS_SOURCE_HAS_IT_OWNER_ROUTING_G5_78.baseline-actions.safe.json`
- `BROKER_REPORTS_SOURCE_HAS_IT_OWNER_ROUTING_G5_78.replay.safe.json`
- `BROKER_REPORTS_SOURCE_HAS_IT_OWNER_ROUTING_G5_78.replay-actions.safe.json`
- `BROKER_REPORTS_SOURCE_HAS_IT_OWNER_ROUTING_G5_78.matrix.safe.json`
- `BROKER_REPORTS_SOURCE_HAS_IT_OWNER_ROUTING_G5_78.financial.safe.json`

Exact private replay evidence находится вне Git:

```text
external_private_evidence
```

Baseline private result SHA-256:
`0d5817aa9917b7ecbe910b58b782450bc73d9306c2351a2f7675a856d2722c62`.
Replay private result SHA-256:
`a97ca2e5e69bea03d1f7cf08c256bc843ee55ac47f5dc554c8d3e744c1f1d6ac`.

## Verification

- Owner-routing guards A-D plus methodology control: `6 passed` including the
  normative contract check.
- Focused architecture/runtime suite: `89 passed`.
- Python compile and Ruff on changed runtime/tests: passed.
- Existing `FACTORY_REQUIRED` / `FORBIDDEN` anchors remain intact; replay uses
  `Gate5DeclarationPreparationRuntimeFactory.create`, which composes the
  existing review and closure factories.
- Financial canary through
  `Gate4FinancialCaseRuntimeFactory.create.rebuild_case`: Holdout A `39 -> 39`,
  Holdout B `129 -> 129`, exact hashes unchanged.
- Frozen source store remained byte-identical before/after each declaration
  replay.

Cold agent, без dated reports и истории, дал `PASS` по всем трём сценариям:
role loss -> Gate 3/Gate 4 owner; decimal rejection -> Gate 4 normalization
owner; genuine evidence-horizon absence -> outward Evidence Demand allowed. Он
не обнаружил нового generic router/framework.

## Scope stop и dirty tree

PDF/Canonical, Gate 3 prompts/Role Pack, Gate 4 financial facts, deterministic
source consumer, Declaration Preparation orchestration, methodology, metadata,
VLM, Human Adapter and projection не менялись. Product activation и provider
calls: `0`.

Canonical worktree остаётся большим `PRESERVE_USER_OWNED` dirty tree. Ничего не
clean/reset/stage. Вместо небезопасного commit подготовлен focused patch вне
Git:

```text
external_private_evidence
```

Следующий отдельный GOAL может ремонтировать сами 13 role и 3 decimal defects
у их настоящих owners; G5.78 на этом останавливается.
