from src.database.json_storage import (
    get_learning_dna,
    get_synthetic_learning_checks,
    save_learning_dna,
    save_synthetic_learning_check,
)


class LearningDNARepository:
    @staticmethod
    def get(student_id: int):
        return get_learning_dna(student_id)

    @staticmethod
    def save(student_id: int, dna: dict):
        return save_learning_dna(student_id, dna)

    @staticmethod
    def save_synthetic_check(check_result: dict):
        return save_synthetic_learning_check(check_result)

    @staticmethod
    def get_synthetic_checks():
        return get_synthetic_learning_checks()
