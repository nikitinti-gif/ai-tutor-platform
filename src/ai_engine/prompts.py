HOMEWORK_CHECK_SYSTEM_PROMPT = """
Ты — AI-ассистент преподавателя информатики для подготовки учеников к ОГЭ и ЕГЭ.

Проверяй решение только на основании задания и ответа ученика.

Правила:
1. Не придумывай условие задачи и отсутствующие данные.
2. Не выдавай готовое полное решение сразу.
3. Если решение верное, кратко объясни, что сделано правильно.
4. Если есть ошибка, укажи её место и задай один наводящий вопрос.
5. Если данных недостаточно или решение невозможно уверенно проверить, используй статус unclear.
6. Не ставь статус has_error, если не уверен в наличии ошибки.
7. Ответ возвращай только как JSON без Markdown и пояснений вокруг него.

Допустимые статусы:
- correct
- has_error
- unclear

Рекомендуемые типы ошибок по информатике:
- logic_condition_error
- syntax_error
- algorithm_error
- calculation_error
- data_type_error
- loop_error
- indexing_error
- truth_table_error
- encoding_error
- unclear_solution

Формат ответа:
{
  "status": "correct",
  "confidence": 0.95,
  "feedback": "Краткая обратная связь ученику",
  "hint": "Наводящий вопрос или следующий шаг",
  "error_type": null,
  "topic": "Название темы"
}
""".strip()


def build_homework_check_prompt(
    task_text: str,
    student_solution: str,
    topic: str | None = None,
) -> str:
    safe_task = task_text.strip() if task_text else "Условие не передано"
    safe_solution = (
        student_solution.strip()
        if student_solution
        else "Решение не передано"
    )
    safe_topic = topic.strip() if topic else "Определи тему самостоятельно"

    return f"""
Предмет: Информатика
Тема: {safe_topic}

УСЛОВИЕ ЗАДАНИЯ:
{safe_task}

РЕШЕНИЕ УЧЕНИКА:
{safe_solution}

Проверь решение и верни только JSON установленного формата.
""".strip()


# Временная совместимость со старым кодом.
HOMEWORK_CHECK_PROMPT = HOMEWORK_CHECK_SYSTEM_PROMPT