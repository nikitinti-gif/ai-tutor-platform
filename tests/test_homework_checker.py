import unittest
import sys
from pathlib import Path
from unittest.mock import Mock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ai_engine.homework_checker import check_homework_text


class HomeworkCheckerTest(unittest.TestCase):
    def test_prompt_requires_simple_and_specific_feedback(self):
        from src.ai_engine.prompts import HOMEWORK_CHECK_SYSTEM_PROMPT

        self.assertIn(
            "понятными ученику 7–9 класса",
            HOMEWORK_CHECK_SYSTEM_PROMPT,
        )
        self.assertIn(
            "одно конкретное место ошибки",
            HOMEWORK_CHECK_SYSTEM_PROMPT,
        )
        self.assertIn(
            "не сообщать итоговый ответ",
            HOMEWORK_CHECK_SYSTEM_PROMPT,
        )

    @patch("src.ai_engine.homework_checker.create_text_provider")
    def test_valid_provider_json_is_parsed(self, provider_factory):
        client = Mock()
        client.check_homework_text.return_value = """
        {
            "status": "has_error",
            "confidence": 0.91,
            "feedback": "В условии цикла неверная граница.",
            "hint": "Какое последнее значение должен обработать цикл?",
            "error_type": "loop_error",
            "topic": "Циклы"
        }
        """
        provider_factory.return_value = client

        result = check_homework_text(
            text="for i in range(1, 10): print(i)",
            task_text="Вывести числа от 1 до 10 включительно.",
            topic="Циклы",
            synthetic_test=True,
        )

        self.assertEqual(result["status"], "has_error")
        self.assertEqual(result["error_type"], "loop_error")
        self.assertFalse(result["needs_teacher_review"])
        provider_factory.assert_called_once_with("gemini")
        client.check_homework_text.assert_called_once_with(
            text="for i in range(1, 10): print(i)",
            task_text="Вывести числа от 1 до 10 включительно.",
            topic="Циклы",
            synthetic_test=True,
        )

    @patch("src.ai_engine.homework_checker.create_text_provider")
    def test_invalid_provider_response_becomes_unclear(
        self,
        provider_factory,
    ):
        client = Mock()
        client.check_homework_text.return_value = "not json"
        provider_factory.return_value = client

        result = check_homework_text(
            text="неполный ответ",
            synthetic_test=True,
        )

        self.assertEqual(result["status"], "unclear")
        self.assertTrue(result["needs_teacher_review"])

    def test_incomplete_provider_response_becomes_unclear(self):
        from src.ai_engine.schemas import validate_homework_check_result

        result = validate_homework_check_result(
            {
                "status": "correct",
                "confidence": 0.99,
                "feedback": "Перевод выполнен верно.",
                "error_type": None,
                "topic": "Системы счисления",
            }
        )

        self.assertEqual(result["status"], "unclear")
        self.assertEqual(result["confidence"], 0.0)
        self.assertTrue(result["needs_teacher_review"])

    def test_contradictory_correct_response_becomes_unclear(self):
        from src.ai_engine.schemas import validate_homework_check_result

        result = validate_homework_check_result(
            {
                "status": "correct",
                "confidence": 1.0,
                "feedback": (
                    "В решении указано 16 + 8 + 2 = 26, "
                    "но правильный ответ — 22."
                ),
                "hint": "Пересчитай сумму степеней двойки.",
                "error_type": "calculation_error",
                "topic": "Системы счисления",
            }
        )

        self.assertEqual(result["status"], "unclear")
        self.assertEqual(result["confidence"], 0.0)
        self.assertTrue(result["needs_teacher_review"])

    def test_error_status_without_error_type_becomes_unclear(self):
        from src.ai_engine.schemas import validate_homework_check_result

        result = validate_homework_check_result(
            {
                "status": "has_error",
                "confidence": 0.99,
                "feedback": "В решении есть ошибка.",
                "hint": "Проверь вычисления.",
                "error_type": None,
                "topic": "Системы счисления",
            }
        )

        self.assertEqual(result["status"], "unclear")
        self.assertTrue(result["needs_teacher_review"])

    def test_yandex_binary_diagnostic_does_not_change_baseline(self):
        from src.ai_engine.evaluation import (
            SYNTHETIC_CASES,
            YANDEX_BINARY_DIAGNOSTIC_CASES,
        )

        self.assertEqual(len(SYNTHETIC_CASES), 15)
        self.assertEqual(len(YANDEX_BINARY_DIAGNOSTIC_CASES), 4)
        self.assertEqual(
            [case["id"] for case in YANDEX_BINARY_DIAGNOSTIC_CASES],
            [
                "unicode_abbreviated",
                "ascii_abbreviated",
                "ascii_full_expansion",
                "ascii_wrong_weight_control",
            ],
        )

    @patch("src.ai_engine.homework_checker.create_text_provider")
    def test_regular_student_text_is_not_sent_to_gemini(
        self,
        provider_factory,
    ):
        result = check_homework_text(text="ответ ученика")

        self.assertEqual(result["status"], "unclear")
        self.assertTrue(result["needs_teacher_review"])
        provider_factory.assert_not_called()

    @patch("src.ai_engine.homework_checker.create_text_provider")
    def test_selected_synthetic_provider_is_used(self, provider_factory):
        client = Mock()
        client.check_homework_text.return_value = """
        {
            "status": "correct",
            "confidence": 0.95,
            "feedback": "Верно.",
            "hint": "Следующая задача.",
            "error_type": null,
            "topic": "Циклы"
        }
        """
        provider_factory.return_value = client

        result = check_homework_text(
            text="for i in range(3): print(i)",
            synthetic_test=True,
            provider_name="mistral",
        )

        self.assertEqual(result["status"], "correct")
        provider_factory.assert_called_once_with("mistral")


if __name__ == "__main__":
    unittest.main()
