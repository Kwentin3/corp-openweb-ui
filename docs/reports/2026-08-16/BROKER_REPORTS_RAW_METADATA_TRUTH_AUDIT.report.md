# Raw Evidence Audit Pack for Metadata Truth Verification

Дата: 2026-08-16

Статус: `AUDIT_COMPLETE_TWO_DIVERGENCE_OWNERS_LOCALIZED`

## Итог

В трёх representative cases база истины проверена от raw PDF до validator. Ошибка не одна и та же во всех случаях:

- известный `CLIENT_CODE -> ACCOUNT_IDENTIFIER` — `LLM_SEMANTIC_ERROR`;
- clean control — `NO_DIVERGENCE`;
- пограничный двухколоночный metadata block — `CANONICAL_ERROR` на уровне structural pairing, без потери literals.

В выбранных случаях не обнаружены `RAW_AMBIGUOUS`, `ORACLE_ERROR`, `VALIDATOR_ERROR` или `MIXED`.

## Case-by-case

| Case | Что видит человек | Что считает oracle | Что увидела/сказала LLM | Что сказал validator | Где ошибка |
|---|---|---|---|---|---|
| F: known failure | Явная строка, подписанная как client code | Значение не является account identifier | Получила точную label cell, соседнюю value cell и их строку; объявила `ACCOUNT_IDENTIFIER` | Focused fact структурно принят как `SAME_TABLE_ROW`; whole proposal отклонён из-за другого relation failure | `LLM_SEMANTIC_ERROR` |
| C: clean success | Явная line с personal-account label и value | `ACCOUNT_IDENTIFIER` | Увидела ту же line и объявила `ACCOUNT_IDENTIFIER` | Все `9/9` assertions приняты | `NO_DIVERGENCE` |
| B: boundary | Три ясные пары left-label/right-value | Period, party и agreement identifier | Получила все шесть literals и восстановила три правильных типа | Все три пары отклонены: direct structural relation отсутствует | `CANONICAL_ERROR` |

## Почему boundary case относится к Canonical

На raw page labels и значения выровнены в двух колонках. Canonical сохраняет каждый literal, но упаковывает labels как `content.text.lines[1..3]`, а соответствующие values как `content.text.lines[134..136]`. Связь между колонками исчезает.

LLM семантически сопоставила пары правильно. Validator не имеет доказанной direct relation и корректно отклонил их fail-closed. Поэтому это не semantic ошибка LLM и не ошибка validator. Старый `canonical_loss_count = 0` означал отсутствие literal loss; он не доказывал сохранность structural pairing.

## Evidence bundle

Приватный bundle `raw-metadata-truth-audit-2026-08-16` содержит для каждого case:

- exact source PDF, full-page PNG и отдельные crops;
- exact Canonical node, addresses, context package и binding registry;
- visual oracle с authority `VISUAL_HUMAN_TRUTH`;
- instruction `1.2.0`, exact model-visible request и response schema;
- raw provider response и raw structured output;
- whole-proposal и isolated single-fact validator decisions;
- divergence receipt и компактный private README.

Manifest содержит SHA-256 для `64` evidence-файлов без самого manifest и служебного Python cache. Все source PDFs совпали с frozen SHA-256; input artifacts и source stores не изменились.

Model-visible request SHA-256:

- Case F: `2d541f11a4e8eb9193980c8f4de4bacb483584a95d5dbd7d11526bc239278033`;
- Case C: `c84f02ccb95177634109de8990550a3f2c12b9de5572ef6ad2bc911c4c790048`;
- Case B: `2d4110c7f8edbe236c6d5b48a289c30735117ec39eff4ad391bdaf154b30f1ad`.

## Scope stop

Audit использует один общий frozen G5.68 replay, чтобы не смешивать разные executions. Provider calls during audit: `0`.

Pipeline, Canonical, oracle, prompt, instruction, schema, validator, regex и broker-specific rules не менялись. Product activation, tuning, commit и push не выполнялись. Raw customer-bearing evidence не добавлен в Git.
