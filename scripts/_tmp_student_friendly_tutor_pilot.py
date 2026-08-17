from pathlib import Path

p = Path('src/services/ege_exam_service.py')
text = p.read_text(encoding='utf-8')
start = text.index('TUTOR_PILOT_TASKS = {\n')
end = text.index('\n\ndef verify_tutor_pilot_answer', start)
replacement = r'''TUTOR_PILOT_TASKS = {
    5: {
        "title": "Алгоритм с двоичной записью",
        "teacher_intro": (
            "Сначала разберём смысл алгоритма. Для каждого N нужно получить новое число R: "
            "перевести N в двоичную запись, дописать биты по правилу и затем прочитать "
            "получившуюся запись как новое двоичное число."
        ),
        "worked_example": (
            "Пример с другим числом: N = 13. 13₁₀ = 1101₂. Последняя цифра 1, "
            "поэтому справа дописываем 0: 11010₂. Это 26₁₀, значит для N = 13 получаем R = 26."
        ),
        "statement": (
            "Рассматриваются натуральные числа N от 10 до 20 включительно. Для каждого N:\n"
            "1) запиши N в двоичной системе;\n"
            "2) если последняя цифра записи равна 1 — допиши справа 0;\n"
            "3) если последняя цифра равна 0 — допиши справа 11;\n"
            "4) получившуюся двоичную запись переведи обратно в десятичное число. Это число R.\n\n"
            "Найди наибольшее N, для которого R < 40."
        ),
        "answer": "19",
    },
    14: {
        "title": "Системы счисления",
        "teacher_intro": (
            "В шестнадцатеричной системе после 9 используются A, B, C, D, E, F. "
            "Их числовые значения: A=10, B=11, C=12, D=13, E=14, F=15. "
            "Чётность проверяем именно по числовому значению цифры."
        ),
        "worked_example": (
            "Пример: 26₁₀ = 1A₁₆. Значения цифр — 1 и 10. Из них чётное только 10, "
            "поэтому чётных цифр в записи одна."
        ),
        "statement": (
            "Переведи число 431 из десятичной системы в шестнадцатеричную. "
            "После этого посчитай, сколько цифр полученной записи имеют чётное числовое значение."
        ),
        "answer": "1",
    },
    27: {
        "title": "Кластеризация и медоид",
        "teacher_intro": (
            "Медоид — это одна из точек самого кластера, для которой сумма расстояний "
            "до остальных точек этого кластера минимальна. Для трёх точек на одной линии "
            "обычно это средняя точка."
        ),
        "worked_example": (
            "Пример: для точек (0,0), (0,2), (0,4) медоид — (0,2): она находится "
            "между двумя другими точками и даёт минимальную сумму расстояний."
        ),
        "statement": (
            "Даны два уже выделенных кластера:\n"
            "A = {(0,0), (0,2), (0,4)}\n"
            "B = {(10,10), (12,10), (14,10)}\n\n"
            "Найди медоид каждого кластера. Затем сложи все четыре координаты двух найденных медоидов."
        ),
        "answer": "24",
    },
}


def render_tutor_pilot_task(task_number: int) -> str:
    task = TUTOR_PILOT_TASKS[task_number]
    return (
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🧑‍🏫 УЧЕБНОЕ ЗАДАНИЕ · КЕГЭ №{task_number}\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📚 {task['title']}\n\n"
        f"💡 Что здесь нужно понять:\n{task['teacher_intro']}\n\n"
        f"🔹 Разобранный пример:\n{task['worked_example']}\n\n"
        f"✍️ Теперь попробуй сам:\n{task['statement']}\n\n"
        "Отправь только итоговый ответ."
    )
'''
text = text[:start] + replacement + text[end:]
p.write_text(text, encoding='utf-8')

p = Path('src/telegram_bot/handlers/student.py')
text = p.read_text(encoding='utf-8')
old = '''    await message.answer(
        "🧑‍🏫 Пилот AI-репетитора · №5, №14 и №27\\n\\n"
        "Сначала реши обычные короткие задания в стиле КЕГЭ. "
        "Диагностика появится только там, где ответ действительно неверный. "
        "Если диагностическая проверка выполнена верно, искать другие слабости наугад не буду."
    )
'''
new = '''    await message.answer(
        "🧑‍🏫 Пилот AI-репетитора · №5, №14 и №27\\n\\n"
        "Сейчас задания даны в учебном режиме: сначала короткое объяснение и пример, "
        "затем похожая задача для самостоятельного решения. По мере освоения навыка "
        "подсказки будут убираться, пока формулировка не станет экзаменационной.\\n\\n"
        "Диагностика появится только после реальной ошибки и не будет искать слабости наугад."
    )
'''
if old not in text:
    raise SystemExit('tutor pilot intro block not found')
text = text.replace(old, new, 1)
p.write_text(text, encoding='utf-8')

p = Path('tests/test_ege_tutor_pilot.py')
text = p.read_text(encoding='utf-8')
addition = '''\n\ndef test_tutor_pilot_scaffolds_before_exam_style():\n    rendered = render_tutor_pilot_task(5)\n    assert "Что здесь нужно понять" in rendered\n    assert "Разобранный пример" in rendered\n    assert "Теперь попробуй сам" in rendered\n    assert "1) запиши N в двоичной системе" in rendered\n    assert "получившуюся двоичную запись переведи обратно" in rendered\n    assert "Полученная запись задаёт число R" not in rendered\n\n\ndef test_each_tutor_task_has_teacher_scaffolding():\n    for task_number in (5, 14, 27):\n        task = TUTOR_PILOT_TASKS[task_number]\n        assert task["teacher_intro"]\n        assert task["worked_example"]\n        rendered = render_tutor_pilot_task(task_number)\n        assert task["worked_example"] in rendered\n        assert "Отправь только итоговый ответ" in rendered\n'''
if 'test_tutor_pilot_scaffolds_before_exam_style' not in text:
    text += addition
p.write_text(text, encoding='utf-8')
