# prints/views.py
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View
import json
import logging
import time
from .services.orchestrator import handle_message

logger = logging.getLogger(__name__)

@csrf_exempt
@require_http_methods(["POST"])
def chat(request):
    """
    챗봇 API 엔드포인트
    """
    start_time = time.time()
    
    try:
        # 요청 데이터 파싱
        data = json.loads(request.body)
        message = data.get("message", "")
        session_id = data.get("session_id", "default")
        
        if not message:
            return JsonResponse({
                "ok": False,
                "error": "메시지가 필요합니다."
            }, status=400)
        
        # 세션에서 히스토리와 슬롯 가져오기
        history = request.session.get(f"chat_history_{session_id}", [])
        slots = request.session.get(f"chat_slots_{session_id}", {})
        
        # 메시지 처리
        response = handle_message(history, slots, message)
        
        # 응답을 히스토리에 추가
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": response.get("question", "")})
        
        # 슬롯 업데이트
        if "slots" in response:
            slots = response["slots"]
        
        # 세션에 저장
        request.session[f"chat_history_{session_id}"] = history
        request.session[f"chat_slots_{session_id}"] = slots
        request.session.modified = True
        
        # 성공 응답
        response["ok"] = True
        return JsonResponse(response)
        
    except json.JSONDecodeError:
        return JsonResponse({
            "ok": False,
            "error": "잘못된 JSON 형식입니다."
        }, status=400)
        
    except Exception as e:
        logger.error(f"Chat API error: {str(e)}")
        return JsonResponse({
            "ok": False,
            "error": "서버 오류가 발생했습니다."
        }, status=500)
    
    finally:
        # 타임아웃 체크
        elapsed = time.time() - start_time
        if elapsed > 25:
            logger.warning(f"Chat API timeout: {elapsed:.2f}s")

@csrf_exempt
@require_http_methods(["POST"])
def reset_chat(request):
    """
    채팅 세션 초기화
    """
    try:
        data = json.loads(request.body)
        session_id = data.get("session_id", "default")
        
        # 세션 데이터 삭제
        request.session.pop(f"chat_history_{session_id}", None)
        request.session.pop(f"chat_slots_{session_id}", None)
        request.session.modified = True
        
        return JsonResponse({
            "ok": True,
            "message": "채팅이 초기화되었습니다."
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            "ok": False,
            "error": "잘못된 JSON 형식입니다."
        }, status=400)
        
    except Exception as e:
        logger.error(f"Reset chat error: {str(e)}")
        return JsonResponse({
            "ok": False,
            "error": "서버 오류가 발생했습니다."
        }, status=500)
