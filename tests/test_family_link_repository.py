import os
import unittest
from unittest.mock import patch

from src.repositories.family_link_repository import (
    FamilyLinkRepository,
    FamilyLinkStorageUnavailableError,
)


class FamilyLinkRepositoryTest(unittest.TestCase):
    def test_database_url_is_required(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(FamilyLinkStorageUnavailableError):
                FamilyLinkRepository.get_student_id(100)

    @patch("src.repositories.family_link_repository._save_code")
    def test_save_code_routes_to_postgres(self, save_code):
        with patch.dict(
            os.environ,
            {"DATABASE_URL": "postgresql://example/test"},
            clear=True,
        ):
            FamilyLinkRepository.save_code("hash", 200, 300)

        save_code.assert_called_once_with(
            "postgresql://example/test",
            "hash",
            200,
            300,
        )

    @patch("src.repositories.family_link_repository._consume_code")
    def test_consume_code_returns_student(self, consume_code):
        consume_code.return_value = 200
        with patch.dict(
            os.environ,
            {"DATABASE_URL": "postgresql://example/test"},
            clear=True,
        ):
            result = FamilyLinkRepository.consume_code("hash", 100)

        self.assertEqual(result, 200)
        consume_code.assert_called_once_with(
            "postgresql://example/test",
            "hash",
            100,
        )


if __name__ == "__main__":
    unittest.main()
