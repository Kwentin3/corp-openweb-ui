#!/usr/bin/env python3
"""Render the canonical dual-VLM table research report from sealed scores."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_DIR = SCRIPT_PATH.parent
sys.path.insert(0, str(SCRIPT_DIR))

from pdf_dual_vlm_canonical_table_contracts import (  # noqa: E402
    SCORE_SCHEMA_VERSION,
    canonical_json_bytes,
)


class CanonicalTableReportError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scores", required=True)
    parser.add_argument("--scores-seal", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    return run(args)


def run(args: argparse.Namespace) -> int:
    scores_path = Path(args.scores).resolve()
    scores = _json(scores_path)
    seal = _json(Path(args.scores_seal).resolve())
    score_sha = hashlib.sha256(scores_path.read_bytes()).hexdigest()
    if (
        scores.get("schema_version") != SCORE_SCHEMA_VERSION
        or seal.get("scores_sha256") != score_sha
        or seal.get("scores_size_bytes") != scores_path.stat().st_size
    ):
        raise CanonicalTableReportError("canonical_table_report_scores_seal_invalid")
    if scores.get("terminal_verified_before_reference_access") is not True:
        raise CanonicalTableReportError(
            "canonical_table_report_reference_boundary_invalid"
        )

    text = _render(scores=scores, scores_sha256=score_sha)
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(text.encode("utf-8-sig"))
    print(
        json.dumps(
            {
                "report": str(output),
                "report_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                "scores_sha256": score_sha,
                "verdict": scores["verdict"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def _render(*, scores: dict[str, Any], scores_sha256: str) -> str:
    controlled = scores["controlled_metrics"]
    providers = controlled["providers"]
    dual = controlled["dual_provider"]
    real = scores["real_pdf_consensus_diagnostics"]
    crop = scores["crop_policy"]
    crop_diagnostic = crop["historical_unreviewed_bbox_containment_diagnostic"]
    examples = scores["representative_examples"]
    structural = real["disagreement_classes"]
    repeatability = scores.get("repeatability")
    if not isinstance(repeatability, dict):
        raise CanonicalTableReportError("canonical_table_report_repeatability_missing")
    repeat_gemini = repeatability["providers"]["gemini"]
    repeat_openai = repeatability["providers"]["openai"]
    current_openai_failures = real["contract_failure_tables"]["openai"]
    lines = [
        "# PDF table: 8% padding и dual-VLM canonical JSON",
        "",
        "Дата: 2026-07-17",
        "",
        "## Короткий вывод",
        "",
        "8% добавлены как единое правило для всех таблиц: от исходной рамки детектора "
        "отступаем на 8% ширины страницы слева и справа и на 8% высоты страницы сверху "
        "и снизу, затем ограничиваем результат границами страницы. Индивидуальной настройки "
        "для отдельных таблиц нет.",
        "",
        "На пяти управляемых таблицах с точной истиной Gemini и OpenAI дали один и тот же "
        "правильный канонический JSON во всех 5 случаях. Ложного совпадения не было.",
        "",
        "На девяти реальных PDF полного совпадения не было ни разу: 0/9 по структуре, "
        "0/9 по содержимому и 0/9 полностью. Это означает, что детерминированный общий "
        "ответ на реальных таблицах пока не достигнут. Два результата нельзя автоматически "
        "склеивать или исправлять.",
        "",
        "Повторный запуск на тех же PNG также изменил часть ответов каждого провайдера. "
        "Поэтому temperature 0 здесь не равен гарантии байт-в-байт или канонической "
        "повторяемости.",
        "",
        f"Итоговый вердикт: `{scores['verdict']}`.",
        "",
        "Это исследовательский результат, не готовность production-пайплайна.",
        "",
        "## Что именно стало выходом нормализатора",
        "",
        "Основной объект — логическая сетка таблицы, а не набор финансовых фактов и не "
        "пары ключ–значение. В контракте нет координат, ролей header/body/total, типов "
        "number/date/currency и финансовой интерпретации.",
        "",
        "```json",
        json.dumps(
            {
                "schema_version": "broker_reports_canonical_table_v1",
                "table_id": "example",
                "row_count": 2,
                "column_count": 2,
                "cells": [
                    {
                        "row_index": 0,
                        "column_index": 0,
                        "row_span": 1,
                        "column_span": 2,
                        "content_state": "present",
                        "source_text": "Summary",
                    },
                    {
                        "row_index": 1,
                        "column_index": 0,
                        "row_span": 1,
                        "column_span": 1,
                        "content_state": "empty",
                        "source_text": "",
                    },
                    {
                        "row_index": 1,
                        "column_index": 1,
                        "row_span": 1,
                        "column_span": 1,
                        "content_state": "present",
                        "source_text": "1,000",
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        "```",
        "",
        "Объединённая ячейка хранится один раз в своей верхней левой позиции со span. "
        "Каждое место сетки должно быть покрыто ровно одной ячейкой. Состояния закрыты: "
        "`present`, `empty`, `unreadable`. Строка `source_text` не превращается в число, "
        "дату, валюту или бизнес-понятие.",
        "",
        "Для сравнения применяется только замороженная техническая нормализация пробелов "
        "и Unicode NFKC. Исходные ответы провайдеров сохранены отдельно, поэтому отличие "
        "форматирования не скрывается.",
        "",
        "## Как обеспечена независимость",
        "",
        "Оба провайдера получили байт-в-байт один PNG, один логический prompt и одну "
        "каноническую схему. На запрос — один preflight и один generate; скрытых повторов, "
        "failover, третьей VLM и передачи ответа соседа не было. Эталон открывался scorer-ом "
        "только после seal терминала.",
        "",
        "Gemini использовал техническую проекцию JSON Schema. Проверка показала, что "
        "обязательные поля, enum и nullability остались эквивалентны. Сравниваемая единица — "
        "`model + provider API + schema adapter`; изолированная причинность модели не доказана.",
        "",
        "## 8% padding и детектор",
        "",
        f"Все {controlled['table_count'] + real['table_count']} кропов воспроизвелись байт-в-байт: "
        f"{_yes_no(crop['all_crops_byte_reproducible'])}.",
        "",
        f"На реальном корпусе 8%-кроп содержит все {crop_diagnostic['record_count']} рамок "
        "из старого чернового референса. Это полезная геометрическая диагностика, но не "
        "accuracy: старый референс явно помечен `human_reviewed: false`. Поэтому надёжность "
        "детекции и полнота реального crop в строгом смысле пока не доказаны человеком.",
        "",
        "## Точная истина: управляемые таблицы",
        "",
        "Корпус: 5 заранее сгенерированных таблиц, 45 логических ячеек. Он включает обычную "
        "сетку, merged header, пустые ячейки, borderless-таблицу, исходные форматы `(50)`, "
        "`$20.00`, `01/02/25` и закрытую нечитаемую ячейку.",
        "",
        "| Метрика | Gemini | OpenAI |",
        "|---|---:|---:|",
        f"| Валидный контракт | {providers['gemini']['contract_valid_tables']}/5 | {providers['openai']['contract_valid_tables']}/5 |",
        f"| Точная структура | {providers['gemini']['exact_structure_tables']}/5 | {providers['openai']['exact_structure_tables']}/5 |",
        f"| Полностью правильная таблица | {providers['gemini']['exact_full_tables']}/5 | {providers['openai']['exact_full_tables']}/5 |",
        f"| Правильное содержимое ячеек | {providers['gemini']['correct_content_cells']}/45 | {providers['openai']['correct_content_cells']}/45 |",
        f"| Пропущенные / лишние ячейки | {providers['gemini']['missing_cells']} / {providers['gemini']['extra_cells']} | {providers['openai']['missing_cells']} / {providers['openai']['extra_cells']} |",
        "",
        "| Dual-VLM метрика | Результат |",
        "|---|---:|",
        f"| Структурный consensus | {dual['structural_consensus_tables']}/5 |",
        f"| Content consensus | {dual['content_consensus_tables']}/5 |",
        f"| Full-table consensus | {dual['full_table_consensus_tables']}/5 |",
        f"| P(correct \| full consensus) | {_pct(dual['correctness_given_full_consensus'])} |",
        f"| Ложный consensus | {dual['false_consensus_count']} |",
        f"| Покрытие automatic acceptance | {_pct(dual['automatic_acceptance_coverage'])} |",
        "",
        "На этой малой точной выборке правило `accept only full consensus` не приняло ни "
        "одной неправильной таблицы. Но пяти простых контролей недостаточно для production-вывода.",
        "",
        "## Реальные PDF: только диагностика consensus",
        "",
        "Accuracy здесь не считается: нет авторитетного построчного референса. Можно честно "
        "сказать только, совпали ли два ответа.",
        "",
        "| Метрика | Результат |",
        "|---|---:|",
        f"| Gemini: валидный контракт | {real['gemini_contract_valid_tables']}/9 |",
        f"| OpenAI: валидный контракт | {real['openai_contract_valid_tables']}/9 |",
        f"| Structural consensus | {real['structural_consensus_tables']}/9 |",
        f"| Content consensus | {real['content_consensus_tables']}/9 |",
        f"| Full-table consensus | {real['full_table_consensus_tables']}/9 |",
        "",
        "Минимальные причины расхождения:",
        "",
        f"- разное число строк: {structural.get('different_row_count', 0)};",
        f"- merged cell против разделённых ячеек: {structural.get('merged_cell_versus_separate_cells', 0)};",
        f"- текст назначен другой ячейке: {structural.get('text_assigned_to_different_cell', 0)};",
        f"- contract failure: {structural.get('provider_contract_failure', 0)}.",
        "",
        f"В финальном запуске contract failure у OpenAI: {len(current_openai_failures)} "
        f"({', '.join(f'`{item}`' for item in current_openai_failures) or 'нет'}). "
        "Модель указала ячейку с `row_index` за пределами собственного `row_count`. "
        "Скорер не исправлял это и не выдавал за ошибку чтения.",
        "",
        "## Повторяемость одинакового запроса",
        "",
        "Два live-run получили те же crop SHA, model view, padding и каноническую схему "
        f"для каждой таблицы: {_yes_no(repeatability['identical_inputs_for_every_table'])}.",
        "",
        "| Провайдер / корпус | Одинаковый canonical output в двух запусках |",
        "|---|---:|",
        f"| Gemini / controlled | {repeat_gemini['controlled_exact_ground_truth']['canonical_output_repeatable_tables']}/{repeat_gemini['controlled_exact_ground_truth']['both_runs_contract_valid_tables']} |",
        f"| OpenAI / controlled | {repeat_openai['controlled_exact_ground_truth']['canonical_output_repeatable_tables']}/{repeat_openai['controlled_exact_ground_truth']['both_runs_contract_valid_tables']} |",
        f"| Gemini / real PDF | {repeat_gemini['real_pdf_unreviewed']['canonical_output_repeatable_tables']}/{repeat_gemini['real_pdf_unreviewed']['both_runs_contract_valid_tables']} |",
        f"| OpenAI / real PDF | {repeat_openai['real_pdf_unreviewed']['canonical_output_repeatable_tables']}/{repeat_openai['real_pdf_unreviewed']['both_runs_contract_valid_tables']} |",
        "",
        f"У Gemini изменились реальные таблицы: {_inline_ids(repeat_gemini['real_pdf_unreviewed']['changed_tables'])}. "
        f"У OpenAI изменились: {_inline_ids(repeat_openai['real_pdf_unreviewed']['changed_tables'])}. "
        "Это отдельная причина не обещать детерминированный ответ на реальном корпусе.",
        "",
        "## Конкретные примеры",
        "",
        _example_line("Правильный полный consensus", examples["correct_consensus"]),
        _example_line("Структурное расхождение", examples["structural_disagreement"]),
        _example_line(
            "Пропуск ячейки одним провайдером", examples["one_provider_omission"]
        ),
        _example_line(
            "Provider contract failure", examples["provider_contract_failure"]
        ),
        _example_line(
            "Чистое content-only расхождение", examples["content_disagreement"]
        ),
        _example_line("Ложный consensus", examples["false_consensus"]),
        "",
        "Чистого content-only расхождения, ложного consensus и одинаковой ошибки двух "
        "провайдеров на точном корпусе не наблюдалось. Это не доказывает, что они невозможны.",
        "",
        "## Ответы на главные вопросы",
        "",
        "- Один VLM нашёл девять ожидаемых областей, а единый 8% padding геометрически "
        "накрыл все девять черновых рамок. Строго назвать детекцию и crop надёжными пока "
        "нельзя: реальный reference не прошёл human review.",
        "- Gemini правильно восстановил 5/5 управляемых таблиц. Его accuracy на реальных "
        "PDF неизвестна.",
        f"- OpenAI правильно восстановил 5/5 управляемых таблиц. На реальных PDF он дал "
        f"валидный контракт в {real['openai_contract_valid_tables']}/9 случаях; accuracy без истины неизвестна.",
        "- На реальных таблицах модели согласились по структуре 0/9, по содержимому 0/9, "
        "полностью 0/9.",
        "- Полный consensus был правильным 5/5 раз только на управляемом корпусе. Ложных "
        "совпадений там не было.",
        "- Нельзя сказать, какая модель точнее в реальных разногласиях: для этого нужна "
        "авторитетная разметка.",
        "- Второй VLM даёт материальную страховку: он не позволил молча принять ни одну из "
        "девяти несовпадающих реальных таблиц. Цена этой страховки сейчас — 100% ручного "
        "маршрута на реальном тесте.",
        "- Full consensus достаточен как условие принятия внутри малого управляемого "
        "корпуса, но не доказан для реальных брокерских PDF.",
        "- Temperature 0 не обеспечил повторяемость реальных JSON: оба провайдера меняли "
        "часть своих канонических таблиц между двумя одинаковыми запусками.",
        "",
        "## Что передавать следующему агенту",
        "",
        "Передавать нужно только один `broker_reports_canonical_table_v1`, если оба "
        "провайдера дали `FULL_TABLE_CONSENSUS=true`. Это JSON сетки с исходным текстом, "
        "пустыми/нечитаемыми ячейками и span, без финансовой интерпретации.",
        "",
        "Если consensus нет или один контракт невалиден, следующему финансовому агенту "
        "ничего автоматически не передаётся. Случай уходит в review вместе с PNG, двумя "
        "raw-ответами и конкретным diff.",
        "",
        "## Минимальная оправданная архитектура",
        "",
        "1. Один замороженный VLM-детектор области таблицы.",
        "2. Один глобальный crop policy: 8% каждой стороны страницы, без per-table tuning.",
        "3. Один нейтральный canonical-table контракт для Gemini и OpenAI.",
        "4. Автоматическое принятие только при полном каноническом совпадении.",
        "5. Любое расхождение или contract failure — в операторский review; никакого "
        "silent repair, третьей VLM или majority vote.",
        "6. Следующий исследовательский шаг — human-reviewed canonical truth для этих "
        "девяти реальных таблиц и повторный scorer без изменения prompt/контракта.",
        "",
        "## Воспроизводимость",
        "",
        f"- terminal SHA-256: `{scores['terminal_sha256']}`;",
        f"- previous terminal SHA-256: `{repeatability['previous_terminal_sha256']}`;",
        f"- scores SHA-256: `{scores_sha256}`;",
        f"- scores canonical JSON SHA-256 check: `{hashlib.sha256(canonical_json_bytes(scores)).hexdigest()}`;",
        "- raw независимые ответы, canonical outputs, PNG crops, machine diffs и HTML review "
        "сохранены в локальном research run;",
        "- production pipeline и OpenWebUI core не менялись.",
        "",
    ]
    return "\n".join(lines)


def _example_line(label: str, value: dict[str, Any] | None) -> str:
    if value is None:
        return f"- {label}: не наблюдалось."
    difference = value.get("selected_difference") or value.get("smallest_difference")
    if difference is None:
        detail = "без расхождения"
    else:
        detail = json.dumps(difference, ensure_ascii=False, sort_keys=True)
    return f"- {label}: `{value['table_id']}` — {detail}."


def _yes_no(value: bool) -> str:
    return "да" if value else "нет"


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def _inline_ids(values: list[str]) -> str:
    return ", ".join(f"`{value}`" for value in values) if values else "нет"


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise CanonicalTableReportError("canonical_table_report_json_not_object")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
