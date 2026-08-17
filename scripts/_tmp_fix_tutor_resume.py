from pathlib import Path

service_path = Path('src/services/ege_exam_service.py')
text = service_path.read_text(encoding='utf-8')
text = text.replace(
'''    diagnostics: dict[int, dict] = field(default_factory=dict)\n    remediation: dict = field(default_factory=dict)\n''',
'''    diagnostics: dict[int, dict] = field(default_factory=dict)\n    remediation: dict = field(default_factory=dict)\n    tutor_pilot_index: int = 0\n    tutor_pilot_stage: str = "supported"\n''')
text = text.replace(
'''            {int(k): dict(v) for k, v in data.get("diagnostics", {}).items()},\n            dict(data.get("remediation", {})),\n        )\n''',
'''            {int(k): dict(v) for k, v in data.get("diagnostics", {}).items()},\n            dict(data.get("remediation", {})),\n            int(data.get("tutor_pilot_index", 0)),\n            str(data.get("tutor_pilot_stage", "supported")),\n        )\n''')
service_path.write_text(text, encoding='utf-8')

student_path = Path('src/telegram_bot/handlers/student.py')
text = student_path.read_text(encoding='utf-8')
text = text.replace(
'''    attempt = create_task_first_tutor_attempt()\n    await state.set_state(StudentEgeExamStates.waiting_tutor_pilot_answer)\n    await state.update_data(ege_attempt=attempt.to_dict(), tutor_pilot_index=0, tutor_pilot_stage="supported")\n''',
'''    attempt = create_task_first_tutor_attempt()\n    attempt.tutor_pilot_index = 0\n    attempt.tutor_pilot_stage = "supported"\n    await state.set_state(StudentEgeExamStates.waiting_tutor_pilot_answer)\n    await state.update_data(ege_attempt=attempt.to_dict(), tutor_pilot_index=0, tutor_pilot_stage="supported")\n''')
text = text.replace(
'''    index = int(data.get("tutor_pilot_index", 0))\n    stage = str(data.get("tutor_pilot_stage", "supported"))\n''',
'''    index = int(data.get("tutor_pilot_index", attempt.tutor_pilot_index))\n    stage = str(data.get("tutor_pilot_stage", attempt.tutor_pilot_stage))\n    attempt.tutor_pilot_index = index\n    attempt.tutor_pilot_stage = stage\n''')
text = text.replace(
'''            await state.update_data(\n                ege_attempt=attempt.to_dict(), tutor_pilot_stage="task27_file_b"\n            )\n''',
'''            attempt.tutor_pilot_stage = "task27_file_b"\n            await state.update_data(\n                ege_attempt=attempt.to_dict(), tutor_pilot_stage="task27_file_b"\n            )\n''')
text = text.replace(
'''            await state.update_data(ege_attempt=attempt.to_dict(), tutor_pilot_stage="transfer")\n''',
'''            attempt.tutor_pilot_stage = "transfer"\n            await state.update_data(ege_attempt=attempt.to_dict(), tutor_pilot_stage="transfer")\n''')
text = text.replace(
'''                await state.update_data(\n                    ege_attempt=attempt.to_dict(), tutor_pilot_stage="task27_file_a"\n                )\n''',
'''                attempt.tutor_pilot_stage = "task27_file_a"\n                await state.update_data(\n                    ege_attempt=attempt.to_dict(), tutor_pilot_stage="task27_file_a"\n                )\n''')
text = text.replace(
'''    index += 1\n    await state.update_data(ege_attempt=attempt.to_dict(), tutor_pilot_index=index, tutor_pilot_stage="supported")\n''',
'''    index += 1\n    attempt.tutor_pilot_index = index\n    attempt.tutor_pilot_stage = "supported"\n    await state.update_data(ege_attempt=attempt.to_dict(), tutor_pilot_index=index, tutor_pilot_stage="supported")\n''')

marker = '''\n\nasync def start_ege_diagnostic_pilot(message: Message, state: FSMContext):\n'''
resume_fn = '''\n\nasync def resume_ege_tutor_pilot_after_restart(message: Message, state: FSMContext) -> None:\n    """Recover a persisted tutor pilot when in-memory FSM was lost on restart/deploy."""\n    saved = get_ege_session(message.from_user.id)\n    if not saved or saved.get("status") != "tutor_pilot_in_progress":\n        from aiogram.dispatcher.event.bases import SkipHandler\n        raise SkipHandler\n\n    from src.services.ege_exam_service import ExamAttempt\n    attempt = ExamAttempt.from_dict(saved.get("attempt"))\n    await state.set_state(StudentEgeExamStates.waiting_tutor_pilot_answer)\n    await state.update_data(\n        ege_attempt=attempt.to_dict(),\n        tutor_pilot_index=attempt.tutor_pilot_index,\n        tutor_pilot_stage=attempt.tutor_pilot_stage,\n    )\n    await receive_ege_tutor_pilot_answer(message, state)\n'''
if resume_fn.strip() not in text:
    text = text.replace(marker, resume_fn + marker)
text = text.replace(
'''    dp.message.register(student_question, F.text == "❓ Задать вопрос")\n''',
'''    dp.message.register(student_question, F.text == "❓ Задать вопрос")\n    dp.message.register(resume_ege_tutor_pilot_after_restart, F.text)\n''')
student_path.write_text(text, encoding='utf-8')

# Regression test: a deploy/restart after the transfer question must not lose answer 23.
test_path = Path('tests/test_tutor_pilot_restart_recovery.py')
test_path.write_text(r'''import asyncio
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
''', encoding='utf-8')
