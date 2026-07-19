import unittest

from src.services.learning_dna_service import format_learning_dna_for_teacher


class LearningDNAServiceTest(unittest.TestCase):
    def test_teacher_card_summarizes_confirmed_signals(self):
        dna = {
            "student_id": -42,
            "signals": [
                {"type": "mistake", "topic": "Системы счисления"},
                {"type": "success", "topic": "Условные операторы"},
            ],
            "skills": {
                "general_learning": {
                    "skill_level": 46,
                    "attempts": 2,
                    "trend": "down",
                }
            },
            "motivation": {"xp": 25},
            "trajectory": {
                "next_focus": "Системы счисления",
                "recommendations": ["Добавить 2–3 задания."],
            },
            "updated_at": "2026-07-19T12:00:00",
        }

        text = format_learning_dna_for_teacher(dna)

        self.assertIn("Подтверждённых сигналов: 2", text)
        self.assertIn("Условные операторы (1)", text)
        self.assertIn("Системы счисления (1)", text)
        self.assertIn("Следующий фокус: Системы счисления", text)
        self.assertIn("general_learning: уровень 46", text)

    def test_empty_profile_is_explicit(self):
        text = format_learning_dna_for_teacher(
            {"student_id": 1, "signals": [], "trajectory": {}}
        )

        self.assertIn("Подтверждённых сигналов: 0", text)
        self.assertIn("Сначала накопить", text)
        self.assertIn("данных пока нет", text)


if __name__ == "__main__":
    unittest.main()
