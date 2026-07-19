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

    @patch("src.repositories.submission_repository._submission_storage_function")
    def test_claim_only_routes_synthetic_queue(self, storage_function):
        claim = storage_function.return_value
        claim.return_value = {"submission_id": "sub_test"}
        with patch.dict(
            os.environ,
            {"DATABASE_URL": "postgresql://example/test"},
            clear=True,
        ):
            result = SubmissionRepository.claim_next_synthetic(2)

        self.assertEqual(result["submission_id"], "sub_test")
        storage_function.assert_called_once_with(
            "claim_next_synthetic_submission"
        )
        claim.assert_called_once_with("postgresql://example/test", 2)

    @patch("src.repositories.submission_repository._submission_storage_function")
    def test_failed_processing_is_released_with_attempt_limit(
        self,
        storage_function,
    ):
        release = storage_function.return_value
        with patch.dict(
            os.environ,
            {"DATABASE_URL": "postgresql://example/test"},
            clear=True,
        ):
            SubmissionRepository.release_or_fail(
                "sub_test",
                "temporary error",
                2,
            )

        storage_function.assert_called_once_with(
            "release_or_fail_submission"
        )
        release.assert_called_once_with(
            "postgresql://example/test",
            "sub_test",
            "temporary error",
            2,
        )

    @patch("src.repositories.submission_repository._submission_storage_function")
    def test_teacher_queue_routes_to_postgres(self, storage_function):
        list_submissions = storage_function.return_value
        list_submissions.return_value = [{"submission_id": "sub_test"}]
        with patch.dict(
            os.environ,
            {"DATABASE_URL": "postgresql://example/test"},
            clear=True,
        ):
            result = SubmissionRepository.list_for_teacher(10)

        self.assertEqual(result[0]["submission_id"], "sub_test")
        storage_function.assert_called_once_with("list_teacher_submissions")
        list_submissions.assert_called_once_with(
            "postgresql://example/test",
            10,
        )

    @patch("src.repositories.submission_repository._submission_storage_function")
    def test_teacher_can_open_submission(self, storage_function):
        get_submission = storage_function.return_value
        get_submission.return_value = {"submission_id": "sub_test"}
        with patch.dict(
            os.environ,
            {"DATABASE_URL": "postgresql://example/test"},
            clear=True,
        ):
            result = SubmissionRepository.get_for_teacher("sub_test")

        self.assertEqual(result["submission_id"], "sub_test")
        storage_function.assert_called_once_with("get_teacher_submission")
        get_submission.assert_called_once_with(
            "postgresql://example/test",
            "sub_test",
        )

    @patch("src.repositories.submission_repository._submission_storage_function")
    def test_teacher_can_complete_submission(self, storage_function):
        complete = storage_function.return_value
        complete.return_value = True
        with patch.dict(
            os.environ,
            {"DATABASE_URL": "postgresql://example/test"},
            clear=True,
        ):
            result = SubmissionRepository.complete("sub_test")

        self.assertTrue(result)
        storage_function.assert_called_once_with("complete_teacher_submission")
        complete.assert_called_once_with(
            "postgresql://example/test",
            "sub_test",
        )


if __name__ == "__main__":
    unittest.main()
