# Broker Reports — Gate 2 Successor Architecture Options

Дата: 2026-07-25  
Статус: `GOAL_8_ARCHITECTURE_OPTIONS: COMPLETED`

## Preferred: D — reuse Financial Evidence decision

```text
Gate 1 evidence
  → DeterministicScopeFactory
  → FinancialEvidenceDecisionContractFactory
  → one bounded model call
  → ValidatedDecisionFactory
  → FinancialEvidenceMaterializerFactory
  → FinancialContextFactory
```

Input: новая versioned deterministic scope package, содержащая authoritative values/lineage и Registry eligibility.  
Model output: существующий `broker_reports_gate2_financial_evidence_decision_v1`.  
Calls: 1 на connected source scope.  
Coverage: каждый selected ref имеет terminal disposition/ownership.  
Стоимость: минимальная из сравнимых вариантов; убирает source/domain calls, но точное значение требует отдельного bounded measurement.

Failure modes:

- deterministic scope не воспроизвёл ref/value → pre-model fail closed;
- model ref/type вне enum → canonical reject;
- unclassified loses value → materialization fail;
- context baseline regresses → rollout stop/rollback.

Compatibility: максимальная, потому что Registry, dispositions, validator, materializer и context уже приняты и GPT-5.4 Nano квалифицирован на этом workload.

Qualification: deterministic tests → synthetic → provider schema → bounded non-customer → actual shadow → full scope.

## Reserve: C — new combined secretary contract

```text
Gate 1 evidence
  → deterministic package-bound metric candidates
  → new source/domain secretary LLM
  → new secretary validator
  → deterministic materializer
  → Gate 2 context
```

Input/output: отдельные `secretary_scope_v1` / `secretary_decision_v1`, по смыслу type + role/ref bindings + disposition.  
Calls: 1.  
Плюс: можно выбрать scope semantics независимо от current financial runtime.  
Минус: почти полный semantic duplicate существующего financial decision, новый translation layer и отдельная qualification authority.

Этот вариант разрешён только при доказанном capability gap варианта D. На текущей базе gap отсутствует.

## Transitional: B — deterministic source, domain LLM retained

```text
Gate 1 evidence
  → deterministic source packages
  → compact domain LLM
  → financial evidence LLM
  → context
```

Calls: 2.  
Плюс: меньше migration impact для domain runtime.  
Минусы: domain и financial stages оба выбирают semantic type/bindings; сохраняются двойная стоимость, расхождения authorities и два comparator layers.

Можно использовать только как временный shadow instrument, не как target.

## Rejected: A — два legacy LLM stages

```text
Gate 1 → source LLM → domain LLM → financial LLM → context
```

Calls: 3; максимальная contract surface. Отклонён, потому что не найдено уникальной source/domain model ability, а current failures сосредоточены именно в повторении internal representation.

## Компонентная ответственность preferred option

| Компонент | Ответственность |
|---|---|
| Gate 1 | literal, labels, source refs, lineage, neutral source units |
| DeterministicScopeFactory | segmentation, router candidates, package boundaries, eligibility |
| Registry | type definitions, roles, compatibility |
| LLM | disposition, type, role/ref bindings, bounded reason |
| Canonical validator | final semantic admission |
| Materializer | IDs, values, provenance, restrictions, completeness, coverage |
| Context factory | единственная source-bound projection |
| Checksum | post-context bounded verification, отдельная authority |

## Full-scope compatibility

Preferred option не утверждается production-ready этим research. Он обязан доказать:

- не меньшую terminal ref coverage;
- literal/provenance identity;
- unclassified preservation;
- zero new type/invention/cross-row;
- context invariant parity;
- cost/call reduction.

## Acceptance

- `IMPLEMENTABLE_OPTIONS: THREE`
- `PREFERRED_OPTION: D`
- `REJECTED_OPTIONS: A_AND_B_AS_TARGET`
- `RESERVE_OPTION: C_ONLY_AFTER_PROVEN_GAP`
- `SEPARATE_SOURCE_DOMAIN_LLM_SEMANTIC_VALUE: NONE_FOUND`
