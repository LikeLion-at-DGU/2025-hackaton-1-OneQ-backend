# prints/views.py
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404
from .models import PrintShop, ChatSession
from .serializers import (
    PrintShopListSerializer, PrintShopDetailSerializer, PrintShopCreateSerializer,
    PrintShopUpdateSerializer, PrintShopPasswordVerifySerializer, ChatSessionSerializer,
    PrintShopStep1Serializer, PrintShopStep2Serializer, PrintShopFinalizeSerializer
)
from .services.ai import PrintShopAIService
from datetime import datetime
import uuid
from rest_framework.views import APIView
from .services.oneqscore import score_and_rank

# ===== 단계별 인쇄소 등록 Views =====

@api_view(['POST'])
def printshop_create_step1(request):
    """1단계: 기본 정보 입력"""
    serializer = PrintShopStep1Serializer(data=request.data)
    if serializer.is_valid():
        printshop = serializer.save()
        return Response({
            'id': printshop.id,
            'message': '1단계가 완료되었습니다. 2단계로 진행해주세요.',
            'next_step': 'step2'
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['PUT', 'PATCH'])
def printshop_update_step2(request, pk):
    """2단계: 상세 정보 입력"""
    printshop = get_object_or_404(PrintShop, pk=pk)
    
    # 1단계가 완료되지 않았으면 오류
    if printshop.registration_status != 'step1':
        return Response({
            'error': '1단계를 먼저 완료해주세요.'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    serializer = PrintShopStep2Serializer(printshop, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response({
            'id': printshop.id,
            'message': '2단계가 완료되었습니다. 3단계로 진행해주세요.',
            'next_step': 'step3'
        })
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['PUT', 'PATCH'])
@parser_classes([MultiPartParser, FormParser])
def printshop_finalize(request, pk):
    """3단계: 최종 등록 (비밀번호 + 사업자등록증)"""
    printshop = get_object_or_404(PrintShop, pk=pk)
    
    # 2단계가 완료되지 않았으면 오류
    if printshop.registration_status != 'step2':
        return Response({
            'error': '2단계를 먼저 완료해주세요.'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    serializer = PrintShopFinalizeSerializer(printshop, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response({
            'id': printshop.id,
            'message': '인쇄소 등록이 완료되었습니다!',
            'status': 'completed'
        })
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
def printshop_registration_status(request, pk):
    """등록 진행 상황 확인"""
    printshop = get_object_or_404(PrintShop, pk=pk)
    return Response({
        'id': printshop.id,
        'status': printshop.registration_status,
        'step1_data': printshop.temp_step1_data,
        'step2_data': printshop.temp_step2_data
    })

# ===== 기존 인쇄소 관련 Views =====

@api_view(['GET'])
def printshop_list(request):
    """인쇄소 목록 조회 (등록 완료된 것만) + 검색 기능"""
    search_query = request.GET.get('q', '')  # 검색어 (선택사항)
    
    try:
        # 기본 필터링
        printshops = PrintShop.objects.filter(
            is_active=True, 
            registration_status='completed'
        )
        
        # 검색어가 있으면 이름으로 필터링
        if search_query:
            printshops = printshops.filter(name__icontains=search_query)
        
        serializer = PrintShopListSerializer(printshops, many=True)
        return Response({
            'search_query': search_query,
            'count': len(serializer.data),
            'printshops': serializer.data
        })
    except Exception as e:
        return Response({
            'error': f'목록 조회 중 오류가 발생했습니다: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def printshop_create(request):
    """인쇄소 등록 (한 번에 모든 정보)"""
    serializer = PrintShopCreateSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
def printshop_detail(request, pk):
    """인쇄소 상세 조회"""
    printshop = get_object_or_404(PrintShop, pk=pk)
    serializer = PrintShopDetailSerializer(printshop)
    return Response(serializer.data)

@api_view(['PUT', 'PATCH'])
def printshop_update(request, pk):
    """인쇄소 정보 수정"""
    printshop = get_object_or_404(PrintShop, pk=pk)
    serializer = PrintShopUpdateSerializer(printshop, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def printshop_verify_password(request, pk):
    """인쇄소 비밀번호 확인"""
    printshop = get_object_or_404(PrintShop, pk=pk)
    serializer = PrintShopPasswordVerifySerializer(data=request.data)
    if serializer.is_valid():
        password = serializer.validated_data['password']
        if check_password(password, printshop.password):
            return Response({'message': '비밀번호가 확인되었습니다.'})
        else:
            return Response({'error': '비밀번호가 올바르지 않습니다.'}, status=status.HTTP_400_BAD_REQUEST)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
def printshop_search(request):
    """인쇄소 이름으로 검색"""
    search_query = request.GET.get('q', '')  # 검색어 (기본값: 빈 문자열)
    
    if not search_query:
        return Response({
            'error': '검색어를 입력해주세요. (예: ?q=동국)'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # 인쇄소 이름으로 검색 (대소문자 구분 없이)
        printshops = PrintShop.objects.filter(
            is_active=True,
            registration_status='completed',
            name__icontains=search_query  # 이름에 검색어가 포함된 것들
        )
        
        serializer = PrintShopListSerializer(printshops, many=True)
        return Response({
            'search_query': search_query,
            'count': len(serializer.data),
            'printshops': serializer.data
        })
    except Exception as e:
        return Response({
            'error': f'검색 중 오류가 발생했습니다: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ===== 채팅 세션 관련 Views =====

@api_view(['POST'])
def chatsession_create(request):
    """채팅 세션 생성"""
    session_id = str(uuid.uuid4())
    category = request.data.get('category', '명함')  # 기본값: 명함
    
    # 카테고리별 AI 서비스 초기화
    ai_service = PrintShopAIService(category)
    
    # 초기 메시지 생성
    initial_message = ai_service.get_category_introduction()
    
    chat_session = ChatSession.objects.create(
        session_id=session_id,
        slots={'category': category}  # 카테고리 정보 저장
    )
    
    # 초기 메시지를 히스토리에 추가
    chat_session.history.append({
        'role': 'assistant',
        'content': initial_message,
        'timestamp': datetime.now().isoformat()
    })
    
    chat_session.save()
    serializer = ChatSessionSerializer(chat_session)
    return Response(serializer.data, status=status.HTTP_201_CREATED)

@api_view(['POST'])
def chatsession_send_message(request, session_id):
    """채팅 메시지 전송"""
    chat_session = get_object_or_404(ChatSession, session_id=session_id)
    
    # 사용자 메시지
    user_message = request.data.get('message', '')
    
    # 사용자 메시지를 히스토리에 추가
    chat_session.history.append({
        'role': 'user',
        'content': user_message,
        'timestamp': datetime.now().isoformat()
    })
    
    # AI 서비스 초기화 (기존 대화 히스토리 전달)
    category = chat_session.slots.get('category', '명함')
    ai_service = PrintShopAIService(category)
    
    # 기존 대화 히스토리를 AI 서비스에 로드
    for msg in chat_session.history:
        ai_service.conversation_manager.add_message(msg['role'], msg['content'])
    
    # 기존 슬롯 정보를 AI 서비스에 로드
    ai_service.conversation_manager.current_slots = chat_session.slots.copy()
    
    # AI 응답 생성
    print(f"사용자 메시지: {user_message}")
    print(f"현재 슬롯: {chat_session.slots}")
    
    ai_response = ai_service.process_user_message(user_message, chat_session.slots)
    print(f"AI 응답: {ai_response}")
    
    # 슬롯 정보 업데이트
    chat_session.slots = ai_response.get('slots', chat_session.slots)
    
    # AI 응답을 히스토리에 추가
    chat_session.history.append({
        'role': 'assistant',
        'content': ai_response['message'],
        'timestamp': datetime.now().isoformat()
    })
    
    chat_session.save()
    serializer = ChatSessionSerializer(chat_session)
    return Response(serializer.data)

@api_view(['GET'])
def chatsession_history(request, session_id):
    """채팅 히스토리 조회"""
    chat_session = get_object_or_404(ChatSession, session_id=session_id)
    serializer = ChatSessionSerializer(chat_session)
    return Response(serializer.data)


# === 사업자등록증 인증관련 뷰 ===
@api_view(['POST'])
@permission_classes([IsAdminUser])
def printshop_verify(request, pk):
    """인쇄소 인증 (관리자용)"""
    printshop = get_object_or_404(PrintShop, pk=pk)
    
    # Django의 관리자 권한 확인 (IsAdminUser가 자동으로 처리)
    # request.user.is_staff가 True인 사용자만 접근 가능
    
    # 인증 상태 변경
    action = request.data.get('action', 'verify')  # 'verify' 또는 'unverify'
    
    if action == 'verify':
        printshop.is_verified = True
        message = '인증이 완료되었습니다.'
    elif action == 'unverify':
        printshop.is_verified = False
        message = '인증이 취소되었습니다.'
    else:
        return Response({
            'error': '잘못된 액션입니다. (verify 또는 unverify)'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    printshop.save()
    
    return Response({
        'id': printshop.id,
        'name': printshop.name,
        'is_verified': printshop.is_verified,
        'message': message,
        'verified_by': request.user.username
    })

@api_view(['GET'])
def printshop_verification_status(request, pk):
    """인쇄소 인증 상태 확인"""
    printshop = get_object_or_404(PrintShop, pk=pk)
    return Response({
        'id': printshop.id,
        'name': printshop.name,
        'is_verified': printshop.is_verified,
        'registration_status': printshop.registration_status,
        'has_business_license': bool(printshop.business_license)
    })


class PrintShopRankAPIView(APIView):
    """
    POST /api/printshops/rank
    body 예시:
    {
        "category": "명함",
        "quantity": 300,
        "size": "90x50mm",
        "printing": "양면 컬러",
        "finishing": "무광",
        "due_days": 3,
        "region": "서울-중구",
        "budget": 150000
    }
    """
    def post(self, request):
        try:
            # 카테고리 필터와 동일 기준의 후보 셋
            all_printshops = PrintShop.objects.filter(
                is_active=True,
                registration_status='completed'
            )
            candidates = [s for s in all_printshops if (request.data.get("category") or "명함") in (s.available_categories or [])]
            result = score_and_rank(request.data, candidates)
            return Response(result, status=200)
        except Exception as e:
            return Response({"detail": str(e)}, status=400)
