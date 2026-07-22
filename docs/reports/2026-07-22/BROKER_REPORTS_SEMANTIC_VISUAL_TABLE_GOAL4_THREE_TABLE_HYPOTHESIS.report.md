# Broker Reports — Goal 4: проверка семантического JSON на трёх замороженных таблицах

Дата: 2026-07-22

Статус: `COMPLETED`

Gate scope: шесть Gemini master executions; три OpenAI executions — независимый non-authoritative control

## Результат

Гипотеза на выбранных трёх таблицах подтвердилась. Проблема прежнего контракта была не в неспособности Gemini читать таблицу, а в требовании одновременно восстановить физическую сетку, spans и полное покрытие slots.

После замены model-facing ответа на `description + rows` все шесть ответов Gemini:

- разобрались как строгий JSON без repair;
- сохранили 64 из 64 видимых labels;
- сохранили 52 из 52 amounts буквально;
- сохранили 20 из 20 проверяемых currency/sign/parenthesis literals;
- правильно связали 52 из 52 amounts с их строками;
- сохранили полный порядок labels;
- не добавили ни одного label, amount или marker;
- не потребовали ни одной смысловой ручной коррекции.

Gemini A и B материально идентичны на каждой из трёх таблиц. В таблице 02 различается только краткое `description`; `rows` совпадают.

Это положительный диагностический результат, но не основание для автоматического production-default. Выборка намеренно мала; поддерживаемый продуктовый профиль должен быть проверен в Goal 5 на bounded actual corpus.

## Боль и причина прежних отказов

Старый `broker_reports_canonical_table_v1` просил модель решить две разные задачи:

1. буквально прочитать labels, amounts и markers;
2. построить физическую topology: размеры grid, индексы, spans и покрытие slots.

Вторая задача не нужна для сохранения смысла, но могла обнулить полезный результат первой. Самый ясный пример — таблица 03: старый Gemini-ответ дважды содержательно прочитал все четыре labels и обе суммы, однако считался невалидным из-за uncovered grid slots. В новом контракте оба Gemini runs прошли schema и literal gate со 100% fidelity.

Таблица 02 показывала другой дефект старой абстракции: два Gemini runs по-разному моделировали topology многострочного header. В новом эксперименте смысловые строки обоих runs идентичны. Следовательно, семантический контракт убрал различие, которое не влияло на downstream-смысл.

## Замороженный контур

Новые crops не создавались. Повторно использованы точные PNG из ручного evidence pack:

| Таблица | Crop SHA-256 | Размер | Renderer |
|---|---|---:|---|
| 01 | `3ceb1b9fdc4ab135a93f06df31fc9765e13b7096e2ab918c6bd73de36edc1496` | 1255 × 913 | PyMuPDF 1.26.5, 150 DPI |
| 02 | `3555dee6305a121eab692bc22ea1ccf4b21bd6c544bb6c524bdbc27ffc7fc7e8` | 653 × 478 | PyMuPDF 1.26.5, 150 DPI |
| 03 | `c58acddbd4fe1b458d4141fca46b0d04c37a1fd504521f404399c7c7914039ef` | 711 × 381 | PyMuPDF 1.26.5, 150 DPI |

Замороженные model-facing identities:

- schema: `broker_reports_semantic_table_transcription_v1`;
- schema SHA-256: `71584a0564b2175c4233ec8072873a72054a7a61e8fb81f6fd88e54690dbadc1`;
- prompt: `broker_reports_semantic_table_transcription_prompt_v1`;
- prompt SHA-256: `9b54abe91313a87aacfe756ccec662b0c669188919b5db0bd0aab3bcee58dee2`;
- Gemini: `models/gemini-3.5-flash`;
- OpenAI control: `gpt-5.4-mini-2026-03-17`.

Существующие provider factory, Gemini/OpenAI adapters, native transports и `Gate2OpenWebUIProviderConnectionResolver` не изменялись относительно принятого Goal 3 revision `5bf2392278830a6a51aeab9512f43c0efac2276f`.

## Измерения

| Provider scope | JSON | Labels | Amounts | Markers | Binding | Hallucinations | Manual corrections |
|---|---:|---:|---:|---:|---:|---:|---:|
| Gemini, 6 runs | 6/6 | 64/64 | 52/52 | 20/20 | 52/52 | 0 | 0 |
| OpenAI control, 3 runs | 3/3 | 31/32 | 26/26 | 10/10 | 26/26 | 0 | 4 |

OpenAI полностью совпал с source-only reference на таблицах 01 и 03. На таблице 02 он:

- не включил один видимый header;
- трижды вернул пустую строку вместо требуемого `null`;
- сохранил все шесть amounts, все три currency markers и все шесть row/value bindings.

OpenAI control не участвовал в выборе или ремонте Gemini master result и не влиял на обязательный gate.

## Важная поправка scorer

Первый диагностический подсчёт ошибочно требовал, чтобы currency marker и amount находились в разных cells. Gemini последовательно использовал минимальную двухколоночную форму и возвращал marker вместе с amount в одной строке. Это разрешено самим контрактом: модель должна использовать минимум логических колонок, сохраняя исходные символы буквально.

Scorer был исправлен общим правилом: для измерения literal fidelity формы `['$', '1,000']` и `['$ 1,000']` считаются эквивалентными наборами source-visible literals. Правило:

- применяется только в офлайн-оценке;
- не меняет raw или parsed provider JSON;
- не меняет prompt или model-facing schema;
- не выполняет смысловую нормализацию суммы;
- не запускало провайдеров повторно.

После исправления scorer все raw responses, adapter responses, execution records и crop bytes были повторно сверены по SHA-256. Изменились только score, receipt и отчёт.

## Исполнение и anti-drift

- Gemini executions: 6;
- OpenAI control executions: 3;
- attempt number каждого execution: 1;
- hidden retries: 0;
- provider failover/switch: 0;
- provider merge/repair: 0;
- whole-document uploads: 0;
- source reference была недоступна провайдерам;
- geometry, spans и physical coverage не использовались как метрики;
- customer acceptance не заявляется.

Все девять provider executions завершились terminal status `completed`. Наблюдаемый transport latency находился в диапазоне 2.936–5.681 секунды.

## Evidence

Приватный операторский пакет находится в:

`docs/reports/2026-07-22/BROKER_REPORTS_SEMANTIC_THREE_TABLE_HYPOTHESIS_EVIDENCE/`

Он содержит 62 файла: три byte-identical crops, source-only references, девять exact raw JSON responses, parsed responses, native adapter responses, execution metadata, per-response scores, repeatability receipts и terminal evidence.

Пакет намеренно исключён из Git, поскольку содержит исходные табличные значения и private provider evidence. Безопасная привязка:

- safe receipt internal hash: `0a3f7aab21e7ca6e12e356377a3cbe1a0fafa7e1a4eb14ae8ec5b4f4003b6d1f`;
- safe receipt file SHA-256: `f6dc73af2cb8e56283baa9af5e04eaf66adc072d295cb93630a5d364eeb240a7`;
- private terminal file SHA-256: `9599d8998b38f52cf660e8800f6487aa73552a7d2802ad144ab78779c084a699`;
- source-only reference SHA-256: `66096a7f0efa3e80c7d887e643e873531e39451d48f10dbd933fa03737b8b1ca`.

## Вывод

На этих трёх замороженных сложных таблицах облегчённый JSON сохранил объектное представление и одновременно достиг той смысловой точности, ради которой рассматривался Markdown. Код больше не требует от VLM физической реконструкции таблицы, а модель стабильно возвращает labels и values в правильных строках.

Здравое зерно решения подтверждено: JSON не нужно выбрасывать — нужно было поднять его на правильный уровень абстракции. Следующий узкий шаг — проверить тот же неизменный контракт на bounded actual corpus и явно отделить поддерживаемые layouts от fail-closed layouts.

## Terminal acceptance

```text
FROZEN_TABLES: EXACTLY_THREE
CROP_BYTES_CHANGED: ZERO
GEMINI_EXECUTIONS: SIX
OPENAI_CONTROL_EXECUTIONS: THREE
LABEL_COMPLETENESS: 100_PERCENT (Gemini master gate)
AMOUNT_FIDELITY: 100_PERCENT (Gemini master gate)
ROW_VALUE_BINDING: 100_PERCENT (Gemini master gate)
HALLUCINATED_LABELS_AND_AMOUNTS: ZERO
GEMINI_MATERIAL_REPEATABILITY: PASSED
GEOMETRIC_FAILURES_AS_METRIC: ZERO
GOAL_4_THREE_TABLE_HYPOTHESIS: COMPLETED
```
