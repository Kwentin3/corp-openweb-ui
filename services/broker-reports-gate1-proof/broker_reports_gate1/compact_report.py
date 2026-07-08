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


def render_compact_report(report: dict) -> str:
    lines: list[str] = [_heading(report), ""]
    files_total = int(report.get("files_total") or report.get("summary_counts", {}).get("files_total") or 0)
    lines.append(f"Обработано файлов: {files_total}")
    container_counts = report.get("container_counts") or {}
    if container_counts:
        lines.extend(["", "Форматы:"])
        for key, count in sorted(container_counts.items()):
            lines.append(f"- {CONTAINER_LABELS.get(str(key), str(key))}: {count}")
    class_counts = report.get("document_class_counts") or {}
    if class_counts:
        lines.extend(["", "Найденные типы документов:"])
        for key, count in sorted(class_counts.items()):
            lines.append(f"- {DOCUMENT_CLASS_LABELS.get(str(key), 'Требует проверки')}: {count}")
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
    lines.extend(["", "Следующий шаг:", _next_step(report)])
    run_id = report.get("normalization_run_id")
    if run_id:
        lines.extend(["", f"Техническая ссылка: run {run_id}"])
    return "\n".join(lines).strip()


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
    if report.get("gate2_handoff_status") == "ready_with_safe_refs":
        return "Можно переходить к извлечению фактов из брокерских отчетов."
    return "Проверьте предупреждения и подтвердите переход к извлечению фактов."
