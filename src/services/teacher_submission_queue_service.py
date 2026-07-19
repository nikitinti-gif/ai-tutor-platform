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
