import os


def _get_task_set(*args, **kwargs):
    from src.database.adaptive_task_storage import get_postgres_adaptive_task_set
    return get_postgres_adaptive_task_set(*args, **kwargs)


def _mark_task_set_sent(*args, **kwargs):
    from src.database.adaptive_task_storage import mark_postgres_adaptive_task_set_sent
    return mark_postgres_adaptive_task_set_sent(*args, **kwargs)


class AdaptiveTaskRepository:
    @staticmethod
    def _database_url() -> str:
        database_url = os.getenv("DATABASE_URL", "").strip()
        if not database_url:
            raise RuntimeError("Для диагностических наборов нужен PostgreSQL.")
        return database_url

    @staticmethod
    def save_confirmed(draft: dict, teacher_telegram_id: int) -> dict:
        database_url = AdaptiveTaskRepository._database_url()

        from src.database.adaptive_task_storage import (
            save_postgres_adaptive_task_set,
        )

        return save_postgres_adaptive_task_set(
            database_url,
            draft,
            teacher_telegram_id,
        )

    @staticmethod
    def get(task_set_id: str) -> dict | None:
        return _get_task_set(
            AdaptiveTaskRepository._database_url(), task_set_id
        )

    @staticmethod
    def mark_sent(task_set_id: str, parent_telegram_id: int) -> bool:
        return _mark_task_set_sent(
            AdaptiveTaskRepository._database_url(), task_set_id, parent_telegram_id
        )
