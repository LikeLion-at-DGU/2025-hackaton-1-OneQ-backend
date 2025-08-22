# prints/services/ai.py
import json
import re
from typing import Dict, List, Optional
from ..models import PrintShop
from .gpt_client import GPTClient
from .db_formatter import DBFormatter
from .conversation_manager import ConversationManager
from .oneqscore import score_and_rank

def _to_int(v, default=0):
    if isinstance(v, int): 
        return v
    s = str(v or "")
    s = re.sub(r"[^\d]", "", s)
    return int(s) if s else default

def _to_money(v, default=0):
    """
    '15만원', '120,000원', '7만 5천원', '200000' 등을 정규화 → 원 단위 정수
    너무 복잡하게 가지 않고, 대표 케이스만 안전 처리
    """
    if v is None:
        return default
    s = str(v).strip().replace(",", "").replace(" ", "")
    # 완전 숫자만: 그대로
    if s.isdigit():
        return int(s)
    # '만원' 단위
    m = re.match(r"^(\d+)(만|만원)$", s)
    if m:
        return int(m.group(1)) * 10000
    # '천원'
    m = re.match(r"^(\d+)(천|천원)$", s)
    if m:
        return int(m.group(1)) * 1000
    # '원' 접미사
    m = re.match(r"^(\d+)원$", s)
    if m:
        return int(m.group(1))
    # 섞여있을 때 숫자만 추출 (마지막 fallback)
    digits = re.sub(r"[^\d]", "", s)
    return int(digits) if digits else default

def _norm_region(v: str) -> str:
    if not v:
        return ""
    s = str(v).strip().replace(" ", "")
    s = s.replace("/", "-").replace("_", "-")
    return s

def _coerce_numbers(slots: Dict) -> Dict:
    """
    GPT 응답에 섞여 들어온 문자열 값을 안전한 숫자/정규화 값으로 강제.
    """
    out = dict(slots or {})
    if 'quantity' in out:
        out['quantity'] = _to_int(out['quantity'], 1)
    if 'due_days' in out:
        out['due_days'] = _to_int(out['due_days'], 3)
    if 'budget' in out:
        out['budget'] = _to_money(out['budget'], 0)
    if 'region' in out:
        out['region'] = _norm_region(out['region'])
    return out

def _sanitize_plain(text: str) -> str:
    """출력에서 마크다운을 제거하고 순수 텍스트로 정리."""
    if not text:
        return ""
    t = str(text)
    # 굵게/이탤릭/코드 기호 제거
    t = t.replace("**", "")
    t = t.replace("__", "")
    t = t.replace("`", "")
    # 헤더/표시적 기호(#, >)는 행의 선두에서만 제거
    t = re.sub(r"(?m)^\s*[#>\|]+\s*", "", t)
    # 불필요한 연속 공백 정리
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()

class PrintShopAIService:
    """인쇄소 DB 기반 AI 챗봇 서비스 (GPT-4-mini 통합)"""
    
    def __init__(self, category: str):
        print(f"=== AI 서비스 초기화 ===")
        print(f"전달받은 카테고리: {category}")
        print(f"카테고리 타입: {type(category)}")
        
        self.category = category # "명함", "배너", "포스터" 등 카테고리 수집
        self.printshops = self._get_printshops_by_category(category) # 해당 카테고리를 지원하는 인쇄소만 필터링
        self.category_info = self._get_category_info() # 카테고리별 정보 수집
        
        # GPT 관련 객체들 초기화
        self.gpt_client = GPTClient()
        self.db_formatter = DBFormatter(self.category_info, self.category)
        self.conversation_manager = ConversationManager()
        
        # GPT 사용 가능 여부 확인
        self.use_gpt = self.gpt_client.is_available()
        
        print(f"AI 서비스 카테고리: {self.category}")
        print(f"=== AI 서비스 초기화 완료 ===")
    
    def _get_printshops_by_category(self, category: str) -> List[PrintShop]:
        """카테고리별 인쇄소 조회"""
        print(f"=== 인쇄소 조회 디버깅 시작 ===")
        print(f"요청된 카테고리: {category}")
        print(f"카테고리 타입: {type(category)}")
        
        # 카테고리 매핑 (한글 → 영어)
        category_mapping = {
            '명함': 'card',
            '배너': 'banner', 
            '포스터': 'poster',
            '스티커': 'sticker',
            '현수막': 'banner2',
            '브로슈어': 'brochure'
        }
        
        # 한글 카테고리를 영어로 변환
        english_category = category_mapping.get(category, category)
        print(f"영어 카테고리로 변환: {category} → {english_category}")
        
        # 모든 활성화된 인쇄소 조회
        all_printshops = PrintShop.objects.filter(
            is_active=True,
            registration_status='completed'
        )
        print(f"활성화된 인쇄소 수: {all_printshops.count()}")
        
        # 모든 인쇄소 상태 출력
        for shop in all_printshops:
            print(f"인쇄소: {shop.name}")
            print(f"  - is_active: {shop.is_active}")
            print(f"  - registration_status: {shop.registration_status}")
            print(f"  - available_categories: {shop.available_categories}")
            print(f"  - available_categories 타입: {type(shop.available_categories)}")
        
        # 해당 카테고리를 지원하는 인쇄소만 필터링
        filtered_printshops = []
        for printshop in all_printshops:
            print(f"\n인쇄소 확인: {printshop.name}")
            print(f"  - 카테고리: {printshop.available_categories}")
            
            # available_categories가 None이거나 빈 리스트인 경우 처리
            available_cats = printshop.available_categories or []
            if not isinstance(available_cats, list):
                available_cats = []
                print(f"  - available_cats 변환: {available_cats}")
            
            print(f"  - 찾는 카테고리: {english_category}")
            print(f"  - 포함 여부: {english_category in available_cats}")
            
            if english_category in available_cats:
                filtered_printshops.append(printshop)
                print(f"  ✓ {printshop.name} 추가됨")
            else:
                print(f"  ✗ {printshop.name} 제외됨 (카테고리 불일치: {english_category} not in {available_cats})")
        
        print(f"\n=== 최종 필터링된 인쇄소 수: {len(filtered_printshops)} ===")
        return filtered_printshops
    
    def _get_category_info(self) -> Dict:
        """카테고리별 정보 수집"""
        if not self.printshops: # 등록된 인쇄소가 없다면 빈 딕셔너리 반환환
            return {}
        
        combined_info = {} # 카테고리별 정보를 저장할 딕셔너리
        
        category_fields = { # 각 카테고리마다 필요한 DB 필드들을 정의
            '명함': ['business_card_paper_options', 'business_card_printing_options', 'business_card_finishing_options', 'business_card_min_quantity'],
            '배너': ['banner_size_options', 'banner_stand_options', 'banner_min_quantity'],
            '포스터': ['poster_paper_options', 'poster_coating_options', 'poster_min_quantity'],
            '스티커': ['sticker_type_options', 'sticker_size_options', 'sticker_min_quantity'],
            '현수막': ['banner_large_size_options', 'banner_large_processing_options', 'banner_large_min_quantity'],
            '브로슈어': ['brochure_paper_options', 'brochure_size_options', 'brochure_folding_options', 'brochure_min_quantity']
        }
        # 각 필드별 정보 수집집
        if self.category in category_fields:
            for field in category_fields[self.category]:
                field_values = []
                for printshop in self.printshops:
                    value = getattr(printshop, field, '') # DB 필드에서 값 가져오기기
                    if value: # 값이 있으면 리스트에 추가
                        field_values.append(value)
                
                if field_values:
                    # 중복 제거하고 합치기
                    combined_info[field] = '\n'.join(set(field_values))
        
        return combined_info
    
    def get_category_introduction(self) -> str:
        """카테고리 소개 메시지"""
        # 각 카테고리마다 다른 인사말 제공공
        introductions = {
            '명함': "안녕하세요! 명함 제작 전문 챗봇입니다. 🏢\n\n명함 제작에 필요한 정보를 단계별로 안내해드릴게요.",
            '배너': "안녕하세요! 배너 제작 전문 챗봇입니다. 🎨\n\n배너 제작에 필요한 정보를 단계별로 안내해드릴게요.",
            '포스터': "안녕하세요! 포스터 제작 전문 챗봇입니다. 📢\n\n포스터 제작에 필요한 정보를 단계별로 안내해드릴게요.",
            '스티커': "안녕하세요! 스티커 제작 전문 챗봇입니다. 🏷️\n\n스티커 제작에 필요한 정보를 단계별로 안내해드릴게요.",
            '현수막': "안녕하세요! 현수막 제작 전문 챗봇입니다. 🏁\n\n현수막 제작에 필요한 정보를 단계별로 안내해드릴게요.",
            '브로슈어': "안녕하세요! 브로슈어 제작 전문 챗봇입니다. 📖\n\n브로슈어 제작에 필요한 정보를 단계별로 안내해드릴게요."
        }
        
        intro = introductions.get(self.category, "안녕하세요! 인쇄 제작 전문 챗봇입니다.")
        
        # 첫 번째 질문 추가
        intro += "\n\n" + self._get_first_question()
        
        return intro
    
    def _get_first_question(self) -> str:
        """첫 번째 질문 생성"""
        # 각 카테고리마다 필요한 정보를 수집하는 순서
        category_flows = {
            '명함': ['quantity', 'size', 'paper', 'printing', 'finishing'],
            '배너': ['size', 'quantity', 'stand'],
            '포스터': ['paper', 'size', 'quantity', 'coating'],
            '스티커': ['type', 'size', 'quantity'],
            '현수막': ['size', 'quantity', 'processing'],
            '브로슈어': ['paper', 'folding', 'size', 'quantity']
        }
        
        # 현재 카테고리의 순서 가져오기
        common_tail = ['due_days', 'region', 'budget']
        flow = category_flows.get(self.category, []) + common_tail
        return self._get_question_for_slot(flow[0]) if flow else "어떤 정보가 필요하신가요?"
    
    def _get_question_for_slot(self, slot: str) -> str:
        """슬롯별 질문 생성 (DB 정보 포함)"""
        questions = {
            'quantity': '수량은 얼마나 하실 건가요?', # 수량은 자유 입력이므로 바로 질문(DB 조회 불필요요)
            'paper': self._get_paper_question(),
            'size': self._get_size_question(),
            'printing': '인쇄 방식은 어떻게 하시겠어요? (단면, 양면)', # 인쇄 방식은 단면,양면 두 가지만 존재하므로 바로 질문
            'finishing': self._get_finishing_question(),
            'coating': self._get_coating_question(),
            'type': self._get_type_question(),
            'stand': self._get_stand_question(),
            'processing': self._get_processing_question(),
            'folding': self._get_folding_question(),
            'due_days': '납기는 며칠 후까지 필요하세요? (예: 1~7일, 기본 3일)',
            'region':   '수령/배송 지역은 어디인가요? (예: 서울-중구 / 없으면 “없음”)',
            'budget':   '예산이 있으시면 알려주세요. (예: 15만원 / 없으면 “없음”)'
        }
        
        return questions.get(slot, f'{slot}에 대해 알려주세요.')
    
    # 각 슬롯별 질문 생성 함수(DB 정보 조회 후 질문 생성)
    def _get_paper_question(self) -> str:
        """용지 질문 (DB 정보 포함)"""
        papers = self._extract_papers_from_db()
        if papers:
            return f"용지는 어떤 걸로 하시겠어요? ({', '.join(papers)})"
        return "용지는 어떤 걸로 하시겠어요?"
    
    def _get_size_question(self) -> str:
        """사이즈 질문 (DB 정보 포함)"""
        sizes = self._extract_sizes_from_db()
        if sizes:
            return f"사이즈는 어떻게 하시겠어요? ({', '.join(sizes)})"
        return "사이즈는 어떻게 하시겠어요?"
    
    def _get_finishing_question(self) -> str:
        """후가공 질문 (DB 정보 포함)"""
        finishing_options = self._extract_finishing_from_db()
        if finishing_options:
            return f"후가공 옵션은 어떤 걸 원하시나요? ({', '.join(finishing_options)})"
        return "후가공 옵션은 어떤 걸 원하시나요?"
    
    def _get_coating_question(self) -> str:
        """코팅 질문 (DB 정보 포함)"""
        coating_options = self._extract_coating_from_db()
        if coating_options:
            return f"코팅 옵션은 어떤 걸 원하시나요? ({', '.join(coating_options)})"
        return "코팅 옵션은 어떤 걸 원하시나요?"
    
    def _get_type_question(self) -> str:
        """종류 질문 (DB 정보 포함)"""
        types = self._extract_types_from_db()
        if types:
            return f"어떤 종류로 하시겠어요? ({', '.join(types)})"
        return "어떤 종류로 하시겠어요?"
    
    def _get_stand_question(self) -> str:
        """거치대 질문 (DB 정보 포함)"""
        stands = self._extract_stands_from_db()
        if stands:
            return f"거치대는 어떤 걸 원하시나요? ({', '.join(stands)})"
        return "거치대는 어떤 걸 원하시나요?"
    
    def _get_processing_question(self) -> str:
        """가공 질문 (DB 정보 포함)"""
        processing_options = self._extract_processing_from_db()
        if processing_options:
            return f"추가 가공 옵션은 어떤 걸 원하시나요? ({', '.join(processing_options)})"
        return "추가 가공 옵션은 어떤 걸 원하시나요?"
    
    def _get_folding_question(self) -> str:
        """접지 질문 (DB 정보 포함)"""
        folding_options = self._extract_folding_from_db()
        if folding_options:
            return f"접지 방식은 어떤 걸 원하시나요? ({', '.join(folding_options)})"
        return "접지 방식은 어떤 걸 원하시나요?"
    
    # DB에서 정보 추출 함수 (자연어 처리 기반)
    def _extract_papers_from_db(self) -> List[str]:
        """DB에서 용지 정보 추출 (GPT 활용)"""
        paper_fields = {
            '명함': 'business_card_paper_options',
            '포스터': 'poster_paper_options',
            '브로슈어': 'brochure_paper_options'
        }
        
        field = paper_fields.get(self.category)
        if not field or field not in self.category_info:
            return []
        
        content = self.category_info[field]
        if not content:
            return []
        
        # GPT를 활용해서 용지 옵션 추출
        return self._extract_options_with_gpt(content, "용지")
    
    def _extract_sizes_from_db(self) -> List[str]:
        """DB에서 사이즈 정보 추출 (GPT 활용)"""
        size_fields = {
            '명함': 'business_card_paper_options',  # 명함은 용지 옵션에서 사이즈 정보 추출
            '배너': 'banner_size_options',
            '스티커': 'sticker_size_options',
            '현수막': 'banner_large_size_options',
            '브로슈어': 'brochure_size_options'
        }
        
        field = size_fields.get(self.category)
        if not field or field not in self.category_info:
            return []
        
        content = self.category_info[field]
        if not content:
            return []
        
        # GPT를 활용해서 사이즈 옵션 추출
        return self._extract_options_with_gpt(content, "사이즈")
    
    def _extract_finishing_from_db(self) -> List[str]:
        """DB에서 후가공 정보 추출 (GPT 활용)"""
        finishing_fields = {
            '명함': 'business_card_finishing_options'
        }
        
        field = finishing_fields.get(self.category)
        if not field or field not in self.category_info:
            return []
        
        content = self.category_info[field]
        if not content:
            return []
        
        # GPT를 활용해서 후가공 옵션 추출
        return self._extract_options_with_gpt(content, "후가공")
    
    def _extract_coating_from_db(self) -> List[str]:
        """DB에서 코팅 정보 추출 (GPT 활용)"""
        coating_fields = {
            '포스터': 'poster_coating_options'
        }
        
        field = coating_fields.get(self.category)
        if not field or field not in self.category_info:
            return []
        
        content = self.category_info[field]
        if not content:
            return []
        
        # GPT를 활용해서 코팅 옵션 추출
        return self._extract_options_with_gpt(content, "코팅")
    
    def _extract_types_from_db(self) -> List[str]:
        """DB에서 종류 정보 추출 (GPT 활용)"""
        type_fields = {
            '스티커': 'sticker_type_options'
        }
        
        field = type_fields.get(self.category)
        if not field or field not in self.category_info:
            return []
        
        content = self.category_info[field]
        if not content:
            return []
        
        # GPT를 활용해서 종류 옵션 추출
        return self._extract_options_with_gpt(content, "종류")
    
    def _extract_stands_from_db(self) -> List[str]:
        """DB에서 거치대 정보 추출 (GPT 활용)"""
        stand_fields = {
            '배너': 'banner_stand_options'
        }
        
        field = stand_fields.get(self.category)
        if not field or field not in self.category_info:
            return []
        
        content = self.category_info[field]
        if not content:
            return []
        
        # GPT를 활용해서 거치대 옵션 추출
        return self._extract_options_with_gpt(content, "거치대")
    
    def _extract_processing_from_db(self) -> List[str]:
        """DB에서 가공 정보 추출 (GPT 활용)"""
        processing_fields = {
            '현수막': 'banner_large_processing_options'
        }
        
        field = processing_fields.get(self.category)
        if not field or field not in self.category_info:
            return []
        
        content = self.category_info[field]
        if not content:
            return []
        
        # GPT를 활용해서 가공 옵션 추출
        return self._extract_options_with_gpt(content, "가공")
    
    def _extract_folding_from_db(self) -> List[str]:
        """DB에서 접지 정보 추출 (GPT 활용)"""
        folding_fields = {
            '브로슈어': 'brochure_folding_options'
        }
        
        field = folding_fields.get(self.category)
        if not field or field not in self.category_info:
            return []
        
        content = self.category_info[field]
        if not content:
            return []
        
        # GPT를 활용해서 접지 옵션 추출
        return self._extract_options_with_gpt(content, "접지")
    
    def _extract_options_with_gpt(self, content: str, option_type: str) -> List[str]:
        """GPT를 활용해서 DB 내용에서 옵션 추출"""
        if not self.use_gpt or not content:
            return []
        
        try:
            # GPT에게 옵션 추출 요청
            prompt = f"""
다음 텍스트에서 {option_type} 관련 옵션들을 추출해주세요.

텍스트: {content}

요구사항:
1. {option_type}와 관련된 모든 옵션을 찾아주세요
2. 각 옵션은 쉼표로 구분해서 나열해주세요
3. 가격 정보나 설명은 제외하고 옵션명만 추출해주세요
4. 중복된 옵션은 제거해주세요

예시 응답 형식:
반누보, 휘라레, 아트지, 스노우지

JSON 형태로 응답해주세요:
{{"options": ["옵션1", "옵션2", "옵션3"]}}
"""
            
            response = self.gpt_client.process_conversation(prompt)
            
            if 'error' in response:
                return []
            
            # JSON 응답에서 옵션 추출
            try:
                if isinstance(response, dict) and 'options' in response:
                    return response['options']
                elif isinstance(response, str):
                    # 문자열 응답에서 옵션 추출 시도
                    import json
                    parsed = json.loads(response)
                    if 'options' in parsed:
                        return parsed['options']
            except:
                pass
            
            # GPT 응답이 실패하면 간단한 키워드 매칭으로 폴백
            return self._fallback_keyword_extraction(content, option_type)
            
        except Exception as e:
            print(f"GPT 옵션 추출 실패: {e}")
            return self._fallback_keyword_extraction(content, option_type)
    
    def _fallback_keyword_extraction(self, content: str, option_type: str) -> List[str]:
        """GPT 실패 시 간단한 키워드 매칭으로 폴백"""
        # 기본 키워드 패턴 (GPT 실패 시 사용)
        keyword_patterns = {
            "용지": ['반누보', '휘라레', '스타드림퀼츠', '아트지', '스노우지', '랑데부', '양상블', '무광', '유광', '백상지'],
            "사이즈": ['A4', 'A5', 'A3', 'B4', 'B5', '90×54mm', '85×54mm', '600×1800mm', '150×300mm', '200×400mm'],
            "후가공": ['형압', '박', '오시', '절취선', '도무송', '넘버링'],
            "코팅": ['유광', '무광', '스팟 UV', '에폭시'],
            "종류": ['싱글', '시트', '롤', '데칼', '띠부'],
            "거치대": ['미니배너 거치대', '실내 거치대', '실외 거치대'],
            "가공": ['사방 아일렛', '열재단', '각목막대'],
            "접지": ['2단', '3단']
        }
        
        patterns = keyword_patterns.get(option_type, [])
        found_options = []
        
        for pattern in patterns:
            if pattern in content:
                found_options.append(pattern)
        
        return list(set(found_options))
    
    def process_user_message(self, message: str, current_slots: Dict) -> Dict:
        """사용자 메시지 처리 (GPT-4-mini 기반)"""
        # GPT 사용 가능하면 GPT로 처리, 아니면 간단한 기본 응답
        if self.use_gpt:
            try:
                return self._process_conversation_with_gpt(message, current_slots)
            except Exception as e:
                print(f"GPT 처리 오류: {e}")
                return self._simple_fallback_response(message, current_slots)
        else:
            return self._simple_fallback_response(message, current_slots)
    
    def _process_conversation_with_gpt(self, message: str, current_slots: Dict) -> Dict:
        """GPT-4-mini로 대화 처리"""
        print(f"GPT 처리 시작 - 메시지: {message}")  # 디버깅 로그
        
        # 대화 히스토리 업데이트 (이미 로드된 경우 중복 방지)
        if not self.conversation_manager.conversation_history or \
           self.conversation_manager.conversation_history[-1]['content'] != message:
            self.conversation_manager.add_message('user', message)
        
        # DB 컨텍스트 생성
        db_context = self.db_formatter.format_context_for_gpt()
        
        # 대화 컨텍스트 생성
        conversation_context = self.conversation_manager.get_recent_context()
        
        # GPT 프롬프트 생성
        prompt = self._create_gpt_prompt(message, current_slots, db_context, conversation_context)
        print(f"GPT 프롬프트 생성 완료")  # 디버깅 로그
        
        # GPT API 호출
        response = self.gpt_client.process_conversation(prompt)
        print(f"GPT API 응답: {response}")  # 디버깅 로그
        
        # 응답 처리
        return self._process_gpt_response(response, current_slots)
    
    def _create_gpt_prompt(self, message: str, current_slots: Dict, db_context: str, conversation_context: str) -> str:
        """GPT 프롬프트 생성"""
        # 카테고리별 필수 슬롯 정의
        required_slots = {
            '명함': ['quantity', 'size', 'paper', 'printing', 'finishing'],
            '배너': ['size', 'quantity', 'stand'],
            '포스터': ['paper', 'size', 'quantity', 'coating'],
            '스티커': ['type', 'size', 'quantity'],
            '현수막': ['size', 'quantity', 'processing'],
            '브로슈어': ['paper', 'folding', 'size', 'quantity']
        }
        common_tail = ['due_days', 'region', 'budget']  
        required = required_slots.get(self.category, []) + common_tail
        missing_slots = self.conversation_manager.get_missing_slots(required)
        
        prompt = f"""
너는 인쇄 전문 챗봇이다. 답변은 '순수 텍스트'로만 작성한다(마크다운 금지).
DB 정보와 대화 맥락을 바탕으로 자연스럽게 대화하고, 추천 시에는 이유를 반드시 덧붙인다.

=== 인쇄소 DB 정보 ===
{db_context}

=== 현재 상황 ===
카테고리: {self.category}
수집된 정보: {current_slots}
아직 필요한 정보: {missing_slots}
대화 상태: {self.conversation_manager.get_state()}

=== 전체 대화 히스토리 ===
{conversation_context}

=== 사용자 메시지 ===
{message}

=== 핵심 지시사항 ===
1. **자연어 이해**: 사용자의 다양한 표현을 자유롭게 이해하세요
   - "200부 가능해?" → 수량 정보로 인식
   - "아트지로 할래" → 용지 선택으로 인식
   - "양면으로" → 인쇄 방식으로 인식
   - "형압은 뭐야?" → 용어 설명 요청으로 인식

2. **DB 기반 응답**: 위의 DB 정보만을 바탕으로 정확한 정보 제공
3. **자연스러운 대화**: 친근하고 자연스러운 톤으로 대화
4. **맥락 이해**: 이전 대화를 고려하여 적절한 응답
5. **상태 기억**: 이미 수집된 정보는 다시 묻지 말고 다음 단계로 진행
6. **슬롯 업데이트**: 사용자 메시지에서 정보를 추출하여 적절한 슬롯에 저장

=== 가독성 개선 지침 ===
7. **정보 요약 시 가독성**: 수집된 정보를 요약할 때는 다음과 같이 작성하세요:
   ```
   **현재까지 수집된 정보:**
   
   • 수량: 400부
   • 사이즈: 기본
   • 용지: 모조지
   • 인쇄 방식: 단면
   • 후가공: 칼라
   • 지역: 중구
   
   이제 **예산**(예: 50,000원, 100,000원 등)을 알려주시면, 
   **최종 견적 리포트를 생성할 수 있습니다!**
   ```

=== 응답 작성 규칙(중요) ===
- 말투: 친절하고 담백. 과장 금지. 이모지는 가끔만.
- 마크다운 금지(굵게/헤더/코드블록/표/링크 포맷 X). 불릿이 필요하면 하이픈(-)만 사용.
- 정보 수집 단계에선 한 번에 하나씩 물어보고, 이미 받은 값은 재확인만 한다.
- 용어 설명 요청엔 짧은 정의 + 언제 쓰면 좋은지 + 유의점 1개를 준다.
- 추천/선택지 요청일 때 구조:
    - 이렇게 추천해요: [핵심 제안 1줄]
    - 이유: [핵심 근거 1~3줄]
    - 대안: [상황 바뀔 때 선택지 1~2개]
    - 다음으로 할 일: [사용자의 다음 입력/행동 가이드]

=== 중요: 견적 완료 시 처리 방식 ===
7. **견적 리포트 생성**: 모든 정보 수집 완료 시 주문 진행이 아닌 견적 리포트 제공
   - 사용자가 "네", "확인", "좋아" 등으로 최종 확인 시
   - 견적 리포트와 추천 인쇄소 TOP3를 제공
   - 주문 진행 메시지 대신 "견적 리포트를 생성하겠습니다"라고 응답

=== 처리 방식 ===
- **정보 수집**: 사용자 메시지에서 관련 정보 추출하여 슬롯 업데이트
- **용어 설명**: DB에 있는 용어에 대해 상세히 설명
- **수정 요청**: 사용자가 수정하고 싶어하는 부분 파악
- **확인 요청**: 수집된 정보 확인 및 다음 단계 안내
- **견적 리포트**: 모든 정보 수집 완료 시 견적 리포트 + 추천 인쇄소 TOP3 제공

=== 응답 형식 ===
JSON 형태로 응답해주세요:
{{
    "action": "ask/explain/modify/confirm/quote",
    "message": "사용자에게 보낼 자연스러운 순수 텍스트",
    "slots": {{"quantity": "200부", "paper": "아트지"}},
    "next_question": "다음 질문 (선택적)"
}}

=== 견적 완료 시 예시 ===
사용자가 "네", "확인", "좋아" 등으로 최종 확인 시:
{{
    "action": "quote",
    "message": "견적 리포트를 생성하겠습니다! 수집된 정보를 바탕으로 최적의 인쇄소를 추천해드릴게요.",
    "slots": {{"quantity": "200부", "paper": "아트지", "printing": "양면", "finishing": "형압"}}
}}

**중요**: 
1. 사용자의 의도를 정확히 파악하고, DB 정보를 바탕으로 유용한 응답을 제공하세요.
2. 모든 정보 수집 완료 시 주문 진행이 아닌 견적 리포트를 제공하세요.
3. "주문을 진행하겠습니다" 대신 "견적 리포트를 생성하겠습니다"라고 응답하세요.
"""
        return prompt
    
    def _process_gpt_response(self, response: Dict, current_slots: Dict) -> Dict:
        """GPT 응답 처리"""
        print(f"=== GPT 응답 처리 디버깅 시작 ===")
        print(f"GPT 원본 응답: {response}")
        print(f"GPT 응답 타입: {type(response)}")
        
        if 'error' in response:
            print(f"GPT 오류 발생: {response['error']}")
            return self._simple_fallback_response("", current_slots)
        
        # 응답이 없거나 잘못된 경우 간단한 폴백
        if 'message' not in response or not response['message']:
            print("GPT 응답에 메시지가 없음 - 간단한 폴백 처리")
            return self._simple_fallback_response("", current_slots)
        
        # 슬롯 업데이트
        if 'slots' in response and response['slots']:
            try:
                coerced = _coerce_numbers(response['slots']) # 숫자/금액/지역 정규화
                current_slots.update(coerced)
                self.conversation_manager.update_slots(coerced)
                print(f"슬롯 업데이트: {coerced}")
            except Exception as e:
                print(f"슬롯 업데이트 중 오류: {e}")
        
        # 대화 히스토리에 응답 추가 (중복 방지)
        if 'message' in response:
            try:
                if not self.conversation_manager.conversation_history or \
                    self.conversation_manager.conversation_history[-1]['content'] != response['message']:
                    self.conversation_manager.add_message('assistant', response['message'])
            except Exception as e:
                print(f"대화 히스토리 업데이트 중 오류: {e}")
        
        # 견적 완료 시 견적 리포트 생성
        if response.get('action') == 'quote':
            print("견적 완료 - 견적 리포트 생성 시작")
            try:
                quote_result = self.calculate_quote(current_slots)
                print(f"견적 계산 결과: {quote_result}")
                response['message'] = self._format_final_quote(quote_result)
                response['quote_data'] = quote_result
                print("견적 리포트 생성 완료")
            except Exception as e:
                print(f"견적 리포트 생성 중 오류: {e}")
                return self._simple_fallback_response("", current_slots)
        
        print(f"=== GPT 응답 처리 완료 ===")
        return response
    
    def _simple_fallback_response(self, message: str, current_slots: Dict) -> Dict:
        """GPT 실패 시 간단한 기본 응답"""
        return {
                'action': 'ask',
            'message': '죄송합니다. AI 서비스에 일시적인 문제가 있습니다. 다시 한 번 말씀해주세요.',
                'slots': current_slots
            }
    
    # GPT가 모든 자연어 처리를 담당하므로 하드코딩된 키워드 매칭 로직 제거
    # 대신 GPT 프롬프트에서 DB 정보를 제공하여 자유롭게 처리하도록 함
    
    def _is_all_slots_filled(self, slots: Dict) -> bool:
        """모든 슬롯이 채워졌는지 확인"""
        category_flows = {
            '명함': ['quantity', 'size', 'paper', 'printing', 'finishing'],
            '배너': ['size', 'quantity', 'stand'],
            '포스터': ['paper', 'size', 'quantity', 'coating'],
            '스티커': ['type', 'size', 'quantity'],
            '현수막': ['size', 'quantity', 'processing'],
            '브로슈어': ['paper', 'folding', 'size', 'quantity']
        }
        
        flow = category_flows.get(self.category, [])
        return all(slot in slots and slots[slot] for slot in flow)
    
    def _get_next_question(self, slots: Dict) -> str:
        """다음 질문 생성"""
        category_flows = {
            '명함': ['quantity', 'size', 'paper', 'printing', 'finishing'],
            '배너': ['size', 'quantity', 'stand'],
            '포스터': ['paper', 'size', 'quantity', 'coating'],
            '스티커': ['type', 'size', 'quantity'],
            '현수막': ['size', 'quantity', 'processing'],
            '브로슈어': ['paper', 'folding', 'size', 'quantity']
        }
        common_tail = ['due_days', 'region', 'budget']
        flow = category_flows.get(self.category, []) + common_tail
        
        for slot in flow:
            if slot not in slots or not slots[slot]:
                return self._get_question_for_slot(slot)
        
        return "모든 정보가 수집되었습니다!"
    
    def _format_confirmation_message(self, slots: Dict) -> str:
        """확인 메시지 포맷팅"""
        title = f"{self.category} 견적 정보 확인"
        lines = [title, ""]
        slot_names = {
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
            'due_days': '납기(일)',
            'region': '지역',
            'budget': '예산(원)',
        }
        
        for k, v in slots.items():
            if v and k in slot_names:
                lines.append(f"- {slot_names[k]}: {v}")
        lines.append("")
        lines.append("위 내용이 맞을까요?")
        return "\n".join(lines)
    
    def calculate_quote(self, slots: Dict) -> Dict:
        """원큐스코어(가격40+납기30+작업30) 기반 TOP3 추천 + 전체 후보 리스팅"""
        print(f"견적 계산(ONEQ SCORE) - 카테고리: {self.category}, 슬롯: {slots}")
        print(f"등록된 인쇄소 수: {len(self.printshops)}")

        if not self.printshops:
            return {'error': '등록된 인쇄소가 없습니다.'}

        # 카테고리 정보가 slots['category']에 없을 수 있으니 보강
        slots = dict(slots or {})
        slots.setdefault("category", self.category)

        ranked = score_and_rank(slots, self.printshops)
        if ranked["count"] == 0:
            return {'error': '조건에 맞는 인쇄소가 없습니다. 정보를 다시 확인해주세요.'}

        # 기존 포맷과 호환되게 가공
        quotes = []
        for r in ranked["all"]:
            quotes.append({
                'printshop_name': r['shop_name'],
                'printshop_phone': r['phone'],
                'base_price': int(r['total_price'] / max(1, _to_int(slots.get("quantity"), 1))),  # 대략 단가
                'quantity': _to_int(slots.get("quantity"), 1),
                'total_price': r['total_price'],
                'production_time': r['production_time'],
                'delivery_options': r['delivery_options'],
                'is_verified': r['is_verified'],
                # 디버깅/표시용
                'oneq_scores': r['scores'],   # {'price':..,'due':..,'work':..,'oneq_total':..}
                'eta_hours': r['eta_hours'],
            })

        # TOP3: 기존 키 사용(recommendation_score/_reason)
        top3 = []
        for r in ranked["items"]:
            score = r['scores']['oneq_total']
            pr, du, wk = r['scores']['price'], r['scores']['due'], r['scores']['work']
            reason = f"가격 {pr:.0f} / 납기 {du:.0f} / 작업 {wk:.0f}"
            top3.append({
                'printshop_name': r['shop_name'],
                'printshop_phone': r['phone'],
                'base_price': int(r['total_price'] / max(1, _to_int(slots.get("quantity"), 1))),
                'quantity': _to_int(slots.get("quantity"), 1),
                'total_price': r['total_price'],
                'production_time': r['production_time'],
                'delivery_options': r['delivery_options'],
                'is_verified': r['is_verified'],
                'recommendation_score': score,            # 기존 포맷 호환
                'recommendation_reason': reason
            })

        return {
            'category': self.category,
            'slots': slots,
            'quotes': quotes,
            'top3_recommendations': top3,
            'total_available': len(quotes)
        }
    
    def _calculate_single_quote(self, printshop: PrintShop, slots: Dict) -> Optional[Dict]:
        """단일 인쇄소 견적 계산"""
        try:
            # 기본 가격 (임시)
            base_price = 1000
            
            # 옵션별 가격 추가
            if 'paper' in slots:
                base_price += 500
            
            if 'finishing' in slots:
                base_price += 1000
            
            if 'coating' in slots:
                base_price += 800
            
            # 수량 할인
            quantity = slots.get('quantity', 1)
            # 수량을 숫자로 변환 (예: "200부" -> 200)
            if isinstance(quantity, str):
                quantity = int(''.join(filter(str.isdigit, quantity)))
            else:
                quantity = int(quantity)
            
            if quantity >= 100:
                base_price = int(base_price * 0.9)  # 10% 할인
            elif quantity >= 500:
                base_price = int(base_price * 0.8)  # 20% 할인
            
            total_price = base_price * quantity
            
            return {
                'printshop_name': printshop.name,
                'printshop_phone': printshop.phone,
                'base_price': base_price,
                'quantity': quantity,
                'total_price': total_price,
                'production_time': printshop.production_time,
                'delivery_options': printshop.delivery_options,
                'is_verified': printshop.is_verified
            }
        except Exception as e:
            return None
    
    def _get_top3_recommendations(self, quotes: List[Dict], slots: Dict) -> List[Dict]:
        """추천 인쇄소 TOP3 선택 (가격, 품질, 서비스 등 종합 고려)"""
        if not quotes:
            return []
        
        # 각 인쇄소에 점수 부여
        scored_quotes = []
        for quote in quotes:
            score = self._calculate_recommendation_score(quote, slots)
            scored_quotes.append({
                **quote,
                'recommendation_score': score,
                'recommendation_reason': self._get_recommendation_reason(quote, score)
            })
        
        # 점수순으로 정렬하여 TOP3 선택
        sorted_quotes = sorted(scored_quotes, key=lambda x: x['recommendation_score'], reverse=True)
        return sorted_quotes[:3]
    
    def _calculate_recommendation_score(self, quote: Dict, slots: Dict) -> float:
        """추천 점수 계산 (0-100점)"""
        score = 0.0
        
        # 1. 가격 점수 (40점) - 낮을수록 높은 점수
        total_price = quote.get('total_price', 0)
        if total_price > 0:
            # 가격이 낮을수록 높은 점수 (최대 40점)
            price_score = max(0, 40 - (total_price / 1000))  # 1000원당 1점 차감
            score += price_score
        
        # 2. 품질 점수 (30점) - 인증된 인쇄소 우대
        if quote.get('is_verified', False):
            score += 30
        else:
            score += 15
        
        # 3. 서비스 점수 (20점) - 배송 옵션, 제작 기간 등
        delivery_options = quote.get('delivery_options', '')
        if '당일' in delivery_options or '익일' in delivery_options:
            score += 20
        elif '택배' in delivery_options:
            score += 15
        else:
            score += 10
        
        # 4. 수량 할인 점수 (10점) - 대량 주문 시 할인율 고려
        quantity = slots.get('quantity', 0)
        if isinstance(quantity, str):
            quantity = int(''.join(filter(str.isdigit, quantity)))
        
        if quantity >= 500:
            score += 10
        elif quantity >= 200:
            score += 7
        elif quantity >= 100:
            score += 5
        
        return min(100, score)
    
    def _get_recommendation_reason(self, quote: Dict, score: float) -> str:
        """추천 이유 생성"""
        reasons = []
        
        if quote.get('is_verified', False):
            reasons.append("인증된 인쇄소")
        
        total_price = quote.get('total_price', 0)
        if total_price < 50000:
            reasons.append("합리적인 가격")
        elif total_price < 100000:
            reasons.append("경제적인 가격")
        
        delivery_options = quote.get('delivery_options', '')
        if '당일' in delivery_options:
            reasons.append("당일 배송 가능")
        elif '익일' in delivery_options:
            reasons.append("익일 배송 가능")
        
        if not reasons:
            reasons.append("안정적인 서비스")
        
        return ", ".join(reasons)
    
    def _format_final_quote(self, quote_result: Dict) -> str:
        """최종 견적 리포트 포맷팅"""
        if 'error' in quote_result:
            return f"죄송합니다. {quote_result['error']}"
        
        response = f"{self.category} 최종 견적 리포트\n"
        response += "=" * 50 + "\n\n"
        
        # 수집된 정보 요약
        slots = quote_result['slots']
        response += "주문 정보:\n"
        slot_names = {
            'quantity': '수량',
            'paper': '용지',
            'size': '사이즈',
            'printing': '인쇄 방식',
            'finishing': '후가공',
            'coating': '코팅',
            'type': '종류',
            'stand': '거치대',
            'processing': '가공',
            'folding': '접지'
        }
        
        for key, value in slots.items():
            if value and key in slot_names:
                response += f"• {slot_names[key]}: {value}\n"
        
        response += f"\n견적 현황:\n"
        response += f"• 총 {quote_result.get('total_available', 0)}개 인쇄소에서 견적 가능\n"
        response += f"• 가격대: {self._get_price_range(quote_result['quotes'])}\n\n"
        
        response += "추천 인쇄소 TOP3:\n"
        response += "-" * 30 + "\n"
        
        # TOP3 추천
        top3_recommendations = quote_result.get('top3_recommendations', [])
        for i, quote in enumerate(top3_recommendations, 1):
            response += f"{i}위. {quote['printshop_name']}\n"
            response += f"   추천 점수: {quote.get('recommendation_score', 0):.1f}점\n"
            response += f"   추천 이유: {quote.get('recommendation_reason', '안정적인 서비스')}\n"
            response += f"   연락처: {quote['printshop_phone']}\n"
            response += f"   단가: {quote['base_price']:,}원\n"
            response += f"   총액: {quote['total_price']:,}원\n"
            response += f"   제작기간: {quote['production_time']}\n"
            response += f"   배송: {quote['delivery_options']}\n"
            if quote.get('is_verified', False):
                response += f"   인증된 인쇄소\n"
            response += "\n"
        
        response += "다음 단계:\n"
        response += "• 추천 인쇄소에 직접 연락하여 주문 진행\n"
        response += "• 디자인 파일 준비: AI, PSD, PDF, JPG 등 원본 파일과 함께 견적서를 가져가시면 됩니다\n"
        response += "• 추가 문의사항이 있으시면 언제든 말씀해주세요!\n"
        response += "• 다른 옵션으로 견적을 다시 받고 싶으시면 '다시 견적받기'라고 말씀해주세요."
        
        return response
    
    def _get_price_range(self, quotes: List[Dict]) -> str:
        """가격대 범위 계산"""
        if not quotes:
            return "견적 정보 없음"
        
        prices = [quote.get('total_price', 0) for quote in quotes]
        min_price = min(prices)
        max_price = max(prices)
        
        if min_price == max_price:
            return f"{min_price:,}원"
        else:
            return f"{min_price:,}원 ~ {max_price:,}원"
        
    
