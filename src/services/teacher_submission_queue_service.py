from collections import Counter
from datetime import datetime


STATUS_LABELS = {
    "accepted": "ожидает обработки",
    "processing": "обрабатывается",
    "teacher_review": "анализ готов",
    "completed": "завершена",
    "failed": "ошибка обработки",
}


def _format_time(value: object) -> str:
    if isinstance(value, datetime):
        return value.astimezone().strftime("%d.%m %H:%M")
    if isinstance(value, str) and value:
        return value[:16].replace("T", " ")
    return "—"


def _analysis_summary(analysis: object) -> str | None:
    if not isinstance(analysis, dict):
        return None
    status = analysis.get("status") or "unknown"
    try:
        confidence = float(analysis.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    return f"AI: {status}, уверенность {confidence:.2f}"


def _format_confidence(value: object) -> str:
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "0.00"


def format_teacher_submission_queue(submissions: list[dict]) -> str:
    if not submissions:
        return "📸 Очередь работ пуста."

    counts = Counter(item.get("status", "unknown") for item in submissions)
    synthetic_count = sum(bool(item.get("is_synthetic")) for item in submissions)
    real_count = len(submissions) - synthetic_count
    lines = [
        "📸 Очередь работ",
        "",
        f"Показано: {len(submissions)}",
        f"🧪 Синтетических: {synthetic_count}",
        f"👤 Реальных: {real_count}",
        f"⏳ Ожидают: {counts.get('accepted', 0)}",
        f"✅ Анализ готов: {counts.get('teacher_review', 0)}",
        f"🔴 Ошибок: {counts.get('failed', 0)}",
        "",
    ]

    for index, item in enumerate(submissions, start=1):
        data_label = "🧪 synthetic" if item.get("is_synthetic") else "👤 real"
        status = item.get("status", "unknown")
        status_label = STATUS_LABELS.get(status, status)
        lines.extend([
            f"{index}. {item.get('submission_id', '—')}",
            f"   {data_label} · {status_label}",
            f"   Ученик ID: {item.get('student_telegram_id') or 'не привязан'}",
            f"   Принято: {_format_time(item.get('created_at'))}",
        ])
        analysis_summary = _analysis_summary(item.get("analysis_result"))
        if analysis_summary:
            lines.append(f"   {analysis_summary}")
        if status == "failed" and item.get("last_error"):
            error_text = str(item["last_error"])[:180]
            lines.append(f"   Ошибка: {error_text}")
        lines.append("")

    lines.append(
        "Бесплатный Gemini автоматически обрабатывает только 🧪 synthetic."
    )
    return "\n".join(lines)


def _clip(value: object, limit: int) -> str:
    text = str(value or "—")
    return text if len(text) <= limit else f"{text[:limit - 1]}…"


def format_teacher_submission_detail(submission: dict) -> str:
    data_label = (
        "🧪 Синтетическая работа"
        if submission.get("is_synthetic")
        else "👤 Реальная работа"
    )
    status = submission.get("status", "unknown")
    lines = [
        data_label,
        "",
        f"Номер: {submission.get('submission_id', '—')}",
        f"Статус: {STATUS_LABELS.get(status, status)}",
        f"Ученик ID: {submission.get('student_telegram_id') or 'не привязан'}",
        f"Размер: {submission.get('photo_width', '—')}×{submission.get('photo_height', '—')}",
        f"Принято: {_format_time(submission.get('created_at'))}",
    ]

    analysis = submission.get("analysis_result")
    if not isinstance(analysis, dict):
        lines.extend(["", "AI-анализ не запускался."])
    else:
        lines.extend([
            "",
            f"AI-статус: {analysis.get('status', 'unknown')}",
            f"Уверенность: {_format_confidence(analysis.get('confidence'))}",
            f"Тип ошибки: {analysis.get('error_type') or '—'}",
            "",
            "Транскрипция:",
            _clip(analysis.get("image_transcription"), 1000),
            "",
            "Анализ:",
            _clip(analysis.get("feedback"), 900),
            "",
            "Рекомендация:",
            _clip(analysis.get("hint"), 600),
        ])

    if submission.get("last_error"):
        lines.extend([
            "",
            f"Техническая ошибка: {_clip(submission['last_error'], 300)}",
        ])
    return "\n".join(lines)
