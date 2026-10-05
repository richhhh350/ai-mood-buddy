from fastapi.testclient import TestClient
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from app.database import init_database
from app.main import app
from app.ai_service import AIServiceError
from tests.fixtures import sample_analysis


class AnalyzeEndpointTests(unittest.TestCase):
    def setUp(self):
        self.ai_patcher = patch("app.main.analyze_text", return_value=sample_analysis())
        self.ai = self.ai_patcher.start()
        self.addCleanup(self.ai_patcher.stop)
        self.temp_directory = TemporaryDirectory()
        self.db_patcher = patch(
            "app.database.DB_PATH",
            Path(self.temp_directory.name) / "test.db",
        )
        self.db_patcher.start()
        init_database()
        self.client = TestClient(app)

    def tearDown(self):
        self.db_patcher.stop()
        self.temp_directory.cleanup()

    def test_valid_mood_text_returns_structured_result(self):
        response = self.client.post("/api/analyze", json={"text": "今天有点累"})

        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertTrue(
            {"id", "original_text", "mood", "emoji", "intensity", "response", "action", "created_at"}
            <= set(data)
        )
        self.assertEqual("今天有点累", data["original_text"])

    def test_empty_text_is_rejected(self):
        response = self.client.post("/api/analyze", json={"text": ""})

        self.assertEqual(422, response.status_code)

    def test_text_longer_than_500_characters_is_rejected(self):
        response = self.client.post("/api/analyze", json={"text": "心" * 501})

        self.assertEqual(422, response.status_code)

    def test_whitespace_is_rejected_before_ai_call(self):
        response = self.client.post("/api/analyze", json={"text": " \n\t "})
        self.assertEqual(422, response.status_code)
        self.ai.assert_not_called()
        self.assertEqual([], self.client.get("/api/entries").json())

    def test_trimmed_input_and_model_output_are_saved(self):
        response = self.client.post("/api/analyze", json={"text": "  今天好累  "})
        self.ai.assert_called_once_with("今天好累")
        self.assertEqual("疲惫", response.json()["mood"])
        self.assertEqual("今天好累", response.json()["original_text"])
        self.assertNotIn("safety", response.json())

    def test_ai_failure_never_creates_a_record(self):
        for status in [502, 503, 504]:
            with self.subTest(status=status):
                self.ai.side_effect = AIServiceError("test_failure", "稍后重试", status)
                response = self.client.post("/api/analyze", json={"text": "今天有点累"})
                self.assertEqual(status, response.status_code)
                self.assertEqual("test_failure", response.json()["detail"]["code"])
                self.assertEqual([], self.client.get("/api/entries").json())

    def test_support_response_is_not_saved_as_normal_analysis(self):
        self.ai.return_value = sample_analysis().model_copy(update={"safety": "support_needed"})
        response = self.client.post("/api/analyze", json={"text": "安全分支测试输入"})
        self.assertEqual(200, response.status_code)
        self.assertEqual("support_needed", response.json()["status"])
        self.assertFalse(response.json()["saved"])
        self.assertNotIn("action", response.json())
        self.assertEqual([], self.client.get("/api/entries").json())


if __name__ == "__main__":
    unittest.main(verbosity=2)
