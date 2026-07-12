from src.core.roles import ROLE_STUDENT
from src.repositories.homework_repository import HomeworkRepository
from src.repositories.user_repository import UserRepository


def assign_homework_to_all_students(homework_id: str) -> list[dict]:
    students = UserRepository.get_by_role(ROLE_STUDENT)

    assignments = []

    for student in students:
        assignment = HomeworkRepository.assign_to_student(
            homework_id=homework_id,
            student_id=student["telegram_id"],
        )
        assignments.append(assignment)

    return assignments