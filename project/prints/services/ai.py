# project/prints/services/ai.py
import os
from openai import OpenAI

_client = None

def get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY 미설정")
        _client = OpenAI(api_key=api_key)
    return _client


def ask_gpt(message: str) -> str:
    """
    단일 메시지 → 단일 응답.
    이후 멀티턴 전환 시 messages 배열만 넘기면 됨.
    """
    client = get_client()
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a concise assistant for print estimates."}, # 테스트용
            {"role": "user", "content": message},
        ],
        temperature=0.3,
        max_tokens=200,
        timeout=20,  # 네트워크 지연 대비(초)
    )
    return (resp.choices[0].message.content or "").strip()
