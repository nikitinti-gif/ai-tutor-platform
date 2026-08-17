import asyncio
from types import SimpleNamespace

import src.telegram_bot.handlers.student as student_handler
from src.ai_engine.diagnostics import CONTROL_PROBES
from src.services.ege_exam_service import TASK14_REMEDIATION, TASK27_REMEDIATION


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


def _patch_storage(monkeypatch, sessions, dna_store):
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
    monkeypatch.setattr(
        student_handler.LearningDNARepository,
        "get",
        staticmethod(lambda student_id: dna_store.get(student_id)),
    )
    monkeypatch.setattr(
        student_handler.LearningDNARepository,
        "save",
        staticmethod(lambda student_id, dna: dna_store.__setitem__(student_id, dna)),
    )


def _canonical_answer(task_number: int, base_probe_id: str) -> str:
    probe = next(
        item for item in CONTROL_PROBES[task_number]
        if item["id"] == base_probe_id
    )
    return str(probe["expected_answers"][0])


def _drive_diagnostics(state: FakeState, transcript: list[str]):
    """Disprove task 5; confirm operation 0 of tasks 14 and 27 through handlers."""
    for _ in range(30):
        data = asyncio.run(state.get_data())
        attempt = data.get("ege_attempt") or {}
        remediation = attempt.get("remediation") or {}
        if remediation:
            return

        diagnostics = attempt.get("diagnostics") or {}
        pending_task = None
        pending = None
        for task_number in (5, 14, 27):
            candidate = (diagnostics.get(task_number) or {}).get("pending_probe")
            if candidate:
                pending_task = task_number
                pending = candidate
                break
        assert pending_task is not None and pending is not None

        if pending_task == 5:
            answer = _canonical_answer(pending_task, pending["base_probe_id"])
        elif int(pending["operation_index"]) == 0:
            answer = "definitely-wrong"
        else:
            answer = _canonical_answer(pending_task, pending["base_probe_id"])

        message = FakeMessage(text=answer)
        asyncio.run(student_handler.receive_ege_diagnostic_answer(message, state))
        transcript.extend(message.answers)

        data = asyncio.run(state.get_data())
        if (data.get("ege_attempt") or {}).get("remediation"):
            return

    raise AssertionError("Telegram diagnostics did not reach remediation")


def _drive_remediation(state: FakeState, transcript: list[str]):
    """Answer CONTROL -> TRANSFER -> VERIFY for task 14 and then task 27."""
    for _ in range(12):
        data = asyncio.run(state.get_data())
        attempt = data.get("ege_attempt") or {}
        remediation = attempt.get("remediation") or {}
        if not remediation:
            if state.cleared:
                return
            raise AssertionError("Remediation disappeared before Telegram flow completed")

        task_number = int(remediation["task_number"])
        stage = remediation["stage"]
        if task_number == 14:
            lesson = TASK14_REMEDIATION[remediation["gap_id"]]
        else:
            lesson = TASK27_REMEDIATION[remediation["skill_id"]]
        answer = str(lesson[f"{stage}_answers"][0])

        message = FakeMessage(text=answer)
        asyncio.run(student_handler.receive_ege_remediation_answer(message, state))
        transcript.extend(message.answers)
        if state.cleared:
            return

    raise AssertionError("Telegram remediation did not finish")


def test_pilot_full_telegram_loop_updates_verified_learning_dna(monkeypatch):
    """Protect the real handler/FSM route from pilot start through final mastery."""
    sessions = {}
    dna_store = {}
    _patch_storage(monkeypatch, sessions, dna_store)

    state = FakeState()
    start = FakeMessage()
    asyncio.run(student_handler.start_ege_diagnostic_pilot(start, state))
    transcript = list(start.answers)

    assert any("Пилот разбора ошибок №5, №14 и №27" in text for text in transcript)
    assert sessions[42]["status"] == "diagnostics_in_progress"

    _drive_diagnostics(state, transcript)

    dna = dna_store[42]
    plan = dna["trajectory"]["individual_plan"]
    assert [item["task_number"] for item in plan] == [14, 27]
    assert plan[0]["skill_id"] == "number_systems.calculate_remainder"
    assert plan[1]["skill_id"] == "programming.cluster_count_from_separation"
    assert not any(item["task_number"] == 5 for item in plan)
    assert sessions[42]["status"] == "remediation_in_progress"
    assert any("КОРОТКОЕ ОБУЧЕНИЕ · №14" in text for text in transcript)
    assert any("Точка ошибки подтверждена двумя независимыми пробами" in text for text in transcript)
    assert any("Что нужно повторить:" in text for text in transcript)
    assert any("Ошибается при вычислении остатка" in text for text in transcript)

    _drive_remediation(state, transcript)

    assert state.cleared is True
    assert sessions[42]["status"] == "completed"
    dna = dna_store[42]

    task14 = dna["skills"]["number_systems.calculate_remainder"]
    task27 = dna["skills"]["programming.cluster_count_from_separation"]
    assert task14["mastered"] is True
    assert task27["mastered"] is True
    assert len(task14["remediation_evidence"]) == 3
    assert len(task27["remediation_evidence"]) == 3
    assert [item["stage"] for item in task14["remediation_evidence"]] == [
        "control", "retest", "verification"
    ]
    assert [item["stage"] for item in task27["remediation_evidence"]] == [
        "control", "retest", "verification"
    ]

    next_focus = dna["trajectory"].get("next_focus_skill_id")
    assert next_focus not in {
        "number_systems.calculate_remainder",
        "programming.cluster_count_from_separation",
    }
    assert any("Переходим к следующему доказанному пробелу — №27" in text for text in transcript)
    assert any("КОРОТКОЕ ОБУЧЕНИЕ · №27" in text for text in transcript)
    assert any("🏆 Навык подтверждён" in text for text in transcript)


def test_task27_correct_first_probe_stops_before_unrelated_center_probe(monkeypatch):
    sessions = {}
    dna_store = {}
    _patch_storage(monkeypatch, sessions, dna_store)
    from src.services.ege_exam_service import ExamAttempt, bind_current_diagnostic_probe, mark_current_diagnostic_probe_displayed, next_attempt_diagnostic_probe, submit_diagnostic_answer
    from src.ai_engine.diagnostics import open_diagnostic_case
    from src.skills.skill_graph import load_skill_map
    attempt = ExamAttempt()
    attempt.diagnostics = {27: open_diagnostic_case(27, "wrong", "expected", load_skill_map())}
    bind_current_diagnostic_probe(attempt); mark_current_diagnostic_probe_displayed(attempt)
    result = submit_diagnostic_answer(attempt, "2")
    assert result["is_correct"] is True
    assert attempt.diagnostics[27]["status"] != "confirmed"
    assert next_attempt_diagnostic_probe(attempt) is None


def test_task27_remediation_accepts_numeric_minimum_as_concept_evidence():
    from src.services.ege_exam_service import ExamAttempt, submit_task27_remediation_answer
    attempt = ExamAttempt()
    attempt.remediation = {
        "task_number": 27, "skill_id": "programming.medoid_minimum", "status": "remediating", "stage": "control",
        "control_attempts": 0, "retest_attempts": 0, "verification_attempts": 0, "learning_round": 1, "stage_history": []
    }
    result = submit_task27_remediation_answer(attempt, "11")
    assert result["is_correct"] is True
    assert attempt.remediation["stage"] == "retest"
