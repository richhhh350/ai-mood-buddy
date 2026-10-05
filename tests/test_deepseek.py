import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import httpx2
from fastapi.testclient import TestClient

from app.ai_service import AIServiceError, analyze_text
from app.config import Settings, get_settings
from app.main import app
from tests.fixtures import sample_analysis
import tests.test_ai_service as sdk_tests


def completion(content=None, finish_reason="stop"):
    return {"id": "chat-test", "object": "chat.completion", "created": 0,
            "model": "deepseek-flash", "choices": [{"index": 0, "finish_reason": finish_reason,
            "message": {"role": "assistant", "content": content}}]}


class DeepSeekTests(unittest.TestCase):
    call_with_transport = sdk_tests.AIServiceTests.call_with_transport

    def setUp(self):
        setting_patch = patch("app.ai_service.get_settings", return_value=Settings("deepseek-test-key", "deepseek-flash", "deepseek"))
        self.settings = setting_patch.start()
        self.addCleanup(setting_patch.stop)
        self.requests = []

    def test_deepseek_request_uses_own_host_key_and_json_mode(self):
        result = self.call_with_transport(lambda _: httpx2.Response(200, json=completion(sample_analysis().model_dump_json())))
        self.assertEqual(sample_analysis(), result)
        request = self.requests[0]
        self.assertEqual("https://api.deepseek.com/chat/completions", str(request.url))
        self.assertEqual("Bearer deepseek-test-key", request.headers["authorization"])
        sent = json.loads(request.content)
        self.assertEqual("deepseek-flash", sent["model"])
        self.assertEqual({"type": "json_object"}, sent["response_format"])
        self.assertEqual({"type": "disabled"}, sent["thinking"])
        self.assertIn("JSON", sent["messages"][0]["content"])
        self.assertEqual(2, len(sent["messages"]))
        self.assertEqual("今天有点累", sent["messages"][1]["content"])

    def test_empty_invalid_and_wrong_shape_output_are_rejected(self):
        invalid = sample_analysis().model_dump()
        invalid["intensity"] = 99
        for value in [None, "", "   ", "not json", "{}", json.dumps(invalid), "[]"]:
            with self.subTest(value=value):
                with self.assertRaises(AIServiceError) as caught:
                    self.call_with_transport(lambda _: httpx2.Response(200, json=completion(value)))
                self.assertEqual("ai_invalid_output", caught.exception.code)

    def test_truncation_and_content_filter_are_not_successes(self):
        for reason, code in [("length", "ai_incomplete"), ("content_filter", "ai_refused")]:
            with self.subTest(reason=reason):
                with self.assertRaises(AIServiceError) as caught:
                    self.call_with_transport(lambda _: httpx2.Response(200, json=completion("{}", reason)))
                self.assertEqual(code, caught.exception.code)

    def test_provider_credentials_and_rate_errors_are_sanitized(self):
        for status, code in [(401, "ai_credentials"), (429, "ai_rate_limited")]:
            with self.subTest(status=status):
                self.requests.clear()
                with self.assertRaises(AIServiceError) as caught:
                    self.call_with_transport(lambda _: httpx2.Response(status, json={"error": {"message": "private-text"}}))
                self.assertEqual(code, caught.exception.code)
                self.assertNotIn("private-text", str(caught.exception))
                self.assertEqual(1, len(self.requests))

    def test_deepseek_settings_do_not_fall_back_to_openai_key(self):
        with TemporaryDirectory() as directory:
            with patch("app.config.ENV_FILE", Path(directory) / "absent.env"):
                with patch.dict("os.environ", {"AI_PROVIDER": "deepseek", "OPENAI_API_KEY": "openai-secret"}, clear=True):
                    self.assertEqual("", get_settings().api_key)
                with patch.dict("os.environ", {"AI_PROVIDER": "deepseek", "DEEPSEEK_API_KEY": "ds-secret"}, clear=True):
                    settings = get_settings()
                    self.assertEqual("deepseek-flash", settings.model)
                    self.assertEqual("ds-secret", settings.api_key)
                    self.assertNotIn("ds-secret", repr(settings))

    def test_unknown_provider_is_clear_configuration_error(self):
        self.settings.side_effect = ValueError("invalid provider")
        with self.assertRaises(AIServiceError) as caught:
            analyze_text("测试")
        self.assertEqual("ai_configuration", caught.exception.code)
        with patch("app.main.get_settings", side_effect=ValueError("invalid provider")):
            response = TestClient(app).get("/api/status")
            self.assertFalse(response.json()["ai_configured"])

    def test_missing_key_names_the_selected_provider(self):
        self.settings.return_value = Settings("", "deepseek-flash", "deepseek")
        with self.assertRaises(AIServiceError) as caught:
            analyze_text("测试")
        self.assertIn("DEEPSEEK_API_KEY", str(caught.exception))
        self.assertNotIn("OPENAI_API_KEY", str(caught.exception))
