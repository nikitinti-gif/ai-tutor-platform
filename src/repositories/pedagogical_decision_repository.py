from src.database.json_storage import save_pedagogical_decision


class PedagogicalDecisionRepository:
    @staticmethod
    def save(student_id: int, decision_data: dict):
        return save_pedagogical_decision(student_id, decision_data)