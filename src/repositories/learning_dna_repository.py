import os

from src.database.json_storage import (
    get_learning_dna,
    get_synthetic_learning_checks,
    save_learning_dna,
    save_synthetic_learning_check,
)


def _database_url() -> str:
    return os.getenv("DATABASE_URL", "").strip()


def _postgres_function(name: str):
    from src.database import learning_dna_storage

    return getattr(learning_dna_storage, name)


class LearningDNARepository:
    @staticmethod
    def get(student_id: int):
        database_url = _database_url()
        if database_url:
            return _postgres_function("get_postgres_learning_dna")(
                database_url,
                student_id,
            )
        return get_learning_dna(student_id)

    @staticmethod
    def save(student_id: int, dna: dict):
        database_url = _database_url()
        if database_url:
            return _postgres_function("save_postgres_learning_dna")(
                database_url,
                student_id,
                dna,
            )
        return save_learning_dna(student_id, dna)

    @staticmethod
    def save_synthetic_check(check_result: dict):
        return save_synthetic_learning_check(check_result)

    @staticmethod
    def get_synthetic_checks():
        return get_synthetic_learning_checks()
