# Broker Reports G5.73 — Case C Passport/Citizenship Source-Truth Audit

Дата: 2026-08-16
Режим: audit-only
Product activation: `0`

## Итог

Выбран ровно один verdict:

```text
CASE_C_GEMINI_CITIZENSHIP_SEMANTIC_ERROR_PROVEN
```

И обязательный terminal:

```text
G5_72_CLASSIFIER_RESULT_REQUALIFIED_WITHOUT_MODEL_RERUN
```

## Что установлено по source

Исходная страница снимает визуальную неопределённость: спорная строка читается полностью. Она оформлена как название типа документа и далее перечисляет реквизиты документа.

В source нет отдельного поля или высказывания, которое присваивает человеку роль `PERSON_CITIZENSHIP`. По frozen contract одного типа документа недостаточно: превращение признака документа в гражданство человека было бы выводом одной semantic role из другой.

Следствие:

- oracle gap не доказан;
- source ambiguity не доказана;
- текущий Case C oracle не менялся;
- предложенный Gemini `PERSON_CITIZENSHIP` остаётся extra semantic fact.

## Проверка Markdown отдельно

Frozen Markdown честно передал входной G5.72 crop:

| Проверка | Результат |
|---|---:|
| Потерянный видимый текст | 0 |
| Добавленный текст | 0 |
| Semantic rewrite | 0 |
| Изменённые границы | 0 |

Полная исходная страница содержит продолжение строки правее границы frozen crop. Markdown его не добавлял, поэтому это не transcription loss относительно фактического input G5.72.

Stage 1 G5.72 остаётся квалифицированным.

## Пересчёт G5.72 на frozen outputs

Новых вызовов моделей не было.

| Arm | Case B | Case F | Case C | Итог B/F/C |
|---|---:|---:|---:|---:|
| Gemini | exact | exact | не exact: 1 extra citizenship | 2/3 exact |
| Strong | не exact | exact | exact | 2/3 exact |

Результат G5.72 по существу не изменился: ни один classifier не прошёл все три development cases одним clean run. Repeatability и holdout по-прежнему не разрешены этим результатом.

## Evidence routing

Приватный bundle с исходной страницей, крупным crop, source PDF, frozen Markdown, полными raw classification results обеих моделей и текущим oracle находится вне Git:

```text
../corp-openweb-ui-private-evidence/g573-case-c-citizenship-audit-2026-08-16/
```

В репозиторий помещён только безопасный агрегированный отчёт без персональных значений.

## Scope controls

| Контроль | Значение |
|---|---:|
| Provider calls | 0 |
| Model reruns | 0 |
| Prompt changes | 0 |
| Contract changes | 0 |
| Pipeline changes | 0 |
| Oracle changes | 0 |
| Product activation | 0 |
| Financial runs | 0 |
| Financial code changes | 0 |

## KISS

Выполнена одна проверка: source → human role qualification → re-score frozen outputs. Новых правил паспорта, OCR, prompt tuning, model calls или product-кода не добавлено.
