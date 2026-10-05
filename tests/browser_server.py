"""Isolated browser QA, never loads a real key or the user's production DB.

Run: python -m tests.browser_server. All entries disappear when stopped.
Inputs: 测试失败 -> upstream failure; 安全测试 -> support response; otherwise success.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
import uvicorn
from app import database


def main():
    with TemporaryDirectory(prefix="mood-browser-qa-") as temporary:
        database.DB_PATH = Path(temporary) / "test.db"
        from app import main as application
        from app.ai_service import AIServiceError
        from tests.fixtures import sample_analysis

        def fake_analyze(text):
            if text == "测试失败":
                raise AIServiceError("ai_unavailable", "测试：AI 暂时不可用，本次未保存。", 503)
            return sample_analysis().model_copy(update={
                "safety": "support_needed" if text == "安全测试" else "normal"
            })

        application.analyze_text = fake_analyze
        application.get_settings = lambda: type("QASettings", (), {
            "api_key": "synthetic-not-a-key", "provider": "test",
            "label": "浏览器验收模拟服务（不收费）", "key_variable": "TEST_ONLY",
        })()
        uvicorn.run(application.app, host="127.0.0.1", port=8001)


if __name__ == "__main__":
    main()
