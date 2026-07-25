# Broker Reports — Gate 2 ambiguity discipline, Goal 11D

Дата: 2026-07-25

Статус: `TERMINAL_FAILED`

## Outcome

Выполнена ровно одна live qualification attempt для exact economy candidate
`claude-haiku-4-5-20251001` на неизменном successor workload v2.

Модель/provider route не квалифицированы:

- cases passed: `6/12`;
- cases failed: `6/12`;
- four dispositions represented: `false`;
- canonical outputs produced: `8/12`;
- provider schema rejections: `4/12`;
- final qualification status: `failed`.

Эта exact revision terminal и повторно не запускается.

## Exact attempt boundary

- repository revision:
  `3f9171b855b1004d00585d87eacb089507867acc`;
- exact model:
  `claude-haiku-4-5-20251001`;
- provider profile:
  `anthropic_claude`;
- benchmark canonical hash:
  `430bea21d0a36e993bc50184d971f36dfc75a1d2be12bcf5e43fba7436797d66`;
- prompt SHA-256:
  `30c823d2c509294d4634eac1a4084da9b95056b260bdd64e41d5a5598937d9ae`;
- provider route revision:
  `289bf0618825d53f49ebe2fda1272aa284e5c5b23f072a262f990c80111d74e7`;
- authorization identity:
  `b90fd7fcc888d1a7e5a8ccf93ba99b4c148f95210c57b0cd7b4a8b7812fc9461`;
- live Action content SHA-256:
  `f178b142403e52897d2caf74ad75576162331efa85b0da85d472d8301ad24932`.

Preflight passed before the call:

- Action repository/live parity;
- exact model published;
- exact workload authorization;
- local Q0/Q1;
- Anthropic schema dry-builds `12/12`.

## Failure classes

### Runtime schema rejection — 4 cases

Failure code:

`gate2_model_schema_response_format_rejected`

Affected cases:

- `syn_successor_v2_unique_cash`;
- `syn_successor_v2_unique_printed_total`;
- `syn_successor_v2_optional_missing`;
- `syn_successor_v2_forbidden_neighbour`.

Это все четыре typed-admitted schema cases. Provider route отклонил response
format после успешного local dry-build. Canonical validation/materialization
для них не запускались, потому что contract output не был получен.

### Valid but wrong disposition — 2 cases

- `syn_successor_v2_repeated_header`:
  expected `no_financial_input`, observed
  `unclassified_financial_input`;
- `syn_successor_v2_unsupported_shape`:
  expected `unsupported`, observed
  `unclassified_financial_input`.

Обе outputs прошли canonical validation/materialization, но нарушили product
expectations.

## Observed outcomes

Of 8 canonical outputs:

- `unclassified_financial_input`: `8`;
- `typed_input`: `0`;
- `no_financial_input`: `0`;
- `unsupported`: `0`.

Шесть ambiguity/unclassified cases прошли. Два safe-but-wrong cases не прошли.
Unsafe typed input: `0`.

Полный product comparator/artifact-family proof не строился, потому что четыре
scopes не получили canonical output. Поэтому literal/ownership acceptance на
полный workload не заявляется.

## Economy and latency

- provider calls: `12`;
- recorded input tokens: `19,520`;
- recorded output tokens: `2,235`;
- recorded cost: `$0.030695000`;
- provider duration sum: `51,669 ms`;
- min/average/max duration:
  `1,312 / 4,305.75 / 8,156 ms`.

Token/cost receipts присутствуют для восьми response-producing calls. Четыре
provider-rejected calls не дали budget receipt, поэтому `$0.030695000` — точно
зафиксированная, но не гарантированно полная сумма внешнего биллинга.

Execution exclusions:

- fallback: `0`;
- repair: `0`;
- hidden retry: `0`;
- source/domain/expensive model calls: `0/0/0`;
- customer calls: `0`;
- production writes/routing: `0/0`.

## Evidence and privacy

Complete safe checkpoint receipt remains under ignored `local/`.
SHA-256:

`138c3f03b87ce0ac270befbbf5524fd0dc19c07adf1aeb5253edba85b335fda6`.

Committed evidence is value-free:

- raw provider output absent;
- source groups/literals/value refs absent;
- expected model output absent;
- customer data absent.

## Terminal program blocker

Nano и разрешённый альтернативный Haiku candidate оба terminal failed.
Продолжать перебор моделей запрещено исходной программой.

Goals 12–15 требуют qualified financial evidence model и поэтому не могут быть
честно запущены:

- actual-corpus shadow не авторизован;
- full-scope/checksum не могут доказать выбранный successor stack;
- production admission/release запрещены;
- final closure cannot claim release acceptance.

## Repository boundary

- base:
  `3f9171b855b1004d00585d87eacb089507867acc`;
- branch:
  `codex/broker-reports-gate2-ambiguity-goal11d-haiku-qualification`;
- PR: pending creation;
- code changes: `0`;
- production admission: false.

## Acceptance

- `HAIKU_FINANCIAL_MODEL: REJECTED`
- `AMBIGUITY_DISCIPLINE: FAILED_6_OF_12`
- `FOUR_DISPOSITIONS: FAILED`
- `EXACT_ATTEMPT: TERMINAL`
- `GOALS_12_15: BLOCKED_NO_QUALIFIED_FINANCIAL_MODEL`
