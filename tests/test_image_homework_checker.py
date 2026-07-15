import unittest
from unittest.mock import Mock, patch

from src.ai_engine.homework_checker import check_homework_image
from src.ai_engine.image_evaluation import SYNTHETIC_IMAGE_CASES


class ImageHomeworkCheckerTest(unittest.TestCase):
    def test_all_synthetic_image_fixtures_exist(self):
        self.assertEqual(len(SYNTHETIC_IMAGE_CASES), 5)
        for case in SYNTHETIC_IMAGE_CASES:
            self.assertTrue(case["image_path"].is_file(), case["id"])

    @patch("src.ai_engine.homework_checker.LLMClient")
    def test_synthetic_image_response_is_parsed(self, client_class):
        client = Mock()
        client.transcribe_homework_image.return_value = """
        {
            "legibility": "readable",
            "confidence": 0.98,
            "transcription": "for i in range(1, 11):\\n    print(i)"
        }
        """
        client.check_homework_text.return_value = """
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
        self.assertEqual(result["image_legibility"], "readable")
        client.transcribe_homework_image.assert_called_once()
        client.check_homework_text.assert_called_once()

    @patch("src.ai_engine.homework_checker.LLMClient")
    def test_unreadable_image_is_not_checked_as_solution(
        self,
        client_class,
    ):
        client = Mock()
        client.transcribe_homework_image.return_value = """
        {
            "legibility": "unreadable",
            "confidence": 0.99,
            "transcription": ""
        }
        """
        client_class.return_value = client

        result = check_homework_image(
            image_bytes=b"blurred-synthetic-image",
            mime_type="image/jpeg",
            task_text="Вводится число. Вывести его квадрат.",
            synthetic_test=True,
        )

        self.assertEqual(result["status"], "unclear")
        self.assertEqual(result["error_type"], "unreadable_image")
        client.check_homework_text.assert_not_called()

    @patch("src.ai_engine.homework_checker.LLMClient")
    def test_real_image_is_not_sent_to_gemini(self, client_class):
        result = check_homework_image(
            image_bytes=b"real-image",
            mime_type="image/jpeg",
        )

        self.assertEqual(result["status"], "unclear")
        self.assertTrue(result["needs_teacher_review"])
        client_class.assert_not_called()

    @patch("src.ai_engine.homework_checker.create_text_provider")
    def test_qwen_image_uses_qwen_for_both_steps(self, factory):
        client = Mock()
        client.transcribe_homework_image.return_value = """
        {
            "legibility": "readable",
            "confidence": 0.97,
            "transcription": "for i in range(1, 11): print(i)"
        }
        """
        client.check_homework_text.return_value = """
        {
            "status": "correct",
            "confidence": 0.95,
            "feedback": "Цикл верный.",
            "hint": "Проверь границы диапазона.",
            "error_type": null,
            "topic": "Циклы Python"
        }
        """
        factory.return_value = client

        result = check_homework_image(
            image_bytes=b"synthetic-image",
            mime_type="image/jpeg",
            task_text="Вывести числа от 1 до 10.",
            topic="Циклы Python",
            synthetic_test=True,
            provider_name="qwen",
        )

        self.assertEqual(result["status"], "correct")
        factory.assert_called_once_with("qwen")
        client.transcribe_homework_image.assert_called_once()
        client.check_homework_text.assert_called_once()


if __name__ == "__main__":
    unittest.main()
