import unittest
from datetime import datetime, timezone

from src.services.teacher_submission_queue_service import (
    format_teacher_submission_detail,
    format_teacher_submission_queue,
)


class TeacherSubmissionQueueServiceTest(unittest.TestCase):
    def test_empty_queue(self):
        self.assertEqual(
            format_teacher_submission_queue([]),
            "📸 Очередь работ пуста.",
        )

    def test_queue_separates_synthetic_and_real(self):
        submissions = [
            {
                "submission_id": "sub_syn",
                "student_telegram_id": -100,
                "is_synthetic": True,
                "status": "teacher_review",
                "analysis_result": {
                    "status": "has_error",
                    "confidence": 1.0,
                },
                "created_at": datetime(2026, 7, 19, 10, 0, tzinfo=timezone.utc),
            },
            {
                "submission_id": "sub_real",
                "student_telegram_id": 200,
                "is_synthetic": False,
                "status": "accepted",
                "analysis_result": None,
                "created_at": datetime(2026, 7, 19, 11, 0, tzinfo=timezone.utc),
            },
        ]

        result = format_teacher_submission_queue(submissions)

        self.assertIn("🧪 Синтетических: 1", result)
        self.assertIn("👤 Реальных: 1", result)
        self.assertIn("sub_syn", result)
        self.assertIn("AI: has_error, уверенность 1.00", result)
        self.assertIn("sub_real", result)
        self.assertIn("Бесплатный Gemini", result)

    def test_failed_item_shows_short_error(self):
        result = format_teacher_submission_queue([
            {
                "submission_id": "sub_failed",
                "is_synthetic": True,
                "status": "failed",
                "last_error": "timeout" * 100,
                "created_at": None,
            }
        ])

        self.assertIn("ошибка обработки", result)
        self.assertIn("Ошибка: timeout", result)
        self.assertLess(len(result), 1000)

    def test_synthetic_detail_contains_full_analysis(self):
        result = format_teacher_submission_detail({
            "submission_id": "sub_syn",
            "student_telegram_id": -100,
            "is_synthetic": True,
            "status": "teacher_review",
            "photo_width": 1024,
            "photo_height": 1536,
            "created_at": None,
            "analysis_result": {
                "status": "has_error",
                "confidence": 1.0,
                "error_type": "calculation_error",
                "image_transcription": "16 + 8 + 2 = 26",
                "feedback": "Ошибка в разложении.",
                "hint": "Проверь веса разрядов.",
            },
        })

        self.assertIn("🧪 Синтетическая работа", result)
        self.assertIn("Транскрипция:", result)
        self.assertIn("16 + 8 + 2 = 26", result)
        self.assertIn("Ошибка в разложении.", result)

    def test_real_detail_says_ai_was_not_started(self):
        result = format_teacher_submission_detail({
            "submission_id": "sub_real",
            "is_synthetic": False,
            "status": "accepted",
            "analysis_result": None,
        })

        self.assertIn("👤 Реальная работа", result)
        self.assertIn("AI-анализ не запускался", result)


if __name__ == "__main__":
    unittest.main()
