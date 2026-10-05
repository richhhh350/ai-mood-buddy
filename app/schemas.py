from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MoodRequest(BaseModel):
    # 先去除首尾空白，再判断长度；全空格输入也必须被后端拒绝。
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    text: str = Field(min_length=1, max_length=500)


class MoodAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    mood: str = Field(min_length=2, max_length=8)
    emoji: str = Field(min_length=1, max_length=16)
    intensity: int = Field(ge=1, le=5)
    response: str = Field(min_length=1, max_length=80)
    action: str = Field(min_length=1, max_length=120)
    safety: Literal["normal", "support_needed"]
