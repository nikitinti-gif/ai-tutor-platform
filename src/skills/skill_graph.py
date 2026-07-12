MATH_SKILL_GRAPH = {
    "algebra": {
        "name": "Алгебра",
        "skills": {
            "linear_equations": {
                "name": "Линейные уравнения",
                "subskills": {
                    "move_terms": "Перенос слагаемых",
                    "open_brackets": "Раскрытие скобок",
                    "check_answer": "Проверка ответа",
                },
            },
            "quadratic_equations": {
                "name": "Квадратные уравнения",
                "subskills": {
                    "recognize_quadratic": "Распознавание квадратного уравнения",
                    "discriminant": "Вычисление дискриминанта",
                    "interpret_discriminant": "Интерпретация дискриминанта",
                    "find_roots": "Нахождение корней",
                    "check_roots": "Проверка корней",
                    "solution_format": "Оформление решения",
                },
            },
        },
    }
}


def get_skill_name(skill_id: str) -> str:
    for block in MATH_SKILL_GRAPH.values():
        for topic in block["skills"].values():
            if skill_id in topic["subskills"]:
                return topic["subskills"][skill_id]

    return skill_id