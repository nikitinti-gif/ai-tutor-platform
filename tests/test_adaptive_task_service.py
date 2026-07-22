import unittest

from src.services.adaptive_task_service import (
    build_adaptive_task_draft,
    format_adaptive_task_draft_for_teacher,
)


class AdaptiveTaskServiceTest(unittest.TestCase):
    def test_builds_three_verified_levels_for_current_focus(self):
        dna = {
            "student_id": -42,
            "trajectory": {"next_focus": "Системы счисления"},
        }

        draft = build_adaptive_task_draft(dna)

        self.assertEqual(draft["status"], "teacher_draft")
        self.assertEqual(
            [task["level"] for task in draft["tasks"]],
            ["Лёгкий", "Средний", "Сложный"],
        )
        self.assertTrue(all(task["teacher_answer"] for task in draft["tasks"]))

    def test_unknown_topic_does_not_generate_placeholder_tasks(self):
        with self.assertRaisesRegex(ValueError, "нет проверенного шаблона"):
            build_adaptive_task_draft(
                {"trajectory": {"next_focus": "Неизвестная тема"}}
            )

    def test_teacher_render_marks_draft_as_unsent(self):
        draft = build_adaptive_task_draft(
            {
                "student_id": -42,
                "trajectory": {"next_focus": "Системы счисления"},
            }
        )

        text = format_adaptive_task_draft_for_teacher(draft)

        self.assertIn("Лёгкий уровень", text)
        self.assertIn("Средний уровень", text)
        self.assertIn("Сложный уровень", text)
        self.assertIn("никому не отправлен", text)


if __name__ == "__main__":
    unittest.main()
