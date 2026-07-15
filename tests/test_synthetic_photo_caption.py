import unittest

from src.telegram_bot.handlers.demo import parse_synthetic_photo_task


class SyntheticPhotoCaptionTest(unittest.TestCase):
    def test_task_is_extracted_after_command(self):
        task = parse_synthetic_photo_task(
            "/check_synthetic_photo\nВывести числа от 1 до 10."
        )
        self.assertEqual(task, "Вывести числа от 1 до 10.")

    def test_bot_mention_is_supported(self):
        task = parse_synthetic_photo_task(
            "/check_synthetic_photo@ai_tutor_bot Найти сумму чисел."
        )
        self.assertEqual(task, "Найти сумму чисел.")

    def test_missing_task_is_rejected(self):
        self.assertIsNone(
            parse_synthetic_photo_task("/check_synthetic_photo")
        )

    def test_other_caption_is_rejected(self):
        self.assertIsNone(parse_synthetic_photo_task("обычное фото"))

    def test_qwen_command_extracts_task_only_when_selected(self):
        caption = (
            "/check_qwen_synthetic_photo "
            "Перевести 10110₂ в десятичную систему."
        )

        self.assertIsNone(parse_synthetic_photo_task(caption))
        self.assertEqual(
            parse_synthetic_photo_task(
                caption,
                "/check_qwen_synthetic_photo",
            ),
            "Перевести 10110₂ в десятичную систему.",
        )


if __name__ == "__main__":
    unittest.main()
