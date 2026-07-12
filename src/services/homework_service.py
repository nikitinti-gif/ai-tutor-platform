from src.ai_engine.homework_generator import (
    generate_homework_object,
    render_homework_for_student,
)


def generate_homework_by_topic(topic: str) -> dict:
    return generate_homework_object(topic)


def format_homework_for_student(homework: dict) -> str:
    return render_homework_for_student(homework)