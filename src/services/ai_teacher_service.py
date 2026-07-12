def generate_ai_teacher_feedback(
    check_result: dict,
    learning_dna: dict | None,
    pedagogical_decision: dict,
) -> str:
    status = check_result.get("status")
    feedback = check_result.get("feedback", "")
    hint = check_result.get("hint", "")
    error_type = check_result.get("error_type")
    reasoning = pedagogical_decision.get("reasoning", "")
    action_plan = pedagogical_decision.get("action_plan", [])

    student_actions = []

    for action in action_plan:
        action_lower = action.lower()

        if (
            "уведом" in action_lower
            or "преподав" in action_lower
            or "ручн" in action_lower
        ):
            continue

        student_actions.append(action)

    actions_text = ""

    for index, action in enumerate(student_actions, start=1):
        actions_text += f"{index}. {action}\n"

    if not actions_text:
        actions_text = "Продолжай обучение."

    if status == "correct":
        return (
            "✅ Решение выглядит верным.\n\n"
            f"{feedback}\n\n"
            "🧠 Что это значит:\n"
            f"{reasoning}\n\n"
            "🎯 Следующий шаг:\n"
            f"{actions_text}"
        )

    if status == "has_error":
        return (
            "🟡 В решении есть место, которое нужно перепроверить.\n\n"
            f"{feedback}\n\n"
            f"❓ Наводящий вопрос:\n{hint}\n\n"
            "🧠 Почему это важно:\n"
            f"{reasoning}\n\n"
            "🎯 Что сделать дальше:\n"
            f"{actions_text}"
        )

    return (
        "🔴 Нужна проверка преподавателя.\n\n"
        f"{feedback}\n\n"
        f"💡 Рекомендация:\n{hint}\n\n"
        "🧠 Причина:\n"
        f"{reasoning}\n\n"
        "🎯 План:\n"
        f"{actions_text}"
    )