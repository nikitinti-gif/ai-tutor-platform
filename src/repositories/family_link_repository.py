import os


class FamilyLinkStorageUnavailableError(RuntimeError):
    pass


def _database_url() -> str:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise FamilyLinkStorageUnavailableError(
            "DATABASE_URL не настроен для семейных связей."
        )
    return database_url


def _save_code(*args, **kwargs) -> None:
    from src.database.family_link_storage import save_parent_link_code

    save_parent_link_code(*args, **kwargs)


def _consume_code(*args, **kwargs) -> int | None:
    from src.database.family_link_storage import consume_parent_link_code

    return consume_parent_link_code(*args, **kwargs)


def _get_student_id(*args, **kwargs) -> int | None:
    from src.database.family_link_storage import get_linked_student_id

    return get_linked_student_id(*args, **kwargs)


class FamilyLinkRepository:
    @staticmethod
    def save_code(
        code_hash: str,
        student_telegram_id: int,
        teacher_telegram_id: int,
    ) -> None:
        _save_code(
            _database_url(),
            code_hash,
            student_telegram_id,
            teacher_telegram_id,
        )

    @staticmethod
    def consume_code(
        code_hash: str,
        parent_telegram_id: int,
    ) -> int | None:
        return _consume_code(
            _database_url(),
            code_hash,
            parent_telegram_id,
        )

    @staticmethod
    def get_student_id(parent_telegram_id: int) -> int | None:
        return _get_student_id(_database_url(), parent_telegram_id)
