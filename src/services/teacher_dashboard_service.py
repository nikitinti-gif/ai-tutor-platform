from src.database.json_storage import load_db


STATUS_LABELS = {
    "new": "⚪ Не открыто",
    "opened": "🔵 Открыто",
    "submitted": "🟡 Отправлено",
    "checked": "🟢 Проверено",
}


def _find_user(db: dict, telegram_id: int | str) -> dict | None:
    for user in db.get("users", []):
        if str(user.get("telegram_id")) == str(telegram_id):
            return user

    return None


def _get_latest_homework(db: dict) -> dict | None:
    homework_items = db.get("homework", [])

    if not homework_items:
        return None

    return homework_items[-1]


def _get_homework_topic(homework: dict) -> str:
    homework_data = homework.get("homework_data", {})

    if isinstance(homework_data, dict):
        return (
            homework_data.get("topic")
            or homework.get("topic")
            or "Тема не указана"
        )

    return homework.get("topic") or "Тема не указана"


def generate_teacher_dashboard() -> str:
    db = load_db()

    latest_homework = _get_latest_homework(db)

    if not latest_homework:
        return (
            "📊 Статус домашнего задания\n\n"
            "Домашние задания ещё не создавались."
        )

    homework_id = latest_homework.get("homework_id")
    topic = _get_homework_topic(latest_homework)

    assignments = [
        item
        for item in db.get("student_homework", [])
        if str(item.get("homework_id")) == str(homework_id)
    ]

    if not assignments:
        return (
            "📊 Статус домашнего задания\n\n"
            f"Тема: {topic}\n\n"
            "Это задание пока никому не назначено."
        )

    counters = {
        "new": 0,
        "opened": 0,
        "submitted": 0,
        "checked": 0,
    }

    students_lines = []
    attention_lines = []

    for assignment in assignments:
        status = assignment.get("status", "new")
        student_id = assignment.get("student_id")

        if status in counters:
            counters[status] += 1

        student = _find_user(db, student_id)
        student_name = "Неизвестный ученик"

        if student:
            student_name = student.get("full_name") or student_name

        status_text = STATUS_LABELS.get(status, status)

        students_lines.append(
            f"• {student_name} — {status_text}"
        )

        teacher_review_required = assignment.get(
            "teacher_review_required",
            False,
        )

        error_type = assignment.get("last_error_type")

        if teacher_review_required:
            attention_lines.append(
                f"• {student_name} — требуется проверка преподавателя"
            )
        elif error_type:
            attention_lines.append(
                f"• {student_name} — ошибка: {error_type}"
            )

    total = len(assignments)

    report = (
        "📊 Статус домашнего задания\n\n"
        f"Тема: {topic}\n"
        f"Всего учеников: {total}\n\n"
        f"🟢 Проверено: {counters['checked']}\n"
        f"🟡 Отправлено: {counters['submitted']}\n"
        f"🔵 Открыто: {counters['opened']}\n"
        f"⚪ Не открыто: {counters['new']}\n\n"
        "👨‍🎓 Ученики:\n"
        + "\n".join(students_lines)
    )

    if attention_lines:
        report += (
            "\n\n⚠️ Требуют внимания:\n"
            + "\n".join(attention_lines)
        )

    return report