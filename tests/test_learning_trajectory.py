import unittest

from src.learning_dna.engine import restore_next_focus_from_mastery
from src.learning_dna.trajectory import select_next_topic


class LearningTrajectoryTest(unittest.TestCase):
    def test_restores_missing_focus_for_legacy_mastered_profile(self):
        dna = {
            "trajectory": {"next_focus": None, "recommendations": []},
            "topic_mastery": {
                "Системы счисления": {"mastered": True},
            },
        }

        changed = restore_next_focus_from_mastery(dna)

        self.assertTrue(changed)
        self.assertEqual(
            dna["trajectory"]["next_focus"],
            "Арифметические операции в системах счисления",
        )

    def test_does_not_overwrite_existing_focus(self):
        dna = {
            "trajectory": {"next_focus": "Основы логики"},
            "topic_mastery": {
                "Системы счисления": {"mastered": True},
            },
        }

        changed = restore_next_focus_from_mastery(dna)

        self.assertTrue(changed)
        self.assertEqual(dna["trajectory"]["next_focus"], "Основы логики")
        self.assertEqual(dna["trajectory"]["next_focus_skill_id"], "logic.operations")

    def test_selects_topic_after_completed_one(self):
        self.assertEqual(
            select_next_topic("Системы счисления"),
            "Арифметические операции в системах счисления",
        )

    def test_repairs_zero_attempts_for_legacy_three_level_mastery(self):
        dna = {
            "skills": {"logic.operations": {
                "skill_id": "logic.operations", "attempts": 0,
                "successes": 0, "evidence_count": 0, "mastered": True,
            }},
            "topic_mastery": {"Основы логики": {
                "base": True, "application": True, "transfer": True,
                "mastered": True,
            }},
            "trajectory": {"next_focus": "Алгоритмы и исполнители"},
        }
        self.assertTrue(restore_next_focus_from_mastery(dna))
        skill = dna["skills"]["logic.operations"]
        self.assertEqual(skill["attempts"], 3)
        self.assertEqual(skill["successes"], 3)
        self.assertEqual(skill["evidence_count"], 3)

    def test_skips_already_mastered_topics(self):
        mastery = {
            "Арифметические операции в системах счисления": {"mastered": True},
        }
        self.assertEqual(
            select_next_topic("Системы счисления", mastery),
            "Кодирование информации",
        )

    def test_unknown_topic_requires_teacher_choice(self):
        self.assertIsNone(select_next_topic("Неизвестная тема"))

    def test_end_of_sequence_requires_teacher_choice(self):
        self.assertIsNone(select_next_topic("Циклы"))


if __name__ == "__main__":
    unittest.main()
