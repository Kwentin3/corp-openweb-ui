# Broker Reports — Gate 2 v4 Goal 6: checksum closure

Дата: `2026-07-25`

## Итог

`GOAL_6_CHECKSUM_CLOSURE: COMPLETED_WITH_EXPLICIT_GAP`

Primary checksum-модель `claude-haiku-4-5-20251001` формально
квалифицирована на текущем pinned bundle:
`HAIKU_CHECKSUM: QUALIFIED_3_OF_3`.

Текущая повторная диагностика `gpt-5.4-nano-2026-03-17` не состоялась:
exact model отсутствует в live `/api/models`.
Терминал: `NANO_CHECKSUM: BLOCKED_MODEL_NOT_PUBLISHED`.
Это inventory blocker, а не новый вывод о качестве модели.

## Граница

- repository revision до Goal 6:
  `96177ca29f2ef0879bd5f04ad525d66fe7f35c2a`;
- branch: `codex/broker-reports-gate2-v4-goal6-checksum-closure`;
- delivery PR: `PENDING`;
- synthetic non-customer fixture only;
- customer calls: `0`;
- provider calls: Haiku `1`, Nano `0`;
- fallback calls: `0`;
- repair attempts: `0`;
- stage mutations: `0`;
- raw provider output в repository не записывался.

Модель видела только
`broker_reports_gate2_financial_context_v1`.
PDF, crops, Gate 1 payload, sealed expected values, клиентская методология,
Gate 3 и tax skills в model context не передавались.

## Pinned identity

- model: `claude-haiku-4-5-20251001`;
- provider profile: `anthropic_claude`;
- qualification authorization:
  `45d955c6ef0d4270cbb82b587bcadb6f7adf2faf55e1453fb5d25ccd507ce610`;
- input contract:
  `broker_reports_gate2_financial_context_v1`;
- output contract:
  `broker_reports_gate2_financial_context_checksum_v1`;
- prompt: `gate2_financial_context_checksum_prompt_v1`;
- adapter projection:
  `gate2_anthropic_structural_projection_v1`;
- canonical validator:
  `sha256:561caa46ca51fc538a849df7eff6e2a97419c1e3fb700c7e90d055a258b0bcb9`;
- provider route:
  `openwebui_0.9.6_maintained_route_2026-07-24`;
- canonical schema:
  `8044c7eef08baa76eeb4ddbb368ed857da1f88e67adda1d1994f4140cb733a16`;
- adapted schema:
  `7bf4e1e197458ee88d9de2c6dddc5fdcec8238c364d13992e7aed390d87fec0b`.

## Haiku actual result

| Проверка | Результат |
| --- | ---: |
| metrics reconstructed | `3/3` |
| amount/currency/sign/period | `3/3` |
| source binding | `3/3` |
| semantic visual table metrics | `3/3` |
| arithmetic reconciliation | `1/1` |
| duplicate rows | `0` |
| invented metrics | `0` |

Provider response завершился `end_turn` через strict JSON schema.
Токены: input `6489`, output `321`, cached input `0`.
Фактическая стоимость: `$0.008094000`.
Fallback и repair не использовались.

Safe actual receipt SHA-256:
`ac8eb4f89989d23545758102b0b9a0b33fb34870a5050e9669e8f38af353bfaa`.

## Nano diagnosis

Текущий preflight четырежды, включая финальную проверку перед отчётом,
вернул одинаковый fail-closed результат:

- published models: `34`;
- exact Nano published: `false`;
- failure code: `stage_models_endpoint_model_absent`;
- provider calls: `0`.

Историческая проверка от `2026-07-24` не заменяет current actual run.
Она показала успешный provider/schema вызов, после которого strict comparator
отклонил `3/3` строки из-за dimension mismatch. Amount, currency, sign,
period, source binding, duplicate/invention и aggregate arithmetic checks
тогда были успешны; comparator не ослаблялся.

Следовательно, текущий статус Nano — `BLOCKED_MODEL_NOT_PUBLISHED`, а
исторический статус остаётся `NOT_QUALIFIED_DIMENSION_MISMATCH`.
Prompt, transport и comparator в Goal 6 не изменялись.

## Проверки

- focused checksum/policy/provider suite: `67 passed in 1.28s`;
- full Broker Reports suite:
  `1400 passed, 20 skipped, 5 warnings in 98.47s`;
- full suite exit code: `0`;
- JSON safe receipt parse: passed;
- fallback used: `false`;
- repair attempts: `0`;
- comparator weakening: `0`.

## Решение

Haiku 4.5 закреплён как квалифицированный primary для checksum на точной
связке model/provider/contract/prompt/adapter/validator/route выше.
Отсутствующий Nano не блокирует primary checksum, но остаётся явным
неактивным secondary gap. Он не может использоваться до повторной публикации
exact ID и нового current qualification run.

Без квалифицированной source/domain-модели переход к bounded actual corpus
не разрешён: результаты Goal 3c для обеих Gemini — `NOT_QUALIFIED`.
Поэтому Goal 6 не является полным закрытием Gate 2 и не разрешает подменять
source/domain-модель другим, не прошедшим qualification receipt.

Repository-safe receipt:
[BROKER_REPORTS_GATE2_V4_GOAL6_CHECKSUM_CLOSURE.receipt.safe.json](./BROKER_REPORTS_GATE2_V4_GOAL6_CHECKSUM_CLOSURE.receipt.safe.json).

