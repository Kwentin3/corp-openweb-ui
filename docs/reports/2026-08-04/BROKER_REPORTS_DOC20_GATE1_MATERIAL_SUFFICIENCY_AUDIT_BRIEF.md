# DOC20 brief

Все 48 frozen base calls учтены, но ни один не дал content verdict: существующий adapter отправляет `temperature=0`, которое `gpt-5.6-sol` отклонил HTTP 400.

- Входы: 24 таблицы, 48 Gate 1 JSON, 24 full-page overlays, классы 12/7/5.
- Accounting: 48/48 attempts, 48 failures, 0 retry/fallback/repair, $0.00.
- Adjudication и метрики: `NOT_EVALUATED`, потому что raw verdicts отсутствуют.
- Gate 1, cropper, Gate 2, Gate 3 и product pipeline не изменялись.

```text
DOC20_EXPERIMENT=BLOCKED
DOC20_RESULT=BLOCKED_VERIFIER_ADAPTER_MODEL_INCOMPATIBILITY
GATE1_MATERIAL_SUFFICIENCY=INCONCLUSIVE
BEST_GATE1_ARTIFACT=NOT_EVALUATED
CROP_RESEARCH_POLICY=INCONCLUSIVE
```
