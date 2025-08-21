from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.http import HttpResponseRedirect
from .models import PrintShop, ChatSession

@admin.register(PrintShop)
class PrintShopAdmin(admin.ModelAdmin):
    """인쇄소 관리"""
    list_display = ['name', 'phone', 'email', 'registration_status', 'verification_status', 'is_active', 'created_at']
    list_filter = ['registration_status', 'is_verified', 'is_active', 'created_at']
    search_fields = ['name', 'phone', 'email', 'address']
    readonly_fields = ['id', 'created_at', 'updated_at', 'business_license_preview']
    actions = ['verify_printshops', 'unverify_printshops']
    
    fieldsets = (
        ('기본 정보', {
            'fields': ('name', 'phone', 'email', 'business_hours', 'address')
        }),
        ('서비스 정보', {
            'fields': ('available_categories', 'description')
        }),
        ('공통 정보', {
            'fields': ('production_time', 'delivery_options', 'bulk_discount')
        }),
        ('명함 정보', {
            'fields': ('business_card_paper_options', 'business_card_printing_options', 'business_card_finishing_options', 'business_card_min_quantity'),
            'classes': ('collapse',)
        }),
        ('배너 정보', {
            'fields': ('banner_size_options', 'banner_stand_options', 'banner_min_quantity'),
            'classes': ('collapse',)
        }),
        ('포스터 정보', {
            'fields': ('poster_paper_options', 'poster_coating_options', 'poster_min_quantity'),
            'classes': ('collapse',)
        }),
        ('스티커 정보', {
            'fields': ('sticker_type_options', 'sticker_size_options', 'sticker_min_quantity'),
            'classes': ('collapse',)
        }),
        ('현수막 정보', {
            'fields': ('banner_large_size_options', 'banner_large_processing_options', 'banner_large_min_quantity'),
            'classes': ('collapse',)
        }),
        ('브로슈어 정보', {
            'fields': ('brochure_paper_options', 'brochure_size_options', 'brochure_folding_options', 'brochure_min_quantity'),
            'classes': ('collapse',)
        }),
        ('등록 진행 상황', {
            'fields': ('registration_status', 'temp_step1_data', 'temp_step2_data'),
            'classes': ('collapse',)
        }),
        ('인증 및 보안', {
            'fields': ('password', 'business_license', 'business_license_preview', 'is_verified', 'is_active')
        }),
        ('시스템 정보', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def verification_status(self, obj):
        """인증 상태를 색상으로 표시"""
        if obj.is_verified:
            return format_html('<span style="color: green;">✓ 인증완료</span>')
        else:
            return format_html('<span style="color: red;">✗ 미인증</span>')
    verification_status.short_description = '인증 상태'
    
    def business_license_preview(self, obj):
        """사업자등록증 미리보기"""
        if obj.business_license:
            return format_html(
                '<a href="{}" target="_blank">사업자등록증 보기</a>',
                obj.business_license.url
            )
        return "업로드된 파일 없음"
    business_license_preview.short_description = '사업자등록증'
    
    def verify_printshops(self, request, queryset):
        """선택된 인쇄소들을 인증 완료로 변경"""
        updated = queryset.update(is_verified=True)
        self.message_user(request, f'{updated}개의 인쇄소가 인증 완료되었습니다.')
    verify_printshops.short_description = "선택된 인쇄소 인증 완료"
    
    def unverify_printshops(self, request, queryset):
        """선택된 인쇄소들을 미인증으로 변경"""
        updated = queryset.update(is_verified=False)
        self.message_user(request, f'{updated}개의 인쇄소가 미인증으로 변경되었습니다.')
    unverify_printshops.short_description = "선택된 인쇄소 미인증 처리"

@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    """채팅 세션 관리"""
    list_display = ['session_id', 'is_active', 'created_at', 'updated_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['session_id']
    readonly_fields = ['session_id', 'created_at', 'updated_at']
