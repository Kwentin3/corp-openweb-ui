# G5.71 — Metadata Semantic Adaptation Architecture Search

Дата: 2026-08-16

Статус: `CLOSED_NO_MINIMAL_RELIABLE_ADAPTER_FOUND`

## Terminal

```text
MINIMAL_RELIABLE_METADATA_ADAPTER_NOT_FOUND
HYPOTHESIS_SPACE_EXHAUSTED_WITHIN_KISS_BOUNDARY
EXACT_REMAINING_FAILURE_CLASSES_LOCALIZED
NO_OVERENGINEERED_FALLBACK_ADDED
FINANCIAL_GENERALIZATION_PRESERVED
```

## Короткий вывод

В пределах KISS-границы не найден metadata adapter, который одновременно исправляет известную semantic-ошибку Case F и не ухудшает controls B/C. Поэтому решение не замораживалось, untouched holdout не запускался, product path не менялся.

Сильная модель и разделение extraction/classification дали полезные частичные результаты, но не общий надёжный механизм. Следующий более сложный вариант `extract → verify` сознательно не строился: после провала простого two-stage пути он уже выходит за разрешённую сложность текущего Goal.

## Freeze и границы

- существующий contract `1.0.0`: 11 fact types, новых полей `0`;
- development controls: Case B, Case F, Case C;
- input: frozen visual crops, без flattened Canonical text;
- broker hints, regex semantics, prompt blacklist и fixed-layout rules: `0`;
- retries, failover, best-of-N, voting, judge, output selection и manual repair: `0`;
- product activation и следующий Goal: `0`.

## Проверенные гипотезы

| Гипотеза | Проверка | Результат | Вердикт |
|---|---|---|---|
| H1 — плохой/неоднозначный crop | визуальный аудит Case F и frozen G5.70 evidence | источник однозначен, wrong role воспроизводился 4/4 | refuted |
| H2 — неоднозначный contract | аудит frozen определения `ACCOUNT_IDENTIFIER` | contract требует явно названный broker/investment account и не разрешает замену роли | refuted |
| H3 — positive-only schema принуждает выбрать ближайшую роль | один общий Gemini contract с явным terminal `NO_CONTRACT_MATCH`, 3 single-shot на B/F/C | B 3/3 exact; F 0/3, wrong role 3/3; C 0/3 | refuted |
| H4 — не хватает capability текущей модели | тот же visual input и frozen contract через существующий OpenAI VLM owner, 3 single-shot на B/F/C | F 3/3 exact, но B 2/3 и C 2/3: появились boundary/unsupported-role ошибки | refuted: general reliability не доказана |
| H5 — joint extraction/classification перегружает один call | Stage 1 transcribes source assertions, Stage 2 классифицирует их; один диагностический run на B/F/C | F и C exact, но B потерял 3 assertions и одну value boundary | refuted: general reliability не доказана |

H6 `extract → verify` не реализовывался. Это был бы третий semantic call/новый verification owner после уже неудачного two-stage кандидата, то есть overengineered fallback относительно текущего finish contract.

## Измерения

### H3 — explicit no-match, Gemini Flash

- provider submissions: `9`;
- Case B: `3/3 exact`;
- Case F: `0/3 exact`, wrong role `3/3`;
- Case C: `0/3 exact`;
- totals: correct `24`, missed `3`, wrong role `3`, wrong boundary `3`;
- usage: `18 966` tokens; wall duration: `25 551 ms`.

Явный отрицательный исход не изменил решение модели на Case F. Значит, ошибка не объясняется только positive-only output schema.

### H4 — более сильная модель через существующий VLM owner

Первые две серии по `9` submissions завершились до model output и не использовались как semantic measurements:

1. OpenAI strict schema отверг unsupported `uniqueItems`;
2. после schema projection модель отвергла unsupported `temperature`.

В существующем provider owner оставлены две общие transport-compatibility поправки: wire-schema projection удаляет только `uniqueItems`, сохраняя hash canonical/adapted schema и число transforms; optional `temperature` не отправляется. Canonical metadata schema не менялась. После этого отдельный технический replay дал `9` валидных single-shot outputs:

- Case B: `2/3 exact`, один wrong value boundary;
- Case F: `3/3 exact`;
- Case C: `2/3 exact`, один unsupported semantic role;
- totals frozen evaluator: correct `26`, missed `1`, wrong boundary `1`, invented `1`;
- usage: `11 210` tokens; wall duration: `60 979 ms`.

При визуальной перепроверке Case C спорный literal оказался частично видим в crop, но требуемая semantic role там явно не утверждалась. Source truth под output не менялась; verdict кандидата от этого не зависит.

### H5 — source assertions, затем semantic classification

- calls per document: `2`;
- provider submissions: `6`;
- Case B: correct `2`, missed `3`, wrong boundary `1`;
- Case F: exact;
- Case C: exact;
- usage: `8 468` tokens; wall duration: `22 233 ms`.

Разделение стадий устранило ошибку Case F в одном диагностическом проходе, но потеряло source assertions и границу значения Case B. Повторы не запускались, потому что кандидат уже нарушил control invariant.

## Локализованные классы отказа

1. Gemini Flash не умеет надёжно abstain для визуально явного идентификатора вне contract даже при общем `NO_CONTRACT_MATCH`.
2. Более сильная one-call модель исправляет Case F, но остаётся стохастичной по value boundary и unsupported semantic roles на controls.
3. Простой two-stage путь способен исправить Case F, но transcription stage теряет отдельные visual assertions, а classifier сокращает value boundary; стоимость — два calls на документ.
4. Frozen human transcription и полностью видимый crop могут расходиться по наличию literal. Это отдельная audit/oracle дисциплина; она не дала оснований переписать truth или принять неустойчивый adapter.

## Holdout и архитектурное решение

Freeze-worthy candidate отсутствует: ни H3, ни H4, ни H5 не прошли все development controls. Поэтому untouched holdout корректно помечен `NOT_EXECUTED`, а не использован для дополнительного поиска удачного результата.

Новый metadata framework, verifier, broker vocabulary, semantic dictionary и product integration не добавлены. Proof harnesses остаются изолированными. Единственное maintained изменение — общая OpenAI provider compatibility с тестами и exact generated-bundle parity.

## Проверки

- focused architecture/metadata regression: `169 passed`;
- после финальной bundle-синхронизации: `59 passed` на provider, G5.71 и architecture parity;
- Ruff: passed;
- compileall: passed;
- generated bundle matches maintained source;
- financial replay через существующий factory: Holdout A `39`, Holdout B `129`, exact frozen equality `true`, source stores unchanged `true`.

Private crops, source documents, frozen truths, exact model inputs, raw outputs, journals и transport failures сохранены во внешнем private evidence bundle. В Git-документах находятся только safe aggregates. Commit, push и PR не выполнялись.
