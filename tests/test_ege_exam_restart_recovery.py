import asyncio
from types import SimpleNamespace

import pytest

import src.telegram_bot.handlers.student as student_handler
from src.ai_engine.ege_open_variant_2026 import OPEN_VARIANT_2026
from src.services.ege_exam_service import ExamAttempt, submit_answer
from src.telegram_bot.states.student_states import StudentEgeExamStates


def answer_text(task):
    return "\n".join(" ".join(row) for row in task.answer_rows)


class EmptyRestartedState:
    def __init__(self):
        self.data = {}
        self.state = None

    async def get_state(self):
        return self.state

    async def get_data(self):
        return dict(self.data)

    async def set_state(self, value):
        self.state = value

    async def update_data(self, **kwargs):
        self.data.update(kwargs)


class FakeMessage:
    def __init__(self, user_id, text):
        self.from_user = SimpleNamespace(id=user_id)
        self.text = text
        self.answers = []

    async def answer(self, text, **_kwargs):
        self.answers.append(text)


def persisted_attempt_at(task_number):
    attempt = ExamAttempt()
    for number in range(1, task_number):
        submit_answer(attempt, answer_text(OPEN_VARIANT_2026[number]))
    return attempt


@pytest.mark.parametrize("restart_task", [1, 14, 24])
def test_active_exam_answer_recovers_empty_fsm_and_advances_once(
    monkeypatch, restart_task
):
    student_id = 42
    attempt = persisted_attempt_at(restart_task)
    sessions = {
        student_id: {"status": "in_progress", "attempt": attempt.to_dict()}
    }
    monkeypatch.setattr(
        student_handler.UserRepository,
        "get_by_telegram_id",
        lambda _student_id: {"telegram_id": student_id, "role": "student"},
    )
    monkeypatch.setattr(student_handler, "get_ege_session", sessions.get)
    monkeypatch.setattr(
        student_handler,
        "save_ege_session",
        lambda user_id, data, status="in_progress": sessions.__setitem__(
            user_id, {"status": status, "attempt": data}
        ),
    )
    sent_tasks = []

    async def fake_send(_message, task_number):
        sent_tasks.append(task_number)

    monkeypatch.setattr(student_handler, "_send_ege_task", fake_send)
    state = EmptyRestartedState()
    message = FakeMessage(student_id, answer_text(OPEN_VARIANT_2026[restart_task]))

    asyncio.run(student_handler.recover_ege_answer_after_restart(message, state))

    recovered = ExamAttempt.from_dict(sessions[student_id]["attempt"])
    assert recovered.current_task == restart_task + 1
    assert len(recovered.answers) == restart_task
    assert len(recovered.answer_records) == restart_task
    assert recovered.answers[restart_task] == message.text
    assert recovered.answers | attempt.answers == recovered.answers
    assert sent_tasks == [restart_task + 1]
    assert state.state == StudentEgeExamStates.waiting_answer
    assert state.data["ege_attempt"]["attempt_id"] == attempt.attempt_id


def test_task_24_recovery_preserves_all_previous_23_answers(monkeypatch):
    # Explicit production regression scenario, separate from the position matrix.
    test_active_exam_answer_recovers_empty_fsm_and_advances_once(monkeypatch, 24)


def test_task_27_recovery_records_answer_and_finishes_same_attempt(monkeypatch):
    student_id = 42
    attempt = persisted_attempt_at(27)
    sessions = {student_id: {"status": "in_progress", "attempt": attempt.to_dict()}}
    monkeypatch.setattr(student_handler.UserRepository, "get_by_telegram_id", lambda _id: {"role": "student"})
    monkeypatch.setattr(student_handler, "get_ege_session", sessions.get)
    completed = []

    async def fake_begin(_message, state, finished_attempt):
        completed.append(finished_attempt.to_dict())
        await state.update_data(ege_attempt=finished_attempt.to_dict())

    monkeypatch.setattr(student_handler, "_begin_ege_diagnostics", fake_begin)
    state = EmptyRestartedState()
    message = FakeMessage(student_id, answer_text(OPEN_VARIANT_2026[27]))
    asyncio.run(student_handler.recover_ege_answer_after_restart(message, state))
    assert completed[0]["current_task"] == 28
    assert len(completed[0]["answer_records"]) == 27
    assert completed[0]["attempt_id"] == attempt.attempt_id


@pytest.mark.parametrize(
    ("role", "status"),
    [("student", "completed"), ("student", None), ("teacher", "in_progress")],
)
def test_recovery_does_not_intercept_ineligible_messages(monkeypatch, role, status):
    from aiogram.dispatcher.event.bases import SkipHandler

    session = {"status": status, "attempt": ExamAttempt().to_dict()} if status else None
    monkeypatch.setattr(student_handler.UserRepository, "get_by_telegram_id", lambda _id: {"role": role})
    monkeypatch.setattr(student_handler, "get_ege_session", lambda _id: session)
    with pytest.raises(SkipHandler):
        asyncio.run(student_handler.recover_ege_answer_after_restart(FakeMessage(42, "9"), EmptyRestartedState()))


def test_corrupted_active_session_is_handled_with_visible_error(monkeypatch, caplog):
    monkeypatch.setattr(student_handler.UserRepository, "get_by_telegram_id", lambda _id: {"role": "student"})
    monkeypatch.setattr(student_handler, "get_ege_session", lambda _id: {"status": "in_progress", "attempt": {"current_task": 14}})
    message = FakeMessage(42, "answer")
    with caplog.at_level("WARNING"):
        asyncio.run(student_handler.recover_ege_answer_after_restart(message, EmptyRestartedState()))
    assert "не удалось восстановить" in message.answers[0].lower()
    assert "EGE_SESSION_RECOVERY_CORRUPTED" in caplog.text


def test_ege_session_uses_postgres_when_database_url_is_configured(monkeypatch):
    import src.database.json_storage as storage
    import src.database.postgres_storage as postgres

    records = {}
    monkeypatch.setenv("DATABASE_URL", "postgresql://example/test")
    monkeypatch.setattr(postgres, "load_ege_session", lambda _url, student_id: records.get(student_id))
    monkeypatch.setattr(postgres, "save_ege_session", lambda _url, student_id, record: records.setdefault(student_id, record))
    monkeypatch.setattr(postgres, "delete_ege_session", lambda _url, student_id: records.pop(student_id, None))

    saved = storage.save_ege_session(42, ExamAttempt().to_dict())
    assert records[42] == saved
    assert storage.get_ege_session(42) == saved
    assert storage.delete_ege_session(42) == saved
