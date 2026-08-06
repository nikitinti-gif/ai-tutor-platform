"""Verification matrix for the 27 KЕГЭ tasks in informatics.

The exam layer always checks the final answer locally against an answer key.
AI is optional and belongs to the learning layer: hints and analysis of a wrong
solution.  This keeps the normal exam workflow fast and inexpensive.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ExamAnswerFormat(StrEnum):
    NUMBER = "number"
    TEXT = "text"
    SEQUENCE = "sequence"
    MULTI_VALUE = "multi_value"


class LearningEvidenceFormat(StrEnum):
    NONE = "none"
    TEXT = "text"
    CODE = "code"
    FILE = "file"
    IMAGE = "image"
    MIXED = "mixed"


class VerificationMethod(StrEnum):
    AUTO = "auto"
    PYTHON = "python"
    LLM = "llm"
    VISION = "vision"
    TEACHER = "teacher"


@dataclass(frozen=True, slots=True)
class TaskVerificationRule:
    task_number: int
    topic: str
    exam_answer_format: ExamAnswerFormat
    exam_method: VerificationMethod = VerificationMethod.AUTO
    learning_evidence_format: LearningEvidenceFormat = LearningEvidenceFormat.TEXT
    learning_methods: tuple[VerificationMethod, ...] = (VerificationMethod.LLM,)
    learning_check_units: int = 1
    accepted_extensions: tuple[str, ...] = ()
    max_files: int = 0
    notes: str = ""


# learning_check_units are internal product units, not API tokens or money:
# 0 = local logic only, 1 = text/code LLM help, 3 = image/Vision analysis.
EGE_VERIFICATION_MATRIX: dict[int, TaskVerificationRule] = {
    1: TaskVerificationRule(1, "Графы и таблицы", ExamAnswerFormat.NUMBER, learning_evidence_format=LearningEvidenceFormat.IMAGE, learning_methods=(VerificationMethod.VISION, VerificationMethod.TEACHER), learning_check_units=3, accepted_extensions=(".jpg", ".jpeg", ".png", ".webp"), max_files=1),
    2: TaskVerificationRule(2, "Таблицы истинности", ExamAnswerFormat.SEQUENCE),
    3: TaskVerificationRule(3, "Базы данных", ExamAnswerFormat.NUMBER, learning_evidence_format=LearningEvidenceFormat.FILE, learning_methods=(VerificationMethod.PYTHON, VerificationMethod.LLM), accepted_extensions=(".ods", ".xlsx", ".xls"), max_files=1),
    4: TaskVerificationRule(4, "Кодирование и условие Фано", ExamAnswerFormat.TEXT),
    5: TaskVerificationRule(5, "Анализ алгоритма", ExamAnswerFormat.NUMBER),
    6: TaskVerificationRule(6, "Исполнитель Черепаха", ExamAnswerFormat.NUMBER, learning_evidence_format=LearningEvidenceFormat.IMAGE, learning_methods=(VerificationMethod.VISION, VerificationMethod.TEACHER), learning_check_units=3, accepted_extensions=(".jpg", ".jpeg", ".png", ".webp"), max_files=1),
    7: TaskVerificationRule(7, "Кодирование изображений и звука", ExamAnswerFormat.NUMBER),
    8: TaskVerificationRule(8, "Комбинаторика слов", ExamAnswerFormat.NUMBER, learning_methods=(VerificationMethod.PYTHON, VerificationMethod.LLM)),
    9: TaskVerificationRule(9, "Электронные таблицы", ExamAnswerFormat.NUMBER, learning_evidence_format=LearningEvidenceFormat.FILE, learning_methods=(VerificationMethod.PYTHON, VerificationMethod.LLM), accepted_extensions=(".ods", ".xlsx", ".xls"), max_files=1),
    10: TaskVerificationRule(10, "Поиск в текстовом документе", ExamAnswerFormat.NUMBER, learning_evidence_format=LearningEvidenceFormat.TEXT),
    11: TaskVerificationRule(11, "Количество информации", ExamAnswerFormat.NUMBER),
    12: TaskVerificationRule(12, "Редактор и исполнитель", ExamAnswerFormat.TEXT, learning_methods=(VerificationMethod.PYTHON, VerificationMethod.LLM)),
    13: TaskVerificationRule(13, "IP-адреса и маски", ExamAnswerFormat.NUMBER, learning_methods=(VerificationMethod.PYTHON, VerificationMethod.LLM)),
    14: TaskVerificationRule(14, "Системы счисления", ExamAnswerFormat.NUMBER, learning_methods=(VerificationMethod.PYTHON, VerificationMethod.LLM)),
    15: TaskVerificationRule(15, "Логические выражения", ExamAnswerFormat.NUMBER),
    16: TaskVerificationRule(16, "Рекурсивные алгоритмы", ExamAnswerFormat.NUMBER, learning_methods=(VerificationMethod.PYTHON, VerificationMethod.LLM)),
    17: TaskVerificationRule(17, "Обработка последовательностей", ExamAnswerFormat.NUMBER, learning_evidence_format=LearningEvidenceFormat.CODE, learning_methods=(VerificationMethod.PYTHON, VerificationMethod.LLM), accepted_extensions=(".py", ".txt"), max_files=1, notes="Код запускать только в изолированной среде с лимитами."),
    18: TaskVerificationRule(18, "Робот и электронная таблица", ExamAnswerFormat.NUMBER, learning_evidence_format=LearningEvidenceFormat.FILE, learning_methods=(VerificationMethod.PYTHON, VerificationMethod.LLM), accepted_extensions=(".ods", ".xlsx", ".xls"), max_files=1),
    19: TaskVerificationRule(19, "Теория игр: один ход", ExamAnswerFormat.NUMBER),
    20: TaskVerificationRule(20, "Теория игр: два хода", ExamAnswerFormat.MULTI_VALUE),
    21: TaskVerificationRule(21, "Теория игр: стратегия", ExamAnswerFormat.NUMBER),
    22: TaskVerificationRule(22, "Параллельные процессы", ExamAnswerFormat.NUMBER, learning_evidence_format=LearningEvidenceFormat.FILE, learning_methods=(VerificationMethod.PYTHON, VerificationMethod.LLM), accepted_extensions=(".ods", ".xlsx", ".xls", ".csv"), max_files=1),
    23: TaskVerificationRule(23, "Динамическое программирование исполнителя", ExamAnswerFormat.NUMBER, learning_methods=(VerificationMethod.PYTHON, VerificationMethod.LLM)),
    24: TaskVerificationRule(24, "Обработка символьных строк", ExamAnswerFormat.NUMBER, learning_evidence_format=LearningEvidenceFormat.CODE, learning_methods=(VerificationMethod.PYTHON, VerificationMethod.LLM), accepted_extensions=(".py", ".txt"), max_files=2),
    25: TaskVerificationRule(25, "Делители и маски чисел", ExamAnswerFormat.MULTI_VALUE, learning_evidence_format=LearningEvidenceFormat.CODE, learning_methods=(VerificationMethod.PYTHON, VerificationMethod.LLM), accepted_extensions=(".py", ".txt"), max_files=1),
    26: TaskVerificationRule(26, "Сортировка и обработка данных", ExamAnswerFormat.MULTI_VALUE, learning_evidence_format=LearningEvidenceFormat.CODE, learning_methods=(VerificationMethod.PYTHON, VerificationMethod.LLM), accepted_extensions=(".py", ".txt", ".csv"), max_files=2),
    27: TaskVerificationRule(27, "Программирование повышенной сложности", ExamAnswerFormat.MULTI_VALUE, learning_evidence_format=LearningEvidenceFormat.CODE, learning_methods=(VerificationMethod.PYTHON, VerificationMethod.LLM, VerificationMethod.TEACHER), accepted_extensions=(".py", ".txt"), max_files=2),
}


def get_task_verification_rule(task_number: int) -> TaskVerificationRule:
    try:
        return EGE_VERIFICATION_MATRIX[task_number]
    except KeyError as error:
        raise ValueError("Номер задания КЕГЭ должен быть от 1 до 27.") from error


def validate_verification_matrix() -> None:
    expected = set(range(1, 28))
    actual = set(EGE_VERIFICATION_MATRIX)
    if actual != expected:
        raise RuntimeError(
            f"Некорректная матрица: missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )

    for number, rule in EGE_VERIFICATION_MATRIX.items():
        if rule.task_number != number:
            raise RuntimeError(
                f"Ключ {number} не совпадает с task_number={rule.task_number}"
            )
        if rule.exam_method is not VerificationMethod.AUTO:
            raise RuntimeError(
                f"Базовая проверка задания {number} должна быть AUTO"
            )
        needs_file_limits = rule.learning_evidence_format in {
            LearningEvidenceFormat.CODE,
            LearningEvidenceFormat.FILE,
            LearningEvidenceFormat.IMAGE,
            LearningEvidenceFormat.MIXED,
        }
        if needs_file_limits and (not rule.accepted_extensions or rule.max_files < 1):
            raise RuntimeError(
                f"Для учебного разбора задания {number} не заданы ограничения файлов"
            )
        if not needs_file_limits and (rule.accepted_extensions or rule.max_files):
            raise RuntimeError(
                f"Для задания {number} файловые ограничения лишние"
            )


validate_verification_matrix()
