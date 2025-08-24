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
from .services.oneq_score import calculate_printshop_scores
from datetime import datetime
import uuid
from rest_framework.views import APIView
import re

# ===== 유틸리티 함수 =====

def extract_quote_info(message: str) -> dict:
    """AI 응답에서 견적서 정보를 추출"""
    quote_info = {
        'quote_number': f"ONEQ-{datetime.now().strftime('%Y-%m%d-%H%M')}",
        'creation_date': datetime.now().strftime('%Y년 %m월 %d일'),
        'category': '',
        'specifications': {},
        'quantity': '',
        'due_days': '',
        'region': '',
        'budget': ''
    }
    
    try:
        # 카테고리 추출
        if '📋 요청 정보:' in message:
            # 요청 정보 섹션 찾기
            start_idx = message.find('📋 요청 정보:')
            end_idx = message.find('견적서가 완성되었습니다!')
            
            if start_idx != -1 and end_idx != -1:
                info_section = message[start_idx:end_idx]
                
                # 각 줄을 파싱
                lines = info_section.split('\n')
                for line in lines:
                    line = line.strip()
                    if line.startswith('-'):
                        # 정보 추출
                        if '카테고리:' in line:
                            quote_info['category'] = line.split('카테고리:')[1].strip()
                        elif '용지:' in line:
                            quote_info['specifications']['paper'] = line.split('용지:')[1].strip()
                        elif '사이즈:' in line:
                            quote_info['specifications']['size'] = line.split('사이즈:')[1].strip()
                        elif '코팅:' in line:
                            quote_info['specifications']['coating'] = line.split('코팅:')[1].strip()
                        elif '접지:' in line:
                            quote_info['specifications']['folding'] = line.split('접지:')[1].strip()
                        elif '인쇄:' in line:
                            quote_info['specifications']['printing'] = line.split('인쇄:')[1].strip()
                        elif '후가공:' in line:
                            quote_info['specifications']['finishing'] = line.split('후가공:')[1].strip()
                        elif '수량:' in line:
                            quote_info['quantity'] = line.split('수량:')[1].strip()
                        elif '납기일:' in line:
                            quote_info['due_days'] = line.split('납기일:')[1].strip()
                        elif '지역:' in line:
                            quote_info['region'] = line.split('지역:')[1].strip()
                        elif '예산:' in line:
                            quote_info['budget'] = line.split('예산:')[1].strip()
        
        # 견적번호 추출 (=== 최종 견적서 === 섹션에서)
        if '=== 최종 견적서 ===' in message:
            quote_section_start = message.find('=== 최종 견적서 ===')
            if quote_section_start != -1:
                # 견적번호 패턴 찾기 (ONEQ-YYYY-MMDD-HHMM 형식)
                import re
                quote_number_match = re.search(r'ONEQ-\d{4}-\d{4}-\d{4}', message)
                if quote_number_match:
                    quote_info['quote_number'] = quote_number_match.group()
                
                # 생성일 추출
                date_match = re.search(r'\d{4}년\s*\d{1,2}월\s*\d{1,2}일', message)
                if date_match:
                    quote_info['creation_date'] = date_match.group()
                    
    except Exception as e:
        print(f"Error extracting quote info: {e}")
    return quote_info

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
    
    # 지역 정보 추출 (기존 슬롯에서)
    region = chat_session.slots.get('region', '')
    
    # AI 응답 생성 (대화 히스토리와 카테고리별 전문 프롬프트 사용)
    ai_response = ai_client.chat_with_history(conversation_history, category=category, region=region)
    print(f"AI 응답: {ai_response}")
    
    # AI 응답에서 메시지 추출
    if ai_response.get('success'):
        clean_msg = ai_response.get('message', '')
    else:
        clean_msg = ai_response.get('message', '죄송합니다. 일시적인 오류가 발생했습니다.')
    
    # 정보 추출 시도 (사용자 메시지에서 슬롯 정보 추출)
    try:
        extracted_info = ai_client.extract_info(user_message, category, region)
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
    
    # 최종 견적서가 생성되었는지 확인하고 인쇄소 추천 추가
    is_final_quote = False
    quote_info = None
    recommended_shops = None
    
    if "=== 최종 견적서 ===" in clean_msg and "요청하신 정보에 맞는 인쇄소를 추천해드리겠습니다" in clean_msg:
        is_final_quote = True
        
        # 견적 정보 추출
        quote_info = extract_quote_info(clean_msg)
        
        # 추천 인쇄소 가져오기
        recommended_printshops = get_recommended_printshops(chat_session.slots)
        
        if recommended_printshops:
            # 추천 인쇄소 정보를 AI 응답에 추가
            shop_info = "\n\n🏆 추천 인쇄소 Top3:\n"
            for i, shop in enumerate(recommended_printshops[:3], 1):
                shop_info += f"{i}. {shop['name']}\n"
                shop_info += f"   📊 원큐스코어: {shop['recommendation_score']}점\n"
                shop_info += f"   💡 추천이유: {shop['recommendation_reason']}\n"
                shop_info += f"   📞 연락처: {shop['phone']}\n"
                shop_info += f"   📍 주소: {shop['address']}\n"
                shop_info += f"   📧 이메일: {shop['email']}\n"
                shop_info += f"   💰 예상가격: {shop['estimated_total_price']}\n"
                shop_info += f"   ⏰ 제작기간: {shop['estimated_production_time']}\n"
                shop_info += f"   🚚 배송방법: {shop['delivery_methods']}\n\n"
            
            shop_info += "이 견적서와 디자인 파일을 가지고 추천 인쇄소에 방문하시면 됩니다.\n\n좋은 하루 되세요! 원하시는 결과물이 나오길 바랍니다! 😊"            
            # AI 응답 업데이트
            chat_session.history[-1]['content'] = clean_msg + shop_info
            
            # 추천 인쇄소 데이터 구조화
            recommended_shops = []
            for shop in recommended_printshops[:3]:
                # 세부 점수 정보 추출
                score_details = shop.get('score_details', {})
                
                recommended_shops.append({
                    'name': shop['name'],
                    'oneq_score': shop['recommendation_score'],
                    'price_score': score_details.get('price_score', 0),
                    'deadline_score': score_details.get('deadline_score', 0),
                    'workfit_score': score_details.get('workfit_score', 0),
                    'recommendation_reason': shop['recommendation_reason'],
                    'phone': shop['phone'],
                    'address': shop['address'],
                    'email': shop['email'],
                    'estimated_price': shop['estimated_total_price'],
                    'production_period': shop['estimated_production_time'],
                    'delivery_method': shop['delivery_methods']
                })
        else:
            # 추천 인쇄소가 없는 경우
            no_shop_msg = "\n\n😔 죄송합니다. 현재 요청하신 조건에 맞는 인쇄소가 없습니다.\n다른 조건으로 다시 시도해보시거나, 나중에 다시 문의해주세요."
            chat_session.history[-1]['content'] = clean_msg + no_shop_msg
    
    chat_session.save()
    serializer = ChatSessionSerializer(chat_session)
    
    # 응답 데이터 구성
    response_data = serializer.data
    
    # 최종 견적인 경우 추가 데이터 포함
    if is_final_quote:
        # 견적 정보에서 필요한 모든 필드 추출
        final_quote_data = {
            'quote_number': quote_info.get('quote_number', f"ONEQ-{datetime.now().strftime('%Y-%m%d-%H%M')}"),
            'creation_date': quote_info.get('creation_date', datetime.now().strftime('%Y년 %m월 %d일')),
            'category': quote_info.get('category', chat_session.slots.get('category', '')),
            'quantity': quote_info.get('quantity', chat_session.slots.get('quantity', '')),
            'size': quote_info.get('specifications', {}).get('size', chat_session.slots.get('size', '')),
            'paper': quote_info.get('specifications', {}).get('paper', chat_session.slots.get('paper', '')),
            'coating': quote_info.get('specifications', {}).get('coating', chat_session.slots.get('coating', '')),
            'due_days': quote_info.get('due_days', chat_session.slots.get('due_days', '')),
            'budget': quote_info.get('budget', chat_session.slots.get('budget', '')),
            'region': quote_info.get('region', chat_session.slots.get('region', '')),
            'available_printshops': len(recommended_shops) if recommended_shops else 0,
            'price_range': get_price_range(recommended_shops) if recommended_shops else '정보 없음'
        }
        
        response_data.update({
            'is_final_quote': True,
            'quote_info': quote_info,
            'recommended_shops': recommended_shops,
            'final_quote_data': final_quote_data
        })
    else:
        response_data.update({
            'is_final_quote': False
        })
    
    return Response(response_data)

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
            
            # 원큐스코어 계산
            scored_printshops = calculate_printshop_scores(candidates, request.data)
            
            result = {
                'category': category,
                'candidates': len(candidates),
                'recommendations': scored_printshops[:3]  # 상위 3개만 반환
            }
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
    
    # 견적 데이터 구조화
    category = chat_session.slots.get('category')
    
    # DB에서 인쇄소 추천
    recommended_printshops = get_recommended_printshops(chat_session.slots)
    
    final_quote = {
        'quote_number': f"ONEQ-{datetime.now().strftime('%Y-%m%d-%H%M')}",
        'created_date': datetime.now().strftime('%Y년 %m월 %d일'),
        'category': category,
        'slots': chat_session.slots,
        'recommendations': recommended_printshops,
        'total_available': len(recommended_printshops),
        'message': f'{category} 제작 견적이 준비되었습니다.'
    }
    
    return Response({
        'action': 'quote',
        'final_quote': final_quote,
        'message': '모든 정보가 수집되었습니다. 최종 견적을 확인해 주세요.'
    })

def get_recommended_printshops(slots):
    """사용자 요구사항에 맞는 인쇄소 추천"""
    category = slots.get('category')
    region = slots.get('region', '')
    budget = slots.get('budget', '')
    
    # 기본 필터링: 활성화된 인쇄소만
    printshops = PrintShop.objects.filter(
        is_active=True,
        registration_status='completed'
    )
    
    # 카테고리 필터링
    if category:
        category_mapping = {
            '명함': 'card',
            '배너': 'banner', 
            '포스터': 'poster',
            '스티커': 'sticker',
            '현수막': 'banner2',
            '브로슈어': 'brochure'
        }
        eng_category = category_mapping.get(category, category)
        
        # Python 레벨에서 카테고리 필터링 (더 안전함)
        filtered_printshops = []
        for shop in printshops:
            available_cats = shop.available_categories or []
            if eng_category in available_cats or category in available_cats:
                filtered_printshops.append(shop)
        printshops = filtered_printshops
    
    # 지역 필터링 (복합 지역 표현 지원)
    if region:
        from .services.ai_client import AIClient
        ai_client = AIClient()
        target_regions = ai_client._parse_region_expression(region)
        
        filtered_printshops = []
        for shop in printshops:
            if ai_client._match_regions_in_address(target_regions, shop.address):
                filtered_printshops.append(shop)
        printshops = filtered_printshops
    
    # 예산 필터링 (간단한 텍스트 매칭)
    if budget:
        # 예산 범위 파싱 (예: "25~35만원" -> 250000~350000)
        budget_range = parse_budget_range(budget)
        if budget_range:
            min_budget, max_budget = budget_range
            # 예산 정보가 있는 인쇄소만 필터링 (실제 구현에서는 더 정교한 로직 필요)
            pass
    
    # 상위 10개 후보 선정 (원큐스코어 계산을 위해)
    # 이미 Python 리스트이므로 슬라이싱 사용
    candidates = printshops[:10]
    
    # 원큐스코어 계산
    try:
        scored_printshops = calculate_printshop_scores(candidates, slots)
        # 상위 3개 반환
        return scored_printshops[:3]
    except Exception as e:
        print(f"원큐스코어 계산 오류: {e}")
        # 오류 발생 시 빈 리스트 반환
        return []

def parse_budget_range(budget_str):
    """예산 문자열을 범위로 파싱"""
    try:
        # "25~35만원" -> (250000, 350000)
        if '~' in budget_str:
            parts = budget_str.split('~')
            min_val = int(parts[0].replace('만원', '').strip()) * 10000
            max_val = int(parts[1].replace('만원', '').strip()) * 10000
            return (min_val, max_val)
        # "30만원 이하" -> (0, 300000)
        elif '이하' in budget_str:
            val = int(budget_str.replace('만원 이하', '').strip()) * 10000
            return (0, val)
        # "50만원 이상" -> (500000, float('inf'))
        elif '이상' in budget_str:
            val = int(budget_str.replace('만원 이상', '').strip()) * 10000
            return (val, float('inf'))
        # 단일 값 "30만원" -> (250000, 350000) (근사치)
        else:
            val = int(budget_str.replace('만원', '').strip()) * 10000
            return (val * 0.8, val * 1.2)
    except:
        return None

def get_price_range(recommended_shops):
    """추천 인쇄소들의 가격대를 계산"""
    if not recommended_shops:
        return '정보 없음'
    
    try:
        # 예상 가격에서 숫자만 추출
        prices = []
        for shop in recommended_shops:
            estimated_price = shop.get('estimated_price', '')
            if estimated_price:
                # "30만원" -> 300000
                price_str = str(estimated_price).replace('만원', '').replace(',', '').strip()
                if price_str.isdigit():
                    prices.append(int(price_str) * 10000)
        
        if prices:
            min_price = min(prices)
            max_price = max(prices)
            
            if min_price == max_price:
                return f"{min_price//10000}만원"
            else:
                return f"{min_price//10000}~{max_price//10000}만원"
        else:
            return '정보 없음'
    except Exception as e:
        print(f"가격대 계산 오류: {e}")
        return '정보 없음'
