import os

from src.database.json_storage import (
    enter_student_test_mode,
    get_user_by_telegram_id,
    create_user,
    get_users_by_role,
    restore_user_role,
)


def _database_url() -> str:
    return os.getenv("DATABASE_URL", "").strip()


def _postgres_function(name: str):
    from src.database import user_storage

    return getattr(user_storage, name)


class UserRepository:
    @staticmethod
    def get_by_telegram_id(telegram_id: int):
        database_url = _database_url()
        if database_url:
            return _postgres_function("get_postgres_user")(
                database_url,
                telegram_id,
            )
        return get_user_by_telegram_id(telegram_id)

    @staticmethod
    def create(telegram_id: int, full_name: str, role: str):
        database_url = _database_url()
        if database_url:
            return _postgres_function("create_postgres_user")(
                database_url,
                telegram_id,
                full_name,
                role,
            )
        return create_user(
            telegram_id=telegram_id,
            full_name=full_name,
            role=role,
        )

    @staticmethod
    def get_by_role(role: str):
        database_url = _database_url()
        if database_url:
            return _postgres_function("list_postgres_users_by_role")(
                database_url,
                role,
            )
        return get_users_by_role(role)

    @staticmethod
    def enter_student_test_mode(telegram_id: int, student_role: str):
        database_url = _database_url()
        if database_url:
            return _postgres_function("enter_postgres_student_test_mode")(
                database_url, telegram_id, student_role
            )
        return enter_student_test_mode(telegram_id, student_role)

    @staticmethod
    def restore_role(telegram_id: int, fallback_role: str):
        database_url = _database_url()
        if database_url:
            return _postgres_function("restore_postgres_user_role")(
                database_url, telegram_id, fallback_role
            )
        return restore_user_role(telegram_id, fallback_role)
