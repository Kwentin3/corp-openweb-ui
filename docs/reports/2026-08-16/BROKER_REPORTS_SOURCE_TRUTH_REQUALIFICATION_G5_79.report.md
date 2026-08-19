# G5.79 — Source Truth Requalification

Date: `2026-08-16`

Status: `STRATEGIC_STOP`

## Итог

Визуальная проверка опровергла исходную квалификацию `13 × SOURCE HAS IT →
role binding lost`. Поэтому G5.79 остановлен до любых изменений кода, prompt,
Role Pack, contract или persisted artifacts.

```text
SOURCE_TRUTH_REQUALIFICATION_REQUIRED
GATE2_CONTRACT_VIOLATION_PROVEN
NO_OWNER_FIX_APPLIED_AFTER_STOP
```

Три `decimal_invalid` действительно локализованы в Gate 4 normalization, но
не исправлялись после обязательного stop. Это сохраняет причинную границу и не
делает частичный patch под неверную метрику `13 → 0`.

## Что было заморожено

- `391` текущий Gate 4 fact;
- `13` `gate5_source_fact_required_role_missing`;
- `3` `gate5_source_fact_decimal_invalid`;
- все `16/16` incidents связаны с exact Gate 4 fact, Gate 3 annotation,
  active Canonical target и raw PDF page;
- baseline получен через public Gate 4, Gate 3 persistence и Canonical reader
  paths; direct SQL не использовался;
- provider calls: `0`;
- source/runtime mutation: `0`.

Exact private artifacts и raw screenshots находятся вне Git:

```text
external_private_evidence
```

В bundle находятся frozen incident payload, baseline owner sources, полные
raw pages, crops и contact sheet. До публикации отчёта bundle содержал `29`
files с tree SHA-256
`e2081a13f6b4e1103ac574fa159164f58a85f5d58bbe8b40958747e880cf953c`.

## Role branch: source truth

### Cluster R1 — 12 broad page annotations

Шесть raw pages визуально содержат много отдельных операций. Active Canonical
представляет каждую из этих страниц одним крупным `TEXT` node и не предоставляет
ни одного `TABLE`/row target на странице. Для каждого такого node Gate 3
опубликовал по одной `SECURITY_PURCHASE` и `SECURITY_DISPOSAL` annotation, обе
с нулём bound roles. На части тех же nodes также есть broad dividend, tax или
charge annotations с нулём roles.

Это не двенадцать атомарных source assertions, которым можно назначить по пять
ролей. Одна page-level пара label не может адресовать повторяющиеся строки того
же типа. Gate 3 Role Labeling v1 прямо запрещает повторный выбор строки внутри
coarse page node; для recovery нужен upstream exact row/region target.

Первое расхождение:

```text
raw visual rows
→ active Canonical coarse TEXT only
→ Gate 3 one broad annotation per label
→ Gate 4 role-incomplete pseudo-fact
```

Квалификация: `GATE2_CONTRACT_VIOLATION_PROVEN` (для требуемой exact-row
addressability) и
`SOURCE_TRUTH_REQUALIFICATION_REQUIRED`. Добавлять roles, удалять duplicates
или выбирать одну строку downstream запрещено.

### Cluster R2 — one exact table row

Тринадцатый incident имеет точный Canonical table-row closure. Raw crop и
Canonical одинаково показывают security redemption и quantity; source cells
для amount и currency пусты. Gate 3 правильно оставил эти две required roles
`missing`, Gate 4 правильно сохранил `role_incomplete`.

Квалификация: expected complete fact не подтверждён source truth. Перенос суммы
или валюты из другой строки создал бы запрещённую economic relation.

## Все 13 role incidents

| Incident | Raw truth | Canonical | Gate 3 / Gate 4 | First divergence | Решение |
| --- | --- | --- | --- | --- | --- |
| G579-04 | много операций на странице | coarse `TEXT`, row target отсутствует | broad PURCHASE, 0 roles | Gate 2 atomic structure | requalify |
| G579-05 | много trade rows | coarse `TEXT`, row target отсутствует | broad PURCHASE, 0 roles | Gate 2 atomic structure | requalify |
| G579-06 | много trade rows | coarse `TEXT`, row target отсутствует | broad DISPOSAL, 0 roles | Gate 2 atomic structure | requalify |
| G579-07 | тот же multi-row target, что G579-05 | coarse `TEXT` | broad DISPOSAL, 0 roles | Gate 2 atomic structure | requalify |
| G579-08 | exact redemption row; amount/currency отсутствуют | faithful `TABLE` row | missing сохранены корректно | source expectation | requalify |
| G579-09 | тот же multi-row target, что G579-06 | coarse `TEXT` | broad PURCHASE, 0 roles | Gate 2 atomic structure | requalify |
| G579-10 | тот же multi-row target, что G579-04 | coarse `TEXT` | broad DISPOSAL, 0 roles | Gate 2 atomic structure | requalify |
| G579-11 | много trade rows | coarse `TEXT`, row target отсутствует | broad PURCHASE, 0 roles | Gate 2 atomic structure | requalify |
| G579-12 | много trade rows | coarse `TEXT`, row target отсутствует | broad PURCHASE, 0 roles | Gate 2 atomic structure | requalify |
| G579-13 | много purchase/disposal rows | coarse `TEXT`, row target отсутствует | broad PURCHASE, 0 roles | Gate 2 atomic structure | requalify |
| G579-14 | тот же multi-row target, что G579-11 | coarse `TEXT` | broad DISPOSAL, 0 roles | Gate 2 atomic structure | requalify |
| G579-15 | тот же multi-row target, что G579-13 | coarse `TEXT` | broad DISPOSAL, 0 roles | Gate 2 atomic structure | requalify |
| G579-16 | тот же multi-row target, что G579-12 | coarse `TEXT` | broad DISPOSAL, 0 roles | Gate 2 atomic structure | requalify |

## Decimal branch

Все три source literals визуально подтверждены и дословно сохранены в
Canonical, Gate 3 `exact_text` и Gate 4 `source_literal`.

| Incident | Source form | Current Gate 4 value | First divergence | General law candidate |
| --- | --- | --- | --- | --- |
| G579-01 | signed, grouped amount with leading currency decoration | decoration сохранена, Decimal непригоден | Gate 4 normalization | отделить decoration и механически нормализовать grouping/sign |
| G579-02 | negative disposal quantity | negative quantity сохранена | Gate 4 normalization contract | при уже доказанном DISPOSAL представить quantity как positive magnitude, сохранив source literal |
| G579-03 | negative disposal quantity | negative quantity сохранена | Gate 4 normalization contract | то же общее правило |

Для G579-01 после возможной decimal normalization останется отдельный корректный
`currency_invalid`: source содержит символ, а не однозначный ISO code. Угадывать
валюту запрещено. Поэтому даже будущий Gate 4 fix не докажет автоматически
полную consumability этого fact.

Ни одно из трёх правил не применено: stop сработал раньше mutation phase.

## Before / after

После стратегического stop `after` равен baseline, а не искусственно зелёному
результату:

| Метрика | Before | After |
| --- | ---: | ---: |
| Gate 4 facts | 391 | 391 |
| role missing | 13 | 13 |
| decimal invalid | 3 | 3 |
| security source-ready | 80 | 80 |
| false user document requests from 13+3 | 0 | 0 |
| provider calls | 0 | 0 |
| invented facts | 0 | 0 |
| invented relations | 0 | 0 |

`UPSTREAM_SOURCE_FACT_PRODUCTION_REVIEW` и
`NORMALIZATION_OWNER_REVIEW` остаются: underlying incidents не маскировались и
не фильтровались.

## Preservation

- Maintained financial source/runtime files byte-identical G5.79 baseline:
  `8/8`.
- Focused G5.75/G5.77/G5.78, Gate 4 contract and Gate 5 source-consumption
  guards: `43 passed in 15.21s`.
- G5.78 frozen financial canary remains applicable because maintained code did
  not change: Holdout A `39 → 39`, Holdout B `129 → 129`, exact hashes equal.
- Gate 5 workaround, prompt tweak, regex, broker hint, relation, methodology,
  metadata/VLM and product activation: `0`.
- Current-case downstream replay was intentionally not entered: the finish
  contract requires it only after a valid repair, while the strategic stop
  forbids mutation.
- Dirty tree remains `PRESERVE_USER_OWNED`; stage/commit/reset/cleanup were not
  performed.

## Следующий допустимый шаг

Не «добавить 13 roles». Нужен отдельный архитектурно узкий decision goal:

1. переклассифицировать 12 broad annotations как non-atomic presence claims и
   определить, должны ли они вообще materialize в Gate 4;
2. отдельно решить upstream exact row/region addressability для этих шести
   pages;
3. отдельно подтвердить Gate 4 normalization law для трёх decimal forms;
4. не обещать `96/96`, пока symbol-only currency и source-absent amount/currency
   не закрыты доказательством.

G5.79 на этом закончен своим предусмотренным отрицательным terminal.
