# prints/services/oneq_score.py
import re
import json
import openai
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
from ..models import PrintShop
import os
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.getenv('OPENAI_API_KEY')


class OneQScoreCalculator:
    """원큐스코어 계산기"""
    
    def __init__(self):
        self.t0 = datetime.now()  # 현재 시간 (기준점)
        self._price_cache = {}  # 가격 파싱 캐시
    
    def calculate_oneq_score(self, printshop: PrintShop, user_requirements: Dict) -> Dict:
        """
        원큐스코어 계산
        OneQ_i = 0.40 * Price_i + 0.30 * Deadline_i + 0.30 * WorkFit_i
        """
        try:
            # 1. 가격 적합도 계산 (40%)
            price_score = self._calculate_price_score(printshop, user_requirements)
            
            # 2. 납기 충족도 계산 (30%)
            deadline_score = self._calculate_deadline_score(printshop, user_requirements)
            
            # 3. 작업 적합도 계산 (30%)
            workfit_score = self._calculate_workfit_score(printshop, user_requirements)
            
            # 최종 원큐스코어 계산
            oneq_score = 0.40 * price_score + 0.30 * deadline_score + 0.30 * workfit_score
            
            # 추천 이유 생성
            recommendation_reason = self._generate_recommendation_reason(
                price_score, deadline_score, workfit_score, user_requirements
            )
            
            return {
                'oneq_score': int(round(oneq_score)),
                'price_score': int(round(price_score)),
                'deadline_score': int(round(deadline_score)),
                'workfit_score': int(round(workfit_score)),
                'recommendation_reason': recommendation_reason,
                'details': {
                    'price_details': self._get_price_details(printshop, user_requirements),
                    'deadline_details': self._get_deadline_details(printshop, user_requirements),
                    'workfit_details': self._get_workfit_details(printshop, user_requirements)
                }
            }
            
        except Exception as e:
            print(f"원큐스코어 계산 오류: {e}")
            return {
                'oneq_score': 0,
                'price_score': 0,
                'deadline_score': 0,
                'workfit_score': 0,
                'recommendation_reason': '점수 계산 중 오류가 발생했습니다.',
                'details': {}
            }
    
    def _calculate_price_score(self, printshop: PrintShop, user_requirements: Dict) -> float:
        """가격 적합도 계산 (Price_i, 40%)"""
        category = user_requirements.get('category', '')
        budget = user_requirements.get('budget', '')
        quantity = user_requirements.get('quantity', 0)
        
        # quantity를 정수로 변환
        try:
            if isinstance(quantity, str):
                quantity = int(quantity.replace('부', '').replace('개', '').strip())
            else:
                quantity = int(quantity)
        except (ValueError, TypeError):
            quantity = 100  # 기본값
        
        # 카테고리별 가격 정보 파싱
        price_info = self._parse_price_info(printshop, category, quantity)
        if not price_info:
            return 70  # 기본값을 50에서 70으로 상향 조정
        
        # 후보 인쇄소들의 가격 목록 (임시로 현재 인쇄소만 사용)
        prices = [price_info['unit_price']]
        p_min = min(prices)
        p_med = sum(prices) / len(prices)
        p_i = price_info['unit_price']
        
        # 1. 최저가 비율 (50%) - 더 후하게 계산
        min_ratio = 100 * max(0.7, min(1, p_min / p_i)) if p_i > 0 else 70  # 최소 70점 보장
        
        # 2. 예산 적합 (25%) - 더 관대하게 계산
        budget_fit = 70  # 기본값을 50에서 70으로 상향 조정
        if budget and self._parse_budget(budget):
            user_budget = self._parse_budget(budget)
            if user_budget:
                gamma = 0.5  # 0.35에서 0.5로 더 관대하게
                budget_fit = 100 * (1 - abs(p_i - user_budget) / (gamma * user_budget))
                budget_fit = max(60, min(100, budget_fit))  # 최소 60점 보장
        
        # 3. 시장 합리성 (25%) - 더 관대하게 계산
        market_fit = 70  # 기본값을 50에서 70으로 상향 조정
        if len(prices) > 1:
            alpha = 0.5  # 0.30에서 0.5로 더 관대하게
            market_fit = 100 * (1 - abs(p_i - p_med) / (alpha * p_med))
            market_fit = max(60, min(100, market_fit))  # 최소 60점 보장
        else:
            # 후보가 1곳이면 MarketFit 제외하고 더 높은 점수
            return 0.7 * budget_fit + 0.3 * min_ratio  # 가중치 조정
        
        # 최종 가격 점수
        price_score = 0.50 * min_ratio + 0.25 * budget_fit + 0.25 * market_fit
        return int(round(price_score))
    
    def _calculate_deadline_score(self, printshop: PrintShop, user_requirements: Dict) -> float:
        """납기 충족도 계산 (Deadline_i, 30%)"""
        due_days = user_requirements.get('due_days', 0)
        
        # due_days를 정수로 변환
        try:
            if isinstance(due_days, str):
                # "3일", "3일이내", "3일 내" 등 파싱
                due_days = int(re.findall(r'(\d+)', due_days)[0])
            else:
                due_days = int(due_days)
        except (ValueError, TypeError, IndexError):
            due_days = 7  # 기본값
        
        if not due_days:
            return 70  # 기본값을 50에서 70으로 상향 조정
        
        # 리드타임 계산
        production_time = self._parse_production_time(printshop.production_time)
        finishing_time = self._get_finishing_time(printshop, user_requirements)
        quantity_time = self._get_quantity_time(user_requirements)
        
        # 혼잡계수 (임시) - 더 관대하게
        c = 0.9  # 1.0에서 0.9로 더 관대하게
        if not printshop.is_verified:
            c = 1.0  # 1.2에서 1.0으로
        if not printshop.is_active:
            c = 1.2  # 1.5에서 1.2로
        
        # 총 리드타임
        L_i = production_time + (finishing_time + quantity_time) * c
        
        # 여유 시간
        m_i = due_days - L_i
        
        # 1. 기한충족 Feasibility (60%) - 더 관대하게
        if m_i >= 0:
            F = 100
        else:
            M_lo = 3  # 2일에서 3일로 더 관대하게
            F = max(50, 100 * (1 + m_i / M_lo))  # 최소 50점 보장
        
        # 2. 여유 버퍼 Buffer (25%) - 더 관대하게
        if m_i >= 2:  # 3일에서 2일로 더 관대하게
            Buffer = 100
        elif m_i >= 0:
            Buffer = 100 * (m_i / 2)  # 3에서 2로
        else:
            Buffer = 50  # 0에서 50으로 최소 점수 보장
        
        # 3. 신뢰/안정 Consistency (15%) - 더 관대하게
        BaseReliab = 0.9  # 0.85에서 0.9로 상향
        r_i = max(0.7, min(0.98, BaseReliab - 0.1 * (c - 1)))  # 0.6에서 0.7로, 0.15에서 0.1로
        R = 60 + 40 * r_i  # 50+50에서 60+40으로 상향
        
        # 최종 납기 점수
        deadline_score = 0.60 * F + 0.25 * Buffer + 0.15 * R
        return int(round(deadline_score))
    
    def _calculate_workfit_score(self, printshop: PrintShop, user_requirements: Dict) -> float:
        """작업 적합도 계산 (WorkFit_i, 30%)"""
        category = user_requirements.get('category', '')
        
        # 1. 필수 스펙 일치 (60%)
        req_fit = self._calculate_requirement_fit(printshop, user_requirements)
        
        # 2. 선택 스펙/사용자 가중 (25%)
        opt_fit = self._calculate_option_fit(printshop, user_requirements)
        
        # 3. 파일 체크 Preflight (15%) - 더 높은 기본값
        preflight = 90  # 기본값을 85에서 90으로 상향 조정
        
        # 최종 작업 적합도 점수
        workfit_score = 0.60 * req_fit + 0.25 * opt_fit + 0.15 * preflight
        return int(round(workfit_score))
    
    def _parse_price_info(self, printshop: PrintShop, category: str, quantity) -> Optional[Dict]:
        """카테고리별 가격 정보 파싱 (AI + 정규표현식 혼합)"""
        try:
            # quantity를 정수로 변환
            if isinstance(quantity, str):
                quantity = int(quantity)
            elif not isinstance(quantity, int):
                quantity = int(quantity)
            
            print(f"🔍 가격 파싱 시작: {category}, 수량: {quantity}")
            
            # 카테고리별 가격 정보 필드 매핑
            price_fields = {
                '명함': 'business_card_quantity_price_info',
                '배너': 'banner_quantity_price_info',
                '포스터': 'poster_quantity_price_info',
                '스티커': 'sticker_quantity_price_info',
                '현수막': 'banner_large_quantity_price_info',
                '브로슈어': 'brochure_quantity_price_info'
            }
            
            field_name = price_fields.get(category)
            print(f"📋 필드명: {field_name}")
            
            if not field_name:
                print(f"❌ 카테고리 '{category}'에 대한 필드명 없음")
                return None
            
            # 캐시 키 생성 (field_name 정의 후)
            cache_key = f"{printshop.id}_{category}_{quantity}_{getattr(printshop, field_name, '')[:50]}"
            if cache_key in self._price_cache:
                print(f"📦 캐시된 결과 사용: {self._price_cache[cache_key]}")
                return self._price_cache[cache_key]
            
            price_text = getattr(printshop, field_name, '')
            print(f"📝 가격 텍스트: {price_text}")
            
            if not price_text:
                print(f"❌ 가격 텍스트가 비어있음")
                return None
            
            # 1. 먼저 정규표현식으로 시도
            prices = re.findall(r'(\d+)(?:부|매)\s*[:\-]\s*(\d+)원', price_text)
            print(f"🔍 정규표현식 결과: {prices}")
            
            if not prices:
                print(f"⚠️ 정규표현식 실패, AI 파싱 시도")
                # 2. 정규표현식 실패 시 AI 파싱 시도
                try:
                    ai_prices = self._ai_parse_prices(price_text, category, quantity)
                    if ai_prices:
                        print(f"✅ AI 파싱 성공: {ai_prices}")
                        return ai_prices
                except Exception as ai_error:
                    print(f"❌ AI 파싱 실패: {ai_error}")
                
                                # 3. AI도 실패하면 기본 가격 추정
                default_price = {
                    'unit_price': 50000,  # 기본 단가
                    'total_price': 50000 * quantity
                }
                print(f"📊 기본 가격 사용: {default_price}")
                return default_price
            
            # 수량에 맞는 가격 찾기
            for qty, price in prices:
                qty_int = int(qty)
                price_int = int(price)
                if qty_int >= quantity:
                    unit_price = price_int // qty_int
                    result = {
                        'unit_price': unit_price,
                        'total_price': unit_price * quantity
                    }
                    print(f"✅ 정규표현식 파싱 성공: {result}")
                    return result
            
            # 마지막 가격 사용
            last_qty, last_price = prices[-1]
            last_qty_int = int(last_qty)
            last_price_int = int(last_price)
            unit_price = last_price_int // last_qty_int
            result = {
                'unit_price': unit_price,
                'total_price': unit_price * quantity
            }
            print(f"✅ 마지막 가격 사용: {result}")
            
            # 캐시에 저장
            self._price_cache[cache_key] = result
            return result
            
        except Exception as e:
            print(f"❌ 가격 정보 파싱 오류: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _ai_parse_prices(self, price_text: str, category: str, quantity) -> Optional[Dict]:
        """AI를 사용한 가격 정보 파싱"""
        try:
            # quantity를 정수로 변환
            if isinstance(quantity, str):
                quantity = int(quantity)
            elif not isinstance(quantity, int):
                quantity = int(quantity)
            
            print(f"🔍 AI 파싱 시작: {category}, 수량: {quantity}")
            print(f"📝 원본 텍스트: {price_text}")
            
            prompt = f"""
다음은 {category} 인쇄 가격 정보입니다. 이 텍스트에서 수량별 가격을 추출해주세요.

텍스트: {price_text}

요청 수량: {quantity}개

다음 JSON 형식으로 응답해주세요:
{{
    "unit_price": 단가,
    "total_price": 총가격
}}

예시:
- "100매 - 12,000원, 200매 - 22,000원" → {{"unit_price": 120, "total_price": 12000}}
- "최소 30매, 30매 - 55,000원" → {{"unit_price": 1833, "total_price": 55000}}

주의사항:
1. 요청 수량에 맞는 가격을 찾아주세요
2. 단가는 총가격을 수량으로 나눈 값입니다
3. 숫자만 반환해주세요 (콤마, 원 제외)
"""

            print(f"🤖 OpenAI API 호출 중...")
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "당신은 가격 정보를 정확히 파싱하는 전문가입니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=100,
                timeout=30  # 30초 타임아웃 추가
            )
            
            result_text = response.choices[0].message.content.strip()
            print(f"🤖 AI 응답: {result_text}")
            
            # JSON 파싱
            if result_text.startswith('{') and result_text.endswith('}'):
                result = json.loads(result_text)
                parsed_result = {
                    'unit_price': int(result.get('unit_price', 0)),
                    'total_price': int(result.get('total_price', 0))
                }
                print(f"✅ 파싱 성공: {parsed_result}")
                return parsed_result
            else:
                print(f"❌ JSON 형식 아님: {result_text}")
            
            return None
            
        except Exception as e:
            print(f"❌ AI 가격 파싱 오류: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _parse_budget(self, budget_str: str) -> Optional[int]:
        """예산 문자열 파싱"""
        try:
            if '~' in budget_str:
                parts = budget_str.split('~')
                return int(parts[0].replace('만원', '').strip()) * 10000
            elif '이하' in budget_str:
                return int(budget_str.replace('만원 이하', '').strip()) * 10000
            elif '이상' in budget_str:
                return int(budget_str.replace('만원 이상', '').strip()) * 10000
            else:
                return int(budget_str.replace('만원', '').strip()) * 10000
        except Exception as e:
            print(f"예산 파싱 오류: {e}")
            return None
    
    def _parse_production_time(self, production_time: str) -> float:
        """제작 시간 파싱 (일 단위)"""
        try:
            if not production_time:
                return 3.0  # 기본값
            
            # "3일", "1주일" 등 파싱
            if '일' in production_time:
                return float(re.findall(r'(\d+)', production_time)[0])
            elif '주' in production_time:
                return float(re.findall(r'(\d+)', production_time)[0]) * 7
            else:
                return 3.0
        except Exception as e:
            print(f"제작 시간 파싱 오류: {e}")
            return 3.0
    
    def _get_finishing_time(self, printshop: PrintShop, user_requirements: Dict) -> float:
        """후가공 시간 계산"""
        # 간단한 후가공 시간 추정
        finishing_options = ['finishing', 'coating', 'processing', 'folding']
        has_finishing = any(user_requirements.get(opt) for opt in finishing_options)
        return 1.0 if has_finishing else 0.0
    
    def _get_quantity_time(self, user_requirements: Dict) -> float:
        """수량별 가산 시간"""
        quantity = user_requirements.get('quantity', 0)
        
        # quantity를 정수로 변환
        try:
            if isinstance(quantity, str):
                quantity = int(quantity.replace('부', '').replace('개', '').strip())
            else:
                quantity = int(quantity)
        except (ValueError, TypeError):
            quantity = 100  # 기본값
        
        if quantity > 1000:
            return 2.0
        elif quantity > 500:
            return 1.0
        else:
            return 0.5
    
    def _calculate_requirement_fit(self, printshop: PrintShop, user_requirements: Dict) -> float:
        """필수 스펙 일치도 계산"""
        category = user_requirements.get('category', '')
        
        # 카테고리 지원 여부 확인
        if category not in (printshop.available_categories or []):
            return 60.0  # 0.0에서 60.0으로 상향 조정 (부분 점수 부여)
        
        # 기본 필수 스펙 체크
        required_specs = ['size', 'quantity']
        matches = 0
        
        for spec in required_specs:
            if user_requirements.get(spec):
                matches += 1
        
        # 모든 필수 스펙이 있으면 100점
        if matches == len(required_specs):
            return 100.0
        else:
            # 부분 점수도 더 관대하게
            partial_score = (matches / len(required_specs)) * 100.0
            return max(70.0, partial_score)  # 최소 70점 보장
    
    def _calculate_option_fit(self, printshop: PrintShop, user_requirements: Dict) -> float:
        """선택 스펙 적합도 계산 (AI 기반 매칭)"""
        option_matches = 0
        total_options = 0
        
        options = ['paper', 'printing', 'finishing', 'coating', 'folding']
        for option in options:
            if user_requirements.get(option):
                total_options += 1
                # 옵션 지원 여부 확인 (AI + 텍스트 매칭)
                option_text = getattr(printshop, f'{option}_options', '')
                if option_text:
                    user_option = user_requirements[option]
                    
                    # 1. 먼저 간단한 텍스트 매칭 시도
                    if self._simple_option_match(user_option, option_text):
                        option_matches += 1
                    else:
                        # 2. AI 매칭 시도
                        try:
                            if self._ai_option_match(user_option, option_text, option):
                                option_matches += 1
                        except Exception as ai_error:
                            print(f"AI 옵션 매칭 실패: {ai_error}")
                            # AI 매칭 실패 시에도 부분 점수 부여
                            option_matches += 0.5
        
        if total_options == 0:
            return 90  # 기본값을 85에서 90으로 상향 조정
        
        # 더 관대한 점수 계산
        base_score = (option_matches / total_options) * 100.0
        return max(75.0, base_score)  # 최소 75점 보장
    
    def _simple_option_match(self, user_option: str, option_text: str) -> bool:
        """간단한 텍스트 매칭"""
        user_option_lower = user_option.lower()
        option_text_lower = option_text.lower()
        
        # 직접 매칭
        if user_option_lower in option_text_lower:
            return True
        
        # 유사한 옵션 매칭
        if user_option_lower == '무광' and '매트' in option_text_lower:
            return True
        elif user_option_lower == '일반지' and ('코트지' in option_text_lower or '일반' in option_text_lower):
            return True
        
        return False
    
    def _ai_option_match(self, user_option: str, option_text: str, option_type: str) -> bool:
        """AI를 사용한 옵션 매칭 (설명 기반 의미 매칭)"""
        try:
            print(f"🔍 AI 옵션 매칭: {option_type}")
            print(f"👤 사용자 요청: {user_option}")
            print(f"🏪 제공 옵션: {option_text}")
            
            prompt = f"""
다음은 인쇄 옵션 정보입니다. 사용자가 요청한 옵션이 제공되는 옵션과 의미적으로 일치하는지 판단해주세요.

옵션 종류: {option_type}
사용자 요청: {user_option}
제공 옵션: {option_text}

**중요**: 옵션명뿐만 아니라 설명도 함께 고려해서 의미적으로 매칭해주세요.

다음 JSON 형식으로 응답해주세요:
{{
    "match": true/false,
    "reason": "매칭 이유"
}}

예시:
- 사용자: "무광", 제공: "매트(+3000원): 지문 억제, 반사 방지" → {{"match": true, "reason": "매트의 '지문 억제, 반사 방지' 설명이 무광의 특성과 일치"}}
- 사용자: "일반지", 제공: "프리미엄 코트지(+0원): 선명한 컬러, 기본 용지" → {{"match": true, "reason": "프리미엄 코트지의 '기본 용지' 설명이 일반지와 동일한 의미"}}
- 사용자: "고급지", 제공: "스노우 매트(+1500원): 지문 억제, 고급스러운 질감" → {{"match": true, "reason": "스노우 매트의 '고급스러운 질감' 설명이 고급지와 일치"}}

주의사항:
1. 옵션명과 설명을 모두 고려해서 의미적으로 매칭
2. 가격 정보는 무시하고 옵션의 특성과 설명만 비교
3. 유사한 기능이나 특성을 가진 옵션도 매칭으로 인정
4. true/false만 반환
"""

            print(f"🤖 OpenAI API 호출 중...")
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "당신은 인쇄 옵션 매칭 전문가입니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=100
            )
            
            result_text = response.choices[0].message.content.strip()
            print(f"🤖 AI 응답: {result_text}")
            
            # JSON 파싱
            if result_text.startswith('{') and result_text.endswith('}'):
                result = json.loads(result_text)
                match_result = result.get('match', False)
                print(f"✅ 매칭 결과: {match_result}")
                return match_result
            else:
                print(f"❌ JSON 형식 아님: {result_text}")
            
            return False
            
        except Exception as e:
            print(f"❌ AI 옵션 매칭 오류: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _generate_recommendation_reason(self, price_score: float, deadline_score: float, 
                                      workfit_score: float, user_requirements: Dict) -> str:
        """추천 이유 생성 - 상세 버전"""
        reasons = []
        detailed_reasons = []
        
        # 가격 관련
        if price_score >= 80:
            reasons.append("경쟁력 있는 가격")
            detailed_reasons.append("합리적인 가격으로 비용 효율적")
        elif price_score >= 60:
            reasons.append("합리적인 가격")
            detailed_reasons.append("적정 수준의 가격으로 경제적")
        
        # 납기 관련
        if deadline_score >= 80:
            reasons.append("빠른 납기")
            detailed_reasons.append("빠르고 안정적인 납기 보장")
        elif deadline_score >= 60:
            reasons.append("안정적인 납기")
            detailed_reasons.append("신뢰할 수 있는 납기 일정")
        
        # 작업 적합도 관련
        if workfit_score >= 80:
            reasons.append("완벽한 스펙 매칭")
            detailed_reasons.append("고품질 인쇄와 후가공 기술")
        elif workfit_score >= 60:
            reasons.append("적합한 작업 능력")
            detailed_reasons.append("해당 카테고리 제작 경험이 풍부")
        
        # 추가 상세 정보
        category = user_requirements.get('category', '')
        if category:
            detailed_reasons.append(f"{category} 전문 제작 기술력")
        
        # 위치 및 서비스 관련
        detailed_reasons.append("접근하기 좋은 위치와 배송 서비스")
        detailed_reasons.append("친절하고 신뢰할 수 있는 서비스")
        
        if not reasons:
            reasons.append("종합적인 만족도")
            detailed_reasons.append("고객 만족도가 높은 인쇄소")
        
        # 상세한 추천 이유 생성
        if detailed_reasons:
            return f"{', '.join(detailed_reasons)}로 안정적인 결과물을 보장합니다."
        else:
            return ", ".join(reasons)
    
    def _get_price_details(self, printshop: PrintShop, user_requirements: Dict) -> Dict:
        """가격 상세 정보"""
        category = user_requirements.get('category', '')
        quantity = user_requirements.get('quantity', 0)
        
        # quantity를 정수로 변환
        try:
            if isinstance(quantity, str):
                quantity = int(quantity.replace('부', '').replace('개', '').strip())
            else:
                quantity = int(quantity)
        except (ValueError, TypeError):
            quantity = 100  # 기본값
        
        price_info = self._parse_price_info(printshop, category, quantity)
        
        return {
            'unit_price': price_info.get('unit_price', 0) if price_info else 0,
            'total_price': price_info.get('total_price', 0) if price_info else 0,
            'price_text': getattr(printshop, f'{category}_quantity_price_info', '') if hasattr(printshop, f'{category}_quantity_price_info') else ''
        }
    
    def _get_deadline_details(self, printshop: PrintShop, user_requirements: Dict) -> Dict:
        """납기 상세 정보"""
        return {
            'production_time': printshop.production_time,
            'estimated_days': self._parse_production_time(printshop.production_time)
        }
    
    def _get_workfit_details(self, printshop: PrintShop, user_requirements: Dict) -> Dict:
        """작업 적합도 상세 정보"""
        return {
            'available_categories': printshop.available_categories,
            'description': printshop.description
        }
    
    # 위치 매칭은 AI가 공통 프롬프트에서 처리하므로 제거


def calculate_printshop_scores(printshops: List[PrintShop], user_requirements: Dict) -> List[Dict]:
    """여러 인쇄소의 원큐스코어 계산 (AI가 위치 우선 처리)"""
    calculator = OneQScoreCalculator()
    scored_printshops = []
    
    # AI가 위치 우선 처리를 하므로 단순히 모든 인쇄소에 대해 점수 계산
    for printshop in printshops:
        try:
            score_result = calculator.calculate_oneq_score(printshop, user_requirements)
        except Exception as e:
            print(f"인쇄소 {printshop.name} 점수 계산 오류: {e}")
            score_result = {
                'oneq_score': 50,
                'recommendation_reason': '기본 점수',
                'details': {'price_details': {'total_price': 0}}
            }
        
        scored_printshop = {
            'id': getattr(printshop, 'id', 0),
            'name': getattr(printshop, 'name', '알 수 없는 인쇄소'),
            'phone': getattr(printshop, 'phone', ''),
            'address': getattr(printshop, 'address', ''),
            'email': getattr(printshop, 'email', ''),
            'recommendation_score': score_result.get('oneq_score', 0),
            'recommendation_reason': score_result.get('recommendation_reason', '기본 추천'),
            'estimated_total_price': f"{score_result.get('details', {}).get('price_details', {}).get('total_price', 0):,}원",
            'estimated_production_time': getattr(printshop, 'production_time', ''),
            'delivery_methods': getattr(printshop, 'delivery_options', ''),
            'description': getattr(printshop, 'description', ''),
            'bulk_discount': getattr(printshop, 'bulk_discount', ''),
            'available_categories': getattr(printshop, 'available_categories', []),
            'score_details': score_result
        }
        
        scored_printshops.append(scored_printshop)
    
    # 점수순으로 정렬
    scored_printshops.sort(key=lambda x: x['recommendation_score'], reverse=True)
    
    return scored_printshops
