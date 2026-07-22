import os


class AdaptiveTaskRepository:
    @staticmethod
    def save_confirmed(draft: dict, teacher_telegram_id: int) -> dict:
        database_url = os.getenv("DATABASE_URL", "").strip()
        if not database_url:
            raise RuntimeError("Для сохранения диагностического набора нужен PostgreSQL.")

        from src.database.adaptive_task_storage import (
            save_postgres_adaptive_task_set,
        )

        return save_postgres_adaptive_task_set(
            database_url,
            draft,
            teacher_telegram_id,
        )
