import os
import unittest
from unittest.mock import patch

from src.repositories.submission_repository import (
    SubmissionRepository,
    SubmissionStorageUnavailableError,
)


class SubmissionRepositoryTest(unittest.TestCase):
    def test_database_url_is_required(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(SubmissionStorageUnavailableError):
                SubmissionRepository.create({})

    @patch(
        "src.repositories.submission_repository._create_homework_submission"
    )
    def test_create_uses_configured_postgres(self, create_submission):
        submission = {"submission_id": "sub_test"}
        create_submission.return_value = submission

        with patch.dict(
            os.environ,
            {"DATABASE_URL": "postgresql://example/test"},
            clear=True,
        ):
            result = SubmissionRepository.create(submission)

        self.assertEqual(result, submission)
        create_submission.assert_called_once_with(
            "postgresql://example/test",
            submission,
        )

    @patch("src.repositories.submission_repository._mark_teacher_notified")
    def test_teacher_notification_is_persisted(self, mark_notified):
        with patch.dict(
            os.environ,
            {"DATABASE_URL": "postgresql://example/test"},
            clear=True,
        ):
            SubmissionRepository.mark_teacher_notified("sub_test")

        mark_notified.assert_called_once_with(
            "postgresql://example/test",
            "sub_test",
        )


if __name__ == "__main__":
    unittest.main()
