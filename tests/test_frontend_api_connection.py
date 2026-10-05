from pathlib import Path
import unittest


APP_JS = Path(__file__).parent.parent / "app" / "static" / "app.js"


class FrontendApiConnectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = APP_JS.read_text(encoding="utf-8")

    def test_frontend_calls_analyze_api(self):
        self.assertIn('fetch("/api/analyze"', self.source)
        self.assertIn('method: "POST"', self.source)
        self.assertIn("JSON.stringify({ text: originalText })", self.source)

    def test_frontend_handles_failed_request(self):
        self.assertIn("if (!response.ok)", self.source)
        self.assertIn("暂时没有分析成功，请稍后重试", self.source)

    def test_old_fake_reply_list_is_removed(self):
        self.assertNotIn("fakeReplies", self.source)

    def test_history_uses_backend_instead_of_local_storage(self):
        self.assertIn('fetch("/api/entries")', self.source)
        self.assertIn('method: "DELETE"', self.source)
        self.assertNotIn("localStorage", self.source)

    def test_dynamic_text_is_escaped_before_rendering(self):
        self.assertIn("function escapeHtml", self.source)
        self.assertIn("escapeHtml(entry.original_text)", self.source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
