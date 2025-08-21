# prints/models.py
from django.db import models
from django.contrib.auth.models import User
import uuid

# verbose_name은 admin에서 볼 때 보여지는 이름
class ChatSession(models.Model):
    """채팅 세션"""
    session_id = models.CharField(max_length=100, primary_key=True, verbose_name="세션 ID")
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, verbose_name="사용자")
    
    # 채팅 데이터
    history = models.JSONField(default=list, verbose_name="대화 기록")
    slots = models.JSONField(default=dict, verbose_name="슬롯 데이터")
    
    # 상태
    is_active = models.BooleanField(default=True, verbose_name="활성화")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="시작일")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="마지막 활동")
    
    class Meta:
        db_table = 'chat_sessions'
        verbose_name = '채팅 세션'
        verbose_name_plural = '채팅 세션'
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"세션 {self.session_id} - {self.updated_at.strftime('%Y-%m-%d %H:%M')}"

class PrintShop(models.Model):
    """인쇄소 정보 모델""" 
    id = models.AutoField(primary_key=True, verbose_name="인쇄소 ID")
    
    # === 기본 정보 ===
    name = models.CharField(max_length=100, blank=True, verbose_name="인쇄소 이름")
    phone = models.CharField(max_length=20, blank=True, verbose_name="전화번호")
    email = models.EmailField(blank=True, verbose_name="이메일")
    business_hours = models.CharField(max_length=100, blank=True, verbose_name="영업시간")
    address = models.TextField(blank=True, verbose_name="주소")
    

    
    # === 서비스 정보 ===
    available_categories = models.JSONField(default=list, blank=True, verbose_name="가능한 카테고리")
    description = models.TextField(blank=True, verbose_name="인쇄소 설명")
    
    # === 공통 정보 ===
    production_time = models.CharField(max_length=100, blank=True, verbose_name="평균 제작 소요 시간")
    delivery_options = models.TextField(blank=True, verbose_name="배송 옵션들")
    bulk_discount = models.TextField(blank=True, verbose_name="대량 구매 할인율")
    
    # === 명함 구조화 정보 (폼 구조에 맞게 수정) ===
    business_card_paper_options = models.TextField(blank=True, verbose_name="명함 용지 종류 (옵션명+가격+설명)")
    business_card_printing_options = models.TextField(blank=True, verbose_name="명함 인쇄 방식 (옵션명+가격+설명)")
    business_card_finishing_options = models.TextField(blank=True, verbose_name="명함 후가공 옵션 (옵션명+가격+설명)")
    business_card_quantity_price_info = models.TextField(blank=True, verbose_name="명함 수량 및 가격정보 (수량별 가격+최소주문수량)")
    
    # === 배너 구조화 정보 (폼 구조에 맞게 수정) ===
    banner_size_options = models.TextField(blank=True, verbose_name="배너 사이즈 종류 (사이즈명+가격+크기)")
    banner_stand_options = models.TextField(blank=True, verbose_name="배너 거치대 종류 (거치대명+가격+설명)")
    banner_quantity_price_info = models.TextField(blank=True, verbose_name="배너 수량 및 가격정보 (수량별 가격+최소주문수량)")
    
    # === 포스터 구조화 정보 (폼 구조에 맞게 수정) ===
    poster_paper_options = models.TextField(blank=True, verbose_name="포스터 용지 종류 (옵션명+가격+설명)")
    poster_coating_options = models.TextField(blank=True, verbose_name="포스터 코팅 종류 (옵션명+가격+설명)")
    poster_quantity_price_info = models.TextField(blank=True, verbose_name="포스터 수량 및 가격정보 (수량별 가격+최소주문수량)")
    
    # === 스티커 구조화 정보 (폼 구조에 맞게 수정) ===
    sticker_type_options = models.TextField(blank=True, verbose_name="스티커 종류 (옵션명+가격+설명)")
    sticker_size_options = models.TextField(blank=True, verbose_name="스티커 사이즈 종류 (사이즈명+가격+크기)")
    sticker_quantity_price_info = models.TextField(blank=True, verbose_name="스티커 수량 및 가격정보 (수량별 가격+최소주문수량)")
    
    # === 현수막 구조화 정보 (폼 구조에 맞게 수정) ===
    banner_large_size_options = models.TextField(blank=True, verbose_name="현수막 사이즈 종류 (사이즈명+가격+크기)")
    banner_large_processing_options = models.TextField(blank=True, verbose_name="현수막 추가가공 종류 (옵션명+가격+설명)")
    banner_large_quantity_price_info = models.TextField(blank=True, verbose_name="현수막 수량 및 가격정보 (수량별 가격+최소주문수량)")
    
    # === 브로슈어 구조화 정보 (폼 구조에 맞게 수정) ===
    brochure_paper_options = models.TextField(blank=True, verbose_name="브로슈어 용지 종류 (옵션명+가격+설명)")
    brochure_size_options = models.TextField(blank=True, verbose_name="브로슈어 사이즈 종류 (사이즈명+가격+크기)")
    brochure_folding_options = models.TextField(blank=True, verbose_name="브로슈어 접지 종류 (옵션명+가격+설명)")
    brochure_quantity_price_info = models.TextField(blank=True, verbose_name="브로슈어 수량 및 가격정보 (수량별 가격+최소주문수량)")
    
    # === 행정 자료 ===
    business_license = models.FileField(upload_to='business_licenses/', blank=True, verbose_name="사업자등록증")
    password = models.CharField(max_length=128, blank=True, verbose_name="수정 비밀번호")
    
    # === 등록 상태 관리 ===
    temp_step1_data = models.JSONField(default=dict, blank=True, verbose_name="1단계 임시 데이터") # 1단계에서 입력한 기본 정보 임시 저장
    temp_step2_data = models.JSONField(default=dict, blank=True, verbose_name="2단계 임시 데이터") # 1단계 + 2단계 데이터를 합쳐서 임시 저장장
    registration_status = models.CharField(max_length=20, default='step1', verbose_name="등록 단계",
                                         choices=[
                                             ('step1', '1단계: 기본 정보'), # 1단계 완료
                                             ('step2', '2단계: 상세 정보'), # 2단계 완료
                                             ('completed', '등록 완료') # 3단계 완료
                                         ]) # 현재 등록 진행 상황 추적적
    
    # === 상태 관리 ===
    is_verified = models.BooleanField(default=False, verbose_name="인증 완료") # 사업자등록증 인증 완료 여부
    is_active = models.BooleanField(default=False, verbose_name="활성화") # 인쇄소 활성화 여부 True시 정상 운영 중인 인쇄소소
    
    # === 시간 정보 ===
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="등록일")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="수정일")
    
    class Meta:
        verbose_name = "인쇄소" # admin에서 볼 때 보여지는 이름
        verbose_name_plural = "인쇄소들" # admin에서 볼 때 보여지는 이름 복수형
    
    def __str__(self):
        return self.name or f"임시 인쇄소 ({self.id})" # 인쇄소 이름이 없으면 임시 인쇄소 (id) 로 표시
