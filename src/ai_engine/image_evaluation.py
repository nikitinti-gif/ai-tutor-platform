from pathlib import Path

from src.ai_engine.homework_checker import check_homework_image


PROJECT_ROOT = Path(__file__).resolve().parents[2]

FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"

SYNTHETIC_IMAGE_CASES = [
    {
        "id": "loop_handwritten_correct",
        "topic": "Циклы Python",
        "task": (
            "Вывести целые числа от 1 до 10 включительно, "
            "каждое с новой строки."
        ),
        "image_path": FIXTURES_DIR / "synthetic_loop_correct.jpg",
        "mime_type": "image/jpeg",
        "expected": "correct",
    },
    {
        "id": "loop_handwritten_off_by_one",
        "topic": "Циклы Python",
        "task": (
            "Вывести целые числа от 1 до 10 включительно, "
            "каждое с новой строки."
        ),
        "image_path": FIXTURES_DIR / "synthetic_loop_error.jpg",
        "mime_type": "image/jpeg",
        "expected": "has_error",
    },
    {
        "id": "binary_handwritten_correct",
        "topic": "Системы счисления",
        "task": (
            "Перевести двоичное число 10110 в десятичную систему."
        ),
        "image_path": FIXTURES_DIR / "synthetic_binary_correct.jpg",
        "mime_type": "image/jpeg",
        "expected": "correct",
    },
    {
        "id": "binary_handwritten_error",
        "topic": "Системы счисления",
        "task": (
            "Перевести двоичное число 10110 в десятичную систему."
        ),
        "image_path": FIXTURES_DIR / "synthetic_binary_error.jpg",
        "mime_type": "image/jpeg",
        "expected": "has_error",
    },
    {
        "id": "unreadable_handwritten_solution",
        "topic": "Ввод и вывод Python",
        "task": "Вводится целое число. Вывести его квадрат.",
        "image_path": FIXTURES_DIR / "synthetic_unreadable.jpg",
        "mime_type": "image/jpeg",
        "expected": "unclear",
    },
]


def evaluate_synthetic_image_case(case: dict | None = None) -> dict:
    selected_case = case or SYNTHETIC_IMAGE_CASES[0]
    image_path = Path(selected_case["image_path"])
    image_bytes = image_path.read_bytes()

    result = check_homework_image(
        image_bytes=image_bytes,
        mime_type=selected_case["mime_type"],
        task_text=selected_case["task"],
        topic=selected_case["topic"],
        synthetic_test=True,
    )
    actual = result["status"]

    return {
        "id": selected_case["id"],
        "expected": selected_case["expected"],
        "actual": actual,
        "match": actual == selected_case["expected"],
        "confidence": result["confidence"],
        "feedback": result["feedback"],
        "hint": result["hint"],
        "error_type": result["error_type"],
    }
