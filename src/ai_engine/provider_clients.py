import os
from typing import Protocol

import httpx

from src.ai_engine.llm_client import (
    LLMClient,
    LLMConfigurationError,
    LLMDataPolicyError,
    LLMResponseError,
)
from src.ai_engine.prompts import (
    HOMEWORK_CHECK_SYSTEM_PROMPT,
    build_homework_check_prompt,
)


SUPPORTED_TEXT_PROVIDERS = ("gemini", "mistral", "yandex")
DEFAULT_MISTRAL_MODEL = "mistral-small-latest"
DEFAULT_YANDEX_MODEL = "yandexgpt/latest"
DEFAULT_YANDEX_BASE_URL = "https://ai.api.cloud.yandex.net/v1"


class HomeworkTextProvider(Protocol):
    def check_homework_text(
        self,
        text: str,
        task_text: str | None = None,
        topic: str | None = None,
        synthetic_test: bool = False,
    ) -> str: ...


class OpenAICompatibleHomeworkClient:
    def __init__(
        self,
        *,
        provider_name: str,
        api_key: str,
        model: str,
        base_url: str,
        extra_headers: dict[str, str] | None = None,
        timeout: float = 45.0,
    ):
        if not api_key:
            raise LLMConfigurationError(
                f"API-ключ провайдера {provider_name} не найден."
            )
        if not model:
            raise LLMConfigurationError(
                f"Модель провайдера {provider_name} не указана."
            )

        self.provider_name = provider_name
        self.model = model
        self.url = f"{base_url.rstrip('/')}/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            **(extra_headers or {}),
        }
        self.timeout = timeout

    def check_homework_text(
        self,
        text: str,
        task_text: str | None = None,
        topic: str | None = None,
        synthetic_test: bool = False,
    ) -> str:
        if not synthetic_test:
            raise LLMDataPolicyError(
                f"{self.provider_name} разрешён только для "
                "синтетических тестовых примеров."
            )

        user_prompt = build_homework_check_prompt(
            task_text=task_text or "",
            student_solution=text,
            topic=topic,
        )
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": HOMEWORK_CHECK_SYSTEM_PROMPT,
                },
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 1200,
            "response_format": {"type": "json_object"},
        }

        try:
            with httpx.Client(
                timeout=self.timeout,
                trust_env=False,
            ) as client:
                response = client.post(
                    self.url,
                    headers=self.headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as error:
            status = error.response.status_code
            detail = error.response.text[:300]
            raise LLMResponseError(
                f"{self.provider_name} вернул HTTP {status}: {detail}"
            ) from error
        except (httpx.HTTPError, ValueError) as error:
            raise LLMResponseError(
                f"Ошибка запроса к {self.provider_name}: {error}"
            ) from error

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise LLMResponseError(
                f"{self.provider_name} вернул неожиданный ответ."
            ) from error

        if not isinstance(content, str) or not content.strip():
            raise LLMResponseError(
                f"{self.provider_name} вернул пустой результат проверки."
            )
        return content


def create_text_provider(provider_name: str) -> HomeworkTextProvider:
    normalized = provider_name.strip().lower()

    if normalized == "gemini":
        return LLMClient()

    if normalized == "mistral":
        return OpenAICompatibleHomeworkClient(
            provider_name="mistral",
            api_key=os.getenv("MISTRAL_API_KEY", ""),
            model=os.getenv("MISTRAL_MODEL", DEFAULT_MISTRAL_MODEL),
            base_url="https://api.mistral.ai/v1",
        )

    if normalized == "yandex":
        api_key = os.getenv("YANDEX_API_KEY", "")
        folder_id = os.getenv("YANDEX_FOLDER_ID", "")
        if not folder_id:
            raise LLMConfigurationError(
                "YANDEX_FOLDER_ID не найден."
            )
        model = os.getenv("YANDEX_MODEL", DEFAULT_YANDEX_MODEL)
        if not model.startswith("gpt://"):
            model = f"gpt://{folder_id}/{model.lstrip('/')}"

        return OpenAICompatibleHomeworkClient(
            provider_name="yandex",
            api_key=api_key,
            model=model,
            base_url=os.getenv(
                "YANDEX_BASE_URL",
                DEFAULT_YANDEX_BASE_URL,
            ),
            extra_headers={
                "Authorization": f"Api-Key {api_key}",
                "OpenAI-Project": folder_id,
            },
        )

    supported = ", ".join(SUPPORTED_TEXT_PROVIDERS)
    raise LLMConfigurationError(
        f"Неизвестный AI-провайдер: {provider_name}. "
        f"Допустимые значения: {supported}."
    )
