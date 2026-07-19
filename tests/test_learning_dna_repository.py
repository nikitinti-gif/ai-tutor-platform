import os
import unittest
from unittest.mock import patch

from src.repositories.learning_dna_repository import LearningDNARepository


class LearningDNARepositoryTest(unittest.TestCase):
    @patch("src.repositories.learning_dna_repository._postgres_function")
    def test_get_routes_to_postgres_when_configured(self, postgres_function):
        get_dna = postgres_function.return_value
        get_dna.return_value = {"student_id": 42}

        with patch.dict(
            os.environ,
            {"DATABASE_URL": "postgresql://example/test"},
            clear=True,
        ):
            result = LearningDNARepository.get(42)

        self.assertEqual(result["student_id"], 42)
        postgres_function.assert_called_once_with("get_postgres_learning_dna")
        get_dna.assert_called_once_with("postgresql://example/test", 42)

    @patch("src.repositories.learning_dna_repository._postgres_function")
    def test_save_routes_to_postgres_when_configured(self, postgres_function):
        save_dna = postgres_function.return_value
        dna = {"student_id": 42, "signals": []}
        save_dna.return_value = dna

        with patch.dict(
            os.environ,
            {"DATABASE_URL": "postgresql://example/test"},
            clear=True,
        ):
            result = LearningDNARepository.save(42, dna)

        self.assertEqual(result, dna)
        postgres_function.assert_called_once_with("save_postgres_learning_dna")
        save_dna.assert_called_once_with(
            "postgresql://example/test",
            42,
            dna,
        )

    @patch("src.repositories.learning_dna_repository.get_learning_dna")
    def test_get_keeps_json_fallback_without_database_url(self, get_dna):
        get_dna.return_value = {"student_id": 42}

        with patch.dict(os.environ, {}, clear=True):
            result = LearningDNARepository.get(42)

        self.assertEqual(result["student_id"], 42)
        get_dna.assert_called_once_with(42)


if __name__ == "__main__":
    unittest.main()
