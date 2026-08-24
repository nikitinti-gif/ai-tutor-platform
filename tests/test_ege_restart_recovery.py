import asyncio
from types import SimpleNamespace

import pytest
from aiogram.dispatcher.event.bases import SkipHandler

import src.telegram_bot.handlers.student as student_handler
from src.services.ege_exam_service import ExamAttempt, submit_answer
from src.telegram_bot.states.student_states import StudentEgeExamStates


class FakeState:
    def __init__(self, state=None):
        self.state = state
        self.data = {}

    async def get_state(self):
        return self.state

    async def set_state(self, state):
        self.state = state

    async def get_data(self):
        return dict(self.data)

    async def update_data(self, **kwargs):
        self.data.update(kwargs)


class FakeMessage:
    def __init__(self, text="9", user_id=42):
        self.text = text
        self.from_user = SimpleNamespace(id=user_id)
        self.answers = []

    async def answer(self, text, **kwargs):
        self.answers.append(text)


def active_session(task_number=1):
    attempt = ExamAttempt()
    for _ in range(1, task_number):
        submit_answer(attempt, "wrong")
    return {"status": "in_progress", "attempt": attempt.to_dict()}


def configure(monkeypatch, saved):
    writes = []
    monkeypatch.setattr(student_handler, "get_ege_session", lambda _student_id: saved)
    monkeypatch.setattr(
        student_handler,
        "save_ege_session",
        lambda student_id, attempt, status="in_progress": writes.append((student_id, attempt, status)),
    )
    monkeypatch.setattr(
        "src.repositories.user_repository.UserRepository.get_by_telegram_id",
        lambda _student_id: {"role": "student"},
    )
    monkeypatch.setattr(student_handler, "_send_ege_task", lambda *_args: asyncio.sleep(0))
    return writes


def test_active_exam_with_empty_fsm_is_recovered(monkeypatch):
    writes = configure(monkeypatch, active_session())
    state = FakeState()
    asyncio.run(student_handler.recover_ege_answer_after_restart(FakeMessage(), state))
    assert state.state == StudentEgeExamStates.waiting_answer
    assert writes[-1][1]["current_task"] == 2


@pytest.mark.parametrize("fsm", ["StudentHomeworkCheckStates:waiting_solution_text", "another:flow"])
def test_active_exam_does_not_capture_nonempty_fsm(monkeypatch, fsm):
    configure(monkeypatch, active_session())
    with pytest.raises(SkipHandler):
        asyncio.run(student_handler.recover_ege_answer_after_restart(FakeMessage(), FakeState(fsm)))


def test_completed_exam_with_empty_fsm_is_not_recovered(monkeypatch):
    saved = active_session()
    saved["status"] = "completed"
    configure(monkeypatch, saved)
    with pytest.raises(SkipHandler):
        asyncio.run(student_handler.recover_ege_answer_after_restart(FakeMessage(), FakeState()))


def test_task24_recovery_preserves_previous_answers_and_advances_once(monkeypatch):
    writes = configure(monkeypatch, active_session(24))
    state = FakeState()
    asyncio.run(student_handler.recover_ege_answer_after_restart(FakeMessage("wrong"), state))
    saved_attempt = writes[-1][1]
    assert len(saved_attempt["answer_records"]) == 24
    assert [item["task_number"] for item in saved_attempt["answer_records"]] == list(range(1, 25))
    assert saved_attempt["current_task"] == 25
    assert len(writes) == 1
