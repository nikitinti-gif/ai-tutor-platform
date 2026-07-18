import hashlib
import secrets


LINK_CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
LINK_CODE_LENGTH = 8


def normalize_link_code(code: str) -> str:
    return "".join(code.upper().split())


def generate_link_code() -> str:
    return "".join(
        secrets.choice(LINK_CODE_ALPHABET)
        for _ in range(LINK_CODE_LENGTH)
    )


def hash_link_code(code: str) -> str:
    normalized = normalize_link_code(code)
    if len(normalized) != LINK_CODE_LENGTH:
        raise ValueError("Код привязки должен содержать 8 символов.")
    if any(character not in LINK_CODE_ALPHABET for character in normalized):
        raise ValueError("Код привязки содержит недопустимые символы.")
    return hashlib.sha256(normalized.encode("ascii")).hexdigest()


def make_synthetic_student_id(admin_telegram_id: int) -> int:
    if not isinstance(admin_telegram_id, int) or admin_telegram_id == 0:
        raise ValueError("Некорректный Telegram ID администратора.")
    return -abs(admin_telegram_id)


def is_synthetic_student_id(student_telegram_id: int) -> bool:
    return isinstance(student_telegram_id, int) and student_telegram_id < 0
