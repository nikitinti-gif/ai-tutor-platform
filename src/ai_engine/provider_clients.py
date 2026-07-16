import base64
import os
import threading
import time
import uuid
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
    build_homework_image_transcription_prompt,
)
from src.ai_engine.schemas import (
    HOMEWORK_CHECK_RESPONSE_SCHEMA,
    IMAGE_TRANSCRIPTION_RESPONSE_SCHEMA,
)


SUPPORTED_TEXT_PROVIDERS = ("gemini", "mistral", "yandex")
GIGACHAT_PROVIDER = "gigachat"
QWEN_PROVIDER = "qwen"
DEFAULT_MISTRAL_MODEL = "mistral-small-latest"
DEFAULT_YANDEX_MODEL = "yandexgpt/latest"
DEFAULT_YANDEX_BASE_URL = "https://ai.api.cloud.yandex.net/v1"
DEFAULT_GIGACHAT_MODEL = "GigaChat-2-Pro"
DEFAULT_GIGACHAT_SCOPE = "GIGACHAT_API_PERS"
DEFAULT_GIGACHAT_OAUTH_URL = (
    "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
)
DEFAULT_GIGACHAT_BASE_URL = (
    "https://gigachat.devices.sberbank.ru/api/v1"
)
DEFAULT_QWEN_MODEL = "qwen3.6-35b-a3b"
SUPPORTED_QWEN_IMAGE_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}


class HomeworkTextProvider(Protocol):
    def check_homework_text(
        self,
        text: str,
        task_text: str | None = None,
        topic: str | None = None,
        synthetic_test: bool = False,
        pilot_v2: bool = False,
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
        response_format: dict | None = None,
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
        self.response_format = response_format or {"type": "json_object"}
        self.timeout = timeout

    def check_homework_text(
        self,
        text: str,
        task_text: str | None = None,
        topic: str | None = None,
        synthetic_test: bool = False,
        pilot_v2: bool = False,
    ) -> str:
        pilot_allowed = pilot_v2 and self.provider_name == QWEN_PROVIDER
        if not synthetic_test and not pilot_allowed:
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
            "response_format": self.response_format,
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


class QwenHomeworkClient(OpenAICompatibleHomeworkClient):
    def transcribe_homework_image(
        self,
        image_bytes: bytes,
        mime_type: str,
        synthetic_test: bool = False,
        pilot_v2: bool = False,
    ) -> str:
        if not synthetic_test and not pilot_v2:
            raise LLMDataPolicyError(
                "qwen разрешён только для синтетических "
                "тестовых изображений."
            )
        if not image_bytes:
            raise ValueError("Синтетическое изображение пустое.")

        normalized_mime_type = mime_type.strip().lower()
        if normalized_mime_type not in SUPPORTED_QWEN_IMAGE_MIME_TYPES:
            raise ValueError(
                "Qwen Vision поддерживает JPEG, PNG и WEBP."
            )

        encoded_image = base64.b64encode(image_bytes).decode("ascii")
        image_url = (
            f"data:{normalized_mime_type};base64,{encoded_image}"
        )
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                build_homework_image_transcription_prompt()
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": image_url},
                        },
                    ],
                }
            ],
            "temperature": 0.0,
            "max_tokens": 1200,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "homework_image_transcription",
                    "strict": True,
                    "schema": IMAGE_TRANSCRIPTION_RESPONSE_SCHEMA,
                },
            },
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
                f"qwen vision вернул HTTP {status}: {detail}"
            ) from error
        except (httpx.HTTPError, ValueError) as error:
            raise LLMResponseError(
                f"Ошибка запроса к qwen vision: {error}"
            ) from error

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise LLMResponseError(
                "qwen vision вернул неожиданный ответ."
            ) from error

        if not isinstance(content, str) or not content.strip():
            raise LLMResponseError(
                "qwen vision вернул пустую транскрипцию."
            )
        return content


class GigaChatHomeworkClient:
    _token_cache: dict[tuple[str, str, str], tuple[str, float]] = {}
    _token_cache_lock = threading.Lock()

    def __init__(
        self,
        *,
        authorization_key: str,
        model: str = DEFAULT_GIGACHAT_MODEL,
        scope: str = DEFAULT_GIGACHAT_SCOPE,
        oauth_url: str = DEFAULT_GIGACHAT_OAUTH_URL,
        base_url: str = DEFAULT_GIGACHAT_BASE_URL,
        ca_bundle: str | bool = True,
        timeout: float = 45.0,
    ):
        if not authorization_key.strip():
            raise LLMConfigurationError(
                "GIGACHAT_AUTH_KEY не найден."
            )
        if not model.strip():
            raise LLMConfigurationError(
                "GIGACHAT_MODEL не указан."
            )

        self.authorization_key = authorization_key.removeprefix(
            "Basic "
        ).strip()
        self.model = model
        self.scope = scope
        self.oauth_url = oauth_url
        self.url = f"{base_url.rstrip('/')}/chat/completions"
        self.ca_bundle = ca_bundle
        self.timeout = timeout
        self._access_token: str | None = None
        self._token_valid_until = 0.0

    def _get_access_token(self) -> str:
        if self._access_token and time.monotonic() < self._token_valid_until:
            return self._access_token

        cache_key = (
            self.authorization_key,
            self.scope,
            self.oauth_url,
        )
        with self._token_cache_lock:
            cached = self._token_cache.get(cache_key)
            if cached and time.monotonic() < cached[1]:
                self._access_token, self._token_valid_until = cached
                return self._access_token

            try:
                with httpx.Client(
                    timeout=self.timeout,
                    trust_env=False,
                    verify=self.ca_bundle,
                ) as client:
                    response = client.post(
                        self.oauth_url,
                        headers={
                            "Authorization": (
                                f"Basic {self.authorization_key}"
                            ),
                            "Accept": "application/json",
                            "Content-Type": (
                                "application/x-www-form-urlencoded"
                            ),
                            "RqUID": str(uuid.uuid4()),
                        },
                        data={"scope": self.scope},
                    )
                    response.raise_for_status()
                    data = response.json()
            except httpx.HTTPStatusError as error:
                status = error.response.status_code
                detail = error.response.text[:300]
                raise LLMResponseError(
                    f"gigachat OAuth вернул HTTP {status}: {detail}"
                ) from error
            except (httpx.HTTPError, ValueError) as error:
                raise LLMResponseError(
                    f"Ошибка авторизации gigachat: {error}"
                ) from error

            token = data.get("access_token")
            if not isinstance(token, str) or not token.strip():
                raise LLMResponseError(
                    "gigachat OAuth вернул ответ без access_token."
                )

            self._access_token = token
            self._token_valid_until = time.monotonic() + 25 * 60
            self._token_cache[cache_key] = (
                self._access_token,
                self._token_valid_until,
            )
            return token

    def check_homework_text(
        self,
        text: str,
        task_text: str | None = None,
        topic: str | None = None,
        synthetic_test: bool = False,
    ) -> str:
        if not synthetic_test:
            raise LLMDataPolicyError(
                "gigachat разрешён только для синтетических "
                "тестовых примеров."
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
        }

        try:
            token = self._get_access_token()
            with httpx.Client(
                timeout=self.timeout,
                trust_env=False,
                verify=self.ca_bundle,
            ) as client:
                response = client.post(
                    self.url,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as error:
            status = error.response.status_code
            detail = error.response.text[:300]
            raise LLMResponseError(
                f"gigachat вернул HTTP {status}: {detail}"
            ) from error
        except (httpx.HTTPError, ValueError) as error:
            raise LLMResponseError(
                f"Ошибка запроса к gigachat: {error}"
            ) from error

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise LLMResponseError(
                "gigachat вернул неожиданный ответ."
            ) from error

        if not isinstance(content, str) or not content.strip():
            raise LLMResponseError(
                "gigachat вернул пустой результат проверки."
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
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "homework_check_result",
                    "strict": True,
                    "schema": HOMEWORK_CHECK_RESPONSE_SCHEMA,
                },
            },
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

    if normalized == GIGACHAT_PROVIDER:
        ca_bundle = os.getenv("GIGACHAT_CA_BUNDLE", "").strip()
        return GigaChatHomeworkClient(
            authorization_key=os.getenv("GIGACHAT_AUTH_KEY", ""),
            model=os.getenv(
                "GIGACHAT_MODEL",
                DEFAULT_GIGACHAT_MODEL,
            ),
            scope=os.getenv(
                "GIGACHAT_SCOPE",
                DEFAULT_GIGACHAT_SCOPE,
            ),
            oauth_url=os.getenv(
                "GIGACHAT_OAUTH_URL",
                DEFAULT_GIGACHAT_OAUTH_URL,
            ),
            base_url=os.getenv(
                "GIGACHAT_BASE_URL",
                DEFAULT_GIGACHAT_BASE_URL,
            ),
            ca_bundle=ca_bundle or True,
        )

    if normalized == QWEN_PROVIDER:
        api_key = os.getenv("YANDEX_API_KEY", "")
        folder_id = os.getenv("YANDEX_FOLDER_ID", "")
        if not folder_id:
            raise LLMConfigurationError(
                "YANDEX_FOLDER_ID не найден."
            )
        model = os.getenv("QWEN_MODEL", DEFAULT_QWEN_MODEL)
        if not model.startswith("gpt://"):
            model = f"gpt://{folder_id}/{model.lstrip('/')}"

        return QwenHomeworkClient(
            provider_name=QWEN_PROVIDER,
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
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "homework_check_result",
                    "strict": True,
                    "schema": HOMEWORK_CHECK_RESPONSE_SCHEMA,
                },
            },
        )

    supported = ", ".join(
        (
            *SUPPORTED_TEXT_PROVIDERS,
            GIGACHAT_PROVIDER,
            QWEN_PROVIDER,
        )
    )
    raise LLMConfigurationError(
        f"Неизвестный AI-провайдер: {provider_name}. "
        f"Допустимые значения: {supported}."
    )
