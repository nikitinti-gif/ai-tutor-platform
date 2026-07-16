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
    GigaChatHomeworkClient,
    OpenAICompatibleHomeworkClient,
    QwenHomeworkClient,
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

    def test_pilot_flag_does_not_allow_non_qwen_provider(self):
        client = OpenAICompatibleHomeworkClient(
            provider_name="mistral",
            api_key="secret",
            model="model",
            base_url="https://example.test/v1",
        )

        with patch("src.ai_engine.provider_clients.httpx.Client") as cls:
            with self.assertRaises(LLMDataPolicyError):
                client.check_homework_text("real", pilot_v2=True)

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

    def test_gigachat_real_data_is_blocked_before_oauth(self):
        client = GigaChatHomeworkClient(
            authorization_key="secret",
        )

        with patch("src.ai_engine.provider_clients.httpx.Client") as cls:
            with self.assertRaises(LLMDataPolicyError):
                client.check_homework_text("реальный ответ")

        cls.assert_not_called()

    @patch("src.ai_engine.provider_clients.httpx.Client")
    def test_gigachat_exchanges_key_and_calls_pro_model(
        self,
        client_class,
    ):
        oauth_response = Mock()
        oauth_response.json.return_value = {"access_token": "token"}
        chat_response = Mock()
        chat_response.json.return_value = {
            "choices": [
                {"message": {"content": '{"status":"correct"}'}}
            ]
        }
        context_client = Mock()
        context_client.post.side_effect = [
            oauth_response,
            chat_response,
        ]
        client_class.return_value.__enter__.return_value = context_client

        client = GigaChatHomeworkClient(
            authorization_key="Basic secret",
        )
        result = client.check_homework_text(
            "print(1)",
            synthetic_test=True,
        )

        self.assertEqual(result, '{"status":"correct"}')
        oauth_request, chat_request = context_client.post.call_args_list
        self.assertEqual(
            oauth_request.args[0],
            "https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
        )
        self.assertEqual(
            oauth_request.kwargs["headers"]["Authorization"],
            "Basic secret",
        )
        self.assertEqual(
            oauth_request.kwargs["data"],
            {"scope": "GIGACHAT_API_PERS"},
        )
        self.assertEqual(
            chat_request.kwargs["json"]["model"],
            "GigaChat-2-Pro",
        )
        self.assertEqual(
            chat_request.kwargs["headers"]["Authorization"],
            "Bearer token",
        )

    @patch.dict(
        os.environ,
        {
            "GIGACHAT_AUTH_KEY": "key",
            "GIGACHAT_MODEL": "GigaChat-2-Pro",
            "GIGACHAT_SCOPE": "GIGACHAT_API_PERS",
        },
        clear=False,
    )
    def test_gigachat_factory_uses_pro_model(self):
        client = create_text_provider("gigachat")

        self.assertEqual(client.model, "GigaChat-2-Pro")
        self.assertEqual(client.scope, "GIGACHAT_API_PERS")

    @patch("src.ai_engine.provider_clients.httpx.Client")
    def test_gigachat_token_is_reused_between_clients(self, client_class):
        oauth_response = Mock()
        oauth_response.json.return_value = {"access_token": "cached"}
        chat_response = Mock()
        chat_response.json.return_value = {
            "choices": [
                {"message": {"content": '{"status":"correct"}'}}
            ]
        }
        context_client = Mock()
        context_client.post.side_effect = [
            oauth_response,
            chat_response,
            chat_response,
        ]
        client_class.return_value.__enter__.return_value = context_client

        first = GigaChatHomeworkClient(
            authorization_key="cache-secret",
        )
        second = GigaChatHomeworkClient(
            authorization_key="cache-secret",
        )

        first.check_homework_text("one", synthetic_test=True)
        second.check_homework_text("two", synthetic_test=True)

        oauth_calls = [
            call for call in context_client.post.call_args_list
            if call.args[0].endswith("/oauth")
        ]
        self.assertEqual(len(oauth_calls), 1)

    @patch.dict(
        os.environ,
        {
            "YANDEX_API_KEY": "key",
            "YANDEX_FOLDER_ID": "folder",
            "QWEN_MODEL": "qwen3.6-35b-a3b",
        },
        clear=False,
    )
    def test_qwen_factory_uses_yandex_ai_studio(self):
        from src.ai_engine.schemas import HOMEWORK_CHECK_RESPONSE_SCHEMA

        client = create_text_provider("qwen")

        self.assertEqual(
            client.model,
            "gpt://folder/qwen3.6-35b-a3b",
        )
        self.assertEqual(client.provider_name, "qwen")
        self.assertEqual(client.headers["Authorization"], "Api-Key key")
        self.assertEqual(client.headers["OpenAI-Project"], "folder")
        self.assertEqual(client.response_format["type"], "json_schema")
        self.assertTrue(client.response_format["json_schema"]["strict"])
        self.assertEqual(
            client.response_format["json_schema"]["schema"],
            HOMEWORK_CHECK_RESPONSE_SCHEMA,
        )
        self.assertIsInstance(client, QwenHomeworkClient)

    def test_qwen_real_image_is_blocked_before_http_request(self):
        client = QwenHomeworkClient(
            provider_name="qwen",
            api_key="secret",
            model="qwen3.6-35b-a3b",
            base_url="https://example.test/v1",
        )

        with patch("src.ai_engine.provider_clients.httpx.Client") as cls:
            with self.assertRaises(LLMDataPolicyError):
                client.transcribe_homework_image(
                    b"real-image",
                    "image/jpeg",
                )

        cls.assert_not_called()

    @patch("src.ai_engine.provider_clients.httpx.Client")
    def test_qwen_sends_synthetic_image_as_base64(self, client_class):
        from src.ai_engine.schemas import (
            IMAGE_TRANSCRIPTION_RESPONSE_SCHEMA,
        )

        response = Mock()
        response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"legibility":"readable",'
                            '"confidence":0.9,'
                            '"transcription":"print(1)"}'
                        )
                    }
                }
            ]
        }
        context_client = Mock()
        context_client.post.return_value = response
        client_class.return_value.__enter__.return_value = context_client

        client = QwenHomeworkClient(
            provider_name="qwen",
            api_key="secret",
            model="qwen3.6-35b-a3b",
            base_url="https://example.test/v1",
        )
        result = client.transcribe_homework_image(
            b"synthetic-image",
            "image/jpeg",
            synthetic_test=True,
        )

        self.assertIn('"legibility":"readable"', result)
        payload = context_client.post.call_args.kwargs["json"]
        image_part = payload["messages"][0]["content"][1]
        self.assertEqual(image_part["type"], "image_url")
        self.assertTrue(
            image_part["image_url"]["url"].startswith(
                "data:image/jpeg;base64,"
            )
        )
        self.assertEqual(
            payload["response_format"]["json_schema"]["schema"],
            IMAGE_TRANSCRIPTION_RESPONSE_SCHEMA,
        )

    @patch.dict(
        os.environ,
        {
            "OPENROUTER_API_KEY": "openrouter-key",
            "KIMI_MODEL": "moonshotai/kimi-k2.6:free",
        },
        clear=False,
    )
    def test_kimi_factory_uses_moonshot_multimodal_model(self):
        client = create_text_provider("kimi")

        self.assertIsInstance(client, QwenHomeworkClient)
        self.assertEqual(client.provider_name, "kimi")
        self.assertEqual(client.model, "moonshotai/kimi-k2.6:free")
        self.assertEqual(
            client.url,
            "https://openrouter.ai/api/v1/chat/completions",
        )

    @patch("src.ai_engine.provider_clients.httpx.Client")
    def test_kimi_request_disables_thinking_and_omits_temperature(
        self,
        client_class,
    ):
        response = Mock()
        response.json.return_value = {
            "choices": [
                {"message": {"content": '{"status":"correct"}'}}
            ]
        }
        context_client = Mock()
        context_client.post.return_value = response
        client_class.return_value.__enter__.return_value = context_client
        client = QwenHomeworkClient(
            provider_name="kimi",
            api_key="secret",
            model="kimi-k2.6",
            base_url="https://api.moonshot.ai/v1",
        )

        client.check_homework_text("print(1)", synthetic_test=True)

        payload = context_client.post.call_args.kwargs["json"]
        self.assertNotIn("temperature", payload)
        self.assertEqual(payload["thinking"], {"type": "disabled"})

    def test_kimi_real_image_is_blocked_before_http_request(self):
        client = QwenHomeworkClient(
            provider_name="kimi",
            api_key="secret",
            model="kimi-k2.6",
            base_url="https://api.moonshot.ai/v1",
        )

        with patch("src.ai_engine.provider_clients.httpx.Client") as cls:
            with self.assertRaises(LLMDataPolicyError):
                client.transcribe_homework_image(
                    b"real-image",
                    "image/jpeg",
                )

        cls.assert_not_called()

    @patch.dict(
        os.environ,
        {
            "MINIMAX_API_KEY": "minimax-key",
            "MINIMAX_MODEL": "MiniMax-M3",
        },
        clear=False,
    )
    def test_minimax_factory_uses_m3_multimodal_model(self):
        client = create_text_provider("minimax")

        self.assertIsInstance(client, QwenHomeworkClient)
        self.assertEqual(client.provider_name, "minimax")
        self.assertEqual(client.model, "MiniMax-M3")
        self.assertEqual(
            client.url,
            "https://api.minimax.io/v1/chat/completions",
        )
        self.assertEqual(
            client.response_format,
            {"type": "json_object"},
        )

    @patch("src.ai_engine.provider_clients.httpx.Client")
    def test_minimax_request_disables_thinking(self, client_class):
        response = Mock()
        response.json.return_value = {
            "choices": [
                {"message": {"content": '{"status":"correct"}'}}
            ]
        }
        context_client = Mock()
        context_client.post.return_value = response
        client_class.return_value.__enter__.return_value = context_client
        client = QwenHomeworkClient(
            provider_name="minimax",
            api_key="secret",
            model="MiniMax-M3",
            base_url="https://api.minimax.io/v1",
            response_format={"type": "json_object"},
        )

        client.check_homework_text("print(1)", synthetic_test=True)

        payload = context_client.post.call_args.kwargs["json"]
        self.assertEqual(payload["thinking"], {"type": "disabled"})
        self.assertEqual(
            payload["response_format"],
            {"type": "json_object"},
        )

    def test_minimax_real_image_is_blocked_before_http_request(self):
        client = QwenHomeworkClient(
            provider_name="minimax",
            api_key="secret",
            model="MiniMax-M3",
            base_url="https://api.minimax.io/v1",
        )

        with patch("src.ai_engine.provider_clients.httpx.Client") as cls:
            with self.assertRaises(LLMDataPolicyError):
                client.transcribe_homework_image(
                    b"real-image",
                    "image/jpeg",
                )

        cls.assert_not_called()

    @patch.dict(
        os.environ,
        {
            "MISTRAL_API_KEY": "key",
            "MISTRAL_MODEL": "mistral-small-latest",
        },
        clear=False,
    )
    def test_mistral_factory_uses_json_schema(self):
        from src.ai_engine.schemas import HOMEWORK_CHECK_RESPONSE_SCHEMA

        client = create_text_provider("mistral")

        self.assertEqual(client.response_format["type"], "json_schema")
        self.assertTrue(client.response_format["json_schema"]["strict"])
        self.assertEqual(
            client.response_format["json_schema"]["schema"],
            HOMEWORK_CHECK_RESPONSE_SCHEMA,
        )

    def test_unknown_provider_is_rejected(self):
        with self.assertRaises(LLMConfigurationError):
            create_text_provider("unknown")


if __name__ == "__main__":
    unittest.main()
