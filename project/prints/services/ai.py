# prints/services/ai.py
import json
import re
from typing import Dict, List
from datetime import datetime
from ..models import PrintShop
from .gpt_client import GPTClient
from .db_formatter import DBFormatter
from .conversation_manager import ConversationManager
from .oneqscore import score_and_rank
from . import spec


def _to_int(v, default=0):
    if isinstance(v, int): 
        return v
    s = str(v or "")
    s = re.sub(r"[^\d]", "", s)
    return int(s) if s else default

def _to_money(v, default=0):
    """
    '15만원', '120,000원', '7만 5천원', '200000', '10만원이하', '5만원이상' 등을 정규화 → 원 단위 정수
    범위 표현도 처리 (이하/이상/미만/초과)
    """
    if v is None:
        return default
    
    s = str(v).strip().replace(",", "").replace(" ", "")
    
    # 범위 표현 처리
    if "이하" in s or "미만" in s:
        s = s.replace("이하", "").replace("미만", "")
        is_max = True
    elif "이상" in s or "초과" in s:
        s = s.replace("이상", "").replace("초과", "")
        is_max = False
    else:
        is_max = None
    
    # 완전 숫자만: 그대로
    if s.isdigit():
        amount = int(s)
        return amount if is_max is None else amount
    
    # '만원' 단위
    m = re.match(r"^(\d+)(만|만원)$", s)
    if m:
        amount = int(m.group(1)) * 10000
        return amount if is_max is None else amount
    
    # '천원'
    m = re.match(r"^(\d+)(천|천원)$", s)
    if m:
        amount = int(m.group(1)) * 1000
        return amount if is_max is None else amount
    
    # '원' 접미사
    m = re.match(r"^(\d+)원$", s)
    if m:
        amount = int(m.group(1))
        return amount if is_max is None else amount
    
    # 섞여있을 때 숫자만 추출 (마지막 fallback)
    digits = re.sub(r"[^\d]", "", s)
    if digits:
        amount = int(digits)
        return amount if is_max is None else amount
    
    return default

def _norm_region(v: str) -> str:
    if not v:
        return ""
    s = str(v).strip()
    s = s.replace("/", "-").replace("_", "-")
    # "서울 중구" → "서울-중구" 식으로 첫 공백만 하이픈으로
    s = re.sub(r"\s+", " ", s)
    if " " in s and "-" not in s:
        parts = s.split(" ")
        if len(parts) >= 2:
            s = parts[0] + "-" + parts[1]
    # 최종적으로 공백 제거
    return s.replace(" ", "")


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
        """카테고리에 맞는 인쇄소만 필터링(한글/영문 동시 지원 + 공백/형태 보정)"""
        print("=== 인쇄소 조회 디버깅 시작 ===")
        print(f"요청된 카테고리: {category}")
        print(f"카테고리 타입: {type(category)}")

        if not category:
            print("카테고리 없음 - 빈 목록 반환")
            return []

        # 1) 표준 매핑 + 별칭 집합(영/한글 동시 허용)
        category_mapping = {
            "명함": "card",
            "배너": "banner",
            "포스터": "poster",
            "스티커": "sticker",
            "현수막": "banner2",
            "브로슈어": "brochure",
        }
        aliases = {
            "명함": {"명함", "card", "business_card"},
            "배너": {"배너", "banner", "rollup"},
            "포스터": {"포스터", "poster"},
            "스티커": {"스티커", "sticker", "label"},
            "현수막": {"현수막", "banner2", "banner", "largebanner", "large_banner"},
            "브로슈어": {"브로슈어", "brochure", "leaflet", "pamphlet"},
        }

        # 2) 정규화 함수: 모든 공백 제거 + 소문자
        def _norm(s):
            if s is None:
                return ""
            s = str(s)
            s = "".join(s.split())  # 모든 공백(스페이스/개행/탭) 제거 → "포스 터" → "포스터"
            return s.lower()

        kor_cat = str(category).strip()
        eng_cat = category_mapping.get(kor_cat)
        target_set = set()
        target_set.add(_norm(kor_cat))
        if eng_cat:
            target_set.add(_norm(eng_cat))
        # 별칭 병합
        for alias in aliases.get(kor_cat, set()):
            target_set.add(_norm(alias))

        print(f"정규화된 타겟 토큰: {sorted(list(target_set))}")

        # 3) 활성/등록완료 인쇄소 조회
        all_printshops = PrintShop.objects.filter(
            is_active=True,
            registration_status="completed",
        )
        print(f"활성화된 인쇄소 수: {all_printshops.count()}")

        filtered_printshops = []

        import json as _json

        for shop in all_printshops:
            raw = shop.available_categories or []
            # 문자열로 저장된 경우 처리
            if isinstance(raw, str):
                raw_str = raw.strip()
                parsed = None
                # JSON 리스트 문자열 시도: '["포스터","배너"]'
                if (raw_str.startswith("[") and raw_str.endswith("]")) or (raw_str.startswith('"') and raw_str.endswith('"')):
                    try:
                        parsed = _json.loads(raw_str)
                    except Exception:
                        parsed = None
                if parsed is None:
                    # 콤마 구분 문자열 시도: "포스터, 배너"
                    parsed = [p.strip() for p in raw_str.split(",") if p.strip()]
                available = parsed
            elif isinstance(raw, list):
                available = raw
            else:
                available = []

            # 항목 정규화
            avail_norm = {_norm(x) for x in available if x}

            # 매칭 여부
            ok = bool(target_set & avail_norm)

            print(f"- {shop.name}")
            print(f"  원본 카테고리: {available}")
            print(f"  정규화 카테고리: {sorted(list(avail_norm))}")
            print(f"  매칭 여부: {ok}")

            if ok:
                filtered_printshops.append(shop)

        print(f"\n=== 최종 필터링된 인쇄소 수: {len(filtered_printshops)} ===")
        return filtered_printshops



    
    def _get_category_info(self) -> Dict:
        """카테고리별 정보 수집"""
        if not self.printshops: # 등록된 인쇄소가 없다면 빈 딕셔너리 반환환
            return {}
        
        combined_info = {} # 카테고리별 정보를 저장할 딕셔너리
        
        category_fields = { # 각 카테고리마다 필요한 DB 필드들을 정의
            '명함': ['business_card_paper_options', 'business_card_printing_options', 'business_card_finishing_options', 'business_card_quantity_price_info'],
            '배너': ['banner_size_options', 'banner_stand_options', 'banner_quantity_price_info'],
            '포스터': ['poster_paper_options', 'poster_coating_options', 'poster_quantity_price_info'],
            '스티커': ['sticker_type_options', 'sticker_size_options', 'sticker_quantity_price_info'],
            '현수막': ['banner_large_size_options', 'banner_large_processing_options', 'banner_large_quantity_price_info'],
            '브로슈어': ['brochure_paper_options', 'brochure_size_options', 'brochure_folding_options', 'brochure_quantity_price_info']
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
        flow = spec.CATEGORY_SLOT_FLOW.get(self.category, [])
        return flow[0][1] if flow else "어떤 정보가 필요하신가요?"

    
    def _get_question_for_slot(self, slot: str) -> str:
        """슬롯별 질문 생성 (DB 정보 포함)"""
        questions = {
            'quantity': '수량은 얼마나 하실 건가요?', # 수량은 자유 입력이므로 바로 질문(DB 조회 불필요)
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
            # 가격 정보 제거하고 옵션명만 표시
            clean_papers = []
            for paper in papers:
                # 가격 정보가 포함된 경우 제거 (예: "아트지(1000원)" -> "아트지")
                if '(' in paper and '원' in paper:
                    clean_papers.append(paper.split('(')[0].strip())
                else:
                    clean_papers.append(paper)
            return f"용지는 어떤 걸로 하시겠어요? ({', '.join(clean_papers)})"
        return "용지는 어떤 걸로 하시겠어요?"
    
    def _get_size_question(self) -> str:
        """사이즈 질문 (DB 정보 포함)"""
        # 명함과 포스터는 기본 사이즈 옵션 제공하되 유연하게 처리
        if self.category == "명함":
            return "사이즈는 어떻게 하시겠어요? (90×54mm, 85×54mm, 90×50mm, 85×50mm 등 - 원하시는 사이즈 말씀해주세요)"
        elif self.category == "포스터":
            return "사이즈는 어떻게 하시겠어요? (A4, A3, A2, A1, A0, B4, B3, B2, B1 등 - 원하시는 사이즈 말씀해주세요)"
        
        # 다른 카테고리는 기존 로직 유지
        sizes = self._extract_sizes_from_db()
        if sizes:
            # 가격 정보 제거하고 옵션명만 표시
            clean_sizes = []
            for size in sizes:
                # 가격 정보가 포함된 경우 제거
                if '(' in size and '원' in size:
                    clean_sizes.append(size.split('(')[0].strip())
                else:
                    clean_sizes.append(size)
            return f"사이즈는 어떻게 하시겠어요? ({', '.join(clean_sizes)})"
        return "사이즈는 어떻게 하시겠어요?"
    
    def _get_finishing_question(self) -> str:
        """후가공 질문 (DB 정보 포함)"""
        finishing_options = self._extract_finishing_from_db()
        if finishing_options:
            # 가격 정보 제거하고 옵션명만 표시
            clean_options = []
            for option in finishing_options:
                # 가격 정보가 포함된 경우 제거
                if '(' in option and '원' in option:
                    clean_options.append(option.split('(')[0].strip())
                else:
                    clean_options.append(option)
            return f"후가공 옵션은 어떤 걸 원하시나요? ({', '.join(clean_options)})"
        return "후가공 옵션은 어떤 걸 원하시나요?"
    
    def _get_coating_question(self) -> str:
        """코팅 질문 (DB 정보 포함)"""
        coating_options = self._extract_coating_from_db()
        if coating_options:
            # 가격 정보 제거하고 옵션명만 표시
            clean_options = []
            for option in coating_options:
                # 가격 정보가 포함된 경우 제거
                if '(' in option and '원' in option:
                    clean_options.append(option.split('(')[0].strip())
                else:
                    clean_options.append(option)
            return f"코팅 옵션은 어떤 걸 원하시나요? ({', '.join(clean_options)})"
        return "코팅 옵션은 어떤 걸 원하시나요?"
    
    def _get_type_question(self) -> str:
        """종류 질문 (DB 정보 포함)"""
        types = self._extract_types_from_db()
        if types:
            # 가격 정보 제거하고 옵션명만 표시
            clean_types = []
            for type_option in types:
                # 가격 정보가 포함된 경우 제거
                if '(' in type_option and '원' in type_option:
                    clean_types.append(type_option.split('(')[0].strip())
                else:
                    clean_types.append(type_option)
            return f"어떤 종류로 하시겠어요? ({', '.join(clean_types)})"
        return "어떤 종류로 하시겠어요?"
    
    def _get_stand_question(self) -> str:
        """거치대 질문 (DB 정보 포함)"""
        stands = self._extract_stands_from_db()
        if stands:
            # 가격 정보 제거하고 옵션명만 표시
            clean_stands = []
            for stand in stands:
                # 가격 정보가 포함된 경우 제거
                if '(' in stand and '원' in stand:
                    clean_stands.append(stand.split('(')[0].strip())
                else:
                    clean_stands.append(stand)
            return f"거치대는 어떤 걸 원하시나요? ({', '.join(clean_stands)})"
        return "거치대는 어떤 걸 원하시나요?"
    
    def _get_processing_question(self) -> str:
        """가공 질문 (DB 정보 포함)"""
        processing_options = self._extract_processing_from_db()
        if processing_options:
            # 가격 정보 제거하고 옵션명만 표시
            clean_options = []
            for option in processing_options:
                # 가격 정보가 포함된 경우 제거
                if '(' in option and '원' in option:
                    clean_options.append(option.split('(')[0].strip())
                else:
                    clean_options.append(option)
            return f"추가 가공 옵션은 어떤 걸 원하시나요? ({', '.join(clean_options)})"
        return "추가 가공 옵션은 어떤 걸 원하시나요?"
    
    def _get_folding_question(self) -> str:
        """접지 질문 (DB 정보 포함)"""
        folding_options = self._extract_folding_from_db()
        if folding_options:
            # 가격 정보 제거하고 옵션명만 표시
            clean_options = []
            for option in folding_options:
                # 가격 정보가 포함된 경우 제거
                if '(' in option and '원' in option:
                    clean_options.append(option.split('(')[0].strip())
                else:
                    clean_options.append(option)
            return f"접지 방식은 어떤 걸 원하시나요? ({', '.join(clean_options)})"
        return "접지 방식은 어떤 걸 원하시나요?"
    
    # DB에서 정보 추출 함수 (자연어 처리 기반)
    def _extract_papers_from_db(self) -> List[str]:
        """DB에서 용지 정보 추출 (GPT 활용)"""
        paper_fields = {
            '명함': 'business_card_paper_options',
            '포스터': 'poster_paper_options',
            '브로슈어': 'brochure_paper_options'
        }
        
        # 배너, 스티커, 현수막은 용지 정보가 없으므로 빈 리스트 반환
        if self.category not in paper_fields:
            return []
        
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
            '포스터': 'poster_paper_options',  # 포스터는 용지 옵션에서 사이즈 정보 추출
            '스티커': 'sticker_size_options',
            '현수막': 'banner_large_size_options',
            '브로슈어': 'brochure_size_options'
        }
        
        field = size_fields.get(self.category)
        if not field or field not in self.category_info:
            # 포스터의 경우 기본 사이즈 옵션 제공
            if self.category == '포스터':
                return ['A4', 'A3', 'A2', 'A1', 'A0', 'B4', 'B3', 'B2', 'B1']
            return []
        
        content = self.category_info[field]
        if not content:
            # 포스터의 경우 기본 사이즈 옵션 제공
            if self.category == '포스터':
                return ['A4', 'A3', 'A2', 'A1', 'A0', 'B4', 'B3', 'B2', 'B1']
            return []
        
        # 포스터의 경우 사이즈 정보가 용지 옵션에 포함되어 있을 수 있으므로
        # 먼저 사이즈 전용 필드에서 찾고, 없으면 용지 옵션에서 추출
        if self.category == '포스터':
            # 포스터 사이즈 전용 필드가 없으므로 용지 옵션에서 사이즈 정보 추출
            extracted_sizes = self._extract_options_with_gpt(content, "사이즈")
            if extracted_sizes:
                return extracted_sizes
            else:
                # 사이즈 정보가 없으면 기본 포스터 사이즈 제공
                return ['A4', 'A3', 'A2', 'A1', 'A0', 'B4', 'B3', 'B2', 'B1']
        
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
        try:
            # GPT 사용 가능하면 GPT로 처리, 아니면 간단한 기본 응답
            if self.use_gpt:
                try:
                    return self._process_conversation_with_gpt(message, current_slots)
                except Exception as e:
                    print(f"GPT 처리 오류: {e}")
                    return self._simple_fallback_response(message, current_slots)
            else:
                return self._simple_fallback_response(message, current_slots)
        except Exception as e:
            print(f"사용자 메시지 처리 중 오류: {e}")
            return self._simple_fallback_response(message, current_slots)
    
    def _process_conversation_with_gpt(self, message: str, current_slots: Dict) -> Dict:
        """GPT-4-mini로 대화 처리"""
        try:
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
        except Exception as e:
            print(f"GPT 대화 처리 중 오류: {e}")
            return self._simple_fallback_response(message, current_slots)
    
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
        required = spec.required_slots(self.category)
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
    - "그거로 할게" → 이전 질문에 대한 긍정적 응답으로 인식
    - "넵", "네", "좋아" → 확인/동의 응답으로 인식
    - 절대 '모든 정보가 수집되었습니다'라는 문구는 쓰지 마세요. 서버가 판단합니다.
    - 미싱 슬롯 목록 {missing_slots}가 비어 있지 않다면, '아직 필요한 정보: …' 형태로만 안내하세요.


2. **DB 기반 응답**: 위의 DB 정보만을 바탕으로 정확한 정보 제공
3. **자연스러운 대화**: 친근하고 자연스러운 톤으로 대화
4. **맥락 이해**: 이전 대화를 고려하여 적절한 응답
5. **상태 기억**: 이미 수집된 정보는 다시 묻지 말고 다음 단계로 진행, 이미 채워진 슬롯은 절대 다시 묻지 말고 다음 미싱 슬롯만 하나씩 진행
6. **슬롯 업데이트**: 사용자 메시지에서 정보를 추출하여 적절한 슬롯에 저장
7. **가격 정보 제외**: 질문할 때는 가격 정보를 말하지 말고 옵션명만 제공하세요
 8. **카테고리별 질문 순서**: 반드시 현재 카테고리에 맞는 질문을 해야 합니다
    - 포스터: 용지 → 사이즈(A4, A3, A2 등) → 수량 → 코팅
    - 명함: 수량 → 사이즈(90x50mm 등) → 용지 → 인쇄방식 → 후가공
    - 배너: 사이즈 → 수량 → 거치대
    - 스티커: 종류 → 사이즈 → 수량
    - 현수막: 사이즈 → 수량 → 가공
    - 브로슈어: 용지 → 접지 → 사이즈 → 수량
    
         **중요**: 명함과 포스터는 대부분의 인쇄소가 표준 규격 용지를 보유하고 있어서, 사용자가 원하는 사이즈가 DB에 없어도 "네, 그 사이즈로 가능합니다"라고 응답하고 저장하세요. 인쇄소들이 일반적으로 A4, A3, B4, B5 등 표준 규격과 90×54mm, 85×54mm 등 명함 표준 사이즈를 처리할 수 있습니다.

9. **대화 흐름 관리**:
   - 한 번에 하나의 정보만 수집
   - 사용자가 여러 정보를 한 번에 말하면 순서대로 처리
   - 불명확한 답변 시 구체적으로 다시 질문
   - 다음 단계로 넘어가기 전 현재 정보 확인

10. **긍정적 접근**: "없다", "준비되지 않았다" 대신 "이것도 좋아요", "이것도 비슷한 효과를 낼 수 있어요"로 대안 제시

=== 응답 작성 규칙 ===
- **말투**: 친절하고 담백. 과장 금지. 이모지는 가끔만
- **마크다운 금지**: 굵게/헤더/코드블록/표/링크 포맷 X. 불릿이 필요하면 하이픈(-)만 사용
- **정보 수집**: 한 번에 하나씩 물어보고, 이미 받은 값은 재확인만
- **용어 설명**: 짧은 정의 + 언제 쓰면 좋은지 + 유의점 1개
- **추천 구조**: 핵심 제안 → 이유 → 대안 → 다음 단계 안내

=== 대화 상황별 응답 가이드 ===
1. **용어 설명 요청 시**:
   - 간단한 정의 (1-2문장) + 언제 사용하면 좋은지 (1문장) + 주의사항 (1문장)
   - 예시: "코트지는 매끄럽고 광택이 있는 표면을 가진 용지로, 색상이 선명하게 재현됩니다. 주로 사진이나 컬러가 강조되는 디자인에 적합합니다. 하지만 반사가 있을 수 있어 특정 조명 환경에서는 시인성이 떨어질 수 있습니다."

2. **확인/동의 응답 시**:
   - 선택한 옵션 확인 + 다음 단계 안내
   - 예시: "코트지로 결정하셨군요! 다음으로는 인쇄 방식을 선택해 주세요. 단면 인쇄로 하시겠어요, 아니면 양면 인쇄로 하시겠어요?"

3. **불명확한 답변 시**:
   - 구체적으로 다시 질문 + 선택지 명확히 제시
   - 예시: "어떤 사이즈를 원하시는지 명확하지 않네요. A4, A3, A2 중에서 선택해 주세요."

4. **수정 요청 시**:
   - 수정할 정보 확인 + 새로운 선택지 제시
   - 예시: "사이즈를 수정하고 싶으시군요. 어떤 사이즈로 변경하시겠어요? (A4, A3, A2)"

  5. **DB에 없는 정보 요청 시**:
    - 자연스럽게 대안으로 유도 + 긍정적 접근
    - 예시: "A0 사이즈 말고 A1 사이즈는 어떠세요? A1도 충분히 큰 포스터 제작에 적합하고, 가격도 더 합리적이에요."
    - 예시: "금박 후가공 대신 형압, 박, 도무송 중에서 선택하시면 어떨까요? 비슷한 고급스러운 효과를 낼 수 있어요."
    - **명함/포스터 사이즈**: 대부분의 인쇄소가 표준 규격 용지를 보유하고 있어서, 사용자가 원하는 사이즈가 DB에 없어도 "네, 그 사이즈로 가능합니다"라고 응답하고 저장하세요. 인쇄소들이 일반적으로 표준 규격을 처리할 수 있습니다.

 6. **범위 표현 처리**:
    - 사용자가 "10만원 이하", "3일 이내" 같은 범위를 말하면 그 범위 내에서 조회하도록 안내
    - 예시: "10만원 이하로 예산을 설정하셨군요. 그 범위 내에서 최적의 인쇄소를 찾아드릴게요."
    - 예시: "3일 이내 납기를 원하시는군요. 빠른 납기가 가능한 인쇄소들을 우선적으로 추천해드릴게요."

 7. **최적화 목표**:
    - 모든 조건을 맞는 인쇄소를 찾는 것이 아니라, 사용자 견적에 근접한 최적의 인쇄소를 찾는 것
    - 예시: "정확히 맞는 인쇄소가 없어도, 가장 근접한 조건의 인쇄소들을 추천해드릴게요."
    - 예시: "가격이 조금 더 나올 수 있지만, 품질과 납기를 고려한 최적의 선택을 제안드립니다."

6. **모든 정보 수집 완료 시**:
   - 수집된 정보 요약 + 최종 확인 요청
   - 예시: "모든 정보가 수집되었습니다. 확인해 주시면 최적의 인쇄소를 추천해드릴게요."

=== 정보 요약 형식 ===
수집된 정보를 요약할 때는 다음과 같이 작성하세요:
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

=== 견적 완료 시 처리 ===
- 모든 정보 수집 완료 시 주문 진행이 아닌 견적 리포트 제공
- "주문을 진행하겠습니다" 대신 "견적 리포트를 생성하겠습니다"라고 응답
- 사용자가 "네", "확인", "좋아" 등으로 최종 확인 시 견적 리포트와 추천 인쇄소 TOP3 제공

=== 최종 견적 리포트 출력 예시 ===
배너 최종 견적 리포트
==================================================

주문 정보:
• 사이즈: 600x1800mm
• 수량: 1개
• 거치대: 실내 거치대
• 납기: 3일
• 지역: 서울-중구
• 예산: 15만원

견적 현황:
• 총 5개 인쇄소에서 견적 가능
• 가격대: 120,000원 ~ 180,000원

추천 인쇄소 TOP3:
------------------------------
1위. ABC인쇄소
   추천 점수: 85.2점
   추천 이유: 가격 35 / 납기 28 / 작업 22
   연락처: 02-1234-5678
   단가: 150,000원
   총액: 150,000원
   제작기간: 3일
   배송: 택배 가능
   인증된 인쇄소

2위. DEF인쇄소
   추천 점수: 82.1점
   추천 이유: 가격 32 / 납기 30 / 작업 20
   연락처: 02-2345-6789
   단가: 160,000원
   총액: 160,000원
   제작기간: 2일
   배송: 직접수령 가능

3위. GHI인쇄소
   추천 점수: 78.5점
   추천 이유: 가격 30 / 납기 25 / 작업 23
   연락처: 02-3456-7890
   단가: 140,000원
   총액: 140,000원
   제작기간: 4일
   배송: 택배 가능

다음 단계:
• 추천 인쇄소에 직접 연락하여 주문 진행
• 디자인 파일 준비: AI, PSD, PDF, JPG 등 원본 파일과 함께 견적서를 가져가시면 됩니다
• 추가 문의사항이 있으시면 언제든 말씀해주세요!
• 다른 옵션으로 견적을 다시 받고 싶으시면 '다시 견적받기'라고 말씀해주세요.

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

=== 중요 원칙 ===
1. **사용자 의도 파악**: DB 정보를 바탕으로 유용한 응답 제공
2. **간단명료**: 복잡한 설명보다는 간단명료하게 답변
3. **명확한 안내**: 다음 단계가 무엇인지 항상 명확히 안내
4. **오류 처리**: 시스템 오류 시 "죄송합니다. 일시적인 문제가 있습니다. 다시 한 번 말씀해주세요."라고 응답
"""
        return prompt
    
    def _process_gpt_response(self, response: Dict, current_slots: Dict) -> Dict:
        try:
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

            # 슬롯 업데이트 (정규화)
            if 'slots' in response and response['slots']:
                try:
                    coerced = _coerce_numbers(response['slots'])
                    current_slots.update(coerced)
                    self.conversation_manager.update_slots(coerced)
                    response['slots'] = coerced
                    print(f"슬롯 업데이트(정규화): {coerced}")
                except Exception as e:
                    print(f"슬롯 업데이트 중 오류: {e}")

            # 견적 완료 시 견적 리포트 생성
            if response.get('action') == 'quote':
                print("견적 완료 - 견적 리포트 생성 시작")
                try:
                    quote_result = self.calculate_quote(current_slots)
                    print(f"견적 계산 결과: {quote_result}")

                    # 구조화 결과
                    response['quote_data'] = quote_result
                    response['final_quote'] = {
                        'quote_number': f"ONEQ-{datetime.now().strftime('%Y-%m%d-%H%M')}",
                        'created_date': datetime.now().strftime('%Y년 %m월 %d일'),
                        'category': self.category,
                        'slots': current_slots,
                        'recommendations': quote_result.get('top3_recommendations', []),
                        'total_available': quote_result.get('total_available', 0),
                        'price_range': self._get_price_range(quote_result.get('quotes', [])),
                        'formatted_message': self._format_final_quote(quote_result),
                        'order_summary': self._create_order_summary(current_slots)
                    }

                    # 사용자에게 '리포트 본문' 자체를 메시지로 보냄
                    response['message'] = response['final_quote']['formatted_message']
                    print("견적 리포트 생성 완료")
                except Exception as e:
                    print(f"견적 리포트 생성 중 오류: {e}")
                    return self._simple_fallback_response("", current_slots)

            print(f"=== GPT 응답 처리 완료(게이트 전) ===")
            # 누락 슬롯 게이트(미완료면 자연스럽게 다음 질문으로)
            response = self._gate_incomplete_slots(response, current_slots)

            # 최종 메시지를 히스토리에 이 시점에 기록 (게이트 반영 후/리포트 반영 후)
            try:
                final_msg = response.get('message', '')
                if final_msg and (
                    not self.conversation_manager.conversation_history or
                    self.conversation_manager.conversation_history[-1]['content'] != final_msg
                ):
                    self.conversation_manager.add_message('assistant', final_msg)
            except Exception as e:
                print(f"대화 히스토리 업데이트 중 오류: {e}")

            return response

        except Exception as e:
            print(f"GPT 응답 처리 중 오류: {e}")
            return self._simple_fallback_response("", current_slots)

    
    def _simple_fallback_response(self, message: str, current_slots: Dict) -> Dict:
        """GPT 실패 시 간단한 기본 응답"""
        return {
                'action': 'ask',
            'message': '죄송합니다. AI 서비스에 일시적인 문제가 있습니다. 다시 한 번 말씀해주세요.',
                'slots': current_slots
            }
    
    # GPT가 모든 자연어 처리를 담당하므로 하드코딩된 키워드 매칭 로직 제거
    # 대신 GPT 프롬프트에서 DB 정보를 제공하여 자유롭게 처리하도록 함
    

    
    def calculate_quote(self, slots: Dict) -> Dict:
        """원큐스코어(가격40+납기30+작업30) 기반 TOP3 추천 + 전체 후보 리스팅"""
        try:
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
        except Exception as e:
            print(f"견적 계산 오류: {e}")
            return {'error': f'견적 계산 중 오류가 발생했습니다: {str(e)}'}
    

    
    def _format_final_quote(self, quote_result: Dict) -> str:
        """최종 견적 리포트 포맷팅"""

        if not quote_result or 'error' in quote_result:
            return f"죄송합니다. {quote_result.get('error', '견적 정보를 생성할 수 없습니다.')}"
    
        # 수집된 정보 요약
        raw_slots = quote_result['slots'] or {}
        slots = {
            **raw_slots,
            'quantity': _to_int(raw_slots.get('quantity'), 0),
            'due_days': _to_int(raw_slots.get('due_days'), 0),
            'budget': _to_money(raw_slots.get('budget'), 0),
            'region': _norm_region(raw_slots.get('region', ''))
        }


        if 'error' in quote_result:
            return f"죄송합니다. {quote_result['error']}"
        
        response = f"{self.category} 최종 견적 리포트\n"
        response += "=" * 50 + "\n\n"
        
        # 수집된 정보 요약
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
    
    def _create_order_summary(self, slots: Dict) -> Dict:
        """주문 요약 정보 생성 (프론트엔드용)"""

        q = _to_int(slots.get('quantity'), 0)
        d = _to_int(slots.get('due_days'), 0)
        b = _to_money(slots.get('budget'), 0)
        r = _norm_region(slots.get('region', '없음'))

        summary = {
            'print_type': f"{slots.get('category', '')}",
            'size': slots.get('size', ''),
            'quantity': f"{q}부" if q else '',
            'paper': slots.get('paper', ''),
            'finishing': slots.get('finishing', ''),
            'coating': slots.get('coating', ''),
            'printing': slots.get('printing', ''),
            'due_days': f"{d}일" if d else '',
            'budget': f"{b:,}원" if b else '없음',
            'region': r or '없음'
        }
        
        # 카테고리별 특화 정보 추가
        if slots.get('category') == '명함':
            summary['print_type'] = f"명함 ({slots.get('size', '')})"
        elif slots.get('category') == '포스터':
            summary['print_type'] = f"포스터 ({slots.get('size', '')})"
        elif slots.get('category') == '배너':
            summary['print_type'] = f"배너 ({slots.get('size', '')})"
        elif slots.get('category') == '스티커':
            summary['print_type'] = f"스티커 ({slots.get('type', '')})"
        elif slots.get('category') == '현수막':
            summary['print_type'] = f"현수막 ({slots.get('size', '')})"
        elif slots.get('category') == '브로슈어':
            summary['print_type'] = f"브로슈어 ({slots.get('size', '')}, {slots.get('folding', '')}접지)"
        
        return summary
        
    def _gate_incomplete_slots(self, response: Dict, current_slots: Dict) -> Dict:
        """
        GPT 응답 이후, 실제 필수 슬롯 충족 여부를 서버에서 최종 검증/보정하는 게이트.
        - 미싱 슬롯이 있으면 action을 'ask'로 강제하고, 바로 다음 질문만 메시지로 내려보낸다.
        - 완료/견적 관련 필드는 제거해, 실수로 최종 단계로 넘어가지 못하게 한다.
        """
        effective = dict(current_slots or {})
        if 'slots' in response and isinstance(response['slots'], dict):
            effective.update(response['slots'])

        category = effective.get('category', self.category)
        req = spec.required_slots(category)
        missing = [k for k in req if not effective.get(k)]

        if missing:
            response['action'] = 'ask'
            response['type'] = 'ask'

            nq = spec.next_question(effective)  # {"slot": key, "question": "...", "choices": [...]}
            question = nq.get('question') or "다음 정보를 알려주세요."
            choices = nq.get('choices', [])

            # '질문'만 노출
            response['message'] = question
            response['question'] = question
            if choices:
                response['choices'] = choices

            # 견적 관련 필드 제거
            for k in ('quote_data', 'final_quote'):
                response.pop(k, None)

        return response




# 전역 AI 서비스 인스턴스 (카테고리별로 생성)
_ai_services = {}

def get_ai_service(category: str) -> PrintShopAIService:
    """카테고리별 AI 서비스 인스턴스 반환 (싱글톤 패턴)"""
    if category not in _ai_services:
        _ai_services[category] = PrintShopAIService(category)
    return _ai_services[category]

def ask_action(history: List[Dict], slots: Dict) -> Dict:
    """AI 액션 결정 (orchestrator에서 호출)"""
    try:
        # 카테고리 추출 (기본값: 포스터)
        category = slots.get('category', '포스터')
        ai_service = get_ai_service(category)
        
        # 마지막 사용자 메시지 추출
        user_message = ""
        if history:
            for msg in reversed(history):
                if msg.get('role') == 'user':
                    user_message = msg.get('content', '')
                    break
        
        # AI 서비스로 메시지 처리
        response = ai_service.process_user_message(user_message, slots)
        
        # 액션 표준화
        raw = (response.get('action') or '').strip().lower()
        if raw in ('ask', ''):
            act = 'ASK'
        elif raw in ('explain',):
            act = 'EXPLAIN'
        elif raw in ('confirm',):
            act = 'CONFIRM'
        elif raw in ('quote', 'match'):
            # 모든 필수 슬롯이 채워졌는지 최종 확인
            req = spec.required_slots(category)
            missing = [k for k in req if not (response.get('slots', {}).get(k) or slots.get(k))]
            act = 'MATCH' if not missing else 'ASK'
        else:
            act = 'ASK'

        # 응답 형식 통일
        return {
            'action': act,
            'message': response.get('message', ''),
            'filled_slots': response.get('slots', {}),
            'question': response.get('next_question', '')
        }
        
    except Exception as e:
        print(f"ask_action 오류: {e}")
        return {
            'action': 'ASK',
            'message': '죄송합니다. AI 서비스에 일시적인 문제가 있습니다. 다시 한 번 말씀해주세요.',
            'filled_slots': {},
            'question': ''
        }

def generate_quote_report(slots: Dict) -> str:
    """견적 리포트 생성"""
    try:
        category = slots.get('category', '포스터')
        ai_service = get_ai_service(category)
        quote_result = ai_service.calculate_quote(slots)
        return ai_service._format_final_quote(quote_result)
    except Exception as e:
        print(f"견적 리포트 생성 오류: {e}")
        return "죄송합니다. 견적 리포트 생성 중 오류가 발생했습니다."

def recommend_shops(slots: Dict) -> List[Dict]:
    """인쇄소 추천"""
    try:
        category = slots.get('category', '포스터')
        ai_service = get_ai_service(category)
        quote_result = ai_service.calculate_quote(slots)
        
        if 'error' in quote_result:
            return []
        
        return quote_result.get('top3_recommendations', [])
    except Exception as e:
        print(f"인쇄소 추천 오류: {e}")
        return []

def format_shop_recommendation(shop: Dict) -> str:
    """인쇄소 추천 정보 포맷팅"""
    try:
        return f"""🏢 {shop.get('printshop_name', '알 수 없음')}
📞 {shop.get('printshop_phone', '연락처 없음')}
💰 단가: {shop.get('base_price', 0):,}원
💵 총액: {shop.get('total_price', 0):,}원
⏰ 제작기간: {shop.get('production_time', '문의')}
🚚 배송: {shop.get('delivery_options', '문의')}
⭐ 원큐스코어: {shop.get('recommendation_score', 0):.1f}점
💡 추천이유: {shop.get('recommendation_reason', '안정적인 서비스')}"""
    except Exception as e:
        print(f"인쇄소 포맷팅 오류: {e}")
        return "인쇄소 정보를 불러올 수 없습니다."

def cached_polish(term: str, facts: Dict, user_msg: str) -> str:
    """용어 설명 생성 (캐시된 버전)"""
    try:
        if not facts:
            return f"'{term}'에 대해 간단히 설명드릴게요. {term}은 인쇄 제작에서 자주 사용되는 용어인데, 구체적인 정보는 현재 DB에서 확인 중이에요. 다른 옵션들도 함께 살펴보시면 어떨까요?"
        
        # 간단한 용어 설명 생성
        explanation = f"{term}에 대한 설명:\n\n"
        
        for key, value in facts.items():
            if isinstance(value, dict):
                explanation += f"• {key}: {value.get('description', '설명 없음')}\n"
            else:
                explanation += f"• {key}: {value}\n"
        
        return explanation
    except Exception as e:
        print(f"용어 설명 생성 오류: {e}")
        return f"'{term}'에 대해 설명드리려고 하는데, 다른 유용한 정보를 먼저 안내해드릴까요?"
        
    
