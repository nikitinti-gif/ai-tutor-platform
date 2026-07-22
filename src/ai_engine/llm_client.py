import os
from urllib.parse import urlsplit

from google import genai
from google.genai import types
from dotenv import load_dotenv

from src.ai_engine.prompts import (
    HOMEWORK_CHECK_SYSTEM_PROMPT,
    build_homework_check_prompt,
    build_homework_image_transcription_prompt,
    build_diagnostic_level_prompt,
)
from src.ai_engine.schemas import (
    HOMEWORK_CHECK_RESPONSE_SCHEMA,
    IMAGE_TRANSCRIPTION_RESPONSE_SCHEMA,
    DIAGNOSTIC_LEVEL_RESPONSE_SCHEMA,
)


DEFAULT_GEMINI_MODEL = "gemini-3.1-flash-lite"
SUPPORTED_PROXY_SCHEMES = {"http", "https", "socks5"}
SUPPORTED_IMAGE_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/heic",
    "image/heif",
}


load_dotenv()


class LLMConfigurationError(RuntimeError):
    """Raised when the real LLM provider is not configured."""


class LLMResponseError(RuntimeError):
    """Raised when the provider returns no usable text."""


class LLMDataPolicyError(RuntimeError):
    """Raised when external processing is not explicitly synthetic."""


def build_gemini_http_options(proxy_url: str | None) -> types.HttpOptions:
    """Build isolated transport settings for Gemini requests only."""
    client_args: dict[str, object] = {
        "trust_env": False,
        "timeout": 30.0,
    }

    if proxy_url:
        proxy_url = proxy_url.strip()
        parsed = urlsplit(proxy_url)

        if parsed.scheme.lower() not in SUPPORTED_PROXY_SCHEMES:
            raise LLMConfigurationError(
                "GEMINI_PROXY_URL использует неподдерживаемую схему. "
                "Укажи http://, https:// или socks5://. "
                "socks4:// библиотекой httpx не поддерживается."
            )

        try:
            port = parsed.port
        except ValueError as error:
            raise LLMConfigurationError(
                "В GEMINI_PROXY_URL указан некорректный порт."
            ) from error

        if not parsed.hostname or port is None:
            raise LLMConfigurationError(
                "GEMINI_PROXY_URL должен содержать адрес и порт прокси."
            )

        client_args["proxy"] = proxy_url

    return types.HttpOptions(
        client_args=client_args,
        async_client_args=client_args.copy(),
    )


class LLMClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        proxy_url: str | None = None,
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model or os.getenv(
            "GEMINI_MODEL",
            DEFAULT_GEMINI_MODEL,
        )
        self.proxy_url = proxy_url or os.getenv("GEMINI_PROXY_URL")

        if not self.api_key:
            raise LLMConfigurationError(
                "GEMINI_API_KEY не найден. Добавь ключ в .env и "
                "перезапусти бота."
            )

        self.client = genai.Client(
            api_key=self.api_key,
            http_options=build_gemini_http_options(self.proxy_url),
        )

    def _generate(self, prompt: str) -> str:
        interaction = self.client.interactions.create(
            model=self.model,
            input=prompt,
        )

        if not interaction.output_text:
            raise LLMResponseError("Gemini вернул пустой ответ.")

        return interaction.output_text

    def ask(self, prompt: str) -> str:
        return self._generate(prompt)

    def complete(self, prompt: str) -> str:
        return self._generate(prompt)

    def generate(self, prompt: str) -> str:
        return self._generate(prompt)

    def check_homework_text(
        self,
        text: str,
        task_text: str | None = None,
        topic: str | None = None,
        synthetic_test: bool = False,
    ) -> str:
        if not synthetic_test:
            raise LLMDataPolicyError(
                "Gemini разрешён только для синтетических тестовых "
                "примеров."
            )

        user_prompt = build_homework_check_prompt(
            task_text=task_text or "",
            student_solution=text,
            topic=topic,
        )
        full_prompt = (
            f"{HOMEWORK_CHECK_SYSTEM_PROMPT}\n\n"
            f"{user_prompt}"
        )

        interaction = self.client.interactions.create(
            model=self.model,
            input=full_prompt,
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": HOMEWORK_CHECK_RESPONSE_SCHEMA,
            },
        )

        if not interaction.output_text:
            raise LLMResponseError(
                "Gemini не вернул результат проверки."
            )

        return interaction.output_text

    def transcribe_homework_image(
        self,
        image_bytes: bytes,
        mime_type: str,
        synthetic_test: bool = False,
    ) -> str:
        if not synthetic_test:
            raise LLMDataPolicyError(
                "Gemini разрешён только для синтетических тестовых "
                "изображений."
            )

        if not image_bytes:
            raise ValueError("Синтетическое изображение пустое.")

        normalized_mime_type = mime_type.strip().lower()
        if normalized_mime_type not in SUPPORTED_IMAGE_MIME_TYPES:
            raise ValueError(
                "Неподдерживаемый формат изображения. Используй PNG, "
                "JPEG, WEBP, HEIC или HEIF."
            )

        transcription_prompt = build_homework_image_transcription_prompt()
        image_part = types.Part.from_bytes(
            data=image_bytes,
            mime_type=normalized_mime_type,
        )

        response = self.client.models.generate_content(
            model=self.model,
            contents=[transcription_prompt, image_part],
            config={
                "response_mime_type": "application/json",
                "response_json_schema": (
                    IMAGE_TRANSCRIPTION_RESPONSE_SCHEMA
                ),
            },
        )

        if not response.text:
            raise LLMResponseError(
                "Gemini не вернул транскрипцию изображения."
            )

        return response.text

    def check_diagnostic_levels(self, *, topic: str, tasks: list[dict], student_solution: str, synthetic_test: bool = False) -> str:
        if not synthetic_test:
            raise LLMDataPolicyError("Gemini разрешён только для синтетических диагностических работ.")
        interaction = self.client.interactions.create(
            model=self.model,
            input=build_diagnostic_level_prompt(topic, tasks, student_solution),
            response_format={"type": "text", "mime_type": "application/json", "schema": DIAGNOSTIC_LEVEL_RESPONSE_SCHEMA},
        )
        if not interaction.output_text:
            raise LLMResponseError("Gemini не вернул раздельную диагностику.")
        return interaction.output_text


def ask_llm(prompt: str) -> str:
    """Temporary compatibility wrapper for older imports."""
    return LLMClient().generate(prompt)
