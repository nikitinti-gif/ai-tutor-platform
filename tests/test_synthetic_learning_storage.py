import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.database.json_storage import (
    SYNTHETIC_CHECKS_KEY,
    get_synthetic_learning_checks,
    save_synthetic_learning_check,
)


class SyntheticLearningStorageTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "database.json"
        self.db_patch = patch(
            "src.database.json_storage.DB_FILE",
            str(self.db_path),
        )
        self.db_patch.start()

    def tearDown(self):
        self.db_patch.stop()
        self.temp_dir.cleanup()

    def test_only_policy_v1_fields_are_saved(self):
        record = save_synthetic_learning_check(
            {
                "topic": "Системы счисления",
                "status": "has_error",
                "confidence": 0.97,
                "error_type": "calculation_error",
                "image_transcription": "секретная транскрипция",
                "image_bytes": b"secret-image",
                "task_text": "секретное условие",
                "telegram_id": 123456,
            }
        )

        self.assertEqual(
            set(record),
            {"topic", "status", "confidence", "error_type"},
        )
        stored_text = self.db_path.read_text(encoding="utf-8")
        self.assertNotIn("секретная транскрипция", stored_text)
        self.assertNotIn("секретное условие", stored_text)
        self.assertNotIn("123456", stored_text)

        database = json.loads(stored_text)
        self.assertEqual(
            database["learning_dna"][SYNTHETIC_CHECKS_KEY],
            [record],
        )

    def test_checks_are_appended(self):
        first = {
            "topic": "Циклы",
            "status": "correct",
            "confidence": 1.0,
            "error_type": None,
        }
        second = {
            "topic": "Строки",
            "status": "unclear",
            "confidence": 0.5,
            "error_type": "unreadable_image",
        }

        save_synthetic_learning_check(first)
        save_synthetic_learning_check(second)

        self.assertEqual(
            get_synthetic_learning_checks(),
            [first, second],
        )

    def test_invalid_status_is_rejected(self):
        with self.assertRaises(ValueError):
            save_synthetic_learning_check(
                {
                    "topic": "Циклы",
                    "status": "approved",
                    "confidence": 1.0,
                    "error_type": None,
                }
            )

        self.assertFalse(self.db_path.exists())

    @patch("src.database.json_storage._append_synthetic_check_to_postgres")
    def test_database_url_routes_write_to_postgres(self, append_check):
        expected = {
            "topic": "Циклы",
            "status": "correct",
            "confidence": 1.0,
            "error_type": None,
        }
        append_check.return_value = expected

        with patch.dict("os.environ", {"DATABASE_URL": "postgresql://test"}):
            result = save_synthetic_learning_check(
                {
                    **expected,
                    "image_transcription": "не сохранять",
                    "telegram_id": 123,
                }
            )

        self.assertEqual(result, expected)
        append_check.assert_called_once_with("postgresql://test", expected)
        self.assertFalse(self.db_path.exists())

    @patch("src.database.json_storage._load_synthetic_checks_from_postgres")
    def test_database_url_routes_read_to_postgres(self, load_checks):
        load_checks.return_value = [
            {
                "topic": "Циклы",
                "status": "correct",
                "confidence": 1.0,
                "error_type": None,
            }
        ]

        with patch.dict("os.environ", {"DATABASE_URL": "postgresql://test"}):
            result = get_synthetic_learning_checks()

        self.assertEqual(result, load_checks.return_value)
        load_checks.assert_called_once_with("postgresql://test")


if __name__ == "__main__":
    unittest.main()
