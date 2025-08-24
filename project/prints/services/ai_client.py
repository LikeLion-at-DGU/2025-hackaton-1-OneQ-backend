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
        
        print(f"=== AI 클라이언트 초기화 ===")
        print(f"API 키: {'설정됨' if self.api_key else '설정되지 않음'}")
        print(f"모델: {self.model}")
        print(f"온도: {self.temperature}")
    
    def _parse_region_expression(self, region_text: str) -> List[str]:
        """AI를 사용하여 지역 표현을 파싱하여 개별 지역 리스트로 변환"""
        if not region_text:
            return []
        
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
                return result.get('regions', [region_text])
            except json.JSONDecodeError:
                # JSON 파싱 실패 시 원본 반환
                return [region_text]
                
        except Exception as e:
            print(f"지역 파싱 오류: {e}")
            # 오류 발생 시 원본 반환
            return [region_text]
    
    def _match_regions_in_address(self, target_regions: List[str], address: str) -> bool:
        """AI를 사용하여 주소에서 대상 지역들이 포함되어 있는지 확인"""
        if not address or not target_regions:
            return False
        
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
                return result.get('match', False)
            except json.JSONDecodeError:
                # JSON 파싱 실패 시 간단한 문자열 매칭으로 폴백
                address_lower = address.lower()
                for region in target_regions:
                    if region.lower() in address_lower:
                        return True
                return False
                
        except Exception as e:
            print(f"주소 매칭 오류: {e}")
            # 오류 발생 시 간단한 문자열 매칭으로 폴백
            address_lower = address.lower()
            for region in target_regions:
                if region.lower() in address_lower:
                    return True
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
    
    def _get_db_options(self, category: str, region: str = None) -> Dict[str, List[str]]:
        """DB에서 카테고리별 실제 옵션들을 가져오기"""
        try:
            from ..models import PrintShop
            
            # 활성화된 인쇄소들에서 해당 카테고리 지원하는 곳들 필터링
            printshops = PrintShop.objects.filter(
                is_active=True,
                available_categories__contains=[category]
            )
            
            # 지역 필터링 추가
            if region:
                target_regions = self._parse_region_expression(region)
                filtered_printshops = []
                
                for shop in printshops:
                    if self._match_regions_in_address(target_regions, shop.address):
                        filtered_printshops.append(shop)
                
                printshops = filtered_printshops
            
            options = {}
            
            if category == "현수막":
                # 현수막 사이즈 옵션 수집
                size_options = set()
                processing_options = set()
                
                for shop in printshops:
                    if shop.banner_large_size_options:
                        # 사이즈 정보에서 옵션 추출
                        size_text = shop.banner_large_size_options
                        # 간단한 정규표현식으로 사이즈 추출 (예: 1x3m, 2x4m 등)
                        import re
                        sizes = re.findall(r'\d+x\d+m', size_text)
                        size_options.update(sizes)
                    
                    if shop.banner_large_processing_options:
                        processing_text = shop.banner_large_processing_options
                        # 가공 옵션 추출 (고리, 지퍼 등)
                        if '고리' in processing_text:
                            processing_options.add('고리')
                        if '지퍼' in processing_text:
                            processing_options.add('지퍼')
                
                options['size'] = list(size_options) if size_options else ['1x3m', '2x4m', '3x6m']
                options['processing'] = list(processing_options) if processing_options else ['고리', '지퍼', '없음']
            
            elif category == "브로슈어":
                # 브로슈어 옵션 수집
                paper_options = set()
                size_options = set()
                folding_options = set()
                
                for shop in printshops:
                    if shop.brochure_paper_options:
                        paper_text = shop.brochure_paper_options
                        if '일반지' in paper_text:
                            paper_options.add('일반지')
                        if '아트지' in paper_text:
                            paper_options.add('아트지')
                        if '코팅지' in paper_text:
                            paper_options.add('코팅지')
                        if '합지' in paper_text:
                            paper_options.add('합지')
                    
                    if shop.brochure_size_options:
                        size_text = shop.brochure_size_options
                        if 'A4' in size_text:
                            size_options.add('A4')
                        if 'A5' in size_text:
                            size_options.add('A5')
                        if 'B5' in size_text:
                            size_options.add('B5')
                        if 'A6' in size_text:
                            size_options.add('A6')
                    
                    if shop.brochure_folding_options:
                        folding_text = shop.brochure_folding_options
                        if '2단접지' in folding_text:
                            folding_options.add('2단접지')
                        if '3단접지' in folding_text:
                            folding_options.add('3단접지')
                        if 'Z접지' in folding_text:
                            folding_options.add('Z접지')
                
                options['paper'] = list(paper_options) if paper_options else ['일반지', '아트지', '코팅지', '합지']
                options['size'] = list(size_options) if size_options else ['A4', 'A5', 'B5', 'A6']
                options['folding'] = list(folding_options) if folding_options else ['2단접지', '3단접지', 'Z접지', '없음']
            
            elif category == "포스터":
                # 포스터 옵션 수집
                paper_options = set()
                size_options = set()
                coating_options = set()
                
                for shop in printshops:
                    if shop.poster_paper_options:
                        paper_text = shop.poster_paper_options
                        if '일반지' in paper_text:
                            paper_options.add('일반지')
                        if '아트지' in paper_text:
                            paper_options.add('아트지')
                        if '코팅지' in paper_text:
                            paper_options.add('코팅지')
                        if '합지' in paper_text:
                            paper_options.add('합지')
                    
                    if shop.poster_coating_options:
                        coating_text = shop.poster_coating_options
                        if '무광' in coating_text:
                            coating_options.add('무광')
                        if '유광' in coating_text:
                            coating_options.add('유광')
                        if '스팟' in coating_text:
                            coating_options.add('스팟')
                
                options['paper'] = list(paper_options) if paper_options else ['일반지', '아트지', '코팅지', '합지']
                options['size'] = ['A4', 'A3', 'A2']  # 포스터는 표준 사이즈
                options['coating'] = list(coating_options) if coating_options else ['무광', '유광', '스팟', '없음']
            
            elif category == "명함":
                # 명함 옵션 수집
                paper_options = set()
                size_options = set()
                printing_options = set()
                finishing_options = set()
                
                for shop in printshops:
                    if shop.business_card_paper_options:
                        paper_text = shop.business_card_paper_options
                        if '일반지' in paper_text:
                            paper_options.add('일반지')
                        if '고급지' in paper_text:
                            paper_options.add('고급지')
                        if '아트지' in paper_text:
                            paper_options.add('아트지')
                        if '코팅지' in paper_text:
                            paper_options.add('코팅지')
                    
                    if shop.business_card_printing_options:
                        printing_text = shop.business_card_printing_options
                        if '단면' in printing_text and '흑백' in printing_text:
                            printing_options.add('단면 흑백')
                        if '단면' in printing_text and '컬러' in printing_text:
                            printing_options.add('단면 컬러')
                        if '양면' in printing_text and '흑백' in printing_text:
                            printing_options.add('양면 흑백')
                        if '양면' in printing_text and '컬러' in printing_text:
                            printing_options.add('양면 컬러')
                    
                    if shop.business_card_finishing_options:
                        finishing_text = shop.business_card_finishing_options
                        if '무광' in finishing_text:
                            finishing_options.add('무광')
                        if '유광' in finishing_text:
                            finishing_options.add('유광')
                        if '스팟' in finishing_text:
                            finishing_options.add('스팟')
                        if '엠보싱' in finishing_text:
                            finishing_options.add('엠보싱')
                
                options['paper'] = list(paper_options) if paper_options else ['일반지', '고급지', '아트지', '코팅지']
                options['size'] = ['90×54mm', '85×54mm', '90×50mm', '85×50mm']  # 명함 표준 사이즈
                options['printing'] = list(printing_options) if printing_options else ['단면 흑백', '단면 컬러', '양면 흑백', '양면 컬러']
                options['finishing'] = list(finishing_options) if finishing_options else ['무광', '유광', '스팟', '엠보싱']
            
            return options
            
        except Exception as e:
            print(f"❌ DB 옵션 수집 오류: {e}")
            return {}
    
    def _get_category_info(self, category: str, region: str = None) -> str:
        """카테고리별 정보 수집 순서 반환 (DB 옵션 포함)"""
        # DB에서 실제 옵션들 가져오기
        db_options = self._get_db_options(category, region)
        
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

1. 배너 사이즈: "어떤 사이즈로 하시겠어요? (1x3m, 2x4m, 3x6m 등 중에서 선택해주세요)"
2. 배너 거치대 종류: "거치대는 어떤 걸로 하시겠어요? (X자형, A자형, 롤업형 중에서 선택해주세요)"
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

1. 스티커 종류: "어떤 종류의 스티커를 원하시나요? (일반스티커, 방수스티커, 반사스티커, 전사스티커 중에서 선택해주세요)"
2. 사이즈: "어떤 사이즈로 하시겠어요? (50x50mm, 100x100mm, 200x200mm / 원형은 지름 중에서 선택해주세요)"
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
        
        # DB 옵션으로 템플릿 치환
        if category == "현수막":
            size_options = ', '.join(db_options.get('size', ['1x3m', '2x4m', '3x6m']))
            processing_options = ', '.join(db_options.get('processing', ['고리', '지퍼', '없음']))
            return base_prompt.format(size_options=size_options, processing_options=processing_options)
        
        elif category == "브로슈어":
            paper_options = ', '.join(db_options.get('paper', ['일반지', '아트지', '코팅지', '합지']))
            size_options = ', '.join(db_options.get('size', ['A4', 'A5', 'B5', 'A6']))
            folding_options = ', '.join(db_options.get('folding', ['2단접지', '3단접지', 'Z접지', '없음']))
            return base_prompt.format(paper_options=paper_options, size_options=size_options, folding_options=folding_options)
        
        elif category == "포스터":
            paper_options = ', '.join(db_options.get('paper', ['일반지', '아트지', '코팅지', '합지']))
            size_options = ', '.join(db_options.get('size', ['A4', 'A3', 'A2']))
            coating_options = ', '.join(db_options.get('coating', ['무광', '유광', '스팟', '없음']))
            return base_prompt.format(paper_options=paper_options, size_options=size_options, coating_options=coating_options)
        
        elif category == "명함":
            paper_options = ', '.join(db_options.get('paper', ['일반지', '고급지', '아트지', '코팅지']))
            size_options = ', '.join(db_options.get('size', ['90×54mm', '85×54mm', '90×50mm', '85×50mm']))
            printing_options = ', '.join(db_options.get('printing', ['단면 흑백', '단면 컬러', '양면 흑백', '양면 컬러']))
            finishing_options = ', '.join(db_options.get('finishing', ['무광', '유광', '스팟', '엠보싱']))
            return base_prompt.format(paper_options=paper_options, size_options=size_options, printing_options=printing_options, finishing_options=finishing_options)
        
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
"이 정보를 바탕으로 최종 견적을 생성할까요?"

최종 견적을 생성할 때는 다음 형식으로 응답해주세요:
"=== 최종 견적서 ===

📋 요청 정보:
- [사용자가 입력한 모든 정보를 나열]

견적서가 완성되었습니다! 

이제 요청하신 정보에 맞는 인쇄소를 추천해드리겠습니다."

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
            # DB에서 실제 옵션들 가져오기
            db_options = self._get_db_options(category, region)
            
            # 카테고리별 프롬프트 (DB 옵션 포함)
            category_prompts = {
                                 "스티커": """
스티커 제작 정보를 다음 순서대로 추출해주세요:
1. paper: 스티커 종류 (일반스티커, 방수스티커, 반사스티커, 전사스티커)
2. size: 사이즈 (50x50mm, 100x100mm, 200x200mm / 원형은 지름)
3. quantity: 수량 (숫자만)
4. due_days: 납기일 (며칠 내에 필요한지 숫자만, 예: 3일, 7일, 14일)
5. region: 지역
6. budget: 예산 (숫자만, 원 단위)
""",
                                 "명함": f"""
명함 제작 정보를 다음 순서대로 추출해주세요:
1. paper: 용지 종류 ({', '.join(db_options.get('paper', ['일반지', '고급지', '아트지', '코팅지']))})
2. size: 명함 사이즈 ({', '.join(db_options.get('size', ['90×54mm', '85×54mm', '90×50mm', '85×50mm']))})
3. printing: 인쇄 방식 ({', '.join(db_options.get('printing', ['단면 흑백', '단면 컬러', '양면 흑백', '양면 컬러']))})
4. finishing: 후가공 ({', '.join(db_options.get('finishing', ['무광', '유광', '스팟', '엠보싱']))})
5. quantity: 수량 (숫자만)
6. due_days: 납기일 (며칠 내에 필요한지 숫자만, 예: 3일, 7일, 14일)
7. region: 지역
8. budget: 예산 (숫자만, 원 단위)
""",
                                 "포스터": f"""
포스터 제작 정보를 다음 순서대로 추출해주세요:
1. paper: 용지 종류 ({', '.join(db_options.get('paper', ['일반지', '아트지', '코팅지', '합지']))})
2. size: 포스터 사이즈 ({', '.join(db_options.get('size', ['A4', 'A3', 'A2']))})
3. coating: 포스터 코팅 종류 ({', '.join(db_options.get('coating', ['무광', '유광', '스팟', '없음']))})
4. quantity: 포스터 수량 (숫자만)
5. due_days: 납기일 (며칠 내에 필요한지 숫자만, 예: 3일, 7일, 14일)
6. region: 지역
7. budget: 예산 (숫자만, 원 단위)
""",
                                 "브로슈어": f"""
브로슈어 제작 정보를 다음 순서대로 추출해주세요:
1. paper: 용지 종류 ({', '.join(db_options.get('paper', ['일반지', '아트지', '코팅지', '합지']))})
2. size: 사이즈 종류 ({', '.join(db_options.get('size', ['A4', 'A5', 'B5', 'A6']))})
3. folding: 접지 종류 ({', '.join(db_options.get('folding', ['2단접지', '3단접지', 'Z접지', '없음']))})
4. quantity: 수량 (숫자만)
5. due_days: 납기일 (며칠 내에 필요한지 숫자만, 예: 3일, 7일, 14일)
6. region: 지역
7. budget: 예산 (숫자만, 원 단위)
""",
                "배너": """
배너 제작 정보를 다음 순서대로 추출해주세요:
1. size: 배너 사이즈 (1x3m, 2x4m, 3x6m 등)
2. stand: 배너 거치대 종류 (X자형, A자형, 롤업형)
3. quantity: 배너 수량 (숫자만)
4. due_days: 납기일 (며칠 내에 필요한지 숫자만, 예: 3일, 7일, 14일)
5. region: 지역
6. budget: 예산 (숫자만, 원 단위)
""",
                                 "현수막": f"""
현수막 제작 정보를 다음 순서대로 추출해주세요:
1. size: 현수막 사이즈 ({', '.join(db_options.get('size', ['1x3m', '2x4m', '3x6m']))})
2. processing: 현수막 추가 가공 ({', '.join(db_options.get('processing', ['고리', '지퍼', '없음']))})
3. quantity: 현수막 수량 (숫자만)
4. due_days: 납기일 (며칠 내에 필요한지 숫자만, 예: 3일, 7일, 14일)
5. region: 지역
6. budget: 예산 (숫자만, 원 단위)
"""
            }
            
            system_prompt = category_prompts.get(category, "정보를 추출해주세요.")
            system_prompt += "\n\n사용자 메시지에서 실제로 명시된 정보만 추출해주세요. 질문이나 추천 요청 등에는 빈 값으로 응답하세요.\n\n예산 추출 시 주의사항:\n- '30만원 근처' → '25~35만원'\n- '20만원 이하' → '20만원 이하'\n- '50만원 이상' → '50만원 이상'\n- '10~20만원' → '10~20만원'\n- '약 15만원' → '13~17만원'\n- '대략 25만원' → '22~28만원'\n\nJSON 형태로 응답해주세요:\n{\"filled_slots\": {\"paper\": \"일반지\", \"size\": \"90x54mm\"}, \"action\": \"ASK\"}"
            
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
