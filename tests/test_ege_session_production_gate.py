import asyncio
import logging
from types import SimpleNamespace

import pytest
from aiogram.dispatcher.event.bases import SkipHandler

from src.repositories import ege_session_repository as repository_module
from src.repositories.ege_session_repository import EgeSessionRepository, persistence_info
from src.services.ege_exam_service import ExamAttempt
from src.telegram_bot.handlers import student as student_handler
from src.telegram_bot.states.student_states import StudentEgeExamStates


class State:
    def __init__(self, value=None):
        self.value = value
        self.data = {}

    async def get_state(self):
        return self.value

    async def set_state(self, value):
        self.value = value.state

    async def update_data(self, **data):
        self.data.update(data)

    async def get_data(self):
        return self.data


class Message:
    def __init__(self, text="answer", student_id=42):
        self.text = text
        self.from_user = SimpleNamespace(id=student_id)
        self.answers = []

    async def answer(self, text, **_kwargs):
        self.answers.append(text)


def snapshot(current_task, *, attempt_id="real-e2e"):
    attempt = ExamAttempt(attempt_id=attempt_id, current_task=current_task)
    for task in range(1, current_task):
        attempt.answers[task] = f"old-{task}"
        attempt.results[task] = task % 2 == 0
    return {"status": "in_progress", "attempt": attempt.to_dict()}


@pytest.mark.parametrize("task", [1, 14, 24, 27])
def test_restart_recovers_normal_exam_tasks(monkeypatch, task):
    saved = snapshot(task)
    writes = []
    monkeypatch.setattr(student_handler, "get_ege_session", lambda _id: saved)
    monkeypatch.setattr(student_handler, "save_ege_session", lambda _id, data, status="in_progress": writes.append(data))
    monkeypatch.setattr("src.repositories.user_repository.UserRepository.get_by_telegram_id", lambda _id: {"role": "student"})
    monkeypatch.setattr(student_handler, "_send_ege_task", lambda *_args: _async_none())
    state, message = State(), Message()

    asyncio.run(student_handler.recover_ege_exam_after_restart(message, state))

    expected_state = (
        StudentEgeExamStates.waiting_diagnostic_answer.state
        if task == 27
        else StudentEgeExamStates.waiting_answer.state
    )
    assert state.value == expected_state
    assert writes[-1]["current_task"] == task + 1


async def _async_none():
    return None


@pytest.mark.parametrize(
    "state_value,role,status",
    [("busy", "student", "in_progress"), (None, "teacher", "in_progress"), (None, "student", "completed")],
)
def test_production_gate_skips_non_recoverable_messages(monkeypatch, state_value, role, status):
    monkeypatch.setattr(student_handler, "get_ege_session", lambda _id: {**snapshot(14), "status": status})
    monkeypatch.setattr("src.repositories.user_repository.UserRepository.get_by_telegram_id", lambda _id: {"role": role})
    with pytest.raises(SkipHandler):
        asyncio.run(student_handler.recover_ege_exam_after_restart(Message(), State(state_value)))


def test_completed_attempt_skips_even_with_in_progress_status(monkeypatch):
    monkeypatch.setattr(student_handler, "get_ege_session", lambda _id: snapshot(28))
    monkeypatch.setattr("src.repositories.user_repository.UserRepository.get_by_telegram_id", lambda _id: {"role": "student"})
    message = Message()
    asyncio.run(student_handler.recover_ege_exam_after_restart(message, State()))
    assert "повреждена" in message.answers[0]


def test_corrupted_snapshot_is_visible_and_logged(monkeypatch, caplog):
    monkeypatch.setattr(student_handler, "get_ege_session", lambda _id: {"status": "in_progress", "attempt": "bad"})
    monkeypatch.setattr("src.repositories.user_repository.UserRepository.get_by_telegram_id", lambda _id: {"role": "student"})
    message = Message()
    with caplog.at_level(logging.ERROR):
        asyncio.run(student_handler.recover_ege_exam_after_restart(message, State()))
    assert "повреждена" in message.answers[0]
    assert "EGE_SESSION_RECOVERY_CORRUPTED student_id=42" in caplog.text


def test_persistence_audit(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert persistence_info() == {"backend": "json", "durable": False}
    monkeypatch.setenv("DATABASE_URL", "postgresql://configured")
    assert persistence_info() == {"backend": "postgres", "durable": True}


def test_real_task24_legacy_migration_recovery_has_no_duplicate(monkeypatch, caplog):
    legacy = snapshot(24, attempt_id="attempt-task-24")
    postgres = {}
    monkeypatch.setenv("DATABASE_URL", "postgresql://configured")
    monkeypatch.setattr(repository_module.json_storage, "get_ege_session", lambda _id: legacy)
    monkeypatch.setattr("src.database.ege_session_storage.get_postgres_ege_session", lambda _url, student_id: postgres.get(student_id))
    monkeypatch.setattr("src.database.ege_session_storage.migrate_postgres_ege_session", lambda _url, student_id, session: postgres.setdefault(student_id, session))
    monkeypatch.setattr("src.database.ege_session_storage.save_postgres_ege_session", lambda _url, student_id, session: postgres.__setitem__(student_id, session) or session)
    monkeypatch.setattr(student_handler, "get_ege_session", EgeSessionRepository.get)
    monkeypatch.setattr(student_handler, "save_ege_session", EgeSessionRepository.save)
    monkeypatch.setattr("src.repositories.user_repository.UserRepository.get_by_telegram_id", lambda _id: {"role": "student"})
    monkeypatch.setattr(student_handler, "_send_ege_task", lambda *_args: _async_none())

    with caplog.at_level(logging.INFO):
        migrated = EgeSessionRepository.get(42)
        asyncio.run(student_handler.recover_ege_exam_after_restart(Message("wrong is still one answer"), State()))

    updated = ExamAttempt.from_dict(postgres[42]["attempt"])
    assert migrated["attempt"]["attempt_id"] == "attempt-task-24"
    assert updated.attempt_id == "attempt-task-24"
    assert updated.current_task == 25
    assert {task: updated.answers[task] for task in range(1, 24)} == {
        task: f"old-{task}" for task in range(1, 24)
    }
    assert [record["task_number"] for record in updated.answer_records].count(24) == 1
    assert "EGE_SESSION_MIGRATED student_id=42 from=json to=postgres task=24" in caplog.text
    assert "EGE_SESSION_RECOVERY student_id=42 task=24 fsm_before=None" in caplog.text
