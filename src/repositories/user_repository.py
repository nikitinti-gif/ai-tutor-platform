from src.database.json_storage import (
    get_user_by_telegram_id,
    create_user,
    get_users_by_role,
)


class UserRepository:
    @staticmethod
    def get_by_telegram_id(telegram_id: int):
        return get_user_by_telegram_id(telegram_id)

    @staticmethod
    def create(telegram_id: int, full_name: str, role: str):
        return create_user(
            telegram_id=telegram_id,
            full_name=full_name,
            role=role,
        )

    @staticmethod
    def get_by_role(role: str):
        return get_users_by_role(role)