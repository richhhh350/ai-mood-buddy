from html.parser import HTMLParser
from pathlib import Path
import unittest


HTML_FILE = Path(__file__).parent.parent / "app" / "static" / "index.html"


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.ids = {}
        self.labels = []
        self.text = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        self.tags.append((tag, attributes))
        if "id" in attributes:
            self.ids[attributes["id"]] = (tag, attributes)
        if tag == "label":
            self.labels.append(attributes)

    def handle_data(self, data):
        value = data.strip()
        if value:
            self.text.append(value)


class PageStructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = PageParser()
        cls.parser.feed(HTML_FILE.read_text(encoding="utf-8"))
        cls.page_text = " ".join(cls.parser.text)

    def test_has_main_content_area(self):
        self.assertTrue(any(tag == "main" for tag, _ in self.parser.tags))

    def test_has_product_title(self):
        self.assertIn("AI 心情搭子", self.page_text)

    def test_has_mood_input_with_limit(self):
        tag, attrs = self.parser.ids["mood-input"]
        self.assertEqual("textarea", tag)
        self.assertEqual("input-message", attrs.get("aria-describedby"))
        self.assertIn("/ 500", self.page_text)
        self.assertTrue(attrs.get("placeholder"))

    def test_label_is_connected_to_input(self):
        self.assertTrue(
            any(label.get("for") == "mood-input" for label in self.parser.labels)
        )

    def test_has_analyze_button(self):
        tag, _ = self.parser.ids["analyze-button"]
        self.assertEqual("button", tag)
        self.assertIn("分析一下", self.page_text)

    def test_has_result_and_history_sections(self):
        self.assertEqual("section", self.parser.ids["result"][0])
        self.assertEqual("section", self.parser.ids["history"][0])
        self.assertIn("分析结果", self.page_text)
        self.assertIn("最近记录", self.page_text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
