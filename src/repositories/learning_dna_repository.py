from src.database.json_storage import get_learning_dna, save_learning_dna


class LearningDNARepository:
    @staticmethod
    def get(student_id: int):
        return get_learning_dna(student_id)

    @staticmethod
    def save(student_id: int, dna: dict):
        return save_learning_dna(student_id, dna)