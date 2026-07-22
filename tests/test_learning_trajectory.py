import unittest

from src.learning_dna.trajectory import select_next_topic


class LearningTrajectoryTest(unittest.TestCase):
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
