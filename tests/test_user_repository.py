import os
import unittest
from unittest.mock import patch

from src.repositories.user_repository import UserRepository


class UserRepositoryTest(unittest.TestCase):
    @patch("src.repositories.user_repository._postgres_function")
    def test_get_uses_postgres_when_database_url_exists(self, function):
        get_user = function.return_value
        get_user.return_value = {"telegram_id": 100, "role": "teacher"}
        with patch.dict(
            os.environ,
            {"DATABASE_URL": "postgresql://example/test"},
            clear=True,
        ):
            result = UserRepository.get_by_telegram_id(100)

        self.assertEqual(result["role"], "teacher")
        function.assert_called_once_with("get_postgres_user")
        get_user.assert_called_once_with("postgresql://example/test", 100)

    @patch("src.repositories.user_repository._postgres_function")
    def test_create_uses_postgres(self, function):
        create_user = function.return_value
        create_user.return_value = {"telegram_id": 100, "role": "parent"}
        with patch.dict(
            os.environ,
            {"DATABASE_URL": "postgresql://example/test"},
            clear=True,
        ):
            result = UserRepository.create(100, "Parent", "parent")

        self.assertEqual(result["role"], "parent")
        function.assert_called_once_with("create_postgres_user")
        create_user.assert_called_once_with(
            "postgresql://example/test",
            100,
            "Parent",
            "parent",
        )

    @patch("src.repositories.user_repository._postgres_function")
    def test_role_list_uses_postgres(self, function):
        list_users = function.return_value
        list_users.return_value = []
        with patch.dict(
            os.environ,
            {"DATABASE_URL": "postgresql://example/test"},
            clear=True,
        ):
            result = UserRepository.get_by_role("parent")

        self.assertEqual(result, [])
        function.assert_called_once_with("list_postgres_users_by_role")
        list_users.assert_called_once_with(
            "postgresql://example/test",
            "parent",
        )

    @patch("src.repositories.user_repository.get_user_by_telegram_id")
    def test_local_development_keeps_json_fallback(self, get_user):
        get_user.return_value = {"telegram_id": 100, "role": "teacher"}
        with patch.dict(os.environ, {}, clear=True):
            result = UserRepository.get_by_telegram_id(100)

        self.assertEqual(result["role"], "teacher")
        get_user.assert_called_once_with(100)


if __name__ == "__main__":
    unittest.main()
