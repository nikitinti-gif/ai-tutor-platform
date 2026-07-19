import unittest
import sys
from pathlib import Path
from unittest.mock import Mock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ai_engine.homework_checker import check_homework_text


class HomeworkCheckerTest(unittest.TestCase):
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
            "topic": "Циклы",
            "error_evidence": "range(1, 10)",
            "error_explanation": "Правая граница range не включается."
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
        self.assertEqual(result["error_evidence"], "range(1, 10)")
        self.assertIn("Ошибка в фрагменте", result["feedback"])
        self.assertNotIn("В условии цикла", result["feedback"])
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

    @patch("src.ai_engine.homework_checker.create_text_provider")
    def test_has_error_without_exact_evidence_becomes_unclear(
        self,
        provider_factory,
    ):
        client = Mock()
        client.check_homework_text.return_value = """
        {
            "status": "has_error",
            "confidence": 0.99,
            "feedback": "Решение неверно.",
            "hint": "Проверь вычисление.",
            "error_type": "calculation_error",
            "topic": "Системы счисления",
            "error_evidence": "16 + 4 + 2 = 22",
            "error_explanation": "Указана неверная сумма."
        }
        """
        provider_factory.return_value = client

        result = check_homework_text(
            text="10110₂ = 16 + 8 + 2 = 26₁₀",
            synthetic_test=True,
        )

        self.assertEqual(result["status"], "unclear")
        self.assertEqual(result["confidence"], 0.0)
        self.assertTrue(result["needs_teacher_review"])

    @patch("src.ai_engine.homework_checker.create_text_provider")
    def test_has_error_feedback_is_built_from_evidence(
        self,
        provider_factory,
    ):
        client = Mock()
        client.check_homework_text.return_value = """
        {
            "status": "has_error",
            "confidence": 1.0,
            "feedback": "Ты верно определил веса разрядов.",
            "hint": "Какой вес имеет третий разряд справа?",
            "error_type": "calculation_error",
            "topic": "Системы счисления",
            "error_evidence": "16 + 8 + 2 = 26",
            "error_explanation": "Слагаемое 8 относится к нулевому разряду, а слагаемое 4 пропущено."
        }
        """
        provider_factory.return_value = client

        result = check_homework_text(
            text="10110₂ = 16 + 8 + 2 = 26₁₀",
            synthetic_test=True,
        )

        self.assertEqual(result["status"], "has_error")
        self.assertNotIn("верно определил", result["feedback"])
        self.assertIn("16 + 8 + 2 = 26", result["feedback"])
        self.assertEqual(
            result["provider_feedback"],
            "Ты верно определил веса разрядов.",
        )


if __name__ == "__main__":
    unittest.main()
