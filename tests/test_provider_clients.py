import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ai_engine.llm_client import (
    LLMConfigurationError,
    LLMDataPolicyError,
)
from src.ai_engine.provider_clients import (
    OpenAICompatibleHomeworkClient,
    create_text_provider,
)


class ProviderClientsTest(unittest.TestCase):
    def test_real_data_is_blocked_before_http_request(self):
        client = OpenAICompatibleHomeworkClient(
            provider_name="test",
            api_key="secret",
            model="model",
            base_url="https://example.test/v1",
        )

        with patch("src.ai_engine.provider_clients.httpx.Client") as cls:
            with self.assertRaises(LLMDataPolicyError):
                client.check_homework_text("реальный ответ")

        cls.assert_not_called()

    @patch("src.ai_engine.provider_clients.httpx.Client")
    def test_openai_compatible_request_uses_json_mode(self, client_class):
        response = Mock()
        response.json.return_value = {
            "choices": [
                {"message": {"content": '{"status":"correct"}'}}
            ]
        }
        context_client = Mock()
        context_client.post.return_value = response
        client_class.return_value.__enter__.return_value = context_client

        client = OpenAICompatibleHomeworkClient(
            provider_name="mistral",
            api_key="secret",
            model="mistral-small-latest",
            base_url="https://api.mistral.ai/v1",
        )
        result = client.check_homework_text(
            "print(1)",
            synthetic_test=True,
        )

        self.assertEqual(result, '{"status":"correct"}')
        request = context_client.post.call_args
        self.assertEqual(
            request.args[0],
            "https://api.mistral.ai/v1/chat/completions",
        )
        self.assertEqual(
            request.kwargs["json"]["response_format"],
            {"type": "json_object"},
        )
        response.raise_for_status.assert_called_once()

    @patch.dict(
        os.environ,
        {
            "YANDEX_API_KEY": "key",
            "YANDEX_FOLDER_ID": "folder",
            "YANDEX_MODEL": "yandexgpt/latest",
        },
        clear=False,
    )
    def test_yandex_factory_builds_model_uri_and_headers(self):
        client = create_text_provider("yandex")

        self.assertEqual(
            client.model,
            "gpt://folder/yandexgpt/latest",
        )
        self.assertEqual(client.headers["Authorization"], "Api-Key key")
        self.assertEqual(client.headers["OpenAI-Project"], "folder")

    @patch.dict(os.environ, {"MISTRAL_API_KEY": ""}, clear=False)
    def test_mistral_key_is_required(self):
        with self.assertRaises(LLMConfigurationError):
            create_text_provider("mistral")

    def test_unknown_provider_is_rejected(self):
        with self.assertRaises(LLMConfigurationError):
            create_text_provider("unknown")


if __name__ == "__main__":
    unittest.main()
