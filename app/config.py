"""只在服务端读取配置；不打印或返回密钥。"""
from dataclasses import dataclass, field
import os
from pathlib import Path

from dotenv import dotenv_values


ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
PROVIDERS = {
    "openai": ("OpenAI", "https://api.openai.com/v1", "gpt-4o-mini"),
    "deepseek": ("DeepSeek", "https://api.deepseek.com", "deepseek-flash"),
}


@dataclass(frozen=True)
class Settings:
    api_key: str = field(repr=False)
    model: str = "gpt-4o-mini"
    provider: str = "openai"

    @property
    def label(self):
        return PROVIDERS[self.provider][0]

    @property
    def base_url(self):
        return PROVIDERS[self.provider][1]

    @property
    def key_variable(self):
        return f"{self.provider.upper()}_API_KEY"


def get_settings():
    values = dotenv_values(ENV_FILE, interpolate=False)

    def read(name, default=""):
        return (os.environ.get(name, values.get(name)) or default).strip()

    provider = read("AI_PROVIDER", "openai").lower()
    if provider not in PROVIDERS:
        raise ValueError("AI_PROVIDER 必须为 deepseek 或 openai。")
    return Settings(
        api_key=read(f"{provider.upper()}_API_KEY"),
        model=read(f"{provider.upper()}_MODEL", PROVIDERS[provider][2]),
        provider=provider,
    )
