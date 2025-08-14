from django.shortcuts import render

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from .services.ai import ask_gpt
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])  # 배포 시에는 토큰 등으로 제한 권장
def chat(request):
    """
    POST /api/chat
    body: {"message": "사용자 메시지"}
    """
    msg = (request.data or {}).get("message")
    if not msg:
        return Response({"detail": "message 필드가 필요합니다."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        reply = ask_gpt(msg)
        return Response({"ok": True, "reply": reply}, status=200)
    except Exception as e:
        return Response({"ok": False, "error": str(e)}, status=500)


