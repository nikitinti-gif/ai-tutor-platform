import asyncio
from types import SimpleNamespace

import pytest

import src.telegram_bot.handlers.student as student_handler
from src.services.ege_exam_service import ExamAttempt
from src.telegram_bot.states.student_states import StudentEgeExamStates


class FakeState:
    def __init__(self):
        self.data = {}
        self.state = None

    async def set_state(self, value):
        self.state = value

    async def update_data(self, **kwargs):
        self.data.update(kwargs)


class FakeMessage:
    def __init__(self, user_id=42):
        self.from_user = SimpleNamespace(id=user_id)
        self.answers = []

    async def answer(self, text, **_kwargs):
        self.answers.append(text)


def _run(monkeypatch, dna, attempt, status="completed"):
    saved = {"status": status, "attempt": attempt.to_dict()}
    writes = []
    monkeypatch.setattr(student_handler.LearningDNARepository, "get", lambda _user_id: dna)
    monkeypatch.setattr(student_handler, "get_ege_session", lambda _user_id: saved)
    monkeypatch.setattr(
        student_handler,
        "save_ege_session",
        lambda user_id, value, status="in_progress": writes.append((user_id, value, status)),
    )
    message, state = FakeMessage(), FakeState()
    asyncio.run(student_handler.start_personal_learning(message, state))
    return message, state, writes


def _dna(*items, focus=None):
    return {
        "trajectory": {
            "next_focus_skill_id": focus or items[0]["skill_id"],
            "individual_plan": list(items),
        }
    }


def test_completed_exam_starts_task14_learning_path_not_new_exam(monkeypatch):
    attempt = ExamAttempt()
    attempt.current_task = 28
    item = {"skill_id": "number_systems.large_number_digits", "task_number": 14}
    message, state, writes = _run(monkeypatch, _dna(item), attempt)

    assert writes[-1][2] == "learning_path_in_progress"
    assert state.state == StudentEgeExamStates.waiting_learning_path_answer
    assert any("учебную ветку №14" in answer for answer in message.answers)
    assert not any("Открытый вариант" in answer for answer in message.answers)


@pytest.mark.parametrize("task_number", [5, 27])
def test_partial_skill_uses_existing_remediation(monkeypatch, task_number):
    attempt = ExamAttempt()
    attempt.remediation = {
        "task_number": task_number,
        "skill_id": (
            "number_systems.decimal_binary_conversion"
            if task_number == 5
            else "programming.cluster_count_from_separation"
        ),
        "status": "remediating",
        "stage": "control",
        "control_attempts": 0,
        "retest_attempts": 0,
        "verification_attempts": 0,
        "learning_round": 1,
        "stage_history": [],
    }
    item = {"skill_id": attempt.remediation["skill_id"], "task_number": task_number}
    message, state, writes = _run(monkeypatch, _dna(item), attempt)

    assert writes[-1][2] == "remediation_in_progress"
    assert state.state == StudentEgeExamStates.waiting_remediation_answer
    assert any(f"№{task_number}" in answer for answer in message.answers)


def test_pending_item_is_explained_and_first_executable_item_is_selected(monkeypatch):
    attempt = ExamAttempt()
    pending = {
        "skill_id": "logic.operations",
        "task_number": 2,
        "learning_support_status": "learning_module_pending",
    }
    ready = {"skill_id": "number_systems.large_number_digits", "task_number": 14}
    message, state, writes = _run(monkeypatch, _dna(pending, ready), attempt)

    assert message.answers[0] == "Для этого навыка учебный модуль ещё готовится"
    assert writes[-1][2] == "learning_path_in_progress"
    assert state.state == StudentEgeExamStates.waiting_learning_path_answer


def test_pending_only_does_not_create_exam_or_silently_loop(monkeypatch):
    attempt = ExamAttempt()
    pending = {
        "skill_id": "logic.operations",
        "task_number": 2,
        "learning_support_status": "learning_module_pending",
    }
    message, _state, writes = _run(monkeypatch, _dna(pending), attempt)

    assert writes == []
    assert message.answers == [
        "Для этого навыка учебный модуль ещё готовится",
        "Следующий доступный учебный модуль пока не найден.",
    ]


def test_restart_continues_current_learning_path(monkeypatch):
    from src.services.ege_learning_path import build_learning_path

    attempt = ExamAttempt()
    attempt.learning_path = build_learning_path(14).to_dict()
    message, state, writes = _run(monkeypatch, {}, attempt, "learning_path_in_progress")

    assert writes == []
    assert state.state == StudentEgeExamStates.waiting_learning_path_answer
    assert message.answers[0] == "▶️ Продолжаем индивидуальную учебную ветку №14."
