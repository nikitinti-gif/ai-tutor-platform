import asyncio
from types import SimpleNamespace

import src.telegram_bot.handlers.student as student_handler
from src.services.ege_exam_service import create_task_first_tutor_attempt


class FakeState:
    def __init__(self):
        self.data = {}
        self.state = None
    async def clear(self):
        self.data = {}
        self.state = None
    async def set_state(self, value):
        self.state = value
    async def update_data(self, **kwargs):
        self.data.update(kwargs)
    async def get_data(self):
        return dict(self.data)


class FakeMessage:
    def __init__(self, text='23', user_id=42):
        self.text = text
        self.from_user = SimpleNamespace(id=user_id)
        self.answers = []
    async def answer(self, text, **_kwargs):
        self.answers.append(text)


def test_transfer_answer_survives_fsm_loss_and_continues_to_task14(monkeypatch):
    attempt = create_task_first_tutor_attempt()
    attempt.tutor_pilot_index = 0
    attempt.tutor_pilot_stage = 'transfer'
    saved = {'status': 'tutor_pilot_in_progress', 'attempt': attempt.to_dict()}
    monkeypatch.setattr(student_handler, 'get_ege_session', lambda user_id: saved)
    monkeypatch.setattr(student_handler, 'save_ege_session', lambda *args, **kwargs: None)

    state = FakeState()  # simulates empty MemoryStorage after deploy
    message = FakeMessage('23')
    asyncio.run(student_handler.resume_ege_tutor_pilot_after_restart(message, state))

    assert any('Получилось и без подсказки' in item for item in message.answers)
    assert any('УЧЕБНОЕ ЗАДАНИЕ · КЕГЭ №14' in item for item in message.answers)
    assert state.data['tutor_pilot_index'] == 1
    assert state.data['tutor_pilot_stage'] == 'supported'
