# Broker Reports — Economy requalification v2

Дата повторного прогона: 2026-07-24.

Статус: `COMPLETED_WITH_EXPLICIT_GAPS`.

## Итог

После публикации трёх exact-кандидатов qualification возобновлена и
переиграна на stage OpenWebUI `0.9.6`. Получен рабочий синтетический набор,
но не одна универсальная модель:

- `gpt-5.4-nano-2026-03-17` прошёл financial evidence `4/4`;
- `claude-haiku-4-5-20251001` прошёл bounded source/domain и checksum `3/3`;
- `models/gemini-2.5-flash-lite` виден в aggregate inventory, но maintained
  provider route возвращает upstream `404`;
- ни одна модель не получила production qualification;
- production allowlist остался пустым.

Единица доказательства:

`exact model × provider profile × workload × contract version`.

## Scope и ограничения

Использовались только синтетические fixtures. Customer/actual-corpus,
full-scope, production migration, free JSON, repair, retry-as-repair,
fallback и дорогие модели не использовались. `claude-opus-5`, появившийся
в inventory вместе с кандидатами, не вызывался.

Stage изменялся только пользователем до начала повтора — публикацией трёх
моделей. Этот прогон не менял stage configuration и runtime selection.

## Повторная инвентаризация

- aggregate `/api/models`: `41`;
- `models/gemini-2.5-flash-lite`: опубликован, Gemini route `urlIdx=3`;
- `gpt-5.4-nano-2026-03-17`: опубликован, OpenAI route `urlIdx=0`;
- `claude-haiku-4-5-20251001`: опубликован, Anthropic route `urlIdx=1`;
- delta к предыдущему inventory: три кандидата и `claude-opus-5`;
- удалённых моделей: `0`.

## Workload-specific результат

| Exact model | Source | Domain | Financial evidence | Checksum |
| --- | --- | --- | --- | --- |
| `gpt-5.4-nano-2026-03-17` | `PENDING_STAGE_DELIVERY` | `PENDING_STAGE_DELIVERY` | `SYNTHETIC_QUALIFIED`, `4/4` | `NOT_QUALIFIED`, `0/3` |
| `models/gemini-2.5-flash-lite` | `PENDING_STAGE_DELIVERY` | `PENDING_STAGE_DELIVERY` | `PROVIDER_ROUTE_UNAVAILABLE` | `PROVIDER_ROUTE_UNAVAILABLE` |
| `claude-haiku-4-5-20251001` | `SYNTHETIC_QUALIFIED` | `SYNTHETIC_QUALIFIED` | `NOT_QUALIFIED`, `2/4` | `SYNTHETIC_QUALIFIED`, `3/3` |

`PENDING_STAGE_DELIVERY` не является provider/model failure. Локальная
policy v1.3 содержит исправленный reasoning control для GPT и регистрацию
Gemini 2.5, но эти изменения не выпускались в stage Function в рамках
research-only повтора.

## Подробности live evidence

### GPT-5.4 Nano

После отключения неподдерживаемого `reasoning_effort=minimal` canonical
financial runner принял все четыре dispositions:

| Fixture | Input tokens | Output tokens | Cost USD | Результат |
| --- | ---: | ---: | ---: | --- |
| typed evidence | 1309 | 110 | 0.000399300 | passed |
| unclassified input | 555 | 57 | 0.000182250 | passed |
| no financial content | 558 | 33 | 0.000152850 | passed |
| unsupported content | 556 | 32 | 0.000151200 | passed |

Financial total: `2978` input, `232` output, `$0.000885600`.

Checksum provider/schema call завершился успешно (`5234` input, `278`
output, `$0.001394300`), но deterministic comparator не принял ни одну из
трёх строк из-за dimension mismatch. Amount, currency, sign, period,
source binding, duplicate/invention и arithmetic aggregate checks были
успешны; validator/comparator не ослаблялись.

### Gemini 2.5 Flash-Lite

Все financial/checksum provider attempts завершились до generation:
`gate2_model_unavailable_http_404`, usage `0`. Read-only server log
подтвердил exact model marker, `404` и provider availability error; markers
schema, reasoning, quota и auth отсутствовали.

Это расхождение между aggregate publication и реальной доступностью
maintained upstream route. Модель не признаётся quality failure, но до
исправления provider mapping/availability не квалифицируется.

### Claude Haiku 4.5

Один canonical bounded income call одновременно прошёл source и domain:
`6402` input, `471` output, fallback `0`, repair `0`, conflicts/uncovered
`0`; ориентировочная стоимость `$0.008757`.

Financial:

- unclassified — passed;
- no-financial — passed;
- typed — provider schema rejected до usable output;
- unsupported — canonical disposition mismatch.

Checksum прошёл `3/3`: `6489` input, `321` output, `$0.008094`.

## Вызовы и стоимость

- provider attempts: `28`;
- successful/billable calls: `10`;
- failed/pre-generation attempts: `18`;
- fallback calls: `0`;
- repair attempts: `0`;
- customer calls: `0`;
- GPT successful cost: `$0.002279900`;
- Haiku financial/checksum successful cost: `$0.012437`;
- Haiku domain estimated cost: `$0.008757`;
- суммарная actual/estimated стоимость: примерно `$0.023473900`.

Ошибочные pre-generation ответы не имели usage и не включены в стоимость.

## Доставленные изменения

- economy policy поднята до `1.3.0`;
- зарегистрирован Gemini 2.5 Flash-Lite;
- GPT-5.4 Nano и Gemini 2.5 переведены на фактически поддержанный
  `REASONING_DISABLED`;
- добавлена нормализация reasoning rejection и model-unavailable `404`;
- financial/checksum runners отдают только safe budget/provider metadata;
- добавлен factory-owned workload qualification registry;
- добавлен bounded exact-model contract runner;
- domain smoke получил явный `--max-repair-attempts 0`;
- production selection и canonical validators не ослаблялись.

Policy hash:
`ce1a2842fe61e325fefdc0adb5a6a78729b8e7cab24988e4059636b3f215ffc3`.

Workload registry hash:
`72392d9d707c7d21e2975f60fb033e1aebecdb6a29e109e227a1d48ccfde55d7`.

## Проверки

- focused qualification/policy/adapter tests: `89 passed`;
- полный service regression suite: `1352 passed`, `20 skipped`;
- Ruff по изменённым Python-модулям и тестам: passed;
- `git diff --check`: passed;
- safe receipt JSON parse и secret-marker scan: passed.

## Решение

Текущий cheapest proven synthetic набор:

- source/domain — Haiku 4.5;
- financial evidence — GPT-5.4 Nano;
- checksum — Haiku 4.5.

Это не production recommendation: Haiku дорог для целевого режима, а
actual-corpus/full-scope evidence отсутствует. Наиболее ценный следующий
шаг — исправить Gemini 2.5 provider route и повторить те же exact contracts.
После доставки policy v1.3 в stage отдельно прогнать GPT и Gemini на
source/domain. Только затем возможны bounded actual-corpus shadow и
отдельное решение о production migration.

## Acceptance

- publication blockers для трёх requested IDs: `REMOVED`;
- synthetic replay: `COMPLETED_WITH_EXPLICIT_GAPS`;
- canonical financial success: `GPT_5_4_NANO_4_OF_4`;
- canonical checksum success: `HAIKU_4_5_3_OF_3`;
- Gemini maintained provider route: `UNAVAILABLE_HTTP_404`;
- production-qualified subjects: `0`;
- production allowlist: `EMPTY`;
- stage mutations этим прогоном: `0`;
- customer/full-scope calls: `0`.
