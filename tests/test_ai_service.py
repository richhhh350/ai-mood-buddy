"""通过真实 SDK 解析本地模拟 HTTP 响应；绝不请求外部 AI。"""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import httpx2
from openai import OpenAI

from app.ai_service import AIServiceError, analyze_text
from app.config import Settings, get_settings
from tests.fixtures import sample_analysis


def envelope(output=None, status="completed"):
    return {
        "id": "resp_test", "object": "response", "created_at": 0,
        "status": status, "model": "test-model",
        "output": output if output is not None else [{
            "id": "msg_test", "type": "message", "role": "assistant", "status": "completed",
            "content": [{"type": "output_text", "text": sample_analysis().model_dump_json(), "annotations": []}],
        }],
    }


class AIServiceTests(unittest.TestCase):
    def setUp(self):
        self.settings_patch = patch("app.ai_service.get_settings", return_value=Settings("test-key", "test-model"))
        self.settings = self.settings_patch.start()
        self.addCleanup(self.settings_patch.stop)
        self.requests = []

    def call_with_transport(self, handler):
        def capture(request):
            self.requests.append(request)
            return handler(request)

        def client_factory(**kwargs):
            self.assertEqual(0, kwargs["max_retries"])
            self.assertEqual(30.0, kwargs["timeout"])
            return OpenAI(http_client=httpx2.Client(transport=httpx2.MockTransport(capture)), **kwargs)

        with patch("app.ai_service.OpenAI", side_effect=client_factory):
            return analyze_text("今天有点累")

    def test_real_sdk_parses_schema_and_only_sends_current_input(self):
        result = self.call_with_transport(lambda _: httpx2.Response(200, json=envelope()))
        self.assertEqual(sample_analysis(), result)
        sent = json.loads(self.requests[0].content)
        self.assertFalse(sent["store"])
        self.assertEqual("test-model", sent["model"])
        self.assertEqual({"role": "user", "content": "今天有点累"}, sent["input"][1])
        self.assertEqual(2, len(sent["input"]))
        self.assertTrue(sent["text"]["format"]["strict"])

    def test_missing_key_fails_without_constructing_client(self):
        self.settings.return_value = Settings("")
        with patch("app.ai_service.OpenAI") as client:
            with self.assertRaises(AIServiceError) as caught:
                analyze_text("输入")
            self.assertEqual("ai_not_configured", caught.exception.code)
            client.assert_not_called()

    def test_http_failures_are_sanitized_and_not_retried(self):
        for status, code in [(401, "ai_credentials"), (403, "ai_credentials"),
                             (429, "ai_rate_limited"), (500, "ai_unavailable")]:
            with self.subTest(status=status):
                self.requests.clear()
                with self.assertRaises(AIServiceError) as caught:
                    self.call_with_transport(lambda _: httpx2.Response(status, json={"error": {"message": "PRIVATE_TOKEN"}}))
                self.assertEqual(code, caught.exception.code)
                self.assertNotIn("PRIVATE_TOKEN", str(caught.exception))
                self.assertEqual(1, len(self.requests))

    def test_timeout_is_mapped_to_504(self):
        def timeout(request):
            raise httpx2.ReadTimeout("private request details", request=request)
        with self.assertRaises(AIServiceError) as caught:
            self.call_with_transport(timeout)
        self.assertEqual(504, caught.exception.status_code)
        self.assertEqual(1, len(self.requests))

    def test_connection_failure_is_sanitized(self):
        def disconnected(request):
            raise httpx2.ConnectError("private request details", request=request)
        with self.assertRaises(AIServiceError) as caught:
            self.call_with_transport(disconnected)
        self.assertEqual("ai_connection", caught.exception.code)

    def test_refusal_is_not_a_success(self):
        body = envelope()
        body["output"][0]["content"] = [{"type": "refusal", "refusal": "Cannot respond"}]
        with self.assertRaises(AIServiceError) as caught:
            self.call_with_transport(lambda _: httpx2.Response(200, json=body))
        self.assertEqual("ai_refused", caught.exception.code)

    def test_incomplete_output_is_not_a_success(self):
        with self.assertRaises(AIServiceError) as caught:
            self.call_with_transport(lambda _: httpx2.Response(200, json=envelope([], "incomplete")))
        self.assertEqual("ai_incomplete", caught.exception.code)

    def test_invalid_schema_and_json_are_rejected(self):
        invalid = sample_analysis().model_dump()
        invalid["intensity"] = 9
        for content in [json.dumps(invalid), "not json"]:
            with self.subTest(content=content):
                body = envelope()
                body["output"][0]["content"][0]["text"] = content
                with self.assertRaises(AIServiceError) as caught:
                    self.call_with_transport(lambda _: httpx2.Response(200, json=body))
                self.assertEqual("ai_invalid_output", caught.exception.code)

    def test_config_reads_environment_without_exposing_key(self):
        with TemporaryDirectory() as directory:
            with patch("app.config.ENV_FILE", Path(directory) / "absent.env"):
                with patch.dict("os.environ", {"OPENAI_API_KEY": "secret-test", "OPENAI_MODEL": "test-model"}, clear=True):
                    settings = get_settings()
                    self.assertEqual("secret-test", settings.api_key)
                    self.assertEqual("test-model", settings.model)
                    self.assertNotIn("secret-test", repr(settings))
