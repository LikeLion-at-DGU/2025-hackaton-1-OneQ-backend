# prints/services/spec.py
from __future__ import annotations
from typing import Dict, List, Tuple, Optional
import re

# === 카테고리별 슬롯 수집 순서/프롬프트 (요청안 그대로) ===
CATEGORY_SLOT_FLOW: Dict[str, List[Tuple[str, str]]] = {
    "명함": [
        ("paper", "명함용지종류를 선택해주세요. (예: 일반지, 고급지, 아트지, 코팅지)"),
        ("printing", "인쇄방식을 선택해주세요. (예: 단면 흑백, 단면 컬러, 양면 흑백, 양면 컬러)"),
        ("finishing", "후가공옵션을 선택해주세요. (예: 무광, 유광, 스팟, 엠보싱)"),
        ("quantity", "몇 부 필요하신가요? (예: 100부, 200부, 500부, 1000부)"),
        ("due_days", "납기는 며칠 후면 좋을까요? (예: 1일, 2일, 3일, 5일, 7일)"),
        ("region", "지역은 어디로 설정할까요? (예: 서울-중구, 서울-종로, 경기-성남)"),
        ("budget", "예산은 얼마로 설정하시겠어요? (예: 5만원, 10만원, 20만원)")
    ],
    "배너": [
        ("size", "배너 사이즈를 선택해주세요. (예: 1x3m, 2x4m, 3x6m)"),
        ("stand", "배너 거치대 종류를 선택해주세요. (예: X자형, A자형, 롤업형)"),
        ("quantity", "몇 부 필요하신가요? (예: 1개, 2개, 5개)"),
        ("due_days", "납기는 며칠 후면 좋을까요? (예: 1일, 2일, 3일, 5일, 7일)"),
        ("region", "지역은 어디로 설정할까요? (예: 서울-중구, 서울-종로, 경기-성남)"),
        ("budget", "예산은 얼마로 설정하시겠어요? (예: 5만원, 10만원, 20만원)")
    ],
    "포스터": [
        ("paper", "포스터 용지종류를 선택해주세요. (예: 일반지, 아트지, 코팅지, 합지)"),
        ("coating", "코팅 종류를 선택해주세요. (예: 무광, 유광, 스팟, 없음)"),
        ("quantity", "몇 부 필요하신가요? (예: 10부, 50부, 100부, 200부)"),
        ("due_days", "납기는 며칠 후면 좋을까요? (예: 1일, 2일, 3일, 5일, 7일)"),
        ("region", "지역은 어디로 설정할까요? (예: 서울-중구, 서울-종로, 경기-성남)"),
        ("budget", "예산은 얼마로 설정하시겠어요? (예: 5만원, 10만원, 20만원)")
    ],
    "스티커": [
        ("type", "스티커 종류를 선택해주세요. (예: 일반스티커, 방수스티커, 반사스티커, 전사스티커)"),
        ("size", "스티커 사이즈를 선택해주세요. (예: 50x50mm, 100x100mm, 200x200mm / 원형은 지름 예: 원형 50mm, Ø50mm, 지름50mm)"),
        ("quantity", "몇 부 필요하신가요? (예: 100개, 500개, 1000개)"),
        ("due_days", "납기는 며칠 후면 좋을까요? (예: 1일, 2일, 3일, 5일, 7일)"),
        ("region", "지역은 어디로 설정할까요? (예: 서울-중구, 서울-종로, 경기-성남)"),
        ("budget", "예산은 얼마로 설정하시겠어요? (예: 5만원, 10만원, 20만원)")
    ],
    "현수막": [
        ("size", "현수막 사이즈를 선택해주세요. (예: 1x3m, 2x4m, 3x6m)"),
        ("processing", "현수막 추가가공 종류를 선택해주세요. (예: 고리, 지퍼, 없음)"),
        ("quantity", "몇 부 필요하신가요? (예: 1개, 2개, 5개)"),
        ("due_days", "납기는 며칠 후면 좋을까요? (예: 1일, 2일, 3일, 5일, 7일)"),
        ("region", "지역은 어디로 설정할까요? (예: 서울-중구, 서울-종로, 경기-성남)"),
        ("budget", "예산은 얼마로 설정하시겠어요? (예: 5만원, 10만원, 20만원)")
    ],
    "브로슈어": [
        ("paper", "브로슈어 용지종류를 선택해주세요. (예: 일반지, 아트지, 코팅지, 합지)"),
        ("size", "브로슈어 사이즈를 선택해주세요. (예: A4, A5, B5, 명함크기)"),
        ("folding", "브로슈어 접지 종류를 선택해주세요. (예: 2단접지, 3단접지, Z접지, 없음)"),
        ("quantity", "몇 부 필요하신가요? (예: 100부, 200부, 500부, 1000부)"),
        ("due_days", "납기는 며칠 후면 좋을까요? (예: 1일, 2일, 3일, 5일, 7일)"),
        ("region", "지역은 어디로 설정할까요? (예: 서울-중구, 서울-종로, 경기-성남)"),
        ("budget", "예산은 얼마로 설정하시겠어요? (예: 5만원, 10만원, 20만원)")
    ]
}

COMMON_TAIL = []  # 이미 flow에 due_days/region/budget 포함됨

def normalize_quantity(v) -> Optional[int]:
    if v is None: return None
    s = str(v).lower().replace(",", "")
    s = re.sub(r"(부|개|장)$", "", s)
    m = re.findall(r"\d+", s)
    return int(m[0]) if m else None

def normalize_due_days(v) -> Optional[int]:
    if v is None: return None
    s = str(v).lower().replace("일", "")
    m = re.findall(r"\d+", s)
    return int(m[0]) if m else None

def normalize_budget(v) -> Optional[int]:
    # '10만원', '120,000원', '10만5천원', '10만원 이하/이상' 등 처리
    if v is None: return None
    s = str(v).strip().replace(",", "").replace(" ", "")
    # 범위표현은 일단 숫자만 추출해 상한/하한은 oneqscore 쪽에서 유연 처리
    s = s.replace("이하","").replace("미만","").replace("이상","").replace("초과","")
    if s.isdigit(): return int(s)
    m = re.match(r"^(\d+)(만|만원)$", s)
    if m: return int(m.group(1)) * 10000
    m = re.match(r"^(\d+)(천|천원)$", s)
    if m: return int(m.group(1)) * 1000
    m = re.match(r"^(\d+)원$", s)
    if m: return int(m.group(1))
    digits = re.sub(r"[^\d]", "", s)
    return int(digits) if digits else None

def merge_and_normalize(slots: Dict, new_slots: Dict) -> Dict:
    # 이미 채워진 슬롯은 덮어쓰지 않음(“이미 물어본 슬롯은 다시 안 묻기” 보장)
    out = dict(slots or {})
    for k, v in (new_slots or {}).items():
        if v in (None, "", []): 
            continue
        if k in out and out[k]: 
            continue
        if k == "quantity":
            nv = normalize_quantity(v)
        elif k == "due_days":
            nv = normalize_due_days(v)
        elif k == "budget":
            nv = normalize_budget(v)
        else:
            nv = v
        if nv is not None:
            out[k] = nv
    return out

def required_slots(category: str) -> List[str]:
    flow = CATEGORY_SLOT_FLOW.get(category, [])
    return [k for k,_ in flow] + COMMON_TAIL

def find_missing(slots: Dict) -> List[str]:
    cat = slots.get("category")
    req = required_slots(cat) if cat else []
    return [k for k in req if not slots.get(k)]

def next_question(slots: Dict) -> Dict:
    """현재 채워지지 않은 첫 슬롯에 대한 질문만 반환"""
    cat = slots.get("category")
    flow = CATEGORY_SLOT_FLOW.get(cat, [])
    for key, question in flow:
        if not slots.get(key):
            return {"slot": key, "question": question}
    return {"slot": None, "question": "모든 정보가 수집되었습니다. 견적을 생성할까요?"}

def validate(slots: Dict) -> Tuple[bool, Dict]:
    """간단 검증: 필수 누락/형식"""
    errs = {}
    for k in find_missing(slots):
        errs[k] = "필수 항목입니다."
    q = slots.get("quantity")
    if q is not None and (not isinstance(q, int) or q <= 0):
        errs["quantity"] = "수량은 1 이상의 정수여야 합니다."
    d = slots.get("due_days")
    if d is not None and (not isinstance(d, int) or d <= 0):
        errs["due_days"] = "납기는 1 이상의 정수일로 입력해주세요."
    b = slots.get("budget")
    if b is not None and (not isinstance(b, int) or b < 0):
        errs["budget"] = "예산은 0원 이상의 정수여야 합니다."
    return (len(errs) == 0, errs)

def render_summary(slots: Dict) -> str:
    # “부부/원원” 오타 방지: 단위는 고정 포맷으로 표기
    def fmt_qty(v): 
        return f"{int(v)}부" if isinstance(v, int) else str(v)
    def fmt_money(v):
        try:
            i = int(v)
            return f"{i:,}원"
        except:
            return str(v)
    lines = []
    cat = slots.get("category", "")
    lines.append(f"항목: {cat}")
    for k in ["paper","printing","finishing","coating","type","stand","processing","folding","size"]:
        if slots.get(k):
            lines.append(f"{k}: {slots[k]}")
    if slots.get("quantity") is not None:
        lines.append(f"수량: {fmt_qty(slots['quantity'])}")
    if slots.get("region"):
        lines.append(f"지역: {slots['region']}")
    if slots.get("due_days") is not None:
        lines.append(f"납기: {int(slots['due_days'])}일")
    if slots.get("budget") is not None:
        lines.append(f"예산: {fmt_money(slots['budget'])}")
    return "\n".join(lines)

def explain_term(term: str) -> Dict:
    """용어 설명 데이터 반환"""
    # 간단한 용어 설명 데이터
    term_data = {
        "무광": {
            "description": "빛을 반사하지 않는 코팅 방식으로, 고급스러운 느낌을 줍니다.",
            "use_cases": "명함, 브로슈어, 고급 인쇄물"
        },
        "유광": {
            "description": "빛을 반사하는 코팅 방식으로, 선명하고 화려한 느낌을 줍니다.",
            "use_cases": "포스터, 전단지, 홍보물"
        },
        "스팟": {
            "description": "특정 부분만 코팅하여 강조 효과를 주는 방식입니다.",
            "use_cases": "고급 명함, 특별한 디자인이 필요한 인쇄물"
        },
        "엠보싱": {
            "description": "종이에 볼록한 패턴을 만드는 후가공 방식입니다.",
            "use_cases": "고급 명함, 초대장, 특별한 인쇄물"
        },
        "일반지": {
            "description": "기본적인 종이로, 경제적이고 실용적입니다.",
            "use_cases": "일반 명함, 문서, 기본 인쇄물"
        },
        "고급지": {
            "description": "품질이 좋은 종이로, 고급스러운 느낌을 줍니다.",
            "use_cases": "고급 명함, 브로슈어, 중요한 인쇄물"
        },
        "아트지": {
            "description": "미술용지로, 색상 표현이 뛰어납니다.",
            "use_cases": "포스터, 아트워크, 고품질 인쇄물"
        }
    }
    
    return term_data.get(term, {})
