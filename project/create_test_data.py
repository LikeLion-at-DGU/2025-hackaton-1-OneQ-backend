#!/usr/bin/env python3
"""
테스트용 인쇄소 데이터 생성 스크립트
"""

import os
import sys
import django

# Django 설정
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')
django.setup()

from prints.models import PrintShop
from django.contrib.auth.hashers import make_password

def create_test_printshops():
    """테스트용 인쇄소 데이터 생성"""
    print("테스트용 인쇄소 데이터 생성 중...")
    
    # 기존 테스트 데이터 삭제
    PrintShop.objects.filter(name__startswith='테스트').delete()
    
    # 테스트 인쇄소 1
    printshop1 = PrintShop.objects.create(
        name='테스트인쇄소1',
        phone='02-1234-5678',
        email='test1@example.com',
        password=make_password('test1234'),
        address='서울시 강남구 테스트로 123',
        business_license_number='123-45-67890',
        is_active=True,
        is_verified=True,
        registration_status='completed',
        available_categories=['명함', '배너', '포스터'],
        business_card_papers='반누보, 휘라레, 아트지, 스노우지',
        business_card_quantities='100부, 200부, 300부, 500부',
        business_card_printing='단면, 양면',
        business_card_finishing='형압, 박, 오시, 절취선',
        production_time='3-5일',
        delivery_options='택배, 방문수령'
    )
    
    # 테스트 인쇄소 2
    printshop2 = PrintShop.objects.create(
        name='테스트인쇄소2',
        phone='02-2345-6789',
        email='test2@example.com',
        password=make_password('test1234'),
        address='서울시 서초구 테스트로 456',
        business_license_number='234-56-78901',
        is_active=True,
        is_verified=False,
        registration_status='completed',
        available_categories=['명함', '스티커'],
        business_card_papers='반누보, 휘라레, 아트지',
        business_card_quantities='100부, 200부, 500부',
        business_card_printing='단면, 양면',
        business_card_finishing='형압, 박',
        production_time='5-7일',
        delivery_options='택배'
    )
    
    # 테스트 인쇄소 3
    printshop3 = PrintShop.objects.create(
        name='테스트인쇄소3',
        phone='02-3456-7890',
        email='test3@example.com',
        password=make_password('test1234'),
        address='서울시 마포구 테스트로 789',
        business_license_number='345-67-89012',
        is_active=True,
        is_verified=True,
        registration_status='completed',
        available_categories=['명함', '포스터', '브로슈어'],
        business_card_papers='반누보, 휘라레, 스타드림퀼츠, 아트지',
        business_card_quantities='100부, 200부, 300부, 500부, 1000부',
        business_card_printing='단면, 양면',
        business_card_finishing='형압, 박, 오시, 절취선, 도무송',
        production_time='2-3일',
        delivery_options='당일배송, 익일배송, 택배'
    )
    
    print(f"테스트 인쇄소 {PrintShop.objects.filter(name__startswith='테스트').count()}개 생성 완료!")
    print("생성된 인쇄소:")
    for ps in PrintShop.objects.filter(name__startswith='테스트'):
        print(f"- {ps.name} (인증: {ps.is_verified}, 카테고리: {ps.available_categories})")

if __name__ == "__main__":
    create_test_printshops()
