import os

from src.database.json_storage import (
    get_user_by_telegram_id,
    create_user,
    get_users_by_role,
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
