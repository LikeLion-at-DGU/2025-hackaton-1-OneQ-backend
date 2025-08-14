from django.http import JsonResponse
from django.conf import settings
from openai import OpenAI

def gpt_test(request):
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    # 간단 연결 테스트용
    prompt = "원큐 연결 테스트: 전단지 인쇄 옵션을 한 문장으로 요약해줘."

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",  # 비용/속도 괜찮은 테스트 모델
            messages=[
                {"role": "system", "content": "You are a concise assistant."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=120,
            temperature=0.3,
        )
        answer = (resp.choices[0].message.content or "").strip()
        return JsonResponse({"ok": True, "answer": answer})
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)
