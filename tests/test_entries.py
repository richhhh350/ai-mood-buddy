from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import sqlite3
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.database import init_database
from app.main import app
from tests.fixtures import sample_analysis


class EntriesEndpointTests(unittest.TestCase):
    def setUp(self):
        ai_patcher = patch("app.main.analyze_text", return_value=sample_analysis())
        ai_patcher.start()
        self.addCleanup(ai_patcher.stop)
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

    def create_entry(self, text="今天完成了一件事"):
        return self.client.post("/api/analyze", json={"text": text}).json()

    def test_analyzed_mood_is_saved_and_listed(self):
        created = self.create_entry()

        response = self.client.get("/api/entries")

        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(response.json()))
        self.assertEqual(created["id"], response.json()[0]["id"])

    def test_entry_can_be_deleted(self):
        created = self.create_entry()

        delete_response = self.client.delete(f'/api/entries/{created["id"]}')

        self.assertEqual(204, delete_response.status_code)
        self.assertEqual([], self.client.get("/api/entries").json())

    def test_deleting_unknown_entry_returns_404(self):
        response = self.client.delete("/api/entries/not-found")

        self.assertEqual(404, response.status_code)

    def test_all_entries_can_be_cleared(self):
        self.create_entry("第一条")
        self.create_entry("第二条")

        response = self.client.delete("/api/entries")

        self.assertEqual(204, response.status_code)
        self.assertEqual([], self.client.get("/api/entries").json())

    def test_latest_twenty_are_sorted_newest_first(self):
        created = [self.create_entry(f"第 {i} 条测试") for i in range(23)]
        result = self.client.get("/api/entries").json()
        self.assertEqual([entry["id"] for entry in reversed(created[-20:])],
                         [entry["id"] for entry in result])

    def test_records_survive_a_new_client_and_database_initialization(self):
        created = self.create_entry()
        init_database()
        with TestClient(app) as new_client:
            self.assertEqual([created], new_client.get("/api/entries").json())

    def test_sql_and_html_are_stored_as_plain_data(self):
        text = "'); DROP TABLE mood_entries; -- <script>alert(1)</script>"
        self.create_entry(text)
        result = self.client.get("/api/entries").json()
        self.assertEqual(text, result[0]["original_text"])
        self.assertEqual(1, len(result))

    def test_storage_failure_is_safe_and_does_not_save(self):
        with patch("app.main.create_entry", side_effect=sqlite3.OperationalError("private/path/key")):
            response = self.client.post("/api/analyze", json={"text": "测试"})
        self.assertEqual(503, response.status_code)
        self.assertEqual("storage_unavailable", response.json()["detail"]["code"])
        self.assertNotIn("private", response.text)
        self.assertEqual([], self.client.get("/api/entries").json())

    def test_cross_origin_writes_and_foreign_hosts_are_rejected(self):
        created = self.create_entry()
        headers = {"Origin": "https://untrusted.example"}
        self.assertEqual(403, self.client.delete("/api/entries", headers=headers).status_code)
        self.assertEqual(403, self.client.post("/api/analyze", headers=headers, json={"text": "测试"}).status_code)
        self.assertEqual([created], self.client.get("/api/entries").json())
        self.assertEqual(400, self.client.get("/health", headers={"Host": "untrusted.example"}).status_code)

    def test_same_origin_json_works_and_plain_text_is_rejected(self):
        self.assertEqual(200, self.client.post("/api/analyze", headers={"Origin": "http://testserver"}, json={"text": "测试"}).status_code)
        self.assertEqual(415, self.client.post("/api/analyze", content='{"text":"test"}', headers={"Content-Type": "text/plain"}).status_code)

    def test_privacy_and_browser_headers(self):
        response = self.client.get("/")
        self.assertEqual("no-store", response.headers["cache-control"])
        self.assertIn("frame-ancestors 'none'", response.headers["content-security-policy"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
