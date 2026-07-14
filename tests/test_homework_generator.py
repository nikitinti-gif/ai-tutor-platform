import unittest

from src.ai_engine.homework_generator import generate_homework_object


class HomeworkGeneratorTest(unittest.TestCase):
    def test_conditional_operator_homework_has_a_concrete_condition(self):
        homework = generate_homework_object("Условные операторы")

        self.assertEqual(homework["topic"], "Условные операторы")
        self.assertEqual(len(homework["tasks"]), 1)
        self.assertIn("считывает одно целое число x", homework["tasks"][0])
        self.assertIn("positive", homework["tasks"][0])
        self.assertIn("negative", homework["tasks"][0])
        self.assertIn("zero", homework["tasks"][0])
        self.assertNotIn("Задание 1 по теме", homework["tasks"][0])


if __name__ == "__main__":
    unittest.main()
