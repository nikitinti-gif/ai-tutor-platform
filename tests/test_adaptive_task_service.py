import unittest

from src.services.adaptive_task_service import (
    build_adaptive_task_draft,
    format_adaptive_task_draft_for_teacher,
    format_adaptive_task_set_for_family,
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
        self.assertEqual(len(draft["draft_token"]), 16)

    def test_unknown_topic_does_not_generate_placeholder_tasks(self):
        with self.assertRaisesRegex(ValueError, "нет проверенного шаблона"):
            build_adaptive_task_draft(
                {"trajectory": {"next_focus": "Неизвестная тема"}}
            )

    def test_builds_verified_arithmetic_levels_for_next_focus(self):
        draft = build_adaptive_task_draft(
            {
                "student_id": -42,
                "trajectory": {
                    "next_focus": "Арифметические операции в системах счисления"
                },
            }
        )

        self.assertEqual(
            draft["topic"], "Арифметические операции в системах счисления"
        )
        self.assertEqual(
            [task["level"] for task in draft["tasks"]],
            ["Лёгкий", "Средний", "Сложный"],
        )
        self.assertIn("1011₂ + 0110₂", draft["tasks"][0]["task"])
        self.assertIn("26 − 11 = 15", draft["tasks"][1]["teacher_answer"])
        self.assertIn("110111₂", draft["tasks"][2]["teacher_answer"])
        self.assertTrue(all(task["purpose"] for task in draft["tasks"]))

    def test_arithmetic_family_render_hides_verified_answers(self):
        task_set = build_adaptive_task_draft(
            {
                "student_id": -42,
                "trajectory": {
                    "next_focus": "Арифметические операции в системах счисления"
                },
            }
        )
        task_set["task_set_id"] = "diag_arithmetic"

        text = format_adaptive_task_set_for_family(task_set)

        self.assertIn("1011₂ + 0110₂", text)
        self.assertIn("Номер набора: diag_arithmetic", text)
        self.assertNotIn("10001₂ (11 + 6 = 17)", text)
        self.assertNotIn("26 − 11 = 15", text)
        self.assertNotIn("110111₂", text)
        self.assertNotIn("Цель:", text)

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
        self.assertIn("степеням двойки", text)

    def test_family_render_hides_answers_purposes_and_dna(self):
        task_set = build_adaptive_task_draft({
            "student_id": -42,
            "trajectory": {"next_focus": "Системы счисления"},
        })
        task_set["task_set_id"] = "diag_test"

        text = format_adaptive_task_set_for_family(task_set)

        self.assertIn("10101₂", text)
        self.assertIn("Номер набора: diag_test", text)
        self.assertNotIn("Ответ для преподавателя", text)
        self.assertNotIn("21₁₀", text)
        self.assertNotIn("Цель:", text)
        self.assertNotIn("ДНК", text)


if __name__ == "__main__":
    unittest.main()
