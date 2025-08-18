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
    
    # === 장비/기술 정보 ===
    equipment_list = models.JSONField(default=list, blank=True, verbose_name="보유 장비 리스트")
    
    # === 서비스 정보 ===
    available_categories = models.JSONField(default=list, blank=True, verbose_name="가능한 카테고리")
    description = models.TextField(blank=True, verbose_name="인쇄소 설명")
    
    # === 공통 정보 ===
    production_time = models.CharField(max_length=100, blank=True, verbose_name="평균 제작 소요 시간")
    delivery_options = models.TextField(blank=True, verbose_name="배송 옵션들")
    bulk_discount = models.TextField(blank=True, verbose_name="대량 구매 할인율")
    
    # === 명함 구조화 정보 (각 섹션별 텍스트 필드) ===
    business_card_papers = models.TextField(blank=True, verbose_name="명함 용지 종류 & 설명")
    business_card_quantities = models.TextField(blank=True, verbose_name="명함 수량 정보")
    business_card_printing = models.TextField(blank=True, verbose_name="명함 인쇄 방식")
    business_card_finishing = models.TextField(blank=True, verbose_name="명함 후가공 종류 & 설명")
    
    # === 배너 구조화 정보 ===
    banner_sizes = models.TextField(blank=True, verbose_name="배너 사이즈 종류 & 설명")
    banner_stands = models.TextField(blank=True, verbose_name="배너 거치대 종류")
    banner_quantities = models.TextField(blank=True, verbose_name="배너 수량 정보")
    
    # === 포스터 구조화 정보 ===
    poster_papers = models.TextField(blank=True, verbose_name="포스터 용지 종류 & 설명")
    poster_coating = models.TextField(blank=True, verbose_name="포스터 코팅 옵션")
    poster_quantities = models.TextField(blank=True, verbose_name="포스터 수량 정보")
    
    # === 스티커 구조화 정보 ===
    sticker_types = models.TextField(blank=True, verbose_name="스티커 종류 & 설명")
    sticker_quantities = models.TextField(blank=True, verbose_name="스티커 수량 정보")
    sticker_sizes = models.TextField(blank=True, verbose_name="스티커 사이즈 정보")
    
    # === 현수막 구조화 정보 ===
    banner_large_sizes = models.TextField(blank=True, verbose_name="현수막 사이즈 정보")
    banner_large_quantities = models.TextField(blank=True, verbose_name="현수막 수량 정보")
    banner_large_processing = models.TextField(blank=True, verbose_name="현수막 추가가공 종류 & 설명")
    
    # === 브로슈어 구조화 정보 ===
    brochure_papers = models.TextField(blank=True, verbose_name="브로슈어 용지 종류 & 설명")
    brochure_folding = models.TextField(blank=True, verbose_name="브로슈어 형태 (접지 방식)")
    brochure_sizes = models.TextField(blank=True, verbose_name="브로슈어 사이즈 정보")
    brochure_quantities = models.TextField(blank=True, verbose_name="브로슈어 수량 정보")
    
    # === 행정 자료 ===
    business_license = models.FileField(upload_to='business_licenses/', blank=True, verbose_name="사업자등록증")
    password = models.CharField(max_length=128, blank=True, verbose_name="수정 비밀번호")
    
    # === 등록 상태 관리 ===
    temp_step1_data = models.JSONField(default=dict, blank=True, verbose_name="1단계 임시 데이터")
    temp_step2_data = models.JSONField(default=dict, blank=True, verbose_name="2단계 임시 데이터")
    registration_status = models.CharField(max_length=20, default='step1', verbose_name="등록 단계",
                                         choices=[
                                             ('step1', '1단계: 기본 정보'),
                                             ('step2', '2단계: 상세 정보'),
                                             ('completed', '등록 완료')
                                         ])
    
    # === 상태 관리 ===
    is_verified = models.BooleanField(default=False, verbose_name="인증 완료")
    is_active = models.BooleanField(default=False, verbose_name="활성화")
    
    # === 시간 정보 ===
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="등록일")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="수정일")
    
    class Meta:
        verbose_name = "인쇄소"
        verbose_name_plural = "인쇄소들"
    
    def __str__(self):
        return self.name or f"임시 인쇄소 ({self.id})"
