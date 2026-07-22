import unittest
from unittest.mock import Mock, patch

from src.ai_engine.homework_checker import check_diagnostic_transcription
from src.learning_dna.engine import update_learning_dna_after_check


class DiagnosticLevelCheckTest(unittest.TestCase):
    @patch("src.ai_engine.homework_checker.LLMClient")
    def test_three_correct_levels_produce_mastery(self, client_class):
        client = Mock()
        client.check_diagnostic_levels.return_value = '''{
          "level_results": [
            {"level":"easy","status":"correct","confidence":0.99,"evidence":"21","feedback":"Верно"},
            {"level":"medium","status":"correct","confidence":0.98,"evidence":"26","feedback":"Верно"},
            {"level":"hard","status":"correct","confidence":0.97,"evidence":"37","feedback":"Верно"}
          ],
          "knowledge_boundary": null,
          "recommended_action": "Перейти к следующей теме"
        }'''
        client_class.return_value = client
        result = check_diagnostic_transcription(
            student_solution="1) 21 2) 26 3) 37", topic="Системы счисления",
            tasks=[{"level": "Лёгкий", "task": "a", "teacher_answer": "a"}] * 3,
            synthetic_test=True,
        )
        self.assertEqual(result["status"], "correct")
        self.assertTrue(result["diagnostic_mastery"]["topic_mastered"])
        self.assertEqual([x["level"] for x in result["level_results"]], ["easy", "medium", "hard"])

    def test_confirmed_mastery_clears_old_focus(self):
        current = {
            "student_id": 1, "signals": [], "skills": {},
            "memory": {"last_topics": [], "last_errors": [], "last_successes": []},
            "motivation": {"xp": 0, "streak_days": 0},
            "trajectory": {"next_focus": "Системы счисления", "recommendations": []},
        }
        updated = update_learning_dna_after_check(current, 1, {
            "status": "correct", "confidence": .97, "topic": "Системы счисления",
            "error_type": None, "diagnostic_mastery": {
                "base": True, "application": True, "transfer": True,
                "topic_mastered": True,
            }, "knowledge_boundary": None,
        })
        self.assertIsNone(updated["trajectory"]["next_focus"])
        self.assertTrue(updated["topic_mastery"]["Системы счисления"]["mastered"])

    def test_gap_keeps_topic_as_focus(self):
        result = update_learning_dna_after_check(None, 1, {
            "status": "has_error", "confidence": .95, "topic": "Системы счисления",
            "error_type": "diagnostic_level_gap", "knowledge_boundary": "application",
            "diagnostic_mastery": {"base": True, "application": False, "transfer": False, "topic_mastered": False},
        })
        self.assertEqual(result["trajectory"]["next_focus"], "Системы счисления")
        self.assertEqual(result["topic_mastery"]["Системы счисления"]["knowledge_boundary"], "application")


if __name__ == "__main__":
    unittest.main()
