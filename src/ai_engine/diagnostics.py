"""Evidence-based local diagnostics for completed KЕГЭ attempts.

The module deliberately separates a suspected error from a confirmed one.
An incorrect final answer is enough to open a case, but never enough to claim
that a particular reasoning step failed.
"""

from __future__ import annotations

from copy import deepcopy
import re


DIAGNOSIS_NEEDS_EVIDENCE = "needs_evidence"
DIAGNOSIS_PROBABLE = "probable"
DIAGNOSIS_CONFIRMED = "confirmed"


# The first production-quality probe set.  Each probe checks exactly one
# operation from the official task map and has a locally verifiable answer.
# Further KЕГЭ tasks must use this same contract; free-form AI judgements are
# deliberately not accepted as diagnostic evidence.
CONTROL_PROBES = {
    1: (
        {"id": "task01_vertex_mapping_v1", "operation_index": 0, "prompt": "В графе степени вершин A, B, C равны 1, 2, 1. Какая вершина соединена и с A, и с C?", "expected_answers": ("B", "Б")},
        {"id": "task01_edge_weight_v1", "operation_index": 1, "prompt": "Путь состоит из рёбер весом 7 и 11. Каков его общий вес?", "expected_answers": ("18",)},
    ),
    2: (
        {"id": "task02_expression_v1", "operation_index": 0, "prompt": "Чему равно (x И y) ИЛИ z при x=1, y=0, z=1?", "expected_answers": ("1",)},
        {"id": "task02_rows_v1", "operation_index": 1, "prompt": "Сколько наборов значений существует для трёх логических переменных?", "expected_answers": ("8",)},
        {"id": "task02_variable_order_v1", "operation_index": 2, "prompt": "В строках 000, 011 и 101 значения первого столбца равны 0, 0, 1. Какой вектор имеет первый столбец?", "expected_answers": ("001",)},
    ),
    3: (
        {"id": "task03_join_keys_v1", "operation_index": 0, "prompt": "В таблице Продажи поле product_id=7. В таблице Товары строка с id=7 содержит цену 120. Какую цену присоединит связь по ключу?", "expected_answers": ("120",)},
        {"id": "task03_filter_v1", "operation_index": 1, "prompt": "После фильтра район=Север и дата позже 01.03 остались строки: Север 02.03, Юг 04.03, Север 28.02. Сколько строк подходит?", "expected_answers": ("1",)},
        {"id": "task03_packages_v1", "operation_index": 2, "prompt": "В трёх упаковках по 12 единиц. Сколько единиц товара?", "expected_answers": ("36",)},
        {"id": "task03_sum_v1", "operation_index": 3, "prompt": "Сложите количества 24, 18 и 8.", "expected_answers": ("50",)},
    ),
    4: (
        {"id": "task04_prefix_v1", "operation_index": 0, "prompt": "Нарушает ли набор кодов 0, 10, 110 условие Фано? Ответьте да или нет.", "expected_answers": ("нет", "no")},
        {"id": "task04_tree_v1", "operation_index": 1, "prompt": "В двоичном кодовом дереве заняты листья 0 и 10. Какое кратчайшее свободное кодовое слово начинается с 11?", "expected_answers": ("11",)},
        {"id": "task04_min_word_v1", "operation_index": 2, "prompt": "Из допустимых кодовых слов 110, 1110 и 1111 выберите слово минимальной длины.", "expected_answers": ("110",)},
    ),
    5: (
        {"id": "task05_binary_v1", "operation_index": 0, "prompt": "Запишите число 13 в двоичной системе без ведущих нулей.", "expected_answers": ("1101",)},
        {"id": "task05_branch_v1", "operation_index": 1, "prompt": "Если последняя двоичная цифра равна 1, выполняется ветка A, иначе B. Какая ветка для строки 1010?", "expected_answers": ("B", "Б")},
        {"id": "task05_string_change_v1", "operation_index": 2, "prompt": "К двоичной строке 101 приписали справа 0. Какая строка получилась?", "expected_answers": ("1010",)},
        {"id": "task05_boundary_v1", "operation_index": 3, "prompt": "Условию n < 8 удовлетворяет граничное целое 8? Ответьте да или нет.", "expected_answers": ("нет", "no")},
    ),
    6: (
        {"id": "task06_contour_v1", "operation_index": 0, "prompt": "Черепаха прошла вправо 4, вверх 3, влево 4, вниз 3. Замкнут ли контур? Ответьте да или нет.", "expected_answers": ("да", "yes")},
        {"id": "task06_boundary_v1", "operation_index": 1, "prompt": "Точка (0,2) лежит на стороне квадрата 0≤x≤3, 0≤y≤3? Ответьте да или нет.", "expected_answers": ("да", "yes")},
        {"id": "task06_inner_points_v1", "operation_index": 2, "prompt": "Сколько целочисленных точек строго внутри квадрата 0<x<3, 0<y<3?", "expected_answers": ("4",)},
    ),
    7: (
        {"id": "task07_volume_formula_v1", "operation_index": 0, "prompt": "Сколько бит занимает 100 отсчётов при глубине кодирования 16 бит?", "expected_answers": ("1600",)},
        {"id": "task07_channels_duration_v1", "operation_index": 1, "prompt": "Сколько отсчётов всего в стереозаписи длительностью 2 секунды при частоте 1000 Гц?", "expected_answers": ("4000",)},
        {"id": "task07_units_v1", "operation_index": 2, "prompt": "Сколько байт составляют 8192 бита?", "expected_answers": ("1024",)},
    ),
    8: (
        {"id": "task08_position_v1", "operation_index": 0, "prompt": "Двухбуквенные слова из A, B идут как AA, AB, BA, BB. Какой номер у BA?", "expected_answers": ("3",)},
        {"id": "task08_constraints_v1", "operation_index": 1, "prompt": "Сколько слов из списка AA, AB, BA, BB не начинаются с B?", "expected_answers": ("2",)},
        {"id": "task08_odd_position_v1", "operation_index": 2, "prompt": "Является ли номер слова BA в порядке AA, AB, BA, BB нечётным? Ответьте да или нет.", "expected_answers": ("да", "yes")},
    ),
    9: (
        {"id": "task09_max_v1", "operation_index": 0, "prompt": "Найдите максимум среди чисел 7, 12, 5, 9.", "expected_answers": ("12",)},
        {"id": "task09_pairings_v1", "operation_index": 1, "prompt": "Сколько различных разбиений четырёх разных чисел на две неупорядоченные пары?", "expected_answers": ("3",)},
        {"id": "task09_count_rows_v1", "operation_index": 2, "prompt": "Условие выполнилось в строках 2, 5 и 9. Сколько строк нужно засчитать?", "expected_answers": ("3",)},
    ),
    10: (
        {"id": "task10_chapters_v1", "operation_index": 0, "prompt": "Искомое слово встретилось 2 раза в главе 1 и 3 раза в главе 2. Поиск ограничен главой 2. Сколько вхождений учитывать?", "expected_answers": ("3",)},
        {"id": "task10_case_v1", "operation_index": 1, "prompt": "При поиске без учёта регистра сколько совпадений дают слова Код, КОД, код?", "expected_answers": ("3",)},
        {"id": "task10_word_substring_v1", "operation_index": 2, "prompt": "При поиске отдельного слова «кот» сколько совпадений в строке «кот и котик»?", "expected_answers": ("1",)},
    ),
    11: (
        {"id": "task11_bits_per_symbol_v1", "operation_index": 0, "prompt": "Какое минимальное число бит нужно на символ алфавита из 17 символов?", "expected_answers": ("5",)},
        {"id": "task11_round_bytes_v1", "operation_index": 1, "prompt": "Запись занимает 13 бит. До скольких полных байт её нужно округлить?", "expected_answers": ("2",)},
        {"id": "task11_total_volume_v1", "operation_index": 2, "prompt": "Один идентификатор занимает 8 байт. Сколько байт занимают 25 идентификаторов?", "expected_answers": ("200",)},
    ),
    12: (
        {"id": "task12_transition_v1", "operation_index": 0, "prompt": "Команда (1, R, q2) означает записать символ 1, сдвинуться вправо и перейти в какое состояние?", "expected_answers": ("q2",)},
        {"id": "task12_head_move_v1", "operation_index": 1, "prompt": "Головка стоит в позиции 5. После команд R, R, L в какой позиции она окажется?", "expected_answers": ("6",)},
        {"id": "task12_state_stop_v1", "operation_index": 2, "prompt": "После переходов q1→q2→q0, где q0 — состояние остановки, в каком состоянии машина завершит работу?", "expected_answers": ("q0",)},
    ),
    13: (
        {"id": "task13_and_v1", "operation_index": 0, "prompt": "Выполните побитовое И: 11010100 AND 11110000. Ответ дайте восьмибитной двоичной строкой.", "expected_answers": ("11010000",)},
        {"id": "task13_network_broadcast_v1", "operation_index": 1, "prompt": "Для сети 192.168.1.0/30 укажите последний октет broadcast-адреса.", "expected_answers": ("3",)},
        {"id": "task13_max_host_v1", "operation_index": 2, "prompt": "Для сети 192.168.1.0/30 укажите последний октет максимального адреса узла.", "expected_answers": ("2",)},
    ),
    14: (
        {
            "id": "task14_remainder_v1",
            "operation_index": 0,
            "prompt": "Какой остаток получится при делении 254 на 36?",
            "expected_answers": ("2",),
        },
        {
            "id": "task14_digit_property_v1",
            "operation_index": 1,
            "prompt": (
                "Сколько цифр с чётным значением среди цифр "
                "A, B, C, D в 36-ричной системе?"
            ),
            "expected_answers": ("2",),
        },
        {
            "id": "task14_count_all_digits_v1",
            "operation_index": 2,
            "prompt": (
                "При разборе числа получены цифры 2, 0, 4, 0, 6. "
                "Сколько среди них цифр с чётным значением?"
            ),
            "expected_answers": ("5",),
        },
    ),
    15: (
        {"id": "task15_implication_v1", "operation_index": 0, "prompt": "Чему равна импликация 1→0?", "expected_answers": ("0",)},
        {"id": "task15_false_set_v1", "operation_index": 1, "prompt": "На каких целых x из 1, 2, 3 ложно условие x>1? Перечислите числа.", "expected_answers": ("1",)},
        {"id": "task15_min_cover_v1", "operation_index": 2, "prompt": "Какова минимальная длина целочисленного отрезка, покрывающего точки 3 и 8?", "expected_answers": ("5",)},
    ),
    16: (
        {"id": "task16_expand_v1", "operation_index": 0, "prompt": "Дано F(n)=F(n-1)+2 и F(1)=3. Чему равно F(3)?", "expected_answers": ("7",)},
        {"id": "task16_reduce_v1", "operation_index": 1, "prompt": "Если F(n)=F(n-1)+n, чему равно F(5)-F(4)?", "expected_answers": ("5",)},
        {"id": "task16_avoid_huge_v1", "operation_index": 2, "prompt": "Если F(n)=2F(n-1), чему равно отношение F(100)/F(99)?", "expected_answers": ("2",)},
    ),
    17: (
        {"id": "task17_reference_min_v1", "operation_index": 0, "prompt": "Среди положительных чисел последовательности -2, 7, 3, 9 найдите минимум.", "expected_answers": ("3",)},
        {"id": "task17_adjacent_pairs_v1", "operation_index": 1, "prompt": "Сколько соседних пар в последовательности из 6 элементов?", "expected_answers": ("5",)},
        {"id": "task17_count_max_v1", "operation_index": 2, "prompt": "Суммы подходящих пар равны 11, 8 и 15. Укажите количество пар и максимальную сумму через пробел.", "expected_answers": ("3 15",)},
    ),
    18: (
        {"id": "task18_reachability_v1", "operation_index": 0, "prompt": "Робот идёт только вправо и вниз. Достижима ли клетка (3,2) из (1,1) без препятствий? Ответьте да или нет.", "expected_answers": ("да", "yes")},
        {"id": "task18_minmax_v1", "operation_index": 1, "prompt": "В клетку можно прийти с накопленными суммами 12 и 17, стоимость клетки 5. Какова новая минимальная сумма?", "expected_answers": ("17",)},
        {"id": "task18_walls_finish_v1", "operation_index": 2, "prompt": "Единственный вход в конечную клетку перекрыт стеной. Достижима ли клетка? Ответьте да или нет.", "expected_answers": ("нет", "no")},
    ),
    19: (
        {"id": "task19_terminal_v1", "operation_index": 0, "prompt": "Игра заканчивается при сумме ≥77. Является ли позиция с суммой 77 терминальной? Ответьте да или нет.", "expected_answers": ("да", "yes")},
        {"id": "task19_quantifiers_v1", "operation_index": 1, "prompt": "Чтобы игрок имел выигрышный ход, достаточно существования одного хода в терминал или нужны все такие ходы? Ответьте: один или все.", "expected_answers": ("один",)},
        {"id": "task19_min_s_v1", "operation_index": 2, "prompt": "Подходящие значения S: 14, 9, 12. Найдите минимальное.", "expected_answers": ("9",)},
    ),
    20: (
        {"id": "task20_levels_v1", "operation_index": 0, "prompt": "Терминальные позиции имеют уровень 0. Какой уровень у позиции, из которой есть ход прямо в терминал?", "expected_answers": ("1",)},
        {"id": "task20_exclude_first_v1", "operation_index": 1, "prompt": "Позиция позволяет Пете выиграть первым ходом. Подходит ли она условию «выиграть вторым ходом, но не первым»? Ответьте да или нет.", "expected_answers": ("нет", "no")},
        {"id": "task20_two_s_v1", "operation_index": 2, "prompt": "Подходящие S равны 18 и 21. Запишите оба по возрастанию.", "expected_answers": ("18 21",)},
    ),
    21: (
        {"id": "task21_two_conditions_v1", "operation_index": 0, "prompt": "Условие стратегии требует A и B. A истинно, B ложно. Выполнено ли всё условие? Ответьте да или нет.", "expected_answers": ("нет", "no")},
        {"id": "task21_negate_v1", "operation_index": 1, "prompt": "Отрицание утверждения «для всех ходов есть победа» начинается словами «существует ход» или «для всех ходов»?", "expected_answers": ("существует ход",)},
        {"id": "task21_minimize_v1", "operation_index": 2, "prompt": "Стратегическому условию удовлетворяют S=11, 16, 20. Найдите минимальное S.", "expected_answers": ("11",)},
    ),
    22: (
        {"id": "task22_dag_v1", "operation_index": 0, "prompt": "Процесс C зависит от A и B. Какие две дуги входят в C? Запишите предшественников через пробел.", "expected_answers": ("A B", "А Б")},
        {"id": "task22_early_start_v1", "operation_index": 1, "prompt": "Предшественники заканчиваются в моменты 7 и 12. В какой момент процесс может стартовать раньше всего?", "expected_answers": ("12",)},
        {"id": "task22_critical_path_v1", "operation_index": 2, "prompt": "Длины двух путей в DAG равны 18 и 23. Какова длина критического пути?", "expected_answers": ("23",)},
    ),
    23: (
        {"id": "task23_count_paths_v1", "operation_index": 0, "prompt": "Из A в D идут два независимых пути: A-B-D и A-C-D. Сколько программ ведёт из A в D?", "expected_answers": ("2",)},
        {"id": "task23_forbidden_v1", "operation_index": 1, "prompt": "Из трёх путей два проходят через запрещённую вершину X. Сколько допустимых путей останется?", "expected_answers": ("1",)},
        {"id": "task23_duplicates_v1", "operation_index": 2, "prompt": "Один и тот же путь был посчитан дважды, получено 9 вместо истинного количества. Каково истинное количество?", "expected_answers": ("8",)},
    ),
    24: (
        {"id": "task24_occurrences_v1", "operation_index": 0, "prompt": "На каких позициях начинается BC в строке ABCCBC? Нумерация с 1, ответы через пробел.", "expected_answers": ("2 5",)},
        {"id": "task24_window_v1", "operation_index": 1, "prompt": "Окно от позиции 3 до позиции 9 включительно. Какова его длина?", "expected_answers": ("7",)},
        {"id": "task24_max_length_v1", "operation_index": 2, "prompt": "Длины допустимых фрагментов: 12, 19, 17. Найдите максимальную.", "expected_answers": ("19",)},
    ),
    25: (
        {"id": "task25_mask_v1", "operation_index": 0, "prompt": "Подходит ли число 12345 маске 12?4*? Ответьте да или нет.", "expected_answers": ("да", "yes")},
        {"id": "task25_multiples_v1", "operation_index": 1, "prompt": "Какое наименьшее положительное число, кратное 17?", "expected_answers": ("17",)},
        {"id": "task25_sort_v1", "operation_index": 2, "prompt": "Отсортируйте числа 340, 102, 215 по возрастанию.", "expected_answers": ("102 215 340",)},
    ),
    26: (
        {"id": "task26_group_v1", "operation_index": 0, "prompt": "Артикулы A, B, A, C, B образуют сколько групп?", "expected_answers": ("3",)},
        {"id": "task26_weighted_price_v1", "operation_index": 1, "prompt": "Купили 2 товара по 100 и 3 товара по 200. Какова средневзвешенная цена?", "expected_answers": ("160",)},
        {"id": "task26_tie_break_v1", "operation_index": 2, "prompt": "У товаров A и B одинаковый основной показатель. При равенстве выбирают меньший артикул. Что выбрать?", "expected_answers": ("A", "А")},
        {"id": "task26_revenue_v1", "operation_index": 3, "prompt": "Продано 7 единиц по цене 150. Найдите выручку.", "expected_answers": ("1050",)},
    ),
    27: (
        {"id": "task27_clusters_v1", "operation_index": 0, "prompt": "Точки образуют две явно раздельные группы по 4 точки. Сколько кластеров?", "expected_answers": ("2",)},
        {"id": "task27_medoid_v1", "operation_index": 1, "prompt": "Суммы расстояний от точек A, B, C до остальных равны 10, 6, 9. Какая точка является медоидом?", "expected_answers": ("B", "Б")},
        {"id": "task27_labels_v1", "operation_index": 2, "prompt": "После фильтра меток 1, 2, 1, 3 по метке 1 сколько точек останется?", "expected_answers": ("2",)},
        {"id": "task27_distance_v1", "operation_index": 3, "prompt": "Найдите евклидово расстояние между точками (0,0) и (3,4).", "expected_answers": ("5",)},
    ),
}


def _normalize_probe_answer(value: str) -> str:
    return " ".join(re.findall(r"[a-zа-яё]+|[-+]?\d+", value.lower()))


def validate_control_probes(skill_map: dict) -> None:
    """Reject probes that do not point to a real operation in the skill map."""
    for task_number, probes in CONTROL_PROBES.items():
        task = _task_definition(task_number, skill_map)
        operations = task.get("operations", [])
        seen_ids: set[str] = set()
        for probe in probes:
            probe_id = str(probe.get("id", "")).strip()
            operation_index = probe.get("operation_index")
            expected = probe.get("expected_answers", ())
            if not probe_id or probe_id in seen_ids:
                raise ValueError(f"Некорректный ID пробы задания {task_number}.")
            if not isinstance(operation_index, int) or not 0 <= operation_index < len(operations):
                raise ValueError(f"Проба {probe_id} ссылается на неизвестный шаг.")
            if not probe.get("prompt") or not expected:
                raise ValueError(f"Проба {probe_id} не имеет вопроса или ответа.")
            seen_ids.add(probe_id)


def next_control_probe(case: dict) -> dict | None:
    """Return the next unchecked local probe for a diagnostic case."""
    probes = CONTROL_PROBES.get(int(case.get("task_number", 0)), ())
    completed = {
        item.get("probe_id")
        for item in case.get("evidence", [])
        if item.get("kind") == "control_probe"
    }
    operations = case.get("operations", [])
    for probe in probes:
        if probe["id"] not in completed:
            operation_index = probe["operation_index"]
            return {
                "probe_id": probe["id"],
                "prompt": probe["prompt"],
                "tested_step": operations[operation_index],
            }
    return None


def answer_control_probe(case: dict, probe_id: str, answer: str) -> dict:
    """Verify a mini-probe locally and apply its evidence to the case."""
    probes = CONTROL_PROBES.get(int(case.get("task_number", 0)), ())
    probe = next((item for item in probes if item["id"] == probe_id), None)
    if probe is None:
        raise ValueError("Контрольная проба не найдена для этого задания.")
    if any(
        item.get("kind") == "control_probe" and item.get("probe_id") == probe_id
        for item in case.get("evidence", [])
    ):
        raise ValueError("Эта контрольная проба уже пройдена.")
    operations = case.get("operations", [])
    tested_step = operations[probe["operation_index"]]
    normalized = _normalize_probe_answer(answer)
    is_correct = normalized in {
        _normalize_probe_answer(value) for value in probe["expected_answers"]
    }
    return record_control_probe(
        case,
        probe_id=probe_id,
        tested_step=tested_step,
        is_correct=is_correct,
        observed_answer=answer,
    )


def confirmed_case_to_check_result(case: dict) -> dict:
    """Convert evidence-backed diagnosis to the existing Learning DNA contract."""
    if case not in confirmed_cases([case]):
        raise ValueError("В Learning DNA можно передать только подтверждённую ошибку.")
    skill_ids = case.get("skill_ids", [])
    return {
        "status": "has_error",
        "topic": case.get("task_title", f"Задание {case.get('task_number')}"),
        "skill_id": skill_ids[0] if skill_ids else None,
        "error_type": case.get("error_type"),
        "confidence": case.get("confidence"),
        "feedback": f"Подтверждена ошибка на шаге: {case.get('failed_step')}.",
        "recommendation": case.get("learning_action"),
        "diagnostic_evidence": deepcopy(case.get("evidence", [])),
        "source": "local_control_probe",
    }


def _task_definition(task_number: int, skill_map: dict) -> dict:
    task = next(
        (item for item in skill_map.get("tasks", []) if item.get("number") == task_number),
        None,
    )
    if task is None:
        raise ValueError(f"В карте навыков отсутствует задание {task_number}.")
    return task


def open_diagnostic_case(
    task_number: int,
    student_answer: str,
    expected_answer: str,
    skill_map: dict,
) -> dict:
    """Create an unresolved case without inventing a failed step."""
    task = _task_definition(task_number, skill_map)
    return {
        "task_number": task_number,
        "task_title": task.get("title", f"Задание {task_number}"),
        "student_answer": student_answer,
        "expected_answer": expected_answer,
        "skill_ids": list(task.get("skills", [])),
        "operations": list(task.get("operations", [])),
        "candidate_errors": list(task.get("typical_errors", [])),
        "failed_step": None,
        "error_type": None,
        "status": DIAGNOSIS_NEEDS_EVIDENCE,
        "confidence": 0.0,
        "evidence": [
            {
                "kind": "incorrect_final_answer",
                "value": student_answer,
                "proves_failed_step": False,
            }
        ],
        "learning_action": None,
    }


def record_student_step(case: dict, operation_index: int) -> dict:
    """Record self-report as a hypothesis, never as confirmation."""
    updated = deepcopy(case)
    operations = updated.get("operations", [])
    if operation_index < 0 or operation_index >= len(operations):
        raise ValueError("Некорректный номер шага решения.")
    failed_step = operations[operation_index]
    updated["failed_step"] = failed_step
    updated["status"] = DIAGNOSIS_PROBABLE
    updated["confidence"] = 0.45
    updated["evidence"].append(
        {
            "kind": "student_self_report",
            "value": failed_step,
            "proves_failed_step": False,
        }
    )
    return updated


def record_control_probe(
    case: dict,
    *,
    probe_id: str,
    tested_step: str,
    is_correct: bool,
    observed_answer: str,
) -> dict:
    """Apply an independently checked mini-probe to a diagnostic case."""
    if not probe_id.strip() or not tested_step.strip():
        raise ValueError("Контрольная проба должна иметь ID и проверяемый шаг.")
    updated = deepcopy(case)
    updated["evidence"].append(
        {
            "kind": "control_probe",
            "probe_id": probe_id,
            "tested_step": tested_step,
            "is_correct": bool(is_correct),
            "value": observed_answer,
            "proves_failed_step": not is_correct,
        }
    )
    if is_correct:
        updated["status"] = DIAGNOSIS_NEEDS_EVIDENCE
        updated["confidence"] = 0.0
        updated["failed_step"] = None
        updated["error_type"] = None
        updated["learning_action"] = None
    else:
        updated["status"] = DIAGNOSIS_CONFIRMED
        updated["confidence"] = 0.95
        updated["failed_step"] = tested_step
        updated["error_type"] = f"failed_step:{probe_id}"
        updated["learning_action"] = f"Отработать шаг: {tested_step}."
    return updated


def confirmed_cases(cases: list[dict]) -> list[dict]:
    """Return only evidence-backed cases allowed to affect Learning DNA."""
    return [
        deepcopy(case)
        for case in cases
        if case.get("status") == DIAGNOSIS_CONFIRMED
        and any(
            item.get("kind") == "control_probe" and item.get("proves_failed_step")
            for item in case.get("evidence", [])
        )
    ]
