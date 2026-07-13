import unittest
import sys
from pathlib import Path
from unittest.mock import Mock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ai_engine.homework_checker import check_homework_text


class HomeworkCheckerTest(unittest.TestCase):
    @patch("src.ai_engine.homework_checker.LLMClient")
    def test_valid_provider_json_is_parsed(self, client_class):
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
        client_class.return_value = client

        result = check_homework_text(
            text="for i in range(1, 10): print(i)",
            task_text="Вывести числа от 1 до 10 включительно.",
            topic="Циклы",
            synthetic_test=True,
        )

        self.assertEqual(result["status"], "has_error")
        self.assertEqual(result["error_type"], "loop_error")
        self.assertFalse(result["needs_teacher_review"])
        client.check_homework_text.assert_called_once_with(
            text="for i in range(1, 10): print(i)",
            task_text="Вывести числа от 1 до 10 включительно.",
            topic="Циклы",
            synthetic_test=True,
        )

    @patch("src.ai_engine.homework_checker.LLMClient")
    def test_invalid_provider_response_becomes_unclear(
        self,
        client_class,
    ):
        client = Mock()
        client.check_homework_text.return_value = "not json"
        client_class.return_value = client

        result = check_homework_text(
            text="неполный ответ",
            synthetic_test=True,
        )

        self.assertEqual(result["status"], "unclear")
        self.assertTrue(result["needs_teacher_review"])

    @patch("src.ai_engine.homework_checker.LLMClient")
    def test_regular_student_text_is_not_sent_to_gemini(
        self,
        client_class,
    ):
        result = check_homework_text(text="ответ ученика")

        self.assertEqual(result["status"], "unclear")
        self.assertTrue(result["needs_teacher_review"])
        client_class.assert_not_called()


if __name__ == "__main__":
    unittest.main()
