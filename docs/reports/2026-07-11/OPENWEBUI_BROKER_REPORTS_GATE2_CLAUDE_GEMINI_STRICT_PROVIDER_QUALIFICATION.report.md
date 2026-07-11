# Broker Reports Gate 2: проверка Claude и Gemini через provider factory

Дата: 2026-07-11

Среда: live OpenWebUI
Итог: Claude не прошёл строгий контракт; Gemini не представлен в live-каталоге моделей. Расширенные acceptance-прогоны не запускались.

## Простыми словами

Мы проверяли не то, способен ли Claude вообще вернуть JSON, а способен ли он принять ровно тот строгий динамический JSON Schema-контракт, который нужен Gate 2 для безопасного извлечения фактов.

`claude-sonnet-5` этот контракт отверг. Система не стала упрощать schema, переключаться на обычный JSON или пробовать другого провайдера. Факты не созданы.

Gemini проверить нельзя: `/api/models` в текущем live OpenWebUI не возвращает ни одной Gemini-модели. Выдумывать model id или обращаться к соединению в обход OpenWebUI не стали.

## Live-каталог

Для Claude обнаружены:

- `claude-sonnet-5`;
- `claude-sonnet-4-6`.

Для Gemini обнаружено: `0` моделей.

Квалификационная попытка выполнялась один раз для provider profile `anthropic_claude` с model id `claude-sonnet-5`.

## Точный Claude-canary

Параметры:

- domain: `cash_movement`;
- candidate binding: включён;
- `response_format.type`: `json_schema`;
- `json_schema.strict`: `true`;
- fallback: запрещён;
- repair: `0`;
- provider profile: `anthropic_claude`;
- model id: `claude-sonnet-5`;
- synthetic case: `synthetic_gate2_domain_20260711221515`;
- provider schema hash: `2fcf8ef920e7aceae6fef898d4a4c375db7ab0cd73416bd9e19f76d57bff6da4`.

Терминальный результат:

- `model_call_status=failed`;
- `error_code=gate2_model_schema_response_format_rejected`;
- `fallback_used=false`;
- accepted packages: `0`;
- rejected packages: `1`;
- accepted facts: `0`;
- terminal status: `completed_with_rejections`;
- Knowledge/RAG не использовались;
- synthetic case очищен, persisted records помечены `purged`.

Попытка произошла до добавления schema hashes в сохраняемый `safe_metadata`. Поэтому package-specific hash из уже очищенного private payload не восстанавливался и в отчёте не выдумывается. После рефакторинга `model_id`, provider profile, provider/package schema hashes и prompt hash сохраняются в safe audit каждой следующей попытки.

## Gemini

Статус: `not_run`.

Blocker: `gate2_provider_model_not_exposed_in_live_catalog`.

Это не доказательство несовместимости Gemini со schema. Это доказательство отсутствия доступного Gemini model id в проверенной live-конфигурации OpenWebUI на момент прогона.

## Изменения в provider factory

- Добавлен явный `provider_qualification` run mode.
- Capability probe разрешён только профилям `approved` или `probe_required`.
- Профили `unsupported` больше нельзя протащить через probe-флаг.
- Probe-флаг принимается только вместе с `run_mode=provider_qualification`.
- Обычный customer/synthetic путь по-прежнему fail-closed.
- Для служебного qualification-ответа добавлен безопасный blocker code без raw provider payload и без данных документа.
- В raw attempt audit добавлены provider profile, model id, qualification flag, provider/package schema hashes и prompt hash.
- Provider-specific веток в Pipe и smoke-скрипте не добавлено: вызов остаётся factory-first.

## Registry после проверки

| Profile | Статус | Основание |
|---|---|---|
| `openai_gpt` | `approved` | ранее принятый строгий контракт; последний live-вызов был quota-blocked, не schema-rejected |
| `anthropic_claude` | `unsupported` | live `claude-sonnet-5` отверг точный strict dynamic JSON Schema contract |
| `google_gemini` | `probe_required` | Gemini model id отсутствует в live-каталоге; provider call не выполнялся |
| `deepseek` | `unsupported` | strict final JSON Schema не одобрен |
| `zai_glm` | `unsupported` | strict final JSON Schema не одобрен |
| `alibaba_qwen` | `unsupported` | strict final JSON Schema не одобрен |

Статус Claude намеренно консервативен для всего текущего profile route. Если появится другой проверяемый Anthropic connection/adapter contract, его следует квалифицировать отдельным profile id или отдельным доказанным registry revision, а не автоматически переиспользовать этот результат.

## Acceptance gates родительской задачи

По условию GOAL следующие гейты разрешалось продолжать только после успешного canary хотя бы одного нового провайдера. Успешного canary нет, поэтому не запускались:

- расширенный synthetic cash proof;
- real native cash proof;
- real PDF cash proof;
- второй домен `position_snapshot`;
- all-domain synthetic proof.

Это контролируемая остановка, а не незавершённый успешный тест.

Предыдущий результат родительской задачи остаётся без переинтерпретации: provider factory, candidate binding, bounded runtime, fail-closed поведение и live deployment доказаны; accepted live facts через нового провайдера не доказаны. GPT live acceptance ранее был заблокирован исчерпанной API quota.

## Проверки и deployment

- `python -m unittest discover -s tests -p "test_*.py"`: `199 passed`;
- bundle rebuild: passed;
- Closed World bundle tests: passed;
- все три live Functions обновлены и прочитаны обратно;
- Gate 1 hash parity: `eeef05f0cf4d24a4f05a463bac951a4c47de621a2e3028bc7925ca8e586270ed`;
- Gate 2 source hash parity: `b0c1f75587319d5878bf18b702025be9d5474dd20dce033bc4bed55600425822`;
- Gate 2 domain hash parity: `7c7a2fcd0d50883a9477b51a20cfa5d747e5a404faf39c1f08c48c049722d463`;
- 12 managed Prompts обновлены тем же содержимым и прошли readback/hash validation.

## Финальный вердикт

Рефакторинг квалификационного пути завершён и развёрнут. Claude и Gemini не объявлены рабочими без доказательства:

- Claude: точный strict schema contract отклонён;
- Gemini: live model connection не виден;
- fallback и provider bypass отсутствуют;
- неподтверждённые facts не созданы;
- широкие гейты корректно остановлены.
