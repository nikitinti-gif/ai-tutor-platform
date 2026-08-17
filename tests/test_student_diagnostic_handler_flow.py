import asyncio
from types import SimpleNamespace

import pytest

import src.telegram_bot.handlers.student as student_handler


class FakeState:
    def __init__(self):
        self.data = {}
        self.state = None
        self.cleared = False

    async def clear(self):
        self.data = {}
        self.state = None
        self.cleared = True

    async def set_state(self, value):
        self.state = value
        self.cleared = False

    async def update_data(self, **kwargs):
        self.data.update(kwargs)

    async def get_data(self):
        return dict(self.data)


class FakeMessage:
    def __init__(self, user_id=42, text=None):
        self.from_user = SimpleNamespace(id=user_id)
        self.text = text
        self.answers = []

    async def answer(self, text, **_kwargs):
        self.answers.append(text)


class FailingProbeMessage(FakeMessage):
    async def answer(self, text, **_kwargs):
        if "Задание КЕГЭ №" in text:
            raise RuntimeError("telegram delivery failed")
        await super().answer(text, **_kwargs)


def _patch_sessions(monkeypatch, sessions):
    monkeypatch.setattr(student_handler, "ADMIN_TELEGRAM_ID", "42")
    monkeypatch.setattr(student_handler, "AI_DIAGNOSTIC_PROBES_ENABLED", False)
    monkeypatch.setattr(
        student_handler,
        "delete_ege_session",
        lambda user_id: sessions.pop(user_id, None),
    )
    monkeypatch.setattr(
        student_handler,
        "save_ege_session",
        lambda user_id, attempt, status="in_progress": sessions.__setitem__(
            user_id, {"attempt": attempt, "status": status}
        ),
    )
    monkeypatch.setattr(
        student_handler,
        "get_ege_session",
        lambda user_id: sessions.get(user_id),
    )


def test_admin_can_run_5_14_27_pilot_through_telegram_handlers(monkeypatch):
    sessions = {}
    _patch_sessions(monkeypatch, sessions)

    completed = []

    async def fake_complete(message, state, attempt):
        completed.append(attempt.to_dict())
        await state.clear()
        await message.answer("TEST_DIAGNOSTICS_COMPLETED")

    monkeypatch.setattr(student_handler, "_complete_ege_diagnostics", fake_complete)

    state = FakeState()
    start_message = FakeMessage()
    asyncio.run(student_handler.start_ege_diagnostic_pilot(start_message, state))

    assert any("Пилот разбора ошибок №5, №14 и №27" in item for item in start_message.answers)
    assert any("Задание КЕГЭ №5" in item for item in start_message.answers)
    assert sessions[42]["status"] == "diagnostics_in_progress"

    # Two independent wrong answers confirm one operation for each pilot task.
    for task_number in (5, 14, 27):
        first = FakeMessage(text="definitely-wrong")
        asyncio.run(student_handler.receive_ege_diagnostic_answer(first, state))
        assert any("первое свидетельство ошибки" in item for item in first.answers)
        assert any(f"Задание КЕГЭ №{task_number}" in item for item in first.answers)

        second = FakeMessage(text="still-wrong")
        asyncio.run(student_handler.receive_ege_diagnostic_answer(second, state))
        assert any("Точка ошибки подтверждена" in item for item in second.answers)

        if task_number != 27:
            next_task = 14 if task_number == 5 else 27
            assert any(f"Задание КЕГЭ №{next_task}" in item for item in second.answers)

    assert len(completed) == 1
    finished_attempt = completed[0]
    for task_number in (5, 14, 27):
        case = finished_attempt["diagnostics"][task_number]
        assert case["status"] == "confirmed"
        assert case["confidence"] == 0.95
        control_evidence = [
            item for item in case["evidence"]
            if item.get("kind") == "control_probe"
        ]
        assert len(control_evidence) >= 2
        assert all(item.get("evidence_valid") is True for item in control_evidence[-2:])
        assert all(item.get("question") for item in control_evidence[-2:])
        assert all(item.get("student_answer") is not None for item in control_evidence[-2:])
        assert all(item.get("student_id") == "42" for item in control_evidence[-2:])
        assert all(item.get("attempt_id") for item in control_evidence[-2:])
        assert all(item.get("task_number") == task_number for item in control_evidence[-2:])
        assert all(item.get("skill_id") for item in control_evidence[-2:])
        assert all(item.get("hypothesis_id") for item in control_evidence[-2:])
        assert all(item.get("timestamp") for item in control_evidence[-2:])


def test_failed_probe_delivery_is_not_persisted_as_displayed(monkeypatch):
    """STATE_ERROR guard: a Telegram send failure must never create answerable evidence."""
    sessions = {}
    _patch_sessions(monkeypatch, sessions)
    state = FakeState()
    message = FailingProbeMessage()

    with pytest.raises(RuntimeError, match="telegram delivery failed"):
        asyncio.run(student_handler.start_ege_diagnostic_pilot(message, state))

    assert sessions == {}
    assert state.state is None
    assert "ege_attempt" not in state.data


def test_non_admin_cannot_start_diagnostic_pilot(monkeypatch):
    monkeypatch.setattr(student_handler, "ADMIN_TELEGRAM_ID", "42")
    state = FakeState()
    message = FakeMessage(user_id=99)

    asyncio.run(student_handler.start_ege_diagnostic_pilot(message, state))

    assert message.answers == ["⛔ Эта тестовая команда доступна только администратору."]
    assert state.state is None


def test_learning_path_answer_survives_restart(monkeypatch):
    from src.services.ege_exam_service import ExamAttempt
    from src.services.ege_learning_path import TASK14_LEVELS, build_learning_path, submit_answer

    sessions = {}
    _patch_sessions(monkeypatch, sessions)
    attempt = ExamAttempt()
    attempt.results[14] = False
    path = build_learning_path(14)
    for level in TASK14_LEVELS[:5]:
        result = submit_answer(path, str(level["answers"][0]))
        assert result["is_correct"] is True
    assert path.current_index == 5
    attempt.learning_path = path.to_dict()
    sessions[42] = {"attempt": attempt.to_dict(), "status": "learning_path_in_progress"}

    # Simulate a Render restart: aiogram FSM is empty, but persisted session survives.
    state = FakeState()
    message = FakeMessage(text=str(TASK14_LEVELS[5]["answers"][0]))
    asyncio.run(student_handler.resume_ege_learning_path_after_restart(message, state))

    restored = sessions[42]["attempt"]["learning_path"]
    assert restored["current_index"] == 6
    assert any("Поднимаемся на следующий уровень" in item for item in message.answers)
    assert any("ШАГ 7/7" in item for item in message.answers)
