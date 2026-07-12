from datetime import datetime


def generate_homework_object(topic: str) -> dict:
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
        f"После решения отправь фото через кнопку 📸 Проверить решение."
    )