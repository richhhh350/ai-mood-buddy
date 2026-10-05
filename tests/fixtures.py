from app.schemas import MoodAnalysis


def sample_analysis():
    return MoodAnalysis(mood="疲惫", emoji="🌧️", intensity=3,
                        response="连续忙碌确实让人疲惫。", action="喝杯水，休息五分钟。",
                        safety="normal")
