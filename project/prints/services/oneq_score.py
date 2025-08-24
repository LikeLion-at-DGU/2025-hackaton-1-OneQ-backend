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
                'oneq_score': round(oneq_score, 1),
                'price_score': round(price_score, 1),
                'deadline_score': round(deadline_score, 1),
                'workfit_score': round(workfit_score, 1),
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
            return 50.0  # 기본값
        
        # 후보 인쇄소들의 가격 목록 (임시로 현재 인쇄소만 사용)
        prices = [price_info['unit_price']]
        p_min = min(prices)
        p_med = sum(prices) / len(prices)
        p_i = price_info['unit_price']
        
        # 1. 최저가 비율 (50%)
        min_ratio = 100 * max(0, min(1, p_min / p_i)) if p_i > 0 else 0
        
        # 2. 예산 적합 (25%)
        budget_fit = 50.0  # 기본값
        if budget and self._parse_budget(budget):
            user_budget = self._parse_budget(budget)
            if user_budget:
                gamma = 0.35
                budget_fit = 100 * (1 - abs(p_i - user_budget) / (gamma * user_budget))
                budget_fit = max(0, min(100, budget_fit))
        
        # 3. 시장 합리성 (25%)
        market_fit = 50.0  # 기본값
        if len(prices) > 1:
            alpha = 0.30
            market_fit = 100 * (1 - abs(p_i - p_med) / (alpha * p_med))
            market_fit = max(0, min(100, market_fit))
        else:
            # 후보가 1곳이면 MarketFit 제외
            return 0.8 * budget_fit + 0.2 * min_ratio
        
        # 최종 가격 점수
        price_score = 0.50 * min_ratio + 0.25 * budget_fit + 0.25 * market_fit
        return price_score
    
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
            return 50.0
        
        # 리드타임 계산
        production_time = self._parse_production_time(printshop.production_time)
        finishing_time = self._get_finishing_time(printshop, user_requirements)
        quantity_time = self._get_quantity_time(user_requirements)
        
        # 혼잡계수 (임시)
        c = 1.0
        if not printshop.is_verified:
            c = 1.2
        if not printshop.is_active:
            c = 1.5
        
        # 총 리드타임
        L_i = production_time + (finishing_time + quantity_time) * c
        
        # 여유 시간
        m_i = due_days - L_i
        
        # 1. 기한충족 Feasibility (60%)
        if m_i >= 0:
            F = 100
        else:
            M_lo = 2  # 2일
            F = max(0, 100 * (1 + m_i / M_lo))
        
        # 2. 여유 버퍼 Buffer (25%)
        if m_i >= 3:
            Buffer = 100
        elif m_i >= 0:
            Buffer = 100 * (m_i / 3)
        else:
            Buffer = 0
        
        # 3. 신뢰/안정 Consistency (15%)
        BaseReliab = 0.85
        r_i = max(0.6, min(0.98, BaseReliab - 0.15 * (c - 1)))
        R = 50 + 50 * r_i
        
        # 최종 납기 점수
        deadline_score = 0.60 * F + 0.25 * Buffer + 0.15 * R
        return deadline_score
    
    def _calculate_workfit_score(self, printshop: PrintShop, user_requirements: Dict) -> float:
        """작업 적합도 계산 (WorkFit_i, 30%)"""
        category = user_requirements.get('category', '')
        
        # 1. 필수 스펙 일치 (60%)
        req_fit = self._calculate_requirement_fit(printshop, user_requirements)
        
        # 2. 선택 스펙/사용자 가중 (25%)
        opt_fit = self._calculate_option_fit(printshop, user_requirements)
        
        # 3. 파일 체크 Preflight (15%)
        preflight = 85.0  # 기본값 (임시)
        
        # 최종 작업 적합도 점수
        workfit_score = 0.60 * req_fit + 0.25 * opt_fit + 0.15 * preflight
        return workfit_score
    
    def _parse_price_info(self, printshop: PrintShop, category: str, quantity: int) -> Optional[Dict]:
        """카테고리별 가격 정보 파싱 (AI + 정규표현식 혼합)"""
        try:
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
            if not field_name:
                return None
            
            price_text = getattr(printshop, field_name, '')
            if not price_text:
                return None
            
            # 1. 먼저 정규표현식으로 시도
            prices = re.findall(r'(\d+)(?:부|매)\s*[:\-]\s*(\d+)원', price_text)
            
            if not prices:
                # 2. 정규표현식 실패 시 AI 파싱 시도
                try:
                    ai_prices = self._ai_parse_prices(price_text, category, quantity)
                    if ai_prices:
                        return ai_prices
                except Exception as ai_error:
                    print(f"AI 파싱 실패, 기본값 사용: {ai_error}")
                
                # 3. AI도 실패하면 기본 가격 추정
                return {
                    'unit_price': 50000,  # 기본 단가
                    'total_price': 50000 * quantity
                }
            
            # 수량에 맞는 가격 찾기
            for qty, price in prices:
                if int(qty) >= quantity:
                    unit_price = int(price) // int(qty)
                    return {
                        'unit_price': unit_price,
                        'total_price': unit_price * quantity
                    }
            
            # 마지막 가격 사용
            last_qty, last_price = prices[-1]
            unit_price = int(last_price) // int(last_qty)
            return {
                'unit_price': unit_price,
                'total_price': unit_price * quantity
            }
            
        except Exception as e:
            print(f"가격 정보 파싱 오류: {e}")
            return None
    
    def _ai_parse_prices(self, price_text: str, category: str, quantity: int) -> Optional[Dict]:
        """AI를 사용한 가격 정보 파싱"""
        try:
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

            response = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "당신은 가격 정보를 정확히 파싱하는 전문가입니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=100
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # JSON 파싱
            if result_text.startswith('{') and result_text.endswith('}'):
                result = json.loads(result_text)
                return {
                    'unit_price': int(result.get('unit_price', 0)),
                    'total_price': int(result.get('total_price', 0))
                }
            
            return None
            
        except Exception as e:
            print(f"AI 가격 파싱 오류: {e}")
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
        except:
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
        except:
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
            return 0.0
        
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
            return (matches / len(required_specs)) * 100.0
    
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
        
        if total_options == 0:
            return 85.0  # 기본값
        
        return (option_matches / total_options) * 100.0
    
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
        """AI를 사용한 옵션 매칭"""
        try:
            prompt = f"""
다음은 인쇄 옵션 정보입니다. 사용자가 요청한 옵션이 제공되는 옵션과 일치하는지 판단해주세요.

옵션 종류: {option_type}
사용자 요청: {user_option}
제공 옵션: {option_text}

다음 JSON 형식으로 응답해주세요:
{{
    "match": true/false,
    "reason": "매칭 이유"
}}

예시:
- 사용자: "무광", 제공: "UV(+3000원), 매트(+3000원)" → {{"match": true, "reason": "매트는 무광과 동일한 의미"}}
- 사용자: "일반지", 제공: "프리미엄 코트지(+0원), 스노우 매트(+1500원)" → {{"match": true, "reason": "프리미엄 코트지는 일반지의 고급 버전"}}

주의사항:
1. 유사한 의미의 옵션도 매칭으로 인정
2. 가격 정보는 무시하고 옵션명만 비교
3. true/false만 반환
"""

            response = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "당신은 인쇄 옵션 매칭 전문가입니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=100
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # JSON 파싱
            if result_text.startswith('{') and result_text.endswith('}'):
                result = json.loads(result_text)
                return result.get('match', False)
            
            return False
            
        except Exception as e:
            print(f"AI 옵션 매칭 오류: {e}")
            return False
    
    def _generate_recommendation_reason(self, price_score: float, deadline_score: float, 
                                      workfit_score: float, user_requirements: Dict) -> str:
        """추천 이유 생성"""
        reasons = []
        
        if price_score >= 80:
            reasons.append("경쟁력 있는 가격")
        elif price_score >= 60:
            reasons.append("합리적인 가격")
        
        if deadline_score >= 80:
            reasons.append("빠른 납기")
        elif deadline_score >= 60:
            reasons.append("안정적인 납기")
        
        if workfit_score >= 80:
            reasons.append("완벽한 스펙 매칭")
        elif workfit_score >= 60:
            reasons.append("적합한 작업 능력")
        
        if not reasons:
            reasons.append("종합적인 만족도")
        
        return ", ".join(reasons)
    
    def _get_price_details(self, printshop: PrintShop, user_requirements: Dict) -> Dict:
        """가격 상세 정보"""
        category = user_requirements.get('category', '')
        quantity = user_requirements.get('quantity', 0)
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


def calculate_printshop_scores(printshops: List[PrintShop], user_requirements: Dict) -> List[Dict]:
    """여러 인쇄소의 원큐스코어 계산"""
    calculator = OneQScoreCalculator()
    scored_printshops = []
    
    for printshop in printshops:
        try:
            score_result = calculator.calculate_oneq_score(printshop, user_requirements)
        except Exception as e:
            print(f"인쇄소 {printshop.name} 점수 계산 오류: {e}")
            # 기본 점수로 계속 진행
            score_result = {
                'oneq_score': 50.0,
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
