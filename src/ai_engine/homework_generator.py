from datetime import datetime


def generate_homework_object(topic: str) -> dict:
    if topic.strip().casefold() == "условные операторы":
        return {
            "topic": "Условные операторы",
            "theory": (
                "Повтори конструкцию if / elif / else и обрати внимание, "
                "что условия проверяются сверху вниз."
            ),
            "tasks": [
                (
                    "Напиши программу на Python. Программа считывает одно "
                    "целое число x. Если x больше 0, выведи positive; если "
                    "x меньше 0, выведи negative; если x равно 0, выведи zero."
                )
            ],
            "difficulty": "basic",
            "estimated_time_minutes": 10,
            "created_by": "local_verified_template",
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }

    return {
        "topic": topic,
        "theory": f"Повтори основные правила и формулы по теме: {topic}.",
        "tasks": [
            f"Задание 1 по теме «{topic}»: базовый уровень.",
            f"Задание 2 по теме «{topic}»: базовый уровень.",
            f"Задание 3 по теме «{topic}»: средний уровень.",
            f"Задание 4 по теме «{topic}»: средний уровень.",
            f"Задание 5 по теме «{topic}»: повышенный уровень.",
        ],
        "difficulty": "medium",
        "estimated_time_minutes": 35,
        "created_by": "local_ai_stub",
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }


def render_homework_for_student(homework: dict) -> str:
    tasks_text = ""

    for index, task in enumerate(homework["tasks"], start=1):
        tasks_text += f"{index}. {task}\n"

    return (
        f"📚 Домашнее задание\n\n"
        f"Тема: {homework['topic']}\n\n"
        f"📖 Теория:\n{homework['theory']}\n\n"
        f"📝 Задания:\n{tasks_text}\n"
        f"⏱ Примерное время: {homework['estimated_time_minutes']} минут\n"
        f"🎯 Сложность: {homework['difficulty']}\n\n"
        f"После выполнения нажми 📸 Проверить решение и отправь решение текстом."
    )
