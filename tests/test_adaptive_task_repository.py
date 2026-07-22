import os
import unittest
from unittest.mock import patch

from src.repositories.adaptive_task_repository import AdaptiveTaskRepository


class AdaptiveTaskRepositoryTest(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_requires_postgres_to_persist_confirmed_set(self):
        with self.assertRaisesRegex(RuntimeError, "нужен PostgreSQL"):
            AdaptiveTaskRepository.save_confirmed({}, 1)

    @patch("src.repositories.adaptive_task_repository._get_task_set")
    @patch.dict(os.environ, {"DATABASE_URL": "postgresql://test"}, clear=True)
    def test_get_uses_postgres_storage(self, get_task_set):
        get_task_set.return_value = {"task_set_id": "diag_1"}
        result = AdaptiveTaskRepository.get("diag_1")
        self.assertEqual(result["task_set_id"], "diag_1")
        get_task_set.assert_called_once_with("postgresql://test", "diag_1")

    @patch("src.repositories.adaptive_task_repository._mark_task_set_sent")
    @patch.dict(os.environ, {"DATABASE_URL": "postgresql://test"}, clear=True)
    def test_mark_sent_is_scoped_to_set_and_parent(self, mark_sent):
        mark_sent.return_value = True
        self.assertTrue(AdaptiveTaskRepository.mark_sent("diag_1", 77))
        mark_sent.assert_called_once_with("postgresql://test", "diag_1", 77)


if __name__ == "__main__":
    unittest.main()
