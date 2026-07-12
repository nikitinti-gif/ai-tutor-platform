from datetime import datetime, timezone

from src.database.json_storage import load_db


ERROR_TYPE_LABELS = {
    "logic_condition_error": "ошибка в логике условия",
    "algorithm_explanation_error": "ошибка в объяснении алгоритма",
    "unclear_solution": "решение требует более понятного объяснения",
    "algebra_sign_error": "ошибка при переносе слагаемых через знак равенства",
    "calculation_error": "вычислительная ошибка",
    "logic_error": "ошибка в логике решения",
    "formula_error": "ошибка в применении формулы",
    "unknown": "ошибка требует уточнения",
}


STATUS_LABELS = {
    "new": "задание выдано, но ещё не открыто",
    "opened": "задание открыто учеником",
    "submitted": "решение отправлено на проверку",
    "checked": "решение проверено",
}


def _parse_dt(value: str | None) -> datetime:
    if not value:
        return datetime.min

    try:
        normalized = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)

        if dt.tzinfo:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)

        return dt
    except Exception:
        return datetime.min


def _format_dt(value: str | None) -> str | None:
    dt = _parse_dt(value)

    if dt == datetime.min:
        return None

    return dt.strftime("%d.%m.%Y, %H:%M")


def _find_user_by_telegram_id(db: dict, telegram_id: int | str) -> dict | None:
    for user in db.get("users", []):
        if str(user.get("telegram_id")) == str(telegram_id):
            return user

    return None


def _get_latest_student_homework(db: dict) -> dict | None:
    student_homework = db.get("student_homework", [])

    if not student_homework:
        return None

    def sort_key(item: dict) -> datetime:
        return max(
            _parse_dt(item.get("checked_at")),
            _parse_dt(item.get("submitted_at")),
            _parse_dt(item.get("opened_at")),
            _parse_dt(item.get("assigned_at")),
        )

    return sorted(student_homework, key=sort_key)[-1]


def _get_homework_by_id(db: dict, homework_id: str | None) -> dict | None:
    if not homework_id:
        return None

    for homework in db.get("homework", []):
        if str(homework.get("homework_id")) == str(homework_id):
            return homework

    return None


def _get_learning_dna(db: dict, student_id: int | str) -> dict | None:
    learning_dna = db.get("learning_dna", {})

    if isinstance(learning_dna, dict):
        return learning_dna.get(str(student_id)) or learning_dna.get(student_id)

    if isinstance(learning_dna, list):
        for item in learning_dna:
            if str(item.get("student_id")) == str(student_id):
                return item

    return None


def _get_homework_topic(homework: dict | None) -> str:
    if not homework:
        return "Тема не указана"

    homework_data = homework.get("homework_data", {})

    if isinstance(homework_data, dict):
        return (
            homework_data.get("topic")
            or homework.get("topic")
            or "Тема не указана"
        )

    return homework.get("topic") or "Тема не указана"


def _humanize_error_type(error_type: str | None) -> str:
    if not error_type:
        return "ошибка требует уточнения"

    return ERROR_TYPE_LABELS.get(error_type, error_type)


def _extract_memory_item(item) -> tuple[str, str | None]:
    if isinstance(item, str):
        return item, None

    if isinstance(item, dict):
        topic = (
            item.get("topic")
            or item.get("skill_id")
            or item.get("name")
            or item.get("title")
            or "тема не указана"
        )

        error_type = item.get("error_type")

        return str(topic), error_type

    return str(item), None


def _unique_preserve_order(items: list[str]) -> list[str]:
    result = []
    seen = set()

    for item in items:
        if item not in seen:
            result.append(item)
            seen.add(item)

    return result


def _format_errors(last_errors: list, fallback_error_type: str | None) -> str | None:
    if not last_errors and not fallback_error_type:
        return None

    formatted = []

    for item in last_errors[-5:]:
        topic, error_type = _extract_memory_item(item)
        human_error = _humanize_error_type(error_type or fallback_error_type)
        formatted.append(f"{topic} — {human_error}")

    if not formatted and fallback_error_type:
        formatted.append(_humanize_error_type(fallback_error_type))

    unique_items = _unique_preserve_order(formatted)

    return "\n".join(f"• {item}" for item in unique_items)


def _format_successes(last_successes: list) -> str | None:
    if not last_successes:
        return None

    formatted = []

    for item in last_successes[-5:]:
        topic, _ = _extract_memory_item(item)
        formatted.append(topic)

    unique_items = _unique_preserve_order(formatted)

    return "\n".join(f"• {item}" for item in unique_items)


def _build_comment(
    status: str,
    next_focus: str,
    has_errors: bool,
    teacher_review_required: bool,
) -> str:
    if teacher_review_required:
        return (
            "Система рекомендует преподавателю обратить внимание на это решение "
            "и при необходимости дать ученику короткое дополнительное объяснение."
        )

    if status == "checked" and has_errors:
        return (
            f"У ученика есть повторяющаяся зона роста: {next_focus}. "
            "Рекомендуется закрепить этот навык короткой серией похожих заданий."
        )

    if status == "checked":
        return (
            "Задание проверено. Система обновила учебный профиль ученика "
            "и сохранила данные для дальнейшей индивидуальной траектории."
        )

    return (
        "Платформа отслеживает выполнение заданий, ошибки ученика "
        "и формирует индивидуальную траекторию обучения."
    )


def generate_parent_report() -> str:
    db = load_db()

    latest_assignment = _get_latest_student_homework(db)

    if not latest_assignment:
        return (
            "👨‍👩‍👧 Отчёт пока недоступен.\n\n"
            "В системе ещё нет назначенных домашних заданий."
        )

    student_id = latest_assignment.get("student_id")
    student = _find_user_by_telegram_id(db, student_id)

    student_name = "Ученик"

    if student:
        student_name = student.get("full_name") or student_name

    homework = _get_homework_by_id(
        db=db,
        homework_id=latest_assignment.get("homework_id"),
    )

    learning_dna = _get_learning_dna(db, student_id)

    topic = _get_homework_topic(homework)
    status = latest_assignment.get("status", "unknown")
    status_text = STATUS_LABELS.get(status, status)

    submitted_at = _format_dt(latest_assignment.get("submitted_at"))
    checked_at = _format_dt(latest_assignment.get("checked_at"))

    last_error_type = latest_assignment.get("last_error_type")
    teacher_review_required = latest_assignment.get(
        "teacher_review_required",
        False,
    )

    xp = 0
    next_focus = "Пока не определён"
    last_errors = []
    last_successes = []

    if learning_dna:
        motivation = learning_dna.get("motivation", {})
        trajectory = learning_dna.get("trajectory", {})
        memory = learning_dna.get("memory", {})

        if isinstance(motivation, dict):
            xp = motivation.get("xp", 0)

        if isinstance(trajectory, dict):
            next_focus = trajectory.get("next_focus") or next_focus

        if isinstance(memory, dict):
            last_errors = memory.get("last_errors", [])
            last_successes = memory.get("last_successes", [])

    errors_text = _format_errors(last_errors, last_error_type)
    successes_text = _format_successes(last_successes)

    report = (
        "👨‍👩‍👧 Отчёт для родителя\n\n"
        f"Ученик: {student_name}\n"
        f"Тема последнего задания: {topic}\n"
        f"Статус: {status_text}\n\n"
        "📌 Прогресс:\n"
        f"XP: {xp}\n"
        f"Следующий фокус: {next_focus}\n"
    )

    if errors_text:
        report += f"\n⚠️ Зоны роста:\n{errors_text}\n"

    if successes_text:
        report += f"\n✅ Последние успехи:\n{successes_text}\n"

    if submitted_at or checked_at:
        report += "\n🕒 Активность:\n"

        if submitted_at:
            report += f"Решение отправлено: {submitted_at}\n"

        if checked_at:
            report += f"Проверено: {checked_at}\n"

    if teacher_review_required:
        report += "\n⚠️ Требуется внимание преподавателя.\n"

    comment = _build_comment(
        status=status,
        next_focus=next_focus,
        has_errors=bool(errors_text),
        teacher_review_required=teacher_review_required,
    )

    report += f"\n💡 Комментарий:\n{comment}"

    return report