# Broker Reports G5.85 — provider no-response policy и semantic inventory

Дата: 2026-08-17
Terminal: `SEMANTIC_INVENTORY_REQUALIFICATION_REQUIRED`

## Итог

Part A закрыт: operational retry отделён от semantic retry. Part B обнаружил настоящий систематический semantic error и по контракту остановлен без исправления. Поэтому Part C — ordinary Gate 3 replay и последующий Gate 4 rebuild — не выполнялся.

```text
PROVIDER_NO_RESPONSE_POLICY_PROVEN
OPERATIONAL_RETRY_SEPARATED_FROM_SEMANTIC_RETRY
SEMANTIC_RETRY_ZERO
SEMANTIC_INVENTORY_REQUALIFICATION_REQUIRED
```

## Part A — no semantic response

Существующий маршрут сохранён:

```text
Gate3BoundedLabeling / Gate3RoleLabeling
→ Gate2StructuredModelClientFactory.create
→ label_gate3_once
→ existing provider adapter
```

Политика `gate3_operational_no_response_v1` допускает максимум один operational retry. Это минимальная положительная граница: она поглощает ровно один изолированный transient no-response и не превращает задачу в repeated semantic sampling.

Retry разрешён только при одновременном выполнении:

- error code равен `gate2_model_provider_unavailable`;
- adapter уже классифицировал failure как `provider_transport` либо `provider_error_response`;
- usable semantic response отсутствует.

Auth, rate limit, model/config failure, response budget, malformed/invalid semantic content и validator rejection не открывают retry. Полученный semantic response возвращается валидатору один раз; его отклонение не возвращает управление в provider loop.

Exact identity доказана повторным использованием одного sealed `prepared_request`; каждая отправка получает только private deep copy. Receipt связывает обе отправки с одним `request_identity_sha256`. Ceiling test доказал две transport submissions, одну operational retry и отсутствие semantic response; success test доказал тот же request в обеих отправках и остановку после первого semantic response.

Accounting разделён на:

- `semantic_attempts`;
- `transport_submissions`;
- `transport_failures_before_semantic_response`;
- `operational_retries`;
- `semantic_responses_received`;
- `semantic_rejections`.

Реализация находится в существующем shared owner, без нового retry framework: `gate2_model_clients.py:363-504,975-1004`; propagation и batch accounting — `gate3_bounded_labeling.py:91,214-216`, `gate3_role_labeling.py:109,425-427`, `gate3_chunk_batch_labeling.py:381-522`.

Файл исторически называется Gate 2 client, но изменение profile-scoped только для `GATE3_BOUNDED_LABELING_REQUEST_PROFILE`. Gate 2 source/domain semantics, Prompt и request profiles не менялись.

## Part B — machine inventory

Детерминированная карта охватила `1489/1489` current large-document Gate 4 facts:

- 51 source-layout/role-geometry structural class;
- 58 family отрицательных control rows в inventory;
- 0 same-type duplicate targets;
- 0 role targets вне принятой canonical row;
- все Gate 3/Gate 4 identities привязаны через существующие factory/read owners.

| Financial type | Gate 4 facts | Structural classes | Формально qualified до STOP | Wrong | Pending после STOP |
|---|---:|---:|---:|---:|---:|
| `TAX_WITHHELD` | 746 | 23 | 0 | 0 | 746 |
| `DIVIDEND_INCOME` | 539 | 12 | 0 | 105 | 434 |
| `SECURITY_PURCHASE` | 77 | 6 | 0 | 0 | 77 |
| `SECURITY_DISPOSAL` | 77 | 5 | 0 | 0 | 77 |
| `TRANSACTION_CHARGE` | 33 | 3 | 0 | 0 | 33 |
| `COMMISSION` | 13 | 4 | 0 | 0 | 13 |
| `COMMISSION_TOTAL` | 2 | 2 | 0 | 0 | 2 |
| `TAX_WITHHELD_TOTAL` | 2 | 2 | 0 | 0 | 2 |

Нули в колонке `Wrong` вне обнаруженного класса не являются green verdict: обязательный STOP прервал дальнейшую visual qualification. Поэтому `UNEXPLAINED SEMANTIC CLASS = 0` не заявляется.

## Обнаруженный систематический класс

Machine audit нашёл 105 фактов `DIVIDEND_INCOME`, хотя буквальное source description той же строки содержит `US Налог`. Они распределены по 6 страницам, 6 structural classes и 6 provider chunks.

Development-only visual audit исходного PDF подтвердил класс на страницах 4, 5 и 7:

- первая строка-конфликт на странице 4 имеет tax description и положительный кредит;
- на странице 5 тот же tax description повторяется для положительных кредитов и отрицательных дебетов;
- на странице 7 тот же pattern повторяется на других инструментах и датах.

Визуальное наблюдение не стало production fact и не добавлено в runtime. VLM calls: `0`.

## First semantic divergence

Первая current annotation с конфликтом:

```text
annotation_index = 22
PDF page         = 4
structural class = sc_97649d53686922a3
provider chunk   = 10
fact alias       = f005
target alias     = t1241
```

Локализация:

```text
original PDF: explicit US-tax row
→ Canonical: literal row preserved correctly
→ Gate 3 pass-1 provider proposal: DIVIDEND_INCOME   ← FIRST DIVERGENCE
→ Gate 3 role pass: label preserved, roles proposed
→ persistence / Gate 4: proposal preserved exactly
```

Parser/Canonical и Gate 4 не являются первым owner ошибки. Prompt/model/Role Pack не менялись, и semantic correction намеренно не внесена.

## Part C — не выполнен

Ordinary replay был разрешён только после clean A+B. Part B не clean, поэтому:

- ordinary provider calls: `0`;
- новый Gate 3 artifact: не создавался;
- Gate 4 rebuild после ordinary replay: не выполнялся;
- Gate 5: не запускался.

## Проверки

- focused provider/Gate 3/persistence/architecture/bundle tests: `146 passed`, `0 failed`;
- `ruff`: passed;
- `py_compile`: passed;
- maintained-source → generated-bundle parity: passed;
- semantic retry: `0`;
- VLM calls: `0`;
- Git clean/reset/stage/commit: не выполнялись; dirty user-owned tree сохранён.

## Evidence

- `BROKER_REPORTS_PROVIDER_NO_RESPONSE_AND_SEMANTIC_INVENTORY_G5_85.closeout.safe.json` — итог A/B/C;
- `BROKER_REPORTS_OPERATIONAL_RETRY_SEMANTIC_QUALIFICATION_G5_85.machine.safe.json` — 100% machine inventory;
- `BROKER_REPORTS_OPERATIONAL_RETRY_SEMANTIC_QUALIFICATION_G5_85.safe.json` — systematic-conflict localization;
- private evidence: `broker-reports-g5.85-20260817-v1` outside Git;
- proof owners: `scripts/prove_g585_semantic_inventory.py`, `scripts/qualify_g585_semantic_stop.py`.

## KISS и следующий разрешённый шаг

KISS соблюдён: один profile-scoped retry loop, один existing request hash, один bounded ceiling, без queue/scheduler/backoff framework и без semantic retry.

G5.85 не разрешает переход к VLM stand как будто current inventory green. Следующий допустимый GOAL должен сначала отдельно решить или пере-квалифицировать локализованный Gate 3 semantic class. После его clean qualification стратегический следующий GOAL остаётся:

```text
VLM vs CURRENT PARSER comparative stand
```
