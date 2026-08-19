# G5.88 — KISS Table Semantic Contract Qualification

Дата: 2026-08-17
Режим: inactive qualification-only microstand
Terminal: `KISS_TABLE_MARKDOWN_TO_JSON_REJECTED`
Recommendation: `REJECT`

## Решение по гипотезе

Простой контракт технически хорош: он даёт exact exhaustive row set,
нулевые invented/cross-row refs, нулевые model-created literals и
убирает второй semantic call. Но он не решает исходную боль с
нужной semantic/source fidelity:

- из 105 explicit-tax credit-only rows 80 снова отнесены к
  `DIVIDEND_INCOME`; только 25 корректно fail-closed как `UNMAPPED`;
- из 113 source-true existing tax-withholding controls пройдено 110;
  три stock-dividend tax debit rows ушли в `UNMAPPED`;
- untouched holdout прошёл 6/7: все шесть detail fee rows найдены,
  но source total `Всего` получил `NONE` вместо `COMMISSION_TOTAL`.

Это semantic defects замороженного контракта, а не validator,
transport или qualification-harness failures. Prompt, schema, model и semantic enum
после просмотра development result не менялись.

## Source-truth requalification

Исходный frozen control ошибочно ожидал `TAX_WITHHELD` для всех 105
строк. Offline diagnosis без provider calls доказал, что все они
credit-only и явно содержат tax meaning; опубликованный dictionary
прямо запрещает `TAX_WITHHELD` для refund. Поэтом безопасный исход
текущей ontology — `UNMAPPED`, но не `DIVIDEND_INCOME`.

Ещё один frozen baseline control одновременно ожидал на одной строке
`DIVIDEND_INCOME` и `TAX_WITHHELD`. Source row — обычный cash dividend;
tax expectation классифицирован как
`FROZEN_ORACLE_BASELINE_FALSE_POSITIVE` и исключён из скоринга tax controls.
Первоначальный frozen score сохранён неизменным; requalification
записан автономным receipt.

## Development и holdout

| Control | Result |
| --- | ---: |
| explicit-tax credit reversals -> safe `UNMAPPED` | 25/105 |
| explicit-tax credit reversals -> wrong `DIVIDEND_INCOME` | 80/105 |
| true dividends | 25/25 |
| existing source-true tax withholding | 110/113 |
| structural `NONE` | 12/12 |
| purchase/disposal/commission/transaction-charge controls | 4/4 |
| untouched other-layout fee holdout | 6/7 |
| exact input/output row sets | 8/8 table calls |
| invented row/cell refs | 0 |
| cross-row role refs | 0 |
| rejected role bindings | 0 |
| semantic retries / best-of-N / prompt variants | 0 / 0 / 0 |
| VLM calls | 0 |

Development: 7 table calls, 7 raw responses persisted before validation, 7
validated outcomes. Holdout: exactly 1 pre-frozen call after terminal development,
raw persisted before validation. Store tree before/after remained byte-identical.

## Comparison with current two-pass Gate 3

Сравнение на тех же семи development chunks:

| Measure | Current two-pass | KISS one-pass | Change |
| --- | ---: | ---: | ---: |
| provider calls | 14 | 7 | -50.0% |
| input tokens | 129,103 | 59,138 | -54.2% |
| output tokens | 69,712 | 45,703 | -34.4% |
| provider total tokens | 345,936 | 163,265 | -52.8% |
| summed provider duration | 913,015 ms | 462,579 ms | -49.3% |

KISS объективно проще: один provider responsibility, один response,
нет semantic discovery targets, нет role-pass, exact exhaustive validation.
Он уменьшил исходный systematic conflict с 105 до 80 строк, но
80/105 ошибок на главном pain corpus не являются приемлемой
semantic fidelity. Стоимость и простота не компенсируют этот
дефект.

## Deterministic runtime / persistence readiness

Форма V2 payload проходит current persistence только через
compatibility projection, который записывает legacy pass-1 и role-pass
instruction identities. Все 8 payloads с этой projection проходят
contract validator; честный KISS instruction identity тем же validator
отклоняется.

Второй gap — literal granularity. Модель не возвращает `exact_text`, а
только cell ref. Из 1,104 bound roles ни один не имеет `exact_text`; 458
asset/currency bindings указывают на составную description cell.
Current Gate 4 resolver в этом случае берёт всю cell и сохраняет её
целиком как asset/currency role value. Следовательно,
`DIRECT_RUNTIME_MATERIALIZATION_PROVEN=false`: есть формальная
projection, но нет direct persistence path с честным provenance и
достаточной literal granularity.

## Verification and safety

- focused contract/validator tests: `13 passed`;
- focused plus adjacent Gate 3/persistence/Gate 4 tests: `99 passed`;
- Ruff: passed;
- Python compile: passed;
- provider calls: 7 development + 1 untouched holdout;
- semantic retries: 0;
- private raw response written before local validation for every call;
- deterministic store tree: unchanged after both phases;
- production activation, Gate 2/parser, SQL, Gate 4/5 product execution: zero;
- product runtime and generated bundles: unchanged.

Private exact inputs, source rows, model outputs and diagnostics remain outside Git
in `broker-reports-g5.88-20260817-v1`. Git contains only inactive proof tooling,
tests and safe aggregate reports.

## KISS check and terminal

Здравое зерно сохранилось: backend-owned exhaustive rows/cells и
one-pass role-to-cell JSON значительно сокращают calls, tokens, latency и
validator surface. Но semantic hypothesis в точно замороженном виде
отклонена: она не дала reliability на known pain corpus, не прошла
untouched holdout и не доказала direct current-runtime readiness.

`RECOMMENDATION=REJECT`

Новый table-specific Gate 3 по этой ветке не строить. Production path
не менять.

Safe receipt: `BROKER_REPORTS_KISS_TABLE_SEMANTIC_QUALIFICATION_G5_88.safe.json`.
