import os
import unittest
from unittest.mock import patch

from src.repositories.adaptive_task_repository import AdaptiveTaskRepository


class AdaptiveTaskRepositoryTest(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_requires_postgres_to_persist_confirmed_set(self):
        with self.assertRaisesRegex(RuntimeError, "нужен PostgreSQL"):
            AdaptiveTaskRepository.save_confirmed({}, 1)


if __name__ == "__main__":
    unittest.main()
