from rest_framework import serializers
from django.contrib.auth.hashers import make_password, check_password
from .models import PrintShop, ChatSession

class PrintShopListSerializer(serializers.ModelSerializer):
    """인쇄소 목록용 Serializer (비밀번호 제외)"""
    class Meta:
        model = PrintShop
        fields = ['id', 'name', 'phone', 'email', 'business_hours', 'address', 
                 'available_categories', 'is_verified', 'is_active', 'created_at']

class PrintShopDetailSerializer(serializers.ModelSerializer):
    """인쇄소 상세 정보 Serializer"""
    class Meta:
        model = PrintShop
        fields = ['id', 'name', 'phone', 'email', 'business_hours', 'address',
                 'available_categories', 'description',
                 'production_time', 'delivery_options', 'bulk_discount',
                 # 명함 정보
                 'business_card_paper_options', 'business_card_printing_options', 
                 'business_card_finishing_options', 'business_card_quantity_price_info',
                 # 배너 정보
                 'banner_size_options', 'banner_stand_options', 'banner_quantity_price_info',
                 # 포스터 정보
                 'poster_paper_options', 'poster_coating_options', 'poster_quantity_price_info',
                 # 스티커 정보
                 'sticker_type_options', 'sticker_size_options', 'sticker_quantity_price_info',
                 # 현수막 정보
                 'banner_large_size_options', 'banner_large_processing_options', 'banner_large_quantity_price_info',
                 # 브로슈어 정보
                 'brochure_paper_options', 'brochure_size_options', 'brochure_folding_options', 'brochure_quantity_price_info',
                 'is_verified', 'is_active', 'created_at', 'updated_at']

# ===== 단계별 Serializer =====

class PrintShopStep1Serializer(serializers.ModelSerializer):
    """1단계: 기본 정보 입력 Serializer"""
    class Meta:
        model = PrintShop
        fields = ['name', 'phone', 'email', 'business_hours', 'address']
    
    def create(self, validated_data):
        # 1단계 데이터를 임시 저장
        validated_data['temp_step1_data'] = validated_data.copy()
        validated_data['registration_status'] = 'step1'
        return super().create(validated_data)

class PrintShopStep2Serializer(serializers.ModelSerializer):
    """2단계: 상세 정보 입력 Serializer (구조화된 필드들)"""
    
    class Meta:
        model = PrintShop
        fields = [
            # 기본 서비스 정보
            'available_categories', 'description',
            # 공통 정보
            'production_time', 'delivery_options', 'bulk_discount',
            # 명함 정보
            'business_card_paper_options', 'business_card_printing_options', 
            'business_card_finishing_options', 'business_card_quantity_price_info',
            # 배너 정보
            'banner_size_options', 'banner_stand_options', 'banner_quantity_price_info',
            # 포스터 정보
            'poster_paper_options', 'poster_coating_options', 'poster_quantity_price_info',
            # 스티커 정보
            'sticker_type_options', 'sticker_size_options', 'sticker_quantity_price_info',
            # 현수막 정보
            'banner_large_size_options', 'banner_large_processing_options', 'banner_large_quantity_price_info',
            # 브로슈어 정보
            'brochure_paper_options', 'brochure_size_options', 'brochure_folding_options', 'brochure_quantity_price_info'
        ]
    
    def update(self, instance, validated_data):
        # 1단계 데이터와 2단계 데이터를 합쳐서 임시 저장
        step2_data = {}
        step2_data.update(instance.temp_step1_data)  # 1단계 데이터 추가
        step2_data.update(validated_data)  # 2단계 데이터 추가
        
        instance.temp_step2_data = step2_data
        instance.registration_status = 'step2'
        
        # 실제 필드에도 저장 (1단계 + 2단계 데이터 모두)
        for field, value in step2_data.items():
            setattr(instance, field, value)
        
        instance.save()
        return instance

class PrintShopFinalizeSerializer(serializers.ModelSerializer):
    """3단계: 최종 등록 Serializer"""
    password = serializers.CharField(write_only=True, min_length=4, max_length=20)
    password_confirm = serializers.CharField(write_only=True, min_length=4, max_length=20)
    business_license = serializers.FileField(required=True, allow_null=False, allow_empty_file=False)
    
    class Meta:
        model = PrintShop
        fields = ['password', 'password_confirm', 'business_license']
    
    def validate_password(self, value):
        """비밀번호 유효성 검사: 4-20자, 특수문자 1개 이상 필수"""
        if len(value) < 4 or len(value) > 20:
            raise serializers.ValidationError("비밀번호는 4자 이상 20자 이하여야 합니다.")
        
        # 특수문자 포함 여부 확인
        import re
        special_chars = re.findall(r'[!@#$%^&*(),.?":{}|<>]', value)
        if not special_chars:
            raise serializers.ValidationError("비밀번호에 특수문자를 1개 이상 포함해야 합니다.")
        
        return value
    
    def validate(self, data):
        """비밀번호와 비밀번호 확인이 일치하는지 검사"""
        password = data.get('password')
        password_confirm = data.get('password_confirm')
        
        if password and password_confirm and password != password_confirm:
            raise serializers.ValidationError({
                'password_confirm': '비밀번호가 일치하지 않습니다.'
            })
        
        return data
    
    def update(self, instance, validated_data):
        # 비밀번호 확인 필드 제거
        validated_data.pop('password_confirm', None)
        
        # 비밀번호 해싱
        validated_data['password'] = make_password(validated_data['password'])
        
        # 최종 데이터 저장
        instance.password = validated_data['password']
        instance.business_license = validated_data['business_license']  # 필수이므로 항상 저장
        instance.registration_status = 'completed'
        instance.is_active = True
        
        # 임시 데이터 초기화
        instance.temp_step1_data = {}
        instance.temp_step2_data = {}
        
        instance.save()
        return instance

# ===== 기존 Serializer들 (하위 호환성) =====

# 관리자용으로 한 번에 등록할 수 있게 하는 시리얼라이저 (비밀번호 제외)
# 관리자 페이지 / 테스트용 샘플 데이터 입력용
class PrintShopCreateSerializer(serializers.ModelSerializer):
    """인쇄소 등록용 Serializer (한 번에 모든 정보)"""
    password = serializers.CharField(write_only=True, min_length=4, max_length=20)
    password_confirm = serializers.CharField(write_only=True, min_length=4, max_length=20)
    business_license = serializers.FileField(required=True, allow_null=False, allow_empty_file=False)
    
    class Meta:
        model = PrintShop
        fields = [
            # 기본 정보
            'name', 'phone', 'email', 'business_hours', 'address',
            # 서비스 정보
            'available_categories', 'description',
            # 공통 정보
            'production_time', 'delivery_options', 'bulk_discount',
            # 명함 정보
            'business_card_paper_options', 'business_card_printing_options', 
            'business_card_finishing_options', 'business_card_quantity_price_info',
            # 배너 정보
            'banner_size_options', 'banner_stand_options', 'banner_quantity_price_info',
            # 포스터 정보
            'poster_paper_options', 'poster_coating_options', 'poster_quantity_price_info',
            # 스티커 정보
            'sticker_type_options', 'sticker_size_options', 'sticker_quantity_price_info',
            # 현수막 정보
            'banner_large_size_options', 'banner_large_processing_options', 'banner_large_quantity_price_info',
            # 브로슈어 정보
            'brochure_paper_options', 'brochure_size_options', 'brochure_folding_options', 'brochure_quantity_price_info',
            # 행정 자료
            'business_license', 'password', 'password_confirm'
        ]
    
    def validate_password(self, value):
        """비밀번호 유효성 검사: 4-20자, 특수문자 1개 이상 필수"""
        if len(value) < 4 or len(value) > 20:
            raise serializers.ValidationError("비밀번호는 4자 이상 20자 이하여야 합니다.")
        
        # 특수문자 포함 여부 확인
        import re
        special_chars = re.findall(r'[!@#$%^&*(),.?":{}|<>]', value)
        if not special_chars:
            raise serializers.ValidationError("비밀번호에 특수문자를 1개 이상 포함해야 합니다.")
        
        return value
    
    def validate(self, data):
        """비밀번호와 비밀번호 확인이 일치하는지 검사"""
        password = data.get('password')
        password_confirm = data.get('password_confirm')
        
        if password and password_confirm and password != password_confirm:
            raise serializers.ValidationError({
                'password_confirm': '비밀번호가 일치하지 않습니다.'
            })
        
        return data
    
    def create(self, validated_data):
        # 비밀번호 확인 필드 제거
        validated_data.pop('password_confirm', None)
        
        # 비밀번호 해싱
        validated_data['password'] = make_password(validated_data['password'])
        validated_data['registration_status'] = 'completed'
        validated_data['is_active'] = True
        return super().create(validated_data)

class PrintShopUpdateSerializer(serializers.ModelSerializer):
    """인쇄소 수정용 Serializer"""
    new_password = serializers.CharField(write_only=True, required=False)
    current_password = serializers.CharField(write_only=True, required=True)
    
    class Meta:
        model = PrintShop
        fields = [
            # 기본 정보
            'name', 'phone', 'email', 'business_hours', 'address',
            # 서비스 정보
            'available_categories', 'description',
            # 공통 정보
            'production_time', 'delivery_options', 'bulk_discount',
            # 명함 정보
            'business_card_paper_options', 'business_card_printing_options', 
            'business_card_finishing_options', 'business_card_quantity_price_info',
            # 배너 정보
            'banner_size_options', 'banner_stand_options', 'banner_quantity_price_info',
            # 포스터 정보
            'poster_paper_options', 'poster_coating_options', 'poster_quantity_price_info',
            # 스티커 정보
            'sticker_type_options', 'sticker_size_options', 'sticker_quantity_price_info',
            # 현수막 정보
            'banner_large_size_options', 'banner_large_processing_options', 'banner_large_quantity_price_info',
            # 브로슈어 정보
            'brochure_paper_options', 'brochure_size_options', 'brochure_folding_options', 'brochure_quantity_price_info',
            # 비밀번호
            'new_password', 'current_password'
        ]
    
    def validate_current_password(self, value):
        print_shop = self.instance
        if not check_password(value, print_shop.password):
            raise serializers.ValidationError("현재 비밀번호가 올바르지 않습니다.")
        return value
    
    def validate_new_password(self, value):
        """새 비밀번호 유효성 검사: 4-20자, 특수문자 1개 이상 필수"""
        if len(value) < 4 or len(value) > 20:
            raise serializers.ValidationError("비밀번호는 4자 이상 20자 이하여야 합니다.")
        
        # 특수문자 포함 여부 확인
        import re
        special_chars = re.findall(r'[!@#$%^&*(),.?":{}|<>]', value)
        if not special_chars:
            raise serializers.ValidationError("비밀번호에 특수문자를 1개 이상 포함해야 합니다.")
        
        return value
    
    def update(self, instance, validated_data):
        # 비밀번호가 제공된 경우에만 해싱
        if 'new_password' in validated_data:
            validated_data['password'] = make_password(validated_data['new_password'])
        
        # current_password와 new_password는 제거
        validated_data.pop('current_password', None)
        validated_data.pop('new_password', None)
        
        return super().update(instance, validated_data)

class PrintShopPasswordVerifySerializer(serializers.Serializer):
    """인쇄소 비밀번호 확인용 Serializer"""
    password = serializers.CharField(write_only=True)

class ChatSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatSession
        fields = ['session_id', 'history', 'slots', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['session_id', 'created_at', 'updated_at']
