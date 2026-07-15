from __future__ import annotations


CONTAINER_LABELS = {
    "csv": "CSV",
    "txt": "TXT",
    "html_text": "HTML",
    "xlsx": "XLSX",
    "pdf": "PDF",
    "zip": "ZIP",
    "docx": "DOCX",
    "image": "изображение",
    "unknown": "неизвестный формат",
}

DOCUMENT_CLASS_LABELS = {
    "operations_table": "Таблицы операций",
    "source_broker_report": "Брокерские отчеты",
    "dividends_report": "Отчеты по дивидендам",
    "fees_report": "Отчеты по комиссиям",
    "withholding_report": "Отчеты по удержаниям",
    "calculation_template": "Расчетные шаблоны",
    "official_form": "Формы/выходные документы",
    "unsupported": "Не поддерживается",
    "unknown_or_needs_review": "Требует проверки",
}

BLOCKER_LABELS = {
    "no_files": "Файлы не найдены. Прикрепите документы к сообщению.",
    "bytes_unavailable": "Не удалось прочитать содержимое загруженного файла.",
    "unsupported_format": "Формат файла пока не поддерживается для следующего шага.",
    "corrupt_file": "Файл поврежден или не читается.",
    "encrypted_file": "Файл защищен паролем. Загрузите версию без пароля.",
    "raster_requires_ocr_or_review": "Файл похож на скан. Для него нужен OCR или ручная проверка.",
    "zip_requires_review": "Архив требует отдельной проверки состава файлов.",
    "duplicate_review": "Найден возможный дубликат документа.",
    "unknown_role": "Тип документа не распознан уверенно.",
    "privacy_violation": "Безопасный отчет не прошел проверку приватности.",
}

ELIGIBILITY_LABELS = {
    "accepted_as_source_candidate_for_gate2": "\u041f\u043e\u0433\u043b\u043e\u0449\u0435\u043d\u043e \u043a\u0430\u043a source-\u043a\u0430\u043d\u0434\u0438\u0434\u0430\u0442",
    "accepted_for_gate2": "\u041f\u043e\u0433\u043b\u043e\u0449\u0435\u043d\u043e \u043a\u0430\u043a \u0438\u0441\u0442\u043e\u0447\u043d\u0438\u043a",
    "excluded_from_gate2": "\u041d\u0435 \u0438\u0434\u0435\u0442 \u0432 source-\u0438\u0437\u0432\u043b\u0435\u0447\u0435\u043d\u0438\u0435",
    "ocr_required_before_gate2": "\u041d\u0443\u0436\u0435\u043d OCR \u0434\u043e \u0438\u0437\u0432\u043b\u0435\u0447\u0435\u043d\u0438\u044f",
    "source_policy_review": "\u041d\u0435\u044f\u0441\u043d\u043e\u0441\u0442\u044c source-\u0440\u043e\u043b\u0438 \u043f\u043e\u0435\u0434\u0435\u0442 \u0434\u0430\u043b\u044c\u0448\u0435",
    "metadata_review": "\u041d\u0435\u0440\u0435\u0448\u0435\u043d\u043d\u044b\u0435 \u0432\u043e\u043f\u0440\u043e\u0441\u044b \u043f\u043e metadata passport",
    "duplicate_review": "\u0414\u0443\u0431\u043b\u0438: \u043d\u0443\u0436\u0435\u043d canonical choice \u043f\u0435\u0440\u0435\u0434 \u0441\u0432\u0435\u0440\u043a\u043e\u0439",
    "included_in_reduced_subset": "\u0414\u043e\u0441\u0442\u0443\u043f\u043d\u043e \u0434\u043b\u044f source-\u0438\u0437\u0432\u043b\u0435\u0447\u0435\u043d\u0438\u044f",
}

CLARIFICATION_GROUP_LABELS = {
    "missing_period": "Не указан период отчета",
    "missing_account_or_contract": "Не указан счет или договор",
    "unclear_document_role": "Нужно уточнить роль документа",
    "missing_broker_client_metadata": "Не хватает данных брокера/клиента",
    "duplicate_canonical_choice": "Нужно выбрать основной документ среди дублей",
    "outside_scope_confirmation": "Нужно подтвердить, что документ вне кейса",
    "other_metadata_conflict": "Другой конфликт метаданных",
}


CLARIFICATION_CRITICALITY_GROUP_LABELS = {
    "critical": "\u041a\u0440\u0438\u0442\u0438\u0447\u043d\u043e \u0434\u043b\u044f \u043f\u0440\u043e\u0434\u043e\u043b\u0436\u0435\u043d\u0438\u044f",
    "clarifying": "\u0416\u0435\u043b\u0430\u0442\u0435\u043b\u044c\u043d\u043e \u0443\u0442\u043e\u0447\u043d\u0438\u0442\u044c",
    "non_critical": "\u041c\u043e\u0436\u043d\u043e \u043e\u0442\u043b\u043e\u0436\u0438\u0442\u044c",
}

CLARIFICATION_REQUIRED_LABELS = {
    True: "\u043e\u0431\u044f\u0437\u0430\u0442\u0435\u043b\u044c\u043d\u043e",
    False: "\u043d\u0435 \u0431\u043b\u043e\u043a\u0438\u0440\u0443\u0435\u0442 Gate 2",
}


def render_compact_report(report: dict) -> str:
    lines: list[str] = [_heading(report), ""]
    files_total = int(report.get("files_total") or report.get("summary_counts", {}).get("files_total") or 0)
    lines.append(f"Получено документов: {files_total}")
    container_counts = report.get("container_counts") or {}
    if container_counts:
        lines.extend(["", "Форматы:"])
        for key, count in sorted(container_counts.items()):
            lines.append(f"- {CONTAINER_LABELS.get(str(key), str(key))}: {count}")
    processing_outcomes = report.get("file_processing_outcomes") or {}
    if isinstance(processing_outcomes, dict) and processing_outcomes.get("outcomes"):
        lines.extend(["", "Результат обработки файлов:"])
        lines.append(f"- {processing_outcomes.get('user_message') or 'Обработка завершена.'}")
        for outcome in processing_outcomes.get("outcomes", []):
            if not isinstance(outcome, dict):
                continue
            lines.append(
                f"- {outcome.get('file_ref')}: "
                f"{outcome.get('user_message') or 'Требуется проверка результата.'}"
            )
    structural_shadow = report.get("pdf_structural_repair_shadow") or {}
    structural_summary = (
        structural_shadow.get("summary")
        if isinstance(structural_shadow, dict)
        else None
    )
    if isinstance(structural_summary, dict) and structural_summary.get("enabled") is True:
        lines.extend(["", "Автоматическая проверка структуры PDF-таблиц:"])
        lines.append(
            "- Выбрано таблиц: "
            f"{int(structural_summary.get('tables_selected') or 0)}; "
            "согласовано двумя проверками: "
            f"{int(structural_summary.get('accepted_unique_consensus_tables') or 0)}"
        )
        continuation_groups_discovered = int(
            structural_summary.get("continuation_groups_discovered") or 0
        )
        continuation_groups_accepted = int(
            structural_summary.get("continuation_groups_accepted") or 0
        )
        continuation_groups_failed = int(
            structural_summary.get("continuation_groups_failed") or 0
        )
        if continuation_groups_discovered or continuation_groups_failed:
            lines.append(
                "- Продолжения таблиц на соседней странице: "
                f"найдено {continuation_groups_discovered}; "
                f"аккуратно объединено {continuation_groups_accepted}; "
                f"требует проверки {continuation_groups_failed}."
            )
        lines.append("- Режим: проверочный shadow; основной результат Gate 2 не изменён.")
        structural_batch = structural_summary.get("file_processing_outcomes") or {}
        if isinstance(structural_batch, dict) and structural_batch.get("outcomes"):
            lines.append(
                f"- {structural_batch.get('user_message') or 'Проверка файлов завершена.'}"
            )
            for outcome in structural_batch.get("outcomes", []):
                if isinstance(outcome, dict):
                    lines.append(
                        f"- {outcome.get('file_ref')}: "
                        f"{outcome.get('user_message') or 'Требуется проверка результата.'}"
                    )
    class_counts = report.get("document_class_counts") or {}
    if class_counts:
        lines.extend(["", "Найденные типы документов:"])
        for key, count in sorted(class_counts.items()):
            lines.append(f"- {DOCUMENT_CLASS_LABELS.get(str(key), 'Требует проверки')}: {count}")
    full_source = report.get("full_source_coverage_summary") or {}
    if full_source:
        status_counts = full_source.get("status_counts") or {}
        lines.extend(["", "Полное покрытие источников для Gate 2:"])
        lines.append(
            "- Полностью доступны: "
            f"{int(full_source.get('full_coverage_documents_total') or 0)}"
        )
        lines.append(
            "- Extraction-grade units: "
            f"{int(full_source.get('extraction_units_total') or 0)}"
        )
        lines.append(
            "- Частично/не поддержано: "
            f"{int(status_counts.get('partial') or 0)}/"
            f"{int(status_counts.get('blocked') or 0)}"
        )
        lines.append("- Preview используется только для просмотра, не как доказательство полного покрытия.")
    eligibility_summary = report.get("source_eligibility_summary") or {}
    if eligibility_summary:
        processed = int(eligibility_summary.get("documents_total") or files_total)
        source_policy_review = int(eligibility_summary.get("source_policy_review") or 0)
        lines.extend(["", "\u0418\u0442\u043e\u0433 Gate 1: \u043f\u0430\u043a\u0435\u0442 \u043f\u043e\u0433\u043b\u043e\u0449\u0435\u043d"])
        lines.append(f"- \u041f\u0440\u043e\u0447\u0438\u0442\u0430\u043d\u043e/\u043f\u0440\u043e\u0444\u0438\u043b\u0438\u0440\u043e\u0432\u0430\u043d\u043e: {processed}")
        lines.append(f"- {ELIGIBILITY_LABELS['accepted_for_gate2']}: {int(eligibility_summary.get('accepted_for_gate2') or 0)}")
        lines.append(
            f"- {ELIGIBILITY_LABELS['accepted_as_source_candidate_for_gate2']}: "
            f"{int(eligibility_summary.get('accepted_as_source_candidate_for_gate2') or 0)}"
        )
        lines.append(f"- {ELIGIBILITY_LABELS['excluded_from_gate2']}: {int(eligibility_summary.get('excluded_from_gate2') or 0)}")
        lines.append(f"- {ELIGIBILITY_LABELS['ocr_required_before_gate2']}: {int(eligibility_summary.get('ocr_required_before_gate2') or 0)}")
        lines.append(f"- {ELIGIBILITY_LABELS['source_policy_review']}: {source_policy_review}")
        lines.append(f"- {ELIGIBILITY_LABELS['metadata_review']}: {int(eligibility_summary.get('metadata_review') or 0)}")
        lines.append(f"- {ELIGIBILITY_LABELS['duplicate_review']}: {int(eligibility_summary.get('duplicate_review') or 0)}")
        auto_duplicate_groups = int(eligibility_summary.get("auto_resolved_exact_duplicate_groups") or 0)
        auto_duplicate_documents = int(eligibility_summary.get("auto_resolved_exact_duplicate_documents") or 0)
        if auto_duplicate_groups or auto_duplicate_documents:
            lines.append(
                "- Auto-resolved exact duplicates: "
                f"{auto_duplicate_groups} groups, {auto_duplicate_documents} excluded duplicate docs"
            )
        lines.append(f"- {ELIGIBILITY_LABELS['included_in_reduced_subset']}: {int(eligibility_summary.get('included_in_reduced_subset') or 0)}")
        passport_counts = report.get("document_metadata_passport_summary") or {}
        if passport_counts:
            lines.append(
                "- LLM паспорта документов: "
                f"{int(passport_counts.get('validated') or 0)} проверено, "
                f"{int(passport_counts.get('failed') or 0)} заблокировано"
            )
        mode = str(report.get("gate2_handoff_mode") or eligibility_summary.get("handoff_mode") or "")
        lines.append(f"- Handoff mode: {mode or 'unknown'}")
        if mode == "reduced_subset_ready_for_gate2":
            lines.append("- \u041c\u043e\u0436\u043d\u043e \u043d\u0430\u0447\u0438\u043d\u0430\u0442\u044c source-\u0438\u0437\u0432\u043b\u0435\u0447\u0435\u043d\u0438\u0435 \u043f\u043e \u0434\u043e\u0441\u0442\u0443\u043f\u043d\u044b\u043c \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u0430\u043c: \u0434\u0430")
            lines.append("- \u041d\u0435\u0440\u0435\u0448\u0435\u043d\u043d\u044b\u0435 \u0432\u043e\u043f\u0440\u043e\u0441\u044b \u043e\u0441\u0442\u0430\u044e\u0442\u0441\u044f \u0432 issue ledger \u0438 \u043f\u043e\u0435\u0434\u0443\u0442 \u0434\u0430\u043b\u044c\u0448\u0435.")
        elif mode == "full_package_ready_for_gate2":
            lines.append("- \u041c\u043e\u0436\u043d\u043e \u043d\u0430\u0447\u0438\u043d\u0430\u0442\u044c source-\u0438\u0437\u0432\u043b\u0435\u0447\u0435\u043d\u0438\u0435 \u043f\u043e \u0432\u0441\u0435\u043c\u0443 \u043f\u0430\u043a\u0435\u0442\u0443: \u0434\u0430")
        else:
            lines.append("- \u0414\u043e source-\u0438\u0437\u0432\u043b\u0435\u0447\u0435\u043d\u0438\u044f \u0435\u0441\u0442\u044c \u0431\u043b\u043e\u043a\u0435\u0440\u044b: \u0434\u0430")
    domain_summary = report.get("domain_ingestion_summary") or {}
    if domain_summary:
        counts = domain_summary.get("counts") or {}
        stage_readiness = domain_summary.get("stage_readiness") or {}
        next_stage_ref_summary = domain_summary.get("next_stage_ref_summary") or {}
        lines.extend(["", "\u041a\u043e\u043d\u0442\u0435\u043a\u0441\u0442 \u0434\u043e\u043c\u0435\u043d\u0430:"])
        lines.append("- Domain context packet: ready")
        lines.append(f"- \u041d\u0435\u0440\u0435\u0448\u0435\u043d\u043d\u044b\u0435 issue: {int(counts.get('unresolved_issues_total') or 0)}")
        lines.append(
            "- Source-\u0438\u0437\u0432\u043b\u0435\u0447\u0435\u043d\u0438\u0435: "
            f"{stage_readiness.get('source_fact_extraction') or 'unknown'}"
        )
        if next_stage_ref_summary:
            lines.append(
                "- \u041e\u0441\u043d\u043e\u0432\u043d\u044b\u0435 source-\u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u044b: "
                f"{int(next_stage_ref_summary.get('primary_source_extraction_total') or 0)}"
            )
            lines.append(
                "- \u0414\u043e\u043f\u043e\u043b\u043d\u0438\u0442\u0435\u043b\u044c\u043d\u044b\u0435/source-warning refs: "
                f"{int(next_stage_ref_summary.get('source_ready_not_primary_total') or 0)}"
            )
            lines.append(
                "- Cross-check/audit refs: "
                f"{int(next_stage_ref_summary.get('cross_check_total') or 0)}/"
                f"{int(next_stage_ref_summary.get('audit_reference_total') or 0)}"
            )
    blockers = report.get("blockers") or report.get("normalization_blockers") or []
    if blockers:
        lines.extend(["", "Предупреждения:"])
        seen: set[str] = set()
        for blocker in blockers:
            code = str(blocker.get("code") or "")
            if code in seen:
                continue
            seen.add(code)
            lines.append(f"- {BLOCKER_LABELS.get(code, 'Требуется проверка документа.')}")
    clarification = report.get("gate1_clarification_questions") or {}
    questions = clarification.get("questions") if isinstance(clarification, dict) else []
    if questions:
        lines.extend(["", "Вопросы для уточнения:"])
        _append_clarification_questions_by_criticality(lines, questions)
    resolution_summary = report.get("gate1_clarification_resolution_summary") or {}
    if resolution_summary:
        lines.extend(
            [
                "",
                "Ответы по уточнениям:",
                f"- Получено резолюций: {int(resolution_summary.get('resolutions_total') or 0)}",
                f"- Можно использовать для eligibility v2: {int(resolution_summary.get('usable_by_source_eligibility_v2') or 0)}",
            ]
        )
    lines.extend(["", "Следующий шаг:", _next_step(report)])
    run_id = report.get("normalization_run_id")
    if run_id:
        lines.extend(["", f"Техническая ссылка: run {run_id}"])
    return "\n".join(lines).strip()


def _append_clarification_questions_by_criticality(lines: list[str], questions: list[dict]) -> None:
    display_limits = {
        "critical": 10,
        "clarifying": 5,
        "non_critical": 3,
    }
    grouped: dict[str, list[dict]] = {
        "critical": [],
        "clarifying": [],
        "non_critical": [],
    }
    for question in questions:
        if not isinstance(question, dict):
            continue
        criticality = str(question.get("criticality") or "clarifying")
        grouped.setdefault(criticality, []).append(question)
    for criticality in ("critical", "clarifying", "non_critical"):
        bucket = grouped.get(criticality) or []
        if not bucket:
            continue
        lines.append(f"- {CLARIFICATION_CRITICALITY_GROUP_LABELS.get(criticality, criticality)}:")
        limit = display_limits.get(criticality, 5)
        for question in bucket[:limit]:
            required = CLARIFICATION_REQUIRED_LABELS[question.get("required") is True]
            gap_label = CLARIFICATION_GROUP_LABELS.get(
                str(question.get("gap_type") or "other_metadata_conflict"),
                "\u0423\u0442\u043e\u0447\u043d\u0435\u043d\u0438\u0435 \u043c\u0435\u0442\u0430\u0434\u0430\u043d\u043d\u044b\u0445",
            )
            text = str(question.get("question_text") or "").strip()
            question_id = str(question.get("question_id") or "")
            policy_note = _question_policy_note(question)
            suffix = f"; {policy_note}" if policy_note else ""
            lines.append(f"  - [{question_id}] {gap_label}: {text} ({required}{suffix})")
        omitted = len(bucket) - limit
        if omitted > 0:
            lines.append(f"  - \u0415\u0449\u0435 \u0432\u043e\u043f\u0440\u043e\u0441\u043e\u0432 \u0432 \u044d\u0442\u043e\u0439 \u0433\u0440\u0443\u043f\u043f\u0435: {omitted}")


def _question_policy_note(question: dict) -> str:
    parts = []
    dependency_stage = str(question.get("dependency_stage") or "")
    auto_resolution_policy = str(question.get("auto_resolution_policy") or "")
    if dependency_stage:
        parts.append(f"stage={dependency_stage}")
    if auto_resolution_policy and auto_resolution_policy != "none":
        parts.append(f"policy={auto_resolution_policy}")
    return ", ".join(parts)


def _heading(report: dict) -> str:
    status = report.get("run_status")
    if status == "completed":
        return "Нормализация завершена."
    if status == "privacy_failed":
        return "Нормализация остановлена: отчет требует технической проверки."
    if status == "failed_safe":
        return "Нормализация остановлена."
    return "Нормализация завершена с предупреждениями."


def _next_step(report: dict) -> str:
    next_step = report.get("recommended_next_step") or report.get("next_step")
    if next_step == "attach_synthetic_files_and_retry":
        return "Прикрепите файлы брокерского отчета и отправьте сообщение еще раз."
    if next_step == "verify_pipe_byte_access_boundary":
        return "Загрузите файлы еще раз или попросите администратора проверить доступ к uploads."
    if next_step == "fix_safe_projection":
        return "Передайте результат разработчику: безопасная проекция отчета заблокирована."
    if next_step == "continue_with_reduced_gate2_subset_after_specialist_confirmation":
        return "\u041c\u043e\u0436\u043d\u043e \u043d\u0430\u0447\u0438\u043d\u0430\u0442\u044c source-\u0438\u0437\u0432\u043b\u0435\u0447\u0435\u043d\u0438\u0435 \u043f\u043e \u0434\u043e\u0441\u0442\u0443\u043f\u043d\u043e\u043c\u0443 reduced subset; \u043d\u0435\u0440\u0435\u0448\u0435\u043d\u043d\u044b\u0435 issue \u043e\u0441\u0442\u0430\u044e\u0442\u0441\u044f \u0432 issue ledger."
    if next_step == "route_ocr_candidates_to_future_ocr_gate_or_manual_review":
        return "Документы со сканами не идут в Gate 2 без OCR или ручного решения специалиста."
    if next_step == "attach_supported_source_documents_or_review_package":
        return "Нет документов, допущенных к Gate 2. Добавьте поддерживаемые source-документы или отправьте пакет на review."
    if next_step == "review_document_metadata_passports":
        return "Проверьте metadata passport по документам с неполными или спорными метаданными."
    if next_step == "confirm_source_policy_for_candidate_documents":
        return "\u041d\u0435\u044f\u0441\u043d\u043e\u0441\u0442\u044c source-\u0440\u043e\u043b\u0438 \u0443\u0436\u0435 \u043f\u0435\u0440\u0435\u043d\u0435\u0441\u0435\u043d\u0430 \u0432 issue ledger; \u0444\u0438\u043d\u0430\u043b\u044c\u043d\u043e\u0435 \u0438\u0441\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u043d\u0438\u0435 \u0440\u0435\u0448\u0430\u0435\u0442\u0441\u044f downstream."
    if next_step == "choose_canonical_duplicate_documents":
        return "\u0414\u0443\u0431\u043b\u0438 \u043f\u043e\u0433\u043b\u043e\u0449\u0435\u043d\u044b; canonical choice \u043d\u0443\u0436\u0435\u043d \u043f\u0435\u0440\u0435\u0434 \u0441\u0432\u0435\u0440\u043a\u043e\u0439, \u043a\u043e\u043d\u0441\u043e\u043b\u0438\u0434\u0430\u0446\u0438\u0435\u0439 \u0438 declaration-support."
    if next_step == "answer_gate1_metadata_clarification_questions":
        return "Ответьте на вопросы по недостающим метаданным, затем повторите Gate 1.5 handoff."
    if next_step == "answer_gate1_duplicate_clarification_questions":
        return "Выберите основной документ среди дублей, затем повторите Gate 1.5 handoff."
    if report.get("gate2_handoff_status") == "ready_with_safe_refs":
        return "Можно переходить к извлечению фактов из брокерских отчетов."
    if report.get("gate2_handoff_status") == "ready_with_reduced_subset":
        return "\u041c\u043e\u0436\u043d\u043e \u043d\u0430\u0447\u0438\u043d\u0430\u0442\u044c source-\u0438\u0437\u0432\u043b\u0435\u0447\u0435\u043d\u0438\u0435 \u043f\u043e \u0434\u043e\u0441\u0442\u0443\u043f\u043d\u043e\u043c\u0443 subset \u0441 issue context."
    return "Проверьте предупреждения и подтвердите переход к извлечению фактов."
