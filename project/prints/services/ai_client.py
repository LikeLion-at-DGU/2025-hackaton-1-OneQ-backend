# prints/services/ai_client.py
import os
import json
import re
from typing import Dict, Optional, List
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

try:
    import openai
except ImportError:
    openai = None

class AIClient:
    """간단한 AI 연결 클라이언트"""
    
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.model = os.getenv('GPT_MODEL', 'gpt-4o-mini')
        self.temperature = float(os.getenv('GPT_TEMPERATURE', '0.7'))
        
        # 캐싱을 위한 딕셔너리
        self._region_cache = {}
        self._address_cache = {}
        
        print(f"=== AI 클라이언트 초기화 ===")
        print(f"API 키: {'설정됨' if self.api_key else '설정되지 않음'}")
        print(f"모델: {self.model}")
        print(f"온도: {self.temperature}")
    
    def _parse_region_expression(self, region_text: str) -> List[str]:
        """AI를 사용하여 지역 표현을 파싱하여 개별 지역 리스트로 변환"""
        if not region_text:
            return []
        
        # 캐시 확인
        if region_text in self._region_cache:
            return self._region_cache[region_text]
        
        try:
            # AI에게 지역 파싱 요청
            prompt = f"""
사용자가 입력한 지역 표현을 분석해서 해당하는 모든 지역명을 추출해주세요.

입력: "{region_text}"

예시:
- "서울또는경기" → ["서울", "경기"]
- "서울이나경기" → ["서울", "경기"] 
- "충청권" → ["충북", "충남"]
- "경상권" → ["경북", "경남"]
- "수도권" → ["서울", "경기", "인천"]
- "서울" → ["서울"]
- "부산" → ["부산"]

지역명은 다음 중에서 선택해주세요:
서울, 경기, 인천, 부산, 대구, 울산, 대전, 광주, 세종, 제주, 강원, 충북, 충남, 전북, 전남, 경북, 경남

JSON 형태로 응답해주세요:
{{"regions": ["지역1", "지역2", ...]}}
"""
            
            client = openai.OpenAI(api_key=self.api_key)
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "지역 파싱 전문가입니다. 사용자의 자연어 표현을 정확한 지역명 리스트로 변환해주세요."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1  # 정확한 파싱을 위해 낮은 온도
            )
            
            content = response.choices[0].message.content
            
            try:
                result = json.loads(content)
                regions = result.get('regions', [region_text])
                # 캐시에 저장
                self._region_cache[region_text] = regions
                return regions
            except json.JSONDecodeError:
                # JSON 파싱 실패 시 원본 반환
                regions = [region_text]
                self._region_cache[region_text] = regions
                return regions
                
        except Exception as e:
            print(f"지역 파싱 오류: {e}")
            # 오류 발생 시 원본 반환
            regions = [region_text]
            self._region_cache[region_text] = regions
            return regions
    
    def _match_regions_in_address(self, target_regions: List[str], address: str) -> bool:
        """AI를 사용하여 주소에서 대상 지역들이 포함되어 있는지 확인"""
        if not address or not target_regions:
            return False
        
        # 캐시 키 생성
        cache_key = f"{address}:{','.join(sorted(target_regions))}"
        if cache_key in self._address_cache:
            return self._address_cache[cache_key]
        
        try:
            # AI에게 주소 매칭 요청
            prompt = f"""
주소가 특정 지역들에 해당하는지 판단해주세요.

주소: "{address}"
대상 지역들: {target_regions}

예시:
- 주소: "서울특별시 강남구 테헤란로 123", 대상: ["서울", "경기"] → true
- 주소: "경기도 성남시 분당구 정자로 456", 대상: ["서울", "경기"] → true  
- 주소: "부산광역시 해운대구 해운대로 321", 대상: ["서울", "경기"] → false
- 주소: "충청북도 청주시 상당구 987", 대상: ["충북", "충남"] → true

JSON 형태로 응답해주세요:
{{"match": true/false}}
"""
            
            client = openai.OpenAI(api_key=self.api_key)
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "주소 매칭 전문가입니다. 주소가 특정 지역에 해당하는지 정확히 판단해주세요."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
            )
            
            content = response.choices[0].message.content
            
            try:
                result = json.loads(content)
                match_result = result.get('match', False)
                # 캐시에 저장
                self._address_cache[cache_key] = match_result
                return match_result
            except json.JSONDecodeError:
                # JSON 파싱 실패 시 간단한 문자열 매칭으로 폴백
                address_lower = address.lower()
                for region in target_regions:
                    if region.lower() in address_lower:
                        self._address_cache[cache_key] = True
                        return True
                self._address_cache[cache_key] = False
                return False
                
        except Exception as e:
            print(f"주소 매칭 오류: {e}")
            # 오류 발생 시 간단한 문자열 매칭으로 폴백
            address_lower = address.lower()
            for region in target_regions:
                if region.lower() in address_lower:
                    self._address_cache[cache_key] = True
                    return True
            self._address_cache[cache_key] = False
            return False
    
    def is_available(self) -> bool:
        """AI 사용 가능 여부 확인"""
        if not openai:
            print("❌ OpenAI 모듈이 설치되지 않음")
            return False
        
        if not self.api_key:
            print("❌ OpenAI API 키가 설정되지 않음")
            return False
        
        print("✅ AI 클라이언트 사용 가능")
        return True
    
    def _get_filtered_printshops(self, category: str, region: str = None) -> List:
        """카테고리와 지역에 맞는 인쇄소들 필터링"""
        try:
            from ..models import PrintShop
            
            # 활성화된 인쇄소들에서 해당 카테고리 지원하는 곳들 필터링
            all_printshops = PrintShop.objects.filter(is_active=True)
            printshops = []
            
            for shop in all_printshops:
                available_cats = shop.available_categories or []
                if category in available_cats:
                    printshops.append(shop)
            
            # 지역 필터링 추가
            if region:
                target_regions = self._parse_region_expression(region)
                filtered_printshops = []
                
                for shop in printshops:
                    if self._match_regions_in_address(target_regions, shop.address):
                        filtered_printshops.append(shop)
                
                printshops = filtered_printshops
            
            return printshops
            
        except Exception as e:
            print(f"❌ 인쇄소 필터링 오류: {e}")
            return []
    
    def _get_field_options(self, category: str, field_name: str, region: str = None) -> List[str]:
        """특정 필드의 옵션들만 조회 (필요할 때만 호출)"""
        printshops = self._get_filtered_printshops(category, region)
        
        if field_name == 'paper':
            return self._get_paper_options(category, printshops)
        elif field_name == 'size':
            return self._get_size_options(category, printshops)
        elif field_name == 'coating':
            return self._get_coating_options(category, printshops)
        elif field_name == 'printing':
            return self._get_printing_options(category, printshops)
        elif field_name == 'finishing':
            return self._get_finishing_options(category, printshops)
        elif field_name == 'folding':
            return self._get_folding_options(category, printshops)
        elif field_name == 'processing':
            return self._get_processing_options(category, printshops)
        elif field_name == 'stand':
            return self._get_stand_options(category, printshops)
        elif field_name == 'type':
            return self._get_type_options(category, printshops)
        
        return []
    
    def _get_paper_options(self, category: str, printshops: List) -> List[str]:
        """용지 옵션 조회"""
        paper_options = set()
        
        for shop in printshops:
            if category == "명함" and shop.business_card_paper_options:
                paper_text = shop.business_card_paper_options
                if '스노우 매트지' in paper_text or '스노우매트지' in paper_text:
                    paper_options.add('스노우 매트지')
                if '프리미엄 코트지' in paper_text or '프리미엄코트지' in paper_text:
                    paper_options.add('프리미엄 코트지')
                if '반누보' in paper_text:
                    paper_options.add('반누보')
                if '일반지' in paper_text:
                    paper_options.add('일반지')
                if '고급지' in paper_text:
                    paper_options.add('고급지')
                if '아트지' in paper_text:
                    paper_options.add('아트지')
                if '코팅지' in paper_text:
                    paper_options.add('코팅지')
            
            elif category == "포스터" and shop.poster_paper_options:
                paper_text = shop.poster_paper_options
                if '일반지' in paper_text:
                    paper_options.add('일반지')
                if '아트지' in paper_text:
                    paper_options.add('아트지')
                if '코팅지' in paper_text:
                    paper_options.add('코팅지')
                if '합지' in paper_text:
                    paper_options.add('합지')
            
            elif category == "브로슈어" and shop.brochure_paper_options:
                paper_text = shop.brochure_paper_options
                if '일반지' in paper_text:
                    paper_options.add('일반지')
                if '아트지' in paper_text:
                    paper_options.add('아트지')
                if '코팅지' in paper_text:
                    paper_options.add('코팅지')
                if '합지' in paper_text:
                    paper_options.add('합지')
        
        return list(paper_options) if paper_options else []
    
    def _get_size_options(self, category: str, printshops: List) -> List[str]:
        """사이즈 옵션 조회"""
        size_options = set()
        
        for shop in printshops:
            if category == "명함" and shop.business_card_quantity_price_info:
                size_text = shop.business_card_quantity_price_info
                if '90×54' in size_text or '90x54' in size_text:
                    size_options.add('90×54mm')
                if '85×54' in size_text or '85x54' in size_text:
                    size_options.add('85×54mm')
                if '90×50' in size_text or '90x50' in size_text:
                    size_options.add('90×50mm')
                if '85×50' in size_text or '85x50' in size_text:
                    size_options.add('85×50mm')
            
            elif category == "포스터" and shop.poster_quantity_price_info:
                size_text = shop.poster_quantity_price_info
                if 'A4' in size_text:
                    size_options.add('A4')
                if 'A3' in size_text:
                    size_options.add('A3')
                if 'A2' in size_text:
                    size_options.add('A2')
                if 'A1' in size_text:
                    size_options.add('A1')
                if 'A0' in size_text:
                    size_options.add('A0')
            
            elif category == "브로슈어" and shop.brochure_quantity_price_info:
                size_text = shop.brochure_quantity_price_info
                if 'A4' in size_text:
                    size_options.add('A4')
                if 'A5' in size_text:
                    size_options.add('A5')
                if 'B5' in size_text:
                    size_options.add('B5')
                if 'A6' in size_text:
                    size_options.add('A6')
                if '2단' in size_text:
                    size_options.add('2단 A4')
                if '3단' in size_text:
                    size_options.add('3단 A4')
                if '정방형' in size_text:
                    size_options.add('정방형 3단')
            
            elif category == "배너" and shop.banner_size_options:
                size_text = shop.banner_size_options
                import re
                sizes = re.findall(r'\d+x\d+m', size_text)
                size_options.update(sizes)
            
            elif category == "현수막" and shop.banner_large_size_options:
                size_text = shop.banner_large_size_options
                import re
                sizes = re.findall(r'\d+x\d+m', size_text)
                size_options.update(sizes)
            
            elif category == "스티커" and shop.sticker_size_options:
                size_text = shop.sticker_size_options
                import re
                sizes = re.findall(r'\d+x\d+mm', size_text)
                size_options.update(sizes)
                circle_sizes = re.findall(r'지름\s*(\d+)mm', size_text)
                for size in circle_sizes:
                    size_options.add(f'지름{size}mm')
        
        return list(size_options) if size_options else []
    
    def _get_coating_options(self, category: str, printshops: List) -> List[str]:
        """코팅 옵션 조회"""
        coating_options = set()
        
        for shop in printshops:
            if category == "포스터" and shop.poster_coating_options:
                coating_text = shop.poster_coating_options
                if '무광' in coating_text:
                    coating_options.add('무광')
                if '유광' in coating_text:
                    coating_options.add('유광')
                if '스팟' in coating_text:
                    coating_options.add('스팟')
                if '없음' in coating_text or '코팅없음' in coating_text:
                    coating_options.add('없음')
        
        return list(coating_options) if coating_options else []
    
    def _get_printing_options(self, category: str, printshops: List) -> List[str]:
        """인쇄 방식 옵션 조회"""
        printing_options = set()
        
        for shop in printshops:
            if category == "명함" and shop.business_card_printing_options:
                printing_text = shop.business_card_printing_options
                if '단면 4도' in printing_text or '단면4도' in printing_text:
                    printing_options.add('단면 4도')
                if '양면 4도' in printing_text or '양면4도' in printing_text:
                    printing_options.add('양면 4도')
                if '단면' in printing_text and '흑백' in printing_text:
                    printing_options.add('단면 흑백')
                if '단면' in printing_text and '컬러' in printing_text:
                    printing_options.add('단면 컬러')
                if '양면' in printing_text and '흑백' in printing_text:
                    printing_options.add('양면 흑백')
                if '양면' in printing_text and '컬러' in printing_text:
                    printing_options.add('양면 컬러')
        
        return list(printing_options) if printing_options else []
    
    def _get_finishing_options(self, category: str, printshops: List) -> List[str]:
        """후가공 옵션 조회"""
        finishing_options = set()
        
        for shop in printshops:
            if category == "명함" and shop.business_card_finishing_options:
                finishing_text = shop.business_card_finishing_options
                if '부분 UV' in finishing_text or '부분UV' in finishing_text:
                    finishing_options.add('부분 UV')
                if '귀도리' in finishing_text:
                    finishing_options.add('귀도리')
                if '박' in finishing_text:
                    finishing_options.add('박')
                if '무광' in finishing_text:
                    finishing_options.add('무광')
                if '유광' in finishing_text:
                    finishing_options.add('유광')
                if '스팟' in finishing_text:
                    finishing_options.add('스팟')
                if '엠보싱' in finishing_text:
                    finishing_options.add('엠보싱')
        
        return list(finishing_options) if finishing_options else []
    
    def _get_folding_options(self, category: str, printshops: List) -> List[str]:
        """접지 옵션 조회"""
        folding_options = set()
        
        for shop in printshops:
            if category == "브로슈어" and shop.brochure_folding_options:
                folding_text = shop.brochure_folding_options
                if '2단접지' in folding_text:
                    folding_options.add('2단접지')
                if '3단접지' in folding_text:
                    folding_options.add('3단접지')
                if 'Z접지' in folding_text:
                    folding_options.add('Z접지')
        
        return list(folding_options) if folding_options else []
    
    def _get_processing_options(self, category: str, printshops: List) -> List[str]:
        """가공 옵션 조회"""
        processing_options = set()
        
        for shop in printshops:
            if category == "현수막" and shop.banner_large_processing_options:
                processing_text = shop.banner_large_processing_options
                if '고리' in processing_text:
                    processing_options.add('고리')
                if '지퍼' in processing_text:
                    processing_options.add('지퍼')
                if '없음' in processing_text or '가공없음' in processing_text:
                    processing_options.add('없음')
        
        return list(processing_options) if processing_options else []
    
    def _get_stand_options(self, category: str, printshops: List) -> List[str]:
        """거치대 옵션 조회"""
        stand_options = set()
        
        for shop in printshops:
            if category == "배너" and shop.banner_stand_options:
                stand_text = shop.banner_stand_options
                if 'X자형' in stand_text or 'X형' in stand_text:
                    stand_options.add('X자형')
                if 'A자형' in stand_text or 'A형' in stand_text:
                    stand_options.add('A자형')
                if '롤업형' in stand_text or '롤업' in stand_text:
                    stand_options.add('롤업형')
        
        return list(stand_options) if stand_options else []
    
    def _get_type_options(self, category: str, printshops: List) -> List[str]:
        """타입 옵션 조회"""
        type_options = set()
        
        for shop in printshops:
            if category == "스티커" and shop.sticker_type_options:
                type_text = shop.sticker_type_options
                if '일반스티커' in type_text or '일반' in type_text:
                    type_options.add('일반스티커')
                if '방수스티커' in type_text or '방수' in type_text:
                    type_options.add('방수스티커')
                if '반사스티커' in type_text or '반사' in type_text:
                    type_options.add('반사스티커')
                if '전사스티커' in type_text or '전사' in type_text:
                    type_options.add('전사스티커')
        
        return list(type_options) if type_options else []
    
    def _get_category_info(self, category: str, region: str = None) -> str:
        """카테고리별 정보 수집 순서 반환 (필드별 개별 조회)"""
        # 기본 프롬프트 템플릿
        base_prompts = {
            "명함": """명함 제작에 필요한 정보를 다음 순서로 수집해주세요:
정보를 물어볼 때는 괄호 안에 추천 옵션들을 표시해주세요.

1. 용지 종류: "어떤 용지를 사용하시겠어요? ({paper_options} 중에서 선택해주세요)"
2. 명함 사이즈: "어떤 사이즈로 하시겠어요? ({size_options} 중에서 선택해주세요)"
3. 인쇄 방식: "인쇄 방식은 어떻게 하시겠어요? ({printing_options} 중에서 선택해주세요)"
4. 후가공: "후가공은 어떻게 하시겠어요? ({finishing_options} 중에서 선택해주세요)"
5. 수량: "몇 부 필요하신가요?"
6. 납기일: "며칠 내에 필요하신가요?"
7. 지역: "어떤 지역의 인쇄소를 원하시나요?"
8. 예산: "예산은 어느 정도로 생각하고 계신가요?" """,
            
            "배너": """배너 제작에 필요한 정보를 다음 순서로 수집해주세요:
정보를 물어볼 때는 괄호 안에 추천 옵션들을 표시해주세요.

1. 배너 사이즈: "어떤 사이즈로 하시겠어요? ({size_options} 중에서 선택해주세요)"
2. 배너 거치대 종류: "거치대는 어떤 걸로 하시겠어요? ({stand_options} 중에서 선택해주세요)"
3. 배너 수량: "몇 개 필요하신가요?"
4. 납기일: "며칠 내에 필요하신가요?"
5. 지역: "어떤 지역의 인쇄소를 원하시나요?"
6. 예산: "예산은 어느 정도로 생각하고 계신가요?" """,
            
            "포스터": """포스터 제작에 필요한 정보를 다음 순서로 수집해주세요:
정보를 물어볼 때는 괄호 안에 추천 옵션들을 표시해주세요.

1. 용지 종류: "어떤 용지를 사용하시겠어요? ({paper_options} 중에서 선택해주세요)"
2. 포스터 사이즈: "어떤 사이즈로 하시겠어요? ({size_options} 중에서 선택해주세요)"
3. 포스터 코팅 종류: "코팅은 어떻게 하시겠어요? ({coating_options} 중에서 선택해주세요)"
4. 포스터 수량: "몇 부 필요하신가요?"
5. 납기일: "며칠 내에 필요하신가요?"
6. 지역: "어떤 지역의 인쇄소를 원하시나요?"
7. 예산: "예산은 어느 정도로 생각하고 계신가요?" """,
            
            "스티커": """스티커 제작에 필요한 정보를 다음 순서로 수집해주세요:
정보를 물어볼 때는 괄호 안에 추천 옵션들을 표시해주세요.

1. 스티커 종류: "어떤 종류의 스티커를 원하시나요? ({type_options} 중에서 선택해주세요)"
2. 사이즈: "어떤 사이즈로 하시겠어요? ({size_options} 중에서 선택해주세요)"
3. 수량: "몇 개 필요하신가요?"
4. 납기일: "며칠 내에 필요하신가요?"
5. 지역: "어떤 지역의 인쇄소를 원하시나요?"
6. 예산: "예산은 어느 정도로 생각하고 계신가요?" """,
            
            "현수막": """현수막 제작에 필요한 정보를 다음 순서로 수집해주세요:
정보를 물어볼 때는 괄호 안에 추천 옵션들을 표시해주세요.

1. 현수막 사이즈: "어떤 사이즈로 하시겠어요? ({size_options} 중에서 선택해주세요)"
2. 현수막 추가 가공: "가공 옵션은 어떻게 하시겠어요? ({processing_options} 중에서 선택해주세요)"
3. 현수막 수량: "몇 개 필요하신가요?"
4. 납기일: "며칠 내에 필요하신가요?"
5. 지역: "어떤 지역의 인쇄소를 원하시나요?"
6. 예산: "예산은 어느 정도로 생각하고 계신가요?" """,
            
            "브로슈어": """브로슈어 제작에 필요한 정보를 다음 순서로 수집해주세요:
정보를 물어볼 때는 괄호 안에 추천 옵션들을 표시해주세요.

1. 용지 종류: "어떤 용지를 사용하시겠어요? ({paper_options} 중에서 선택해주세요)"
2. 사이즈 종류: "어떤 사이즈로 하시겠어요? ({size_options} 중에서 선택해주세요)"
3. 접지 종류: "접지는 어떻게 하시겠어요? ({folding_options} 중에서 선택해주세요)"
4. 수량: "몇 부 필요하신가요?"
5. 납기일: "며칠 내에 필요하신가요?"
6. 지역: "어떤 지역의 인쇄소를 원하시나요?"
7. 예산: "예산은 어느 정도로 생각하고 계신가요?" """
        }
        
        base_prompt = base_prompts.get(category, "")
        
        # 각 필드별로 개별 조회하여 템플릿 치환
        if category == "현수막":
            size_options = self._get_field_options(category, 'size', region)
            processing_options = self._get_field_options(category, 'processing', region)
            
            size_text = ', '.join(size_options) if size_options else "1x3m, 2x4m, 3x6m 등"
            processing_text = ', '.join(processing_options) if processing_options else "고리, 지퍼, 없음 등"
            
            return base_prompt.format(size_options=size_text, processing_options=processing_text)
        
        elif category == "브로슈어":
            paper_options = self._get_field_options(category, 'paper', region)
            size_options = self._get_field_options(category, 'size', region)
            folding_options = self._get_field_options(category, 'folding', region)
            
            paper_text = ', '.join(paper_options) if paper_options else "일반지, 아트지, 코팅지, 합지 등"
            size_text = ', '.join(size_options) if size_options else "A4, A5, B5, A6 등"
            folding_text = ', '.join(folding_options) if folding_options else "2단접지, 3단접지, Z접지, 없음 등"
            
            return base_prompt.format(paper_options=paper_text, size_options=size_text, folding_options=folding_text)
        
        elif category == "포스터":
            paper_options = self._get_field_options(category, 'paper', region)
            size_options = self._get_field_options(category, 'size', region)
            coating_options = self._get_field_options(category, 'coating', region)
            
            paper_text = ', '.join(paper_options) if paper_options else "일반지, 아트지, 코팅지, 합지 등"
            size_text = ', '.join(size_options) if size_options else "A4, A3, A2, A1, A0 등 (원하는 사이즈 말씀해주세요)"
            coating_text = ', '.join(coating_options) if coating_options else "무광, 유광, 스팟, 없음 등"
            
            return base_prompt.format(paper_options=paper_text, size_options=size_text, coating_options=coating_text)
        
        elif category == "명함":
            paper_options = self._get_field_options(category, 'paper', region)
            size_options = self._get_field_options(category, 'size', region)
            printing_options = self._get_field_options(category, 'printing', region)
            finishing_options = self._get_field_options(category, 'finishing', region)
            
            paper_text = ', '.join(paper_options) if paper_options else "일반지, 고급지, 아트지, 코팅지 등"
            size_text = ', '.join(size_options) if size_options else "90×54mm, 85×54mm, 90×50mm, 85×50mm 등 (원하는 사이즈 말씀해주세요)"
            printing_text = ', '.join(printing_options) if printing_options else "단면 흑백, 단면 컬러, 양면 흑백, 양면 컬러 등"
            finishing_text = ', '.join(finishing_options) if finishing_options else "무광, 유광, 스팟, 엠보싱 등"
            
            return base_prompt.format(paper_options=paper_text, size_options=size_text, printing_options=printing_text, finishing_options=finishing_text)
        
        elif category == "배너":
            size_options = self._get_field_options(category, 'size', region)
            stand_options = self._get_field_options(category, 'stand', region)
            
            size_text = ', '.join(size_options) if size_options else "1x3m, 2x4m, 3x6m 등"
            stand_text = ', '.join(stand_options) if stand_options else "X자형, A자형, 롤업형 등"
            
            return base_prompt.format(size_options=size_text, stand_options=stand_text)
        
        elif category == "스티커":
            type_options = self._get_field_options(category, 'type', region)
            size_options = self._get_field_options(category, 'size', region)
            
            type_text = ', '.join(type_options) if type_options else "일반스티커, 방수스티커, 반사스티커, 전사스티커 등"
            size_text = ', '.join(size_options) if size_options else "50x50mm, 100x100mm, 200x200mm / 원형은 지름 등"
            
            return base_prompt.format(type_options=type_text, size_options=size_text)
        
        return base_prompt
    
    def _get_common_prompt(self) -> str:
        """공통 프롬프트 반환"""
        return """사용자가 질문을 하면 먼저 그 질문에 친근하고 전문적으로 답변해주세요.

정보를 수집할 때는 괄호 안에 추천 옵션들을 표시해주세요:
- "어떤 사이즈를 원하시나요? (1x3m, 2x4m, 3x6m 중에서 선택해주세요)"
- "가공 옵션은 어떻게 하시겠어요? (고리, 지퍼, 없음 중에서 선택해주세요)"
- "용지 종류는 어떤 걸로 하시겠어요? (일반지, 아트지, 코팅지 중에서 선택해주세요)"

답변 후에는 상황에 맞게 자연스럽게 다음 단계로 안내해주세요:
- "도움이 되셨을까요? 궁금한 점이 있으면 더 물어보세요!"
- "이해가 되셨나요? 더 궁금한 점이 있으시면 언제든 말씀해주세요!"
- "혹시 다른 궁금한 점이 있으시면 언제든 물어보세요!"
- "고민해보시고 천천히 선택해보세요!"
- "편하게 고민해보시고 결정해주세요!"
등 상황에 맞는 자연스러운 표현을 사용해주세요.

모든 필요한 정보가 수집되면, 수집된 정보를 정리해서 사용자에게 보여주고 확인받아주세요:
"수집된 정보를 정리해드릴게요:
- [수집된 정보들 나열]
이 정보가 맞는지 확인해주세요! 혹시 수정할 부분이 있으시면 말씀해주세요."

사용자가 정보가 맞다고 확인하면, 최종 견적 생성을 제안해주세요:
"이 정보를 바탕으로 최종 견적을 생성할까요? (최종견적 생성까지 최대 5분 소요될 수 있습니다)"

사용자가 "네", "좋아", "생성해주세요" 등으로 긍정적으로 응답하면, **바로 다음 응답에서** 최종 견적서를 생성해주세요:

"=== 최종 견적서 ===

📋 요청 정보:
- [사용자가 입력한 모든 정보를 나열]

견적서가 완성되었습니다!"

**중요**: 
- 최종 견적서를 바로 생성해주세요.
- **절대 인쇄소 추천 정보를 생성하지 마세요!**
- "이제 요청하신 정보에 맞는 인쇄소를 추천해드리겠습니다." 문구를 반드시 포함해주세요.
- "추천 인쇄소:", "인쇄소 추천" 등의 섹션을 절대 포함하지 마세요.
- **가짜 인쇄소 이름이나 정보를 절대 생성하지 마세요!**
- **"서울 인쇄소 A", "서울 인쇄소 B" 같은 더미 데이터를 절대 생성하지 마세요!**
- 시스템에서 자동으로 인쇄소 정보를 제공하므로 AI가 직접 생성할 필요가 없습니다.
- **최종 견적서만 생성하고 그 이상의 내용은 절대 추가하지 마세요!**

**위치 우선 추천 시스템:**
- 사용자가 특정 지역을 요청한 경우 (예: "서울 중구", "경기도 성남시"), 해당 지역에 위치한 인쇄소를 우선적으로 추천해야 합니다.
- 지역 매칭은 다음과 같이 처리합니다:
  * "서울 중구" → 서울특별시 중구에 위치한 인쇄소 우선
  * "경기도 성남시" → 경기도 성남시에 위치한 인쇄소 우선
  * "부산 해운대구" → 부산광역시 해운대구에 위치한 인쇄소 우선
- 해당 지역에 위치한 인쇄소가 없다면 원큐 스코어에 따라 추천해주세요.
- **중요**: 인쇄소 추천 정보는 시스템에서 자동으로 제공되므로 AI가 직접 생성하지 마세요.
- **절대 가짜 인쇄소 정보를 생성하지 마세요!**
- **AI는 오직 최종 견적서만 생성하고, 인쇄소 추천은 시스템이 담당합니다!**

이미 수집된 정보는 다시 묻지 마세요.
지역을 물어볼 때는 "어떤 지역의 인쇄소를 원하는지"를 묻도록 해주세요.
지역은 단일 지역(예: 서울, 경기) 또는 복합 지역(예: 서울또는경기, 서울이나경기, 충청권) 모두 입력 가능합니다.
납기일을 물어볼 때는 "며칠 내에 필요하신가요?" 또는 "언제까지 필요하신가요?"와 같이 물어보세요.
예산을 물어볼 때는 "예산은 어느 정도로 생각하고 계신가요?" 또는 "예산 범위를 알려주세요"와 같이 물어보세요.
답변은 순수 텍스트로만 작성하고 마크다운을 사용하지 마세요."""
    
    def _get_category_title(self, category: str) -> str:
        """카테고리별 제목 반환"""
        titles = {
            "명함": "명함 제작 전문 챗봇",
            "배너": "배너 제작 전문 챗봇", 
            "포스터": "포스터 제작 전문 챗봇",
            "스티커": "스티커 제작 전문 챗봇",
            "현수막": "현수막 제작 전문 챗봇",
            "브로슈어": "브로슈어 제작 전문 챗봇"
        }
        return titles.get(category, "인쇄 전문 챗봇")
    
    def _build_system_prompt(self, category: str = None, region: str = None) -> str:
        """시스템 프롬프트 구성"""
        if category:
            title = self._get_category_title(category)
            info = self._get_category_info(category, region)
            common = self._get_common_prompt()
            
            return f"""너는 {title}입니다. 

{info}

{common}"""
        else:
            return f"""너는 인쇄 전문가 챗봇입니다. 
사용자의 질문에 친근하고 정확하게 답변해주세요. 
답변은 순수 텍스트로만 작성하고 마크다운을 사용하지 마세요."""
    
    def chat(self, message: str, system_prompt: str = None, category: str = None, region: str = None) -> Dict:
        """간단한 채팅 요청"""
        if not self.is_available():
            return {
                "error": "AI 서비스를 사용할 수 없습니다.",
                "message": "API 키나 모듈이 설정되지 않았습니다."
            }
        
        try:
            # 시스템 프롬프트 구성
            if not system_prompt:
                system_prompt = self._build_system_prompt(category, region)
            
            # OpenAI API 호출
            client = openai.OpenAI(api_key=self.api_key)
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                temperature=self.temperature
            )
            
            content = response.choices[0].message.content
            
            return {
                "success": True,
                "message": content,
                "model": self.model
            }
            
        except Exception as e:
            print(f"❌ AI 호출 오류: {e}")
            return {
                "error": str(e),
                "message": "AI 응답 중 오류가 발생했습니다."
            }
    
    def chat_with_history(self, conversation_history: List[Dict], category: str = None, region: str = None) -> Dict:
        """대화 히스토리를 포함한 채팅 요청"""
        if not self.is_available():
            return {
                "error": "AI 서비스를 사용할 수 없습니다.",
                "message": "API 키나 모듈이 설정되지 않았습니다."
            }
        
        try:
            # 시스템 프롬프트 구성
            system_prompt = self._build_system_prompt(category, region)
            
            # 메시지 구성 (시스템 프롬프트 + 대화 히스토리)
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(conversation_history)
            
            # OpenAI API 호출
            client = openai.OpenAI(api_key=self.api_key)
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature
            )
            
            content = response.choices[0].message.content
            
            return {
                "success": True,
                "message": content,
                "model": self.model
            }
            
        except Exception as e:
            print(f"❌ AI 호출 오류: {e}")
            return {
                "error": str(e),
                "message": "AI 응답 중 오류가 발생했습니다."
            }
    
    def extract_info(self, message: str, category: str, region: str = None) -> Dict:
        """사용자 메시지에서 정보 추출"""
        if not self.is_available():
            return {"error": "AI 서비스를 사용할 수 없습니다."}
        
        try:
            # 카테고리별 프롬프트 (필드별 개별 조회)
            category_prompts = {
                "스티커": f"""
스티커 제작 정보를 다음 순서대로 추출해주세요:
1. type: 스티커 종류 ({', '.join(self._get_field_options(category, 'type', region)) or '일반스티커, 방수스티커, 반사스티커, 전사스티커 등'})
2. size: 사이즈 ({', '.join(self._get_field_options(category, 'size', region)) or '50x50mm, 100x100mm, 200x200mm / 원형은 지름 등'})
3. quantity: 수량 (숫자만)
4. due_days: 납기일 (며칠 내에 필요한지 숫자만, 예: 3일, 7일, 14일)
5. region: 지역
6. budget: 예산 (숫자만, 원 단위)

**자연어 이해**: 사용자가 "일반"이라고 하면 "일반스티커"로, "방수"라고 하면 "방수스티커"로 이해해주세요.
""",
                "명함": f"""
명함 제작 정보를 다음 순서대로 추출해주세요:
1. paper: 용지 종류 ({', '.join(self._get_field_options(category, 'paper', region)) or '일반지, 고급지, 아트지, 코팅지 등'})
2. size: 명함 사이즈 ({', '.join(self._get_field_options(category, 'size', region)) or '90×54mm, 85×54mm, 90×50mm, 85×50mm 등'})
3. printing: 인쇄 방식 ({', '.join(self._get_field_options(category, 'printing', region)) or '단면 흑백, 단면 컬러, 양면 흑백, 양면 컬러 등'})
4. finishing: 후가공 ({', '.join(self._get_field_options(category, 'finishing', region)) or '무광, 유광, 스팟, 엠보싱 등'})
5. quantity: 수량 (숫자만)
6. due_days: 납기일 (며칠 내에 필요한지 숫자만, 예: 3일, 7일, 14일)
7. region: 지역
8. budget: 예산 (숫자만, 원 단위)

**자연어 이해**:
- 사이즈: "기본", "표준", "일반", "보통" → "90×54mm"로 이해
- 인쇄: "단면", "단면인쇄" → "단면 흑백"으로 이해, "양면", "양면인쇄" → "양면 흑백"으로 이해
- 후가공: "귀도리" → "귀도리"로 그대로 이해
""",
                "포스터": f"""
포스터 제작 정보를 다음 순서대로 추출해주세요:
1. paper: 용지 종류 ({', '.join(self._get_field_options(category, 'paper', region)) or '일반지, 아트지, 코팅지, 합지 등'})
2. size: 포스터 사이즈 ({', '.join(self._get_field_options(category, 'size', region)) or 'A4, A3, A2 등'})
3. coating: 포스터 코팅 종류 ({', '.join(self._get_field_options(category, 'coating', region)) or '무광, 유광, 스팟, 없음 등'})
4. quantity: 포스터 수량 (숫자만)
5. due_days: 납기일 (며칠 내에 필요한지 숫자만, 예: 3일, 7일, 14일)
6. region: 지역
7. budget: 예산 (숫자만, 원 단위)

**자연어 이해**: "a4", "A4" → "A4"로, "a3", "A3" → "A3"로 이해해주세요.
""",
                "브로슈어": f"""
브로슈어 제작 정보를 다음 순서대로 추출해주세요:
1. paper: 용지 종류 ({', '.join(self._get_field_options(category, 'paper', region)) or '일반지, 아트지, 코팅지, 합지 등'})
2. size: 사이즈 종류 ({', '.join(self._get_field_options(category, 'size', region)) or 'A4, A5, B5, A6 등'})
3. folding: 접지 종류 ({', '.join(self._get_field_options(category, 'folding', region)) or '2단접지, 3단접지, Z접지, 없음 등'})
4. quantity: 수량 (숫자만)
5. due_days: 납기일 (며칠 내에 필요한지 숫자만, 예: 3일, 7일, 14일)
6. region: 지역
7. budget: 예산 (숫자만, 원 단위)

**자연어 이해**: "2단" → "2단접지"로, "3단" → "3단접지"로, "z접지" → "Z접지"로 이해해주세요.
""",
                "배너": f"""
배너 제작 정보를 다음 순서대로 추출해주세요:
1. size: 배너 사이즈 ({', '.join(self._get_field_options(category, 'size', region)) or '1x3m, 2x4m, 3x6m 등'})
2. stand: 배너 거치대 종류 ({', '.join(self._get_field_options(category, 'stand', region)) or 'X자형, A자형, 롤업형 등'})
3. quantity: 배너 수량 (숫자만)
4. due_days: 납기일 (며칠 내에 필요한지 숫자만, 예: 3일, 7일, 14일)
5. region: 지역
6. budget: 예산 (숫자만, 원 단위)

**자연어 이해**: "x자형" → "X자형"으로, "a자형" → "A자형"으로, "롤업" → "롤업형"으로 이해해주세요.
""",
                "현수막": f"""
현수막 제작 정보를 다음 순서대로 추출해주세요:
1. size: 현수막 사이즈 ({', '.join(self._get_field_options(category, 'size', region)) or '1x3m, 2x4m, 3x6m 등'})
2. processing: 현수막 추가 가공 ({', '.join(self._get_field_options(category, 'processing', region)) or '고리, 지퍼, 없음 등'})
3. quantity: 현수막 수량 (숫자만)
4. due_days: 납기일 (며칠 내에 필요한지 숫자만, 예: 3일, 7일, 14일)
5. region: 지역
6. budget: 예산 (숫자만, 원 단위)

**자연어 이해**: 사용자의 자연어 표현을 정확한 옵션으로 이해해주세요.
"""
            }
            
            system_prompt = category_prompts.get(category, "정보를 추출해주세요.")
            system_prompt += """

**중요한 자연어 이해 가이드**:
- 사용자가 "기본", "표준", "일반", "보통"이라고 하면 가장 일반적인 옵션으로 이해
- 사용자가 "단면", "단면인쇄"라고 하면 "단면 흑백"으로 이해
- 사용자가 "양면", "양면인쇄"라고 하면 "양면 흑백"으로 이해
- 사용자가 "컬러"라고 하면 "단면 컬러"로 이해
- 사용자가 "흑백"이라고 하면 "단면 흑백"으로 이해
- 사용자가 "2단", "3단"이라고 하면 "2단접지", "3단접지"로 이해
- 사용자가 "x자형", "a자형"이라고 하면 "X자형", "A자형"으로 이해
- 사용자가 "롤업"이라고 하면 "롤업형"으로 이해
- 사용자가 "z접지"라고 하면 "Z접지"로 이해
- 사용자가 "a4", "a3" 등 소문자로 입력해도 "A4", "A3"로 이해

사용자 메시지에서 실제로 명시된 정보만 추출해주세요. 질문이나 추천 요청 등에는 빈 값으로 응답하세요.

예산 추출 시 주의사항:
- '30만원 근처' → '25~35만원'
- '20만원 이하' → '20만원 이하'
- '50만원 이상' → '50만원 이상'
- '10~20만원' → '10~20만원'
- '약 15만원' → '13~17만원'
- '대략 25만원' → '22~28만원'

JSON 형태로 응답해주세요:
{"filled_slots": {"paper": "일반지", "size": "90x54mm"}, "action": "ASK"}"
            
            client = openai.OpenAI(api_key=self.api_key)
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                temperature=0.3  # 정확한 추출을 위해 낮은 온도
            )
            
            content = response.choices[0].message.content
            
            try:
                result = json.loads(content)
                return result
            except json.JSONDecodeError:
                return {
                    "error": "JSON 파싱 실패",
                    "raw_response": content
                }
                
        except Exception as e:
            return {"error": f"정보 추출 오류: {str(e)}"}

# 테스트 함수
def test_ai_connection():
    """AI 연결 테스트"""
    ai = AIClient()
    
    if not ai.is_available():
        print("❌ AI 연결 실패")
        return False
    
    print("✅ AI 연결 성공")
    
    # 간단한 채팅 테스트
    response = ai.chat("안녕하세요! 명함 제작에 대해 궁금한 점이 있어요.")
    print(f"채팅 응답: {response}")
    
    # 정보 추출 테스트
    info = ai.extract_info("명함 100부, 90x54mm, 고급지로 만들어주세요", "명함")
    print(f"정보 추출: {info}")
    
    # 지역 파싱 테스트
    test_regions = [
        "서울또는경기",
        "서울이나경기",
        "충청권",
        "서울",
        "경상권"
    ]
    
    print("\n=== 지역 파싱 테스트 ===")
    for region in test_regions:
        parsed = ai._parse_region_expression(region)
        print(f"'{region}' → {parsed}")
    
    return True

if __name__ == "__main__":
    test_ai_connection()
