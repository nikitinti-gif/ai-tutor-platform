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
