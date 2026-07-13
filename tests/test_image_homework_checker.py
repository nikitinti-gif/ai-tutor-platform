import unittest
from unittest.mock import Mock, patch

from src.ai_engine.homework_checker import check_homework_image


class ImageHomeworkCheckerTest(unittest.TestCase):
    @patch("src.ai_engine.homework_checker.LLMClient")
    def test_synthetic_image_response_is_parsed(self, client_class):
        client = Mock()
        client.check_homework_image.return_value = """
        {
            "status": "correct",
            "confidence": 0.96,
            "feedback": "Цикл записан верно.",
            "hint": "Проверь вывод на границах диапазона.",
            "error_type": null,
            "topic": "Циклы Python"
        }
        """
        client_class.return_value = client

        result = check_homework_image(
            image_bytes=b"synthetic-image",
            mime_type="image/jpeg",
            task_text="Вывести числа от 1 до 10 включительно.",
            topic="Циклы Python",
            synthetic_test=True,
        )

        self.assertEqual(result["status"], "correct")
        client.check_homework_image.assert_called_once()

    @patch("src.ai_engine.homework_checker.LLMClient")
    def test_real_image_is_not_sent_to_gemini(self, client_class):
        result = check_homework_image(
            image_bytes=b"real-image",
            mime_type="image/jpeg",
        )

        self.assertEqual(result["status"], "unclear")
        self.assertTrue(result["needs_teacher_review"])
        client_class.assert_not_called()


if __name__ == "__main__":
    unittest.main()
