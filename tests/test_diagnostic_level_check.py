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
        client.critically_recheck_diagnostic.return_value = (
            client.check_diagnostic_levels.return_value
        )
        client_class.return_value = client
        result = check_diagnostic_transcription(
            student_solution="1) 21 2) 26 3) 37", topic="Системы счисления",
            tasks=[{"level": "Лёгкий", "task": "a", "teacher_answer": "a"}] * 3,
            synthetic_test=True,
        )
        self.assertEqual(result["status"], "correct")
        self.assertTrue(result["diagnostic_mastery"]["topic_mastered"])
        self.assertEqual([x["level"] for x in result["level_results"]], ["easy", "medium", "hard"])

    def test_confirmed_mastery_selects_next_curriculum_topic(self):
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
        self.assertEqual(
            updated["trajectory"]["next_focus"],
            "Арифметические операции в системах счисления",
        )
        self.assertTrue(updated["topic_mastery"]["Системы счисления"]["mastered"])
        skill = updated["skills"]["number_systems.base_conversion"]
        self.assertEqual(skill["attempts"], 3)
        self.assertEqual(skill["successes"], 3)
        self.assertNotIn("general_learning", updated["skills"])

    def test_gap_keeps_topic_as_focus(self):
        result = update_learning_dna_after_check(None, 1, {
            "status": "has_error", "confidence": .95, "topic": "Системы счисления",
            "error_type": "diagnostic_level_gap", "knowledge_boundary": "application",
            "diagnostic_mastery": {"base": True, "application": False, "transfer": False, "topic_mastered": False},
        })
        self.assertEqual(result["trajectory"]["next_focus"], "Системы счисления")
        self.assertEqual(result["topic_mastery"]["Системы счисления"]["knowledge_boundary"], "application")

    @patch("src.ai_engine.homework_checker.LLMClient")
    def test_wrong_minimum_counterexample_overrides_model_correct(self, client_class):
        client = Mock()
        client.check_diagnostic_levels.return_value = '''{
          "level_results": [
            {"level":"easy","status":"correct","confidence":1.0,"evidence":"13","feedback":"Верно"},
            {"level":"medium","status":"correct","confidence":1.0,"evidence":"21","feedback":"Верно"},
            {"level":"hard","status":"correct","confidence":0.95,"evidence":"n = 10","feedback":"Верно"}
          ],
          "knowledge_boundary": null,
          "recommended_action": "Тема полностью освоена"
        }'''
        client.critically_recheck_diagnostic.return_value = (
            client.check_diagnostic_levels.return_value
        )
        client_class.return_value = client
        result = check_diagnostic_transcription(
            student_solution=(
                "1. Ответ: 13\n2. Ответ: 21\n3. Сложный уровень\n"
                "Минимальный контрпример: n = 10.\n"
                "Исправленное условие: пока n > 0."
            ),
            topic="Алгоритмы и исполнители",
            tasks=self._algorithm_tasks(),
            synthetic_test=True,
        )
        hard = result["level_results"][2]
        self.assertEqual(result["status"], "has_error")
        self.assertEqual(hard["status"], "has_error")
        self.assertEqual(result["knowledge_boundary"], "hard")
        self.assertFalse(result["diagnostic_mastery"]["topic_mastered"])
        self.assertNotIn("полностью освоена", result["hint"])
        result["skill_id"] = "algorithms.tracing"
        dna = update_learning_dna_after_check(None, 1, result)
        skill = dna["skills"]["algorithms.tracing"]
        self.assertEqual(skill["attempts"], 3)
        self.assertEqual(skill["successes"], 2)
        self.assertEqual(skill["mistakes"], 1)
        self.assertFalse(
            dna["topic_mastery"]["Алгоритмы и исполнители"]["mastered"]
        )

    @patch("src.ai_engine.homework_checker.LLMClient")
    def test_correct_minimum_counterexample_remains_correct(self, client_class):
        client = Mock()
        client.check_diagnostic_levels.return_value = '''{
          "level_results": [
            {"level":"easy","status":"correct","confidence":1.0,"evidence":"13","feedback":"Верно"},
            {"level":"medium","status":"correct","confidence":1.0,"evidence":"21","feedback":"Верно"},
            {"level":"hard","status":"correct","confidence":0.95,"evidence":"n = 1","feedback":"Верно"}
          ],
          "knowledge_boundary": null,
          "recommended_action": "Перейти к следующей теме"
        }'''
        client.critically_recheck_diagnostic.return_value = (
            client.check_diagnostic_levels.return_value
        )
        client_class.return_value = client
        result = check_diagnostic_transcription(
            student_solution=(
                "1. Ответ: 13\n2. Ответ: 21\n3. Сложный уровень\n"
                "Минимальный контрпример: n = 1.\n"
                "Исправленное условие: пока n > 0."
            ),
            topic="Алгоритмы и исполнители",
            tasks=self._algorithm_tasks(),
            synthetic_test=True,
        )
        self.assertEqual(result["status"], "correct")
        self.assertTrue(result["diagnostic_mastery"]["topic_mastered"])

    @patch("src.ai_engine.homework_checker.LLMClient")
    def test_disagreement_becomes_unclear_and_blocks_mastery(self, client_class):
        client = Mock()
        client.check_diagnostic_levels.return_value = '''{
          "level_results": [
            {"level":"easy","status":"correct","confidence":0.98,"evidence":"13","feedback":"Верно"},
            {"level":"medium","status":"correct","confidence":0.97,"evidence":"21","feedback":"Верно"},
            {"level":"hard","status":"correct","confidence":0.95,"evidence":"ответ","feedback":"Верно"}
          ],
          "knowledge_boundary": null,
          "recommended_action": "Освоено"
        }'''
        client.critically_recheck_diagnostic.return_value = '''{
          "level_results": [
            {"level":"easy","status":"correct","confidence":0.99,"evidence":"13","feedback":"Верно"},
            {"level":"medium","status":"correct","confidence":0.99,"evidence":"21","feedback":"Верно"},
            {"level":"hard","status":"has_error","confidence":0.94,"evidence":"ответ","feedback":"Пропущено условие"}
          ],
          "knowledge_boundary": "hard",
          "recommended_action": "Проверить сложный уровень"
        }'''
        client_class.return_value = client
        result = check_diagnostic_transcription(
            student_solution="1. 13\n2. 21\n3. ответ",
            topic="Алгоритмы и исполнители",
            tasks=[
                {"level": "Лёгкий", "task": "a", "teacher_answer": "13"},
                {"level": "Средний", "task": "b", "teacher_answer": "21"},
                {"level": "Сложный", "task": "c", "teacher_answer": "эталон"},
            ],
            synthetic_test=True,
        )
        self.assertEqual(result["status"], "unclear")
        self.assertEqual(result["recheck_status"], "disagreement")
        self.assertEqual(result["level_results"][2]["status"], "unclear")
        self.assertFalse(result["diagnostic_mastery"]["topic_mastered"])
        self.assertTrue(result["needs_teacher_review"])

    @staticmethod
    def _algorithm_tasks():
        return [
            {"level": "Лёгкий", "task": "Найди x.", "teacher_answer": "13"},
            {"level": "Средний", "task": "Найди s.", "teacher_answer": "21"},
            {
                "level": "Сложный",
                "task": "Найди минимальный контрпример.",
                "teacher_answer": "Минимальный контрпример — n = 1.",
            },
        ]


if __name__ == "__main__":
    unittest.main()
