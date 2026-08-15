from pathlib import Path

# Add a task-first pilot: learner solves three compact EGE-like tasks first;
# diagnostics only opens for tasks actually answered incorrectly.
p = Path('src/services/ege_exam_service.py')
text = p.read_text(encoding='utf-8')
marker = '\n\ndef create_pilot_diagnostic_attempt() -> ExamAttempt:\n'
insert = r'''

TUTOR_PILOT_TASKS = {
    5: {
        "title": "Алгоритм над двоичной записью",
        "statement": (
            "Для натурального числа N строится двоичная запись. Если она оканчивается на 1, "
            "справа дописывают 0, иначе справа дописывают 11. Полученная запись задаёт число R. "
            "Найдите наибольшее N от 10 до 20 включительно, для которого R < 40."
        ),
        "answer": "19",
    },
    14: {
        "title": "Системы счисления",
        "statement": (
            "Число 431 записано в десятичной системе. Переведите его в шестнадцатеричную "
            "систему и определите, сколько цифр этой записи имеют чётное числовое значение. "
            "В ответе укажите только количество таких цифр."
        ),
        "answer": "2",  # 431 = 1AF_16; 10(A) is even, 1 and 15(F) are odd -> one.
    },
    27: {
        "title": "Кластеризация",
        "statement": (
            "Даны два явно разделённых кластера точек: A={(0,0),(0,2),(0,4)} и "
            "B={(10,10),(12,10),(14,10)}. Центром каждого кластера считается его медоид — "
            "точка с минимальной суммой расстояний до остальных точек своего кластера. "
            "Найдите сумму всех координат двух медоидов."
        ),
        "answer": "24",
    },
}

# Correct the canonical answer explicitly: 431 = 1AF_16, only A=10 is even.
TUTOR_PILOT_TASKS[14]["answer"] = "1"


def render_tutor_pilot_task(task_number: int) -> str:
    task = TUTOR_PILOT_TASKS[task_number]
    return (
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🎓 ТРЕНИРОВОЧНОЕ ЗАДАНИЕ · №{task_number}\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📚 {task['title']}\n\n"
        f"{task['statement']}\n\n"
        "✍️ Отправь только итоговый ответ."
    )


def verify_tutor_pilot_answer(task_number: int, answer: str) -> bool:
    expected = str(TUTOR_PILOT_TASKS[task_number]["answer"]).strip().lower()
    return answer.strip().lower() == expected


def create_task_first_tutor_attempt() -> ExamAttempt:
    """Create an empty pilot attempt; cases are opened only after real mistakes."""
    return ExamAttempt(current_task=TOTAL_TASKS + 1)


def record_tutor_pilot_answer(attempt: ExamAttempt, task_number: int, answer: str) -> bool:
    """Record a compact EGE-like task and open diagnostics only on an actual error."""
    is_correct = verify_tutor_pilot_answer(task_number, answer)
    expected = str(TUTOR_PILOT_TASKS[task_number]["answer"])
    attempt.answers[task_number] = answer
    attempt.results[task_number] = is_correct
    if is_correct:
        attempt.diagnostics.pop(task_number, None)
    else:
        attempt.diagnostics[task_number] = open_diagnostic_case(
            task_number=task_number,
            student_answer=answer,
            expected_answer=expected,
            skill_map=load_skill_map(),
        )
    return is_correct
'''
if 'TUTOR_PILOT_TASKS = {' not in text:
    if marker not in text:
        raise SystemExit('pilot insertion marker missing')
    text = text.replace(marker, insert + marker, 1)
p.write_text(text, encoding='utf-8')

# FSM state.
p = Path('src/telegram_bot/states/student_states.py')
text = p.read_text(encoding='utf-8')
old = '''class StudentEgeExamStates(StatesGroup):\n    waiting_answer = State()\n    waiting_diagnostic_answer = State()\n    waiting_remediation_answer = State()\n'''
new = '''class StudentEgeExamStates(StatesGroup):\n    waiting_answer = State()\n    waiting_tutor_pilot_answer = State()\n    waiting_diagnostic_answer = State()\n    waiting_remediation_answer = State()\n'''
if old not in text:
    raise SystemExit('student state block missing')
text = text.replace(old, new, 1)
p.write_text(text, encoding='utf-8')

# Telegram handlers.
p = Path('src/telegram_bot/handlers/student.py')
text = p.read_text(encoding='utf-8')
insert_before = '\n\nasync def start_ege_diagnostic_pilot(message: Message, state: FSMContext):\n'
new_handlers = r'''

async def start_ege_tutor_pilot(message: Message, state: FSMContext):
    """Task-first pilot: normal EGE-like tasks before any diagnostic question."""
    is_admin = bool(
        ADMIN_TELEGRAM_ID
        and str(message.from_user.id) == str(ADMIN_TELEGRAM_ID)
    )
    if not is_admin:
        await message.answer("⛔ Эта тестовая команда доступна только администратору.")
        return
    from src.services.ege_exam_service import create_task_first_tutor_attempt, render_tutor_pilot_task

    delete_ege_session(message.from_user.id)
    await state.clear()
    attempt = create_task_first_tutor_attempt()
    await state.set_state(StudentEgeExamStates.waiting_tutor_pilot_answer)
    await state.update_data(ege_attempt=attempt.to_dict(), tutor_pilot_index=0)
    save_ege_session(message.from_user.id, attempt.to_dict(), status="tutor_pilot_in_progress")
    await message.answer(
        "🧑‍🏫 Пилот AI-репетитора · №5, №14 и №27\n\n"
        "Сначала реши обычные короткие задания в стиле КЕГЭ. "
        "Диагностика появится только там, где ответ действительно неверный. "
        "Если диагностическая проверка выполнена верно, искать другие слабости наугад не буду."
    )
    await message.answer(render_tutor_pilot_task(5))


async def receive_ege_tutor_pilot_answer(message: Message, state: FSMContext) -> None:
    from src.services.ege_exam_service import (
        ExamAttempt,
        record_tutor_pilot_answer,
        render_tutor_pilot_task,
    )
    data = await state.get_data()
    attempt_data = data.get("ege_attempt")
    if not attempt_data:
        await state.clear()
        await message.answer("Пилотная сессия не найдена. Запусти /test_ege_tutor.")
        return
    attempt = ExamAttempt.from_dict(attempt_data)
    tasks = (5, 14, 27)
    index = int(data.get("tutor_pilot_index", 0))
    if not 0 <= index < len(tasks):
        await state.clear()
        await message.answer("Пилотная сессия завершена. Запусти /test_ege_tutor заново.")
        return
    task_number = tasks[index]
    is_correct = record_tutor_pilot_answer(attempt, task_number, message.text or "")
    await message.answer(
        "✅ Верно." if is_correct else "❌ Ответ неверный. Сначала закончим три задания, затем разберём только реальные ошибки."
    )
    index += 1
    await state.update_data(ege_attempt=attempt.to_dict(), tutor_pilot_index=index)
    save_ege_session(message.from_user.id, attempt.to_dict(), status="tutor_pilot_in_progress")
    if index < len(tasks):
        await message.answer(render_tutor_pilot_task(tasks[index]))
        return
    if not attempt.diagnostics:
        save_ege_session(message.from_user.id, attempt.to_dict(), status="completed")
        await state.clear()
        await message.answer("🏆 Все три задания выполнены верно. Диагностика не нужна.")
        return
    await message.answer(
        "Теперь разберём только те задания, где была ошибка. "
        "Каждая диагностическая проверка будет короткой и привязанной к конкретному навыку."
    )
    await _begin_ege_diagnostics(message, state, attempt)
'''
if 'async def start_ege_tutor_pilot' not in text:
    if insert_before not in text:
        raise SystemExit('handler insertion marker missing')
    text = text.replace(insert_before, new_handlers + insert_before, 1)

old = '''    dp.message.register(start_ege_diagnostic_pilot, F.text == "/test_ege_diagnostics")\n'''
new = '''    dp.message.register(start_ege_tutor_pilot, F.text == "/test_ege_tutor")\n    dp.message.register(start_ege_diagnostic_pilot, F.text == "/test_ege_diagnostics")\n'''
if old not in text:
    raise SystemExit('registration marker missing')
text = text.replace(old, new, 1)
old2 = '''    dp.message.register(skip_ege_task, StudentEgeExamStates.waiting_answer, F.text == "/skip_ege")\n'''
new2 = '''    dp.message.register(receive_ege_tutor_pilot_answer, StudentEgeExamStates.waiting_tutor_pilot_answer)\n    dp.message.register(skip_ege_task, StudentEgeExamStates.waiting_answer, F.text == "/skip_ege")\n'''
if old2 not in text:
    raise SystemExit('state registration marker missing')
text = text.replace(old2, new2, 1)
p.write_text(text, encoding='utf-8')

# Regression tests for task-first behavior.
p = Path('tests/test_ege_tutor_pilot.py')
p.write_text(r'''from src.services.ege_exam_service import (
    TUTOR_PILOT_TASKS,
    create_task_first_tutor_attempt,
    record_tutor_pilot_answer,
    render_tutor_pilot_task,
)


def test_tutor_pilot_starts_without_fake_diagnostic_cases():
    attempt = create_task_first_tutor_attempt()
    assert attempt.diagnostics == {}
    assert attempt.results == {}


def test_tutor_pilot_opens_case_only_after_real_error():
    attempt = create_task_first_tutor_attempt()
    assert record_tutor_pilot_answer(attempt, 5, TUTOR_PILOT_TASKS[5]["answer"]) is True
    assert 5 not in attempt.diagnostics
    assert record_tutor_pilot_answer(attempt, 14, "999") is False
    assert 14 in attempt.diagnostics
    assert attempt.diagnostics[14]["student_answer"] == "999"
    assert attempt.diagnostics[14]["expected_answer"] == TUTOR_PILOT_TASKS[14]["answer"]


def test_tutor_pilot_tasks_are_student_facing_not_engine_audit():
    for task_number in (5, 14, 27):
        rendered = render_tutor_pilot_task(task_number)
        assert "Гипотеза:" not in rendered
        assert "Почему эта проба подходит" not in rendered
        assert "FALLBACK_PROBE" not in rendered
        assert "TRAIN" not in rendered
        assert "Отправь только итоговый ответ" in rendered


def test_tutor_pilot_canonical_answers():
    attempt = create_task_first_tutor_attempt()
    assert record_tutor_pilot_answer(attempt, 5, "19") is True
    assert record_tutor_pilot_answer(attempt, 14, "1") is True
    assert record_tutor_pilot_answer(attempt, 27, "24") is True
    assert attempt.diagnostics == {}
''', encoding='utf-8')
