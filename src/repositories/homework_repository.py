from src.database.json_storage import (
    create_homework,
    get_active_homework,
    create_student_homework,
    get_student_homework_by_student_id,
    update_student_homework_status,
    get_latest_student_homework,
)


class HomeworkRepository:
    @staticmethod
    def create(topic: str, homework_data: dict, teacher_id: int):
        return create_homework(
            topic=topic,
            homework_data=homework_data,
            teacher_id=teacher_id,
        )

    @staticmethod
    def get_active():
        return get_active_homework()

    @staticmethod
    def assign_to_student(homework_id: str, student_id: int):
        return create_student_homework(
            homework_id=homework_id,
            student_id=student_id,
        )

    @staticmethod
    def get_student_assignments(student_id: int):
        return get_student_homework_by_student_id(student_id)
    
    @staticmethod
    def mark_as_opened(student_homework_id: str):
        return update_student_homework_status(
            student_homework_id=student_homework_id,
            status="opened",
        )

    @staticmethod
    def mark_as_submitted(student_homework_id: str):
        from datetime import datetime

        return update_student_homework_status(
            student_homework_id=student_homework_id,
            status="submitted",
            extra_fields={
                "submitted_at": datetime.now().isoformat(timespec="seconds")
            },
        )

    @staticmethod
    def mark_as_checked(student_homework_id: str, check_result: dict):
        from datetime import datetime

        return update_student_homework_status(
            student_homework_id=student_homework_id,
            status="checked",
            extra_fields={
                "checked_at": datetime.now().isoformat(timespec="seconds"),
                "last_error_type": check_result.get("error_type"),
                "teacher_review_required": check_result.get(
                    "needs_teacher_review",
                    False,
                ),
            },
        )

    @staticmethod
    def get_latest_for_student(student_id: int):
        return get_latest_student_homework(student_id)