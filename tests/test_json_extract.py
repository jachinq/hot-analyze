"""JSON 抽取测试。"""

from app.ai.openai_compat import extract_json


def test_extract_plain_json():
    data = extract_json('{"category": "科技", "importance": 8}')
    assert data["category"] == "科技"


def test_extract_fenced_json():
    text = """```json
{"summary": "测试", "tags": ["a"]}
```"""
    data = extract_json(text)
    assert data["summary"] == "测试"
