from pathlib import Path
import json

# Single source of truth stays in the subject map.
map_path = Path('src/skills/ege_informatics_2026.json')
data = json.loads(map_path.read_text(encoding='utf-8'))

reasoning = {1, 2, 4, 5, 6, 7, 8, 11, 12, 13, 14, 15, 16, 19, 20, 21, 23}
application = {3, 9, 10, 18, 22}
programming = {17, 24, 25, 26, 27}

all_tasks = reasoning | application | programming
assert all_tasks == set(range(1, 28))
assert not (reasoning & application or reasoning & programming or application & programming)

for task in data['tasks']:
    number = int(task['number'])
    if number in reasoning:
        task['solution_mode'] = 'reasoning'
        task['solution_mode_label'] = 'Рассуждение · можно решать без написания программы'
    elif number in application:
        task['solution_mode'] = 'application'
        task['solution_mode_label'] = 'Работа с приложением или файлом'
    else:
        task['solution_mode'] = 'programming'
        task['solution_mode_label'] = 'Программирование · решение через код'

map_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

# Add validated public helpers to the existing skill_graph module instead of
# creating a second registry with overlapping responsibility.
p = Path('src/skills/skill_graph.py')
text = p.read_text(encoding='utf-8')
old = '''        if not task.get("operations") or not task.get("typical_errors"):\n            raise SkillMapValidationError(\n                f"Task {task['number']} lacks operations or typical errors"\n            )\n        mastery = task.get("mastery", {})\n'''
new = '''        if not task.get("operations") or not task.get("typical_errors"):\n            raise SkillMapValidationError(\n                f"Task {task['number']} lacks operations or typical errors"\n            )\n        solution_mode = task.get("solution_mode")\n        if solution_mode not in {"reasoning", "application", "programming"}:\n            raise SkillMapValidationError(\n                f"Task {task['number']} has invalid solution_mode: {solution_mode!r}"\n            )\n        if not str(task.get("solution_mode_label", "")).strip():\n            raise SkillMapValidationError(\n                f"Task {task['number']} lacks solution_mode_label"\n            )\n        mastery = task.get("mastery", {})\n'''
if old not in text:
    raise SystemExit('skill_graph validation insertion point not found')
text = text.replace(old, new, 1)

insert_before = '''def task_diagnostic_path(task_number: int, skill_map: dict | None = None) -> list[str]:\n'''
helpers = '''def get_task(task_number: int, skill_map: dict | None = None) -> dict:\n    """Return one validated EGE task definition."""\n    subject_map = skill_map or load_skill_map()\n    task = next(\n        (item for item in subject_map["tasks"] if item["number"] == task_number),\n        None,\n    )\n    if task is None:\n        raise ValueError(f"Unknown EGE task: {task_number}")\n    return task\n\n\ndef get_task_solution_mode(task_number: int, skill_map: dict | None = None) -> str:\n    """Return reasoning/application/programming route for an EGE task."""\n    return str(get_task(task_number, skill_map)["solution_mode"])\n\n\ndef tasks_by_solution_mode(mode: str, skill_map: dict | None = None) -> list[int]:\n    """Return task numbers belonging to one tutor route."""\n    if mode not in {"reasoning", "application", "programming"}:\n        raise ValueError(f"Unknown solution mode: {mode}")\n    subject_map = skill_map or load_skill_map()\n    return [\n        int(task["number"])\n        for task in subject_map["tasks"]\n        if task.get("solution_mode") == mode\n    ]\n\n\n'''
if helpers not in text:
    if insert_before not in text:
        raise SystemExit('task_diagnostic_path insertion point not found')
    text = text.replace(insert_before, helpers + insert_before, 1)
p.write_text(text, encoding='utf-8')

# Make the pilot explicitly show that #27 belongs to another teaching route.
p = Path('src/telegram_bot/handlers/student.py')
text = p.read_text(encoding='utf-8')
old = '''        "🧑‍🏫 Пилот AI-репетитора · №5, №14 и №27\\n\\n"\n        "Сейчас задания даны в учебном режиме: сначала короткое объяснение и пример, "\n        "затем похожая задача для самостоятельного решения. По мере освоения навыка "\n        "подсказки будут убираться, пока формулировка не станет экзаменационной.\\n\\n"\n        "Диагностика появится только после реальной ошибки и не будет искать слабости наугад."\n'''
new = '''        "🧑‍🏫 Пилот AI-репетитора · два разных режима\\n\\n"\n        "📝 №5 и №14 — блок «Рассуждение»: их учим как задачи, которые можно разобрать "\n        "без написания программы.\\n\\n"\n        "💻 №27 — отдельный блок «Программирование»: здесь Tutor должен учить чтению файла, "\n        "построению алгоритма и написанию Python-кода, а не смешивать это с короткими задачами на листе.\\n\\n"\n        "В каждом режиме поддержка постепенно уменьшается. Диагностика появляется только после реальной ошибки."\n'''
if old not in text:
    raise SystemExit('pilot intro block not found')
text = text.replace(old, new, 1)
p.write_text(text, encoding='utf-8')

# Regression tests for the architectural split.
p = Path('tests/test_skill_graph.py')
t = p.read_text(encoding='utf-8') if p.exists() else ''
addition = '''\n\ndef test_ege_tasks_are_partitioned_by_solution_mode():\n    from src.skills.skill_graph import tasks_by_solution_mode\n    assert tasks_by_solution_mode("reasoning") == [1, 2, 4, 5, 6, 7, 8, 11, 12, 13, 14, 15, 16, 19, 20, 21, 23]\n    assert tasks_by_solution_mode("application") == [3, 9, 10, 18, 22]\n    assert tasks_by_solution_mode("programming") == [17, 24, 25, 26, 27]\n\n\ndef test_task27_is_programming_but_task5_and_14_are_reasoning():\n    from src.skills.skill_graph import get_task_solution_mode\n    assert get_task_solution_mode(27) == "programming"\n    assert get_task_solution_mode(5) == "reasoning"\n    assert get_task_solution_mode(14) == "reasoning"\n'''
if 'test_ege_tasks_are_partitioned_by_solution_mode' not in t:
    t += addition
p.write_text(t, encoding='utf-8')

p = Path('tests/test_ege_tutor_pilot.py')
t = p.read_text(encoding='utf-8')
addition = '''\n\ndef test_tutor_pilot_architecture_keeps_programming_separate_from_reasoning():\n    from src.skills.skill_graph import get_task_solution_mode\n    assert [get_task_solution_mode(n) for n in (5, 14)] == ["reasoning", "reasoning"]\n    assert get_task_solution_mode(27) == "programming"\n'''
if 'test_tutor_pilot_architecture_keeps_programming_separate_from_reasoning' not in t:
    t += addition
p.write_text(t, encoding='utf-8')
