from pathlib import Path

# Student-facing task and remediation wording.
p = Path('src/services/ege_exam_service.py')
text = p.read_text(encoding='utf-8')
repls = {
    '"title": "Кластеризация и медоид"': '"title": "Кластеризация и центр кластера"',
    '"Медоид — это одна из точек самого кластера, для которой сумма расстояний "\n            "до остальных точек этого кластера минимальна. Для трёх точек на одной линии "\n            "обычно это средняя точка."': '"В актуальных заданиях №27 центр кластера задаётся прямо в условии: это одна из исходных точек, "\n            "для которой сумма расстояний до остальных точек кластера минимальна. В математике такой объект "\n            "часто называют медоидом, но ученику важнее следовать определению из условия ЕГЭ."',
    '"Пример: для точек (0,0), (0,2), (0,4) медоид — (0,2): она находится "\n            "между двумя другими точками и даёт минимальную сумму расстояний."': '"Пример: для точек (0,0), (0,2), (0,4) центр по условию ЕГЭ — (0,2): "\n            "сумма расстояний от неё до остальных точек минимальна."',
    '"Найди медоид каждого кластера. Затем сложи все четыре координаты двух найденных медоидов."': '"Найди центр каждого кластера по этому определению. Затем сложи все четыре координаты двух найденных центров."',
    '"B={(20,20),(22,20),(24,20)}. Медоидом кластера считается точка с минимальной "\n            "суммой расстояний до остальных точек своего кластера. Найдите сумму всех координат двух медоидов."': '"B={(20,20),(22,20),(24,20)}. Центром кластера считается одна из его точек с минимальной "\n            "суммой расстояний до остальных точек своего кластера. Найдите сумму всех координат двух центров."',
    '"explanation": "Медоид выбирают по минимальной сумме расстояний до объектов своего кластера."': '"explanation": "В №27 центр кластера выбирают среди исходных точек по минимальной сумме расстояний до остальных точек этого кластера."',
    '"example": "Если A=12, B=9, C=15, медоид B, потому что 9 — минимум."': '"example": "Если для кандидатов A, B, C суммы расстояний равны 12, 9 и 15, центр по условию — B, потому что 9 — минимум."',
    '"control_prompt": "Контроль: суммы A=14, B=11, C=17. Какой медоид выбрать? Ответь буквой A, B или C."': '"control_prompt": "Контроль: суммы расстояний для точек A=14, B=11, C=17. Какая точка будет центром кластера? Ответь A, B или C."',
    '"retest_prompt": "Перенос: суммы A=21, B=16, C=19. Какой медоид оптимален? Ответь буквой A, B или C."': '"retest_prompt": "Перенос: суммы расстояний для точек A=21, B=16, C=19. Какая точка будет центром кластера? Ответь A, B или C."',
    '"verification_prompt": "Независимая проверка: суммы A=18, B=23, C=15. Какой медоид оптимален? Ответь буквой A, B или C."': '"verification_prompt": "Независимая проверка: суммы расстояний для точек A=18, B=23, C=15. Какая точка будет центром кластера? Ответь A, B или C."',
}
for old, new in repls.items():
    if old not in text:
        raise SystemExit(f'missing service block: {old[:80]}')
    text = text.replace(old, new, 1)

# Add an explicit bridge from the small teaching example to the real exam task.
needle = '"Найди центр каждого кластера по этому определению. Затем сложи все четыре координаты двух найденных центров."\n        ),\n        "answer": "24",'
replacement = '"Найди центр каждого кластера по этому определению. Затем сложи все четыре координаты двух найденных центров."\n        ),\n        "exam_bridge": (\n            "Это учебная модель одного шага №27. В реальном КЕГЭ точки читаются из файлов, "\n            "их значительно больше, а разбиение и поиск центров выполняются программой."\n        ),\n        "answer": "24",'
if needle not in text:
    raise SystemExit('task27 exam bridge insertion point not found')
text = text.replace(needle, replacement, 1)

# Render the bridge only for task 27, without adding new generic architecture.
old = '''        f"✍️ Теперь попробуй сам:\\n{task['statement']}\\n\\n"\n        "Отправь только итоговый ответ."\n'''
new = '''        f"✍️ Теперь попробуй сам:\\n{task['statement']}\\n\\n"\n        + (f"🧩 Связь с реальным №27:\\n{task['exam_bridge']}\\n\\n" if task.get("exam_bridge") else "")\n        + "Отправь только итоговый ответ."\n'''
if old not in text:
    raise SystemExit('render_tutor_pilot_task block not found')
text = text.replace(old, new, 1)
p.write_text(text, encoding='utf-8')

# Student-facing diagnosis terminology. Keep the internal skill id for backward compatibility.
p = Path('src/ai_engine/diagnostics.py')
text = p.read_text(encoding='utf-8')
text = text.replace(
    '"description": "Ошибается при выборе медоида по минимальной сумме расстояний.",\n        "required_rule": "Медоид — объект кластера с минимальной суммой расстояний до остальных объектов этого кластера."',
    '"description": "Ошибается при выборе центра кластера по минимальной сумме расстояний.",\n        "required_rule": "В актуальном №27 центр выбирают среди точек кластера: сумма расстояний от него до остальных точек должна быть минимальной."',
    1,
)
p.write_text(text, encoding='utf-8')

# Human-readable Learning DNA name. Internal id remains programming.medoid_minimum to avoid migration churn.
p = Path('src/skills/ege_informatics_2026.json')
text = p.read_text(encoding='utf-8')
text = text.replace(
    '"name": "Выбор медоида по минимальной сумме расстояний"',
    '"name": "Выбор центра кластера по минимальной сумме расстояний"',
    1,
)
text = text.replace('"найти медоид",', '"найти центр кластера по условию",', 1)
p.write_text(text, encoding='utf-8')

# Regression protection for the terminology and real-exam bridge.
p = Path('tests/test_ege_tutor_pilot.py')
tests = p.read_text(encoding='utf-8')
addition = '''\n\ndef test_task27_uses_current_ege_center_definition_not_centroid_average():\n    rendered = render_tutor_pilot_task(27)\n    assert "одна из исходных точек" in rendered\n    assert "сумма расстояний" in rendered\n    assert "среднее арифметическое координат" not in rendered\n    assert "Связь с реальным №27" in rendered\n    assert "читаются из файлов" in rendered\n'''
if 'test_task27_uses_current_ege_center_definition_not_centroid_average' not in tests:
    tests += addition
p.write_text(tests, encoding='utf-8')

p = Path('tests/test_task27_remediation.py')
tests = p.read_text(encoding='utf-8')
addition = '''\n\ndef test_task27_center_remediation_uses_ege_wording():\n    lesson = TASK27_REMEDIATION["programming.medoid_minimum"]\n    assert "центр" in lesson["explanation"].lower()\n    assert "среди исходных точек" in lesson["explanation"].lower()\n    assert "медоид" not in lesson["control_prompt"].lower()\n'''
if 'test_task27_center_remediation_uses_ege_wording' not in tests:
    tests += addition
p.write_text(tests, encoding='utf-8')
