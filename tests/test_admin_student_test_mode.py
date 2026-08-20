import asyncio
import json
from types import SimpleNamespace

import pytest

from src.core.roles import ROLE_STUDENT, ROLE_TEACHER
from src.database import json_storage
from src.repositories.learning_dna_repository import LearningDNARepository
from src.repositories.user_repository import UserRepository
from src.telegram_bot.handlers import registration


class FakeMessage:
    def __init__(self, telegram_id):
        self.from_user = SimpleNamespace(id=telegram_id, full_name="Admin")
        self.answers = []

    async def answer(self, text, **_kwargs):
        self.answers.append(text)


class FakeState:
    def __init__(self):
        self.cleared = False

    async def clear(self):
        self.cleared = True


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    path = tmp_path / "database.json"
    path.write_text(
        json.dumps(
            {
                "users": [
                    {"telegram_id": 42, "full_name": "Admin", "role": "teacher"},
                    {"telegram_id": 99, "full_name": "Other", "role": "student"},
                ],
                "homework": [{"homework_id": "global"}],
                "student_homework": [
                    {"student_id": 42, "homework_id": "global"},
                    {"student_id": 99, "homework_id": "global"},
                ],
                "learning_dna": {"42": {"individual_plan": [1]}, "99": {"signals": [2]}},
                "ege_sessions": {"42": {"attempt": {"task_bank": {"done": 1}}}},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(json_storage, "DB_FILE", str(path))
    monkeypatch.setattr(registration, "ADMIN_TELEGRAM_ID", "42")
    return path


async def run_test_student(telegram_id=42):
    message, state = FakeMessage(telegram_id), FakeState()
    await registration.test_student(message, state)
    return message, state


def test_admin_test_student_changes_teacher_to_student(test_db):
    message, _ = asyncio.run(run_test_student())
    assert UserRepository.get_by_telegram_id(42)["role"] == ROLE_STUDENT
    assert message.answers[-1].startswith("🧪 Тестовый режим ученика включён.")


def test_test_student_clears_only_own_learning_dna(test_db):
    asyncio.run(run_test_student())
    assert LearningDNARepository.get(42) is None
    assert LearningDNARepository.get(99) == {"signals": [2]}


def test_test_student_does_not_change_other_user_or_global_data(test_db):
    asyncio.run(run_test_student())
    db = json_storage.load_db()
    assert UserRepository.get_by_telegram_id(99)["role"] == ROLE_STUDENT
    assert db["homework"] == [{"homework_id": "global"}]
    assert db["student_homework"] == [{"student_id": 99, "homework_id": "global"}]


def test_test_student_clears_exam_attempt(test_db):
    asyncio.run(run_test_student())
    assert json_storage.get_ege_session(42) is None


def test_test_student_clears_fsm(test_db):
    _, state = asyncio.run(run_test_student())
    assert state.cleared is True


def test_non_admin_cannot_use_test_student(test_db):
    before = test_db.read_text(encoding="utf-8")
    message, state = asyncio.run(run_test_student(99))
    assert message.answers == ["Команда недоступна."]
    assert state.cleared is False
    assert test_db.read_text(encoding="utf-8") == before


def test_restore_teacher_restores_saved_role(test_db):
    asyncio.run(run_test_student())
    message, state = FakeMessage(42), FakeState()
    asyncio.run(registration.restore_teacher(message, state))
    assert UserRepository.get_by_telegram_id(42)["role"] == ROLE_TEACHER
    assert state.cleared is True


def test_restore_teacher_keeps_student_e2e_data(test_db):
    asyncio.run(run_test_student())
    LearningDNARepository.save(42, {"signals": ["e2e"]})
    json_storage.save_ege_session(42, {"answers": [1]})
    asyncio.run(registration.restore_teacher(FakeMessage(42), FakeState()))
    assert LearningDNARepository.get(42) == {"signals": ["e2e"]}
    assert json_storage.get_ege_session(42)["attempt"] == {"answers": [1]}


def test_repeated_test_student_is_idempotent_and_keeps_original_role(test_db):
    asyncio.run(run_test_student())
    asyncio.run(run_test_student())
    asyncio.run(registration.restore_teacher(FakeMessage(42), FakeState()))
    assert UserRepository.get_by_telegram_id(42)["role"] == ROLE_TEACHER
