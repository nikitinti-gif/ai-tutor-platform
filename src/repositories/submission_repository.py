import os

class SubmissionStorageUnavailableError(RuntimeError):
    pass


def _database_url() -> str:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise SubmissionStorageUnavailableError(
            "DATABASE_URL не настроен для очереди работ."
        )
    return database_url


def _create_homework_submission(database_url: str, submission: dict) -> dict:
    from src.database.submission_storage import create_homework_submission

    return create_homework_submission(database_url, submission)


def _mark_teacher_notified(database_url: str, submission_id: str) -> None:
    from src.database.submission_storage import mark_teacher_notified

    mark_teacher_notified(database_url, submission_id)


class SubmissionRepository:
    @staticmethod
    def create(submission: dict) -> dict:
        return _create_homework_submission(_database_url(), submission)

    @staticmethod
    def mark_teacher_notified(submission_id: str) -> None:
        _mark_teacher_notified(_database_url(), submission_id)
