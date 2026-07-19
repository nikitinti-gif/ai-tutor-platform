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


def _submission_storage_function(name: str):
    from src.database import submission_storage

    return getattr(submission_storage, name)


class SubmissionRepository:
    @staticmethod
    def create(submission: dict) -> dict:
        return _create_homework_submission(_database_url(), submission)

    @staticmethod
    def mark_teacher_notified(submission_id: str) -> None:
        _mark_teacher_notified(_database_url(), submission_id)

    @staticmethod
    def claim_next_synthetic(max_attempts: int) -> dict | None:
        return _submission_storage_function(
            "claim_next_synthetic_submission"
        )(_database_url(), max_attempts)

    @staticmethod
    def save_analysis(submission_id: str, result: dict) -> None:
        _submission_storage_function("save_submission_analysis")(
            _database_url(), submission_id, result
        )

    @staticmethod
    def release_or_fail(
        submission_id: str,
        error_message: str,
        max_attempts: int,
    ) -> None:
        _submission_storage_function("release_or_fail_submission")(
            _database_url(),
            submission_id,
            error_message,
            max_attempts,
        )

    @staticmethod
    def get_pending_analysis_notification() -> dict | None:
        return _submission_storage_function(
            "get_pending_analysis_notification"
        )(_database_url())

    @staticmethod
    def mark_analysis_notified(submission_id: str) -> None:
        _submission_storage_function("mark_analysis_notified")(
            _database_url(), submission_id
        )

    @staticmethod
    def list_for_teacher(limit: int = 10) -> list[dict]:
        return _submission_storage_function("list_teacher_submissions")(
            _database_url(), limit
        )

    @staticmethod
    def get_for_teacher(submission_id: str) -> dict | None:
        return _submission_storage_function("get_teacher_submission")(
            _database_url(), submission_id
        )

    @staticmethod
    def complete(submission_id: str) -> bool:
        return _submission_storage_function("complete_teacher_submission")(
            _database_url(), submission_id
        )
