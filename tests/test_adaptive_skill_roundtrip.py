import os
import json
import unittest
from unittest.mock import AsyncMock, patch

from src.database.adaptive_task_storage import save_postgres_adaptive_task_set
from src.learning_dna.engine import update_learning_dna_after_check
from src.repositories.adaptive_task_repository import AdaptiveTaskRepository
from src.services.adaptive_task_service import build_adaptive_task_draft
from src.services import submission_worker
from src.services.submission_worker import process_next_synthetic_submission


class _Result:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row


class _Connection:
    def __init__(self):
        self.task_set = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def execute(self, query, params=None):
        normalized = " ".join(query.split())
        if normalized.startswith("INSERT INTO adaptive_task_sets"):
            self.task_set = {
                "task_set_id": params[0], "student_id": params[2],
                "teacher_id": params[3], "topic": params[4],
                "skill_id": params[5], "tasks": json.loads(params[6]),
                "status": "confirmed", "sent_at": None, "parent_id": None,
            }
            return _Result((params[0], "confirmed"))
        if "FROM adaptive_task_sets WHERE task_set_id" in normalized:
            item = self.task_set
            return _Result((
                item["task_set_id"], item["student_id"], item["teacher_id"],
                item["topic"], item["skill_id"], item["tasks"], item["status"],
                item["sent_at"], item["parent_id"],
            ))
        return _Result()


class AdaptiveSkillRoundtripTest(unittest.IsolatedAsyncioTestCase):
    async def test_skill_id_reaches_analysis_and_learning_dna(self):
        draft = build_adaptive_task_draft({
            "student_id": 42,
            "trajectory": {
                "next_focus": "Алгоритмы и исполнители",
                "next_focus_skill_id": "algorithms.tracing",
            },
        })
        connection = _Connection()

        with patch(
            "src.database.adaptive_task_storage.psycopg.connect",
            return_value=connection,
        ):
            saved = save_postgres_adaptive_task_set("postgresql://test", draft, 7)
            with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test"}):
                persisted = AdaptiveTaskRepository.get(saved["task_set_id"])

        self.assertEqual(persisted["skill_id"], "algorithms.tracing")

        bot = AsyncMock()
        bot.get_file.return_value.file_path = "solutions/answer.jpg"
        bot.download_file.side_effect = lambda _path, destination: destination.write(b"jpg")
        diagnostic = {
            "status": "has_error", "confidence": 0.95,
            "topic": persisted["topic"], "error_type": "diagnostic_level_gap",
            "diagnostic_mastery": {
                "base": True, "application": False, "transfer": False,
                "topic_mastered": False,
            },
        }
        submission = {
            "submission_id": "sub_roundtrip", "telegram_file_id": "file_1",
            "task_set_id": persisted["task_set_id"], "processing_attempts": 1,
        }

        with (
            patch.object(
                submission_worker.SubmissionRepository,
                "claim_next_synthetic", return_value=submission,
            ),
            patch.object(
                submission_worker.AdaptiveTaskRepository,
                "get", return_value=persisted,
            ),
            patch("src.services.submission_worker.check_homework_image", return_value={
                "image_legibility": "readable", "image_transcription": "решение",
            }),
            patch("src.services.submission_worker.check_diagnostic_transcription", return_value=diagnostic),
            patch("src.services.submission_worker.SubmissionRepository.save_analysis") as save_analysis,
        ):
            self.assertTrue(await process_next_synthetic_submission(bot))

        analysis = save_analysis.call_args.args[1]
        self.assertEqual(analysis["skill_id"], "algorithms.tracing")
        dna = update_learning_dna_after_check(None, 42, analysis)
        self.assertIn("algorithms.tracing", dna["skills"])
        self.assertEqual(
            dna["trajectory"]["next_focus_skill_id"], "algorithms.tracing"
        )
