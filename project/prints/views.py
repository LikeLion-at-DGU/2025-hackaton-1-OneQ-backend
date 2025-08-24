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
from .services.ai_client import AIClient
from datetime import datetime
import uuid
from rest_framework.views import APIView
import re

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
    
    # 1단계 또는 2단계 상태에서 허용 (2단계 재업데이트 허용)
    if printshop.registration_status not in ['step1', 'step2']:
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
            'message': '인쇄소 등록이 완료되었습니다! 사업자등록증 심의 후 등록이 최종 완료 됩니다. (최대 3일 소요)',
            'status': 'pending'
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
        printshop = serializer.save()
        return Response({
            'id': printshop.id,
            'message': '인쇄소 등록이 완료되었습니다! 사업자등록증 심의 후 등록이 최종 완료 됩니다. (최대 3일 소요)',
            'status': 'pending'
        }, status=status.HTTP_201_CREATED)
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
    category = request.data.get('category')  # 카테고리는 필수값
    
    # 카테고리가 없으면 오류
    if not category:
        return Response({
            'error': '카테고리를 선택해주세요.'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    print(f"=== 채팅 세션 생성 디버깅 ===")
    print(f"요청된 카테고리: {category}")
    print(f"요청 데이터: {request.data}")
    
    # AI 클라이언트 초기화
    ai_client = AIClient()
    
    # 카테고리별 인사말 생성
    category_intros = {
        '명함': "안녕하세요! 명함 제작 전문 챗봇입니다. 🏢\n\n명함 제작에 필요한 정보를 수집해드릴게요.\n\n먼저 어떤 용지 종류를 원하시나요? (일반지, 고급지, 아트지, 코팅지 중 선택해주세요)",
        '배너': "안녕하세요! 배너 제작 전문 챗봇입니다. 🎯\n\n배너 제작에 필요한 정보를 수집해드릴게요.\n\n먼저 어떤 배너 사이즈를 원하시나요? (1x3m, 2x4m, 3x6m 등)",
        '포스터': "안녕하세요! 포스터 제작 전문 챗봇입니다. 🎨\n\n포스터 제작에 필요한 정보를 수집해드릴게요.\n\n먼저 어떤 용지 종류를 원하시나요? (일반지, 아트지, 코팅지, 합지 중 선택해주세요)",
        '스티커': "안녕하세요! 스티커 제작 전문 챗봇입니다. 🏷️\n\n스티커 제작에 필요한 정보를 수집해드릴게요.\n\n먼저 어떤 스티커 종류를 원하시나요? (일반스티커, 방수스티커, 반사스티커, 전사스티커 중 선택해주세요)",
        '현수막': "안녕하세요! 현수막 제작 전문 챗봇입니다. 🏁\n\n현수막 제작에 필요한 정보를 수집해드릴게요.\n\n먼저 어떤 현수막 사이즈를 원하시나요? (1x3m, 2x4m, 3x6m 등)",
        '브로슈어': "안녕하세요! 브로슈어 제작 전문 챗봇입니다. 📄\n\n브로슈어 제작에 필요한 정보를 수집해드릴게요.\n\n먼저 어떤 용지 종류를 원하시나요? (일반지, 아트지, 코팅지, 합지 중 선택해주세요)"
    }
    
    initial_message = category_intros.get(category, "안녕하세요! 인쇄 제작 전문 챗봇입니다.")
    
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
    print(f"생성된 세션 카테고리: {chat_session.slots.get('category')}")
    return Response(serializer.data, status=status.HTTP_201_CREATED)

def _sanitize_plain(text: str) -> str:
    text = text.replace("**", "").replace("__", "").replace("`", "")
    text = re.sub(r"(?m)^\s*[#>\|]+\s*", "", text)
    return text

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
    category = chat_session.slots.get('category')
    
    # 카테고리가 없으면 오류
    if not category:
        return Response({
            'error': '세션에 카테고리 정보가 없습니다.'
        }, status=status.HTTP_400_BAD_REQUEST)
    print(f"=== 채팅 메시지 처리 디버깅 ===")
    print(f"세션 카테고리: {category}")
    print(f"세션 슬롯: {chat_session.slots}")
    print(f"사용자 메시지: {user_message}")
    
    ai_client = AIClient()
    
    # 대화 히스토리를 AI에게 전달하기 위한 메시지 구성
    conversation_history = []
    for msg in chat_session.history:
        conversation_history.append({
            "role": msg['role'],
            "content": msg['content']
        })
    
    # 현재 사용자 메시지 추가
    conversation_history.append({
        "role": "user",
        "content": user_message
    })
    
    # AI 응답 생성 (대화 히스토리와 카테고리별 전문 프롬프트 사용)
    ai_response = ai_client.chat_with_history(conversation_history, category=category)
    print(f"AI 응답: {ai_response}")
    
    # AI 응답에서 메시지 추출
    if ai_response.get('success'):
        clean_msg = ai_response.get('message', '')
    else:
        clean_msg = ai_response.get('message', '죄송합니다. 일시적인 오류가 발생했습니다.')
    
    # 정보 추출 시도 (사용자 메시지에서 슬롯 정보 추출)
    try:
        extracted_info = ai_client.extract_info(user_message, category)
        print(f"추출된 정보: {extracted_info}")
        
        if extracted_info and 'filled_slots' in extracted_info and extracted_info['filled_slots']:
            # 기존 슬롯에 새로운 정보 업데이트 (빈 값은 덮어쓰지 않음)
            current_slots = chat_session.slots.copy()
            for key, value in extracted_info['filled_slots'].items():
                # 값이 비어있지 않을 때만 업데이트
                if value and value.strip():
                    current_slots[key] = value
            chat_session.slots = current_slots
            print(f"업데이트된 슬롯: {chat_session.slots}")
    except Exception as e:
        print(f"정보 추출 오류: {e}")
    
    # AI 응답을 히스토리에 추가
    chat_session.history.append({
        'role': 'assistant',
        'content': clean_msg,
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

            category = request.data.get("category") or "명함"
            category_mapping = {
                '명함': 'card', '배너': 'banner', '포스터': 'poster',
                '스티커': 'sticker', '현수막': 'banner2', '브로슈어': 'brochure'
            }
            eng = category_mapping.get(category, category)

            def _has_cat(shop):
                cats = (shop.available_categories or [])
                return (eng in cats) or (category in cats)

            candidates = [s for s in all_printshops if (request.data.get("category") or "명함") in (s.available_categories or [])]
            result = score_and_rank(request.data, candidates)
            return Response(result, status=200)
        except Exception as e:
            return Response({"detail": str(e)}, status=400)

@api_view(['POST'])
def chat_quote(request):
    """최종 견적 생성/조회"""
    session_id = request.data.get('session_id')
    if not session_id:
        return Response({'detail': 'session_id is required'}, status=400)

    chat_session = get_object_or_404(ChatSession, session_id=session_id)
    
    # 필수 슬롯 검증 추가 (임시)
    missing_slots = []
    if missing_slots:
        missing_names = {
            'quantity': '수량',
            'paper': '용지',
            'size': '사이즈',
            'printing': '인쇄 방식',
            'finishing': '후가공',
            'coating': '코팅',
            'type': '종류',
            'stand': '거치대',
            'processing': '가공',
            'folding': '접지',
            'due_days': '납기',
            'region': '지역',
            'budget': '예산'
        }
        missing_list = [missing_names.get(slot, slot) for slot in missing_slots]
        return Response({
            'action': 'error',
            'message': f'견적 생성에 필요한 정보가 부족합니다: {", ".join(missing_list)}',
            'missing_slots': missing_slots
        }, status=400)
    
    # 간단한 견적 생성 (임시)
    category = chat_session.slots.get('category')
    
    # 견적 데이터 구조화 (임시)
    final_quote = {
        'quote_number': f"ONEQ-{datetime.now().strftime('%Y-%m%d-%H%M')}",
        'created_date': datetime.now().strftime('%Y년 %m월 %d일'),
        'category': category,
        'slots': chat_session.slots,
        'recommendations': [],
        'total_available': 0,
        'message': f'{category} 제작 견적이 준비되었습니다.'
    }
    
    return Response({
        'action': 'quote',
        'final_quote': final_quote,
        'message': '모든 정보가 수집되었습니다. 최종 견적을 확인해 주세요.'
    })
