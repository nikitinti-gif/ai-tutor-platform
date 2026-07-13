import json

from src.ai_engine.schemas import (
    validate_homework_check_result,
    validate_image_transcription_result,
)


def parse_json_safely(raw_text: str) -> dict:
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass

    start = raw_text.find("{")
    end = raw_text.rfind("}")

    if start == -1 or end == -1 or end <= start:
        return {}

    try:
        return json.loads(raw_text[start:end + 1])
    except json.JSONDecodeError:
        return {}


def parse_homework_check_response(raw_text: str) -> dict:
    data = parse_json_safely(raw_text)
    return validate_homework_check_result(data)


def parse_image_transcription_response(raw_text: str) -> dict:
    data = parse_json_safely(raw_text)
    return validate_image_transcription_result(data)
