# G5.77 — Contract Composition audit: strategic stop

> Historical intermediate audit. G5.77 subsequently hardened the maintained
> owner contract and anti-drift navigation, but intentionally did not implement
> the 13 role repairs or 3 decimal repairs. Use the final G5.77 closeout for the
> current scope and this file for the localized runtime violation.

## Terminal

```text
ARCHITECTURE_CONTRACT_VIOLATION_PROVEN
```

Runtime feature-fix остановлен; maintained contracts и anti-drift tests могут
быть усилены без изменения product semantics. Причина — найдено не только
навигационное неудобство, а фактическое противоречие текущего public composition
требуемому `SOURCE HAS IT` routing.

## Точное нарушение

```text
OWNER:
Gate5ClientEvidenceReviewRuntimeFactory.create
→ Gate5HumanGapClosureRuntimeFactory.create / _source_requests

CONSUMER:
Declaration Preparation closure-action planner

CURRENT BEHAVIOR:
каждый required source blocker превращается в
ADDITIONAL_DOCUMENT / document_submission

CONTRACT REQUIRED BEHAVIOR:
если source literal уже доказанно существует,
missing role → upstream source-fact production owner;
decimal normalization failure → normalization owner;
USER_FACT и ADDITIONAL_DOCUMENT запрещены.
```

На сохранённом current-case replay G5.76 это проявилось фактически:

| Reason | Count | Current closure route |
| --- | ---: | --- |
| `gate5_source_fact_required_role_missing` | 13 | `ADDITIONAL_DOCUMENT / document_submission` |
| `gate5_source_fact_decimal_invalid` | 3 | `ADDITIONAL_DOCUMENT / document_submission` |

Raw/Canonical audit G5.76 уже квалифицировал эти 16 incidents как `SOURCE HAS IT`. Поэтому их нельзя объяснить неизвестностью supplied evidence.

## Первый неправильный boundary contract

`Gate5ClientEvidenceReview` сохраняет reason code, но не сохраняет authority-qualified distinction:

```text
SOURCE_ABSENT
SOURCE_HAS_IT_ROLE_BINDING_LOST
SOURCE_HAS_IT_NORMALIZATION_FAILED
```

`Gate5HumanGapClosure._source_requests` вследствие этого группирует все required findings как клиентские document requests. Исправление требует отдельного feature GOAL на минимальное owner-aware routing в существующем finding/action contract. Новый reader, parser или Human Adapter не нужен.

## Что не является нарушением

- Missing signer и filing-instance не подавляют независимый calculation: проверочный replay сохранил `calculation_count=1`, одновременно оставил оба USER_FACT action и закрыл только release.
- Первый `USER_FACT` в actions не является dependency order: calculation уже существовал при первом USER action.
- Blocking granularity `(asset, currency)` соблюдается: один incomplete group не стирает calculation независимого complete group.
- `80 ready / 16 incomplete / 0 calculations` в G5.76 само по себе не bug: fact readiness не равна complete FIFO-group readiness; в current case ни одна активная disposal group не имела полного input set.
- Wrong/missing account, contract и broker metadata не меняют financial fingerprint или calculation count.

Focused behavioral verification: `3 passed` — independent-group granularity, deterministic replay with unresolved USER actions, G5.74 metadata invariant.

## Scope stop

- Authority contracts в момент этого промежуточного снимка изменены: `0`.
- Runtime изменён: `0`.
- Tests изменены: `0`.
- Product semantics изменены: `0`.
- Commit создан: `0`.

G5.77 поэтому ограничен contract/navigation guard, который не выдаёт runtime за
исправленный. Следующий разрешённый feature GOAL должен исправить существующий
`ClientEvidenceReview → HumanGapClosure` routing и добавить observable runtime
guard для `SOURCE HAS IT`.
