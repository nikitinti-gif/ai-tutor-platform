import asyncio
from types import SimpleNamespace

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


def test_admin_can_run_5_14_27_pilot_through_telegram_handlers(monkeypatch):
    sessions = {}

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

    completed = []

    async def fake_complete(message, state, attempt):
        completed.append(attempt.to_dict())
        await state.clear()
        await message.answer("TEST_DIAGNOSTICS_COMPLETED")

    monkeypatch.setattr(student_handler, "_complete_ege_diagnostics", fake_complete)

    state = FakeState()
    start_message = FakeMessage()
    asyncio.run(student_handler.start_ege_diagnostic_pilot(start_message, state))

    assert any("Пилот мини-проб №5, №14 и №27" in item for item in start_message.answers)
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
        control_evidence = [item for item in case["evidence"] if item.get("kind") == "control_probe"]
        assert len(control_evidence) >= 2
        assert all(item.get("evidence_valid") is True for item in control_evidence[-2:])
        assert all(item.get("question") for item in control_evidence[-2:])
        assert all(item.get("student_answer") is not None for item in control_evidence[-2:])


def test_non_admin_cannot_start_diagnostic_pilot(monkeypatch):
    monkeypatch.setattr(student_handler, "ADMIN_TELEGRAM_ID", "42")
    state = FakeState()
    message = FakeMessage(user_id=99)

    asyncio.run(student_handler.start_ege_diagnostic_pilot(message, state))

    assert message.answers == ["⛔ Эта тестовая команда доступна только администратору."]
    assert state.state is None
