from fastapi.testclient import TestClient
import unittest

from app.main import app
from app.config import Settings
from unittest.mock import patch


class StaticPageTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_homepage_is_served_by_python(self):
        response = self.client.get("/")

        self.assertEqual(200, response.status_code)
        self.assertIn("AI 心情搭子", response.text)
        self.assertIn("mood-input", response.text)

    def test_secrets_and_database_are_not_served(self):
        for path in ["/.env", "/data/mood_buddy.db", "/app/config.py"]:
            self.assertEqual(404, self.client.get(path).status_code)

    def test_status_exposes_only_configuration_presence(self):
        with patch("app.main.get_settings", return_value=Settings("secret-test")):
            response = self.client.get("/api/status")
            self.assertEqual({"ai_configured": True, "provider": "openai", "provider_label": "OpenAI",
                              "key_variable": "OPENAI_API_KEY"}, response.json())
            self.assertNotIn("secret-test", response.text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
