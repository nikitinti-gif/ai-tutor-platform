class LLMClient:
    """
    Временный LLM-клиент для MVP.

    Сейчас он работает как rule-based stub:
    - не обращается к платному API;
    - возвращает JSON-строку;
    - совместим с homework_checker.py.
    """

    def ask(self, prompt: str) -> str:
        return ask_llm(prompt)

    def complete(self, prompt: str) -> str:
        return ask_llm(prompt)

    def generate(self, prompt: str) -> str:
        return ask_llm(prompt)


def ask_llm(prompt: str) -> str:
    text = prompt.lower()

    if "не знаю" in text or "непонятно" in text:
        return """
{
    "status": "unclear",
    "topic": "Информатика",
    "feedback": "Решение недостаточно понятно для автоматической проверки.",
    "hint": "Опиши алгоритм пошагово: какие данные вводятся, какое условие проверяется и что выводится.",
    "error_type": "unclear_solution",
    "confidence": 0.6,
    "needs_teacher_review": true
}
"""

    if (
        "ошибка" in text
        or "неверно" in text
        or "x < 10" in text
        or "else" in text
        or "иначе" in text
    ):
        return """
{
    "status": "has_error",
    "topic": "Информатика",
    "feedback": "В решении есть ошибка в логике условия.",
    "hint": "Проверь, правильно ли записано условие и соответствует ли ветка else противоположному случаю.",
    "error_type": "logic_condition_error",
    "confidence": 0.82,
    "needs_teacher_review": false
}
"""

    return """
{
    "status": "correct",
    "topic": "Информатика",
    "feedback": "Решение выглядит логически верным.",
    "hint": "Можешь попробовать записать этот же алгоритм в виде блок-схемы или кода.",
    "error_type": null,
    "confidence": 0.9,
    "needs_teacher_review": false
}
"""