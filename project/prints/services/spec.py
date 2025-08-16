# prints/services/spec.py
from __future__ import annotations
from typing import Dict, List, Tuple, Optional
import re
from . import dummy_data

# 아이템별 필수 슬롯 정의
REQUIRED_SLOTS = {
    "BUSINESS_CARD": ["item_type", "quantity", "size", "material", "finishing", "color_mode", "due_days", "region"],
    "STICKER": ["item_type", "quantity", "size", "material", "shape", "lamination", "due_days", "region"],
    "BANNER": ["item_type", "size", "material", "grommet", "due_days", "region"],
    "SIGN": ["item_type", "size", "material", "finishing", "due_days", "region"]
}

# 슬롯별 선택지 (인쇄소 데이터 기반)
def get_choices_for_slot(slot_name: str, item_type: str = "BUSINESS_CARD") -> List:
    """슬롯별 선택지 반환 (인쇄소 데이터 기반)"""
    
    if slot_name == "quantity":
        return [100, 200, 500, 1000, "직접 입력"]
    
    elif slot_name == "size":
        if item_type == "BUSINESS_CARD":
            return ["90x50mm", "86x54mm", "맞춤 입력"]
        elif item_type == "STICKER":
            return ["A4", "A3", "맞춤 입력"]
        elif item_type == "BANNER":
            return ["A1", "A0", "맞춤 입력"]
        else:
            return ["표준 사이즈", "맞춤 입력"]
    
    elif slot_name == "material":
        # 인쇄소 데이터에서 재질 목록 가져오기
        shops = dummy_data.get_shops_by_category(item_type.lower())
        materials = set()
        for shop in shops:
            materials.update(shop["paper_types"].keys())
        return list(materials) + ["맞춤 입력"]
    
    elif slot_name == "finishing":
        shops = dummy_data.get_shops_by_category(item_type.lower())
        coatings = set()
        for shop in shops:
            coatings.update(shop["post_processing"]["coating"])
        return sorted(list(coatings)) + ["없음"]
    
    elif slot_name == "color_mode":
        return ["단면 컬러", "양면 컬러", "단면 흑백"]
    
    elif slot_name == "shape":
        return ["사각", "원형", "자유형(도무송)"]
    
    elif slot_name == "lamination":
        return ["무광 라미", "유광 라미", "없음"]
    
    elif slot_name == "grommet":
        return ["모서리 4개", "상단 2개", "없음"]
    
    elif slot_name == "due_days":
        return [1, 2, 3, 5, 7]
    
    elif slot_name == "region":
        return ["서울-중구", "서울-종로", "경기-성남", "직접 입력"]
    
    return []

def get_choices_for_slot_by_shop(slot_name: str, shop_id: str, item_type: str = "BUSINESS_CARD") -> List:
    """특정 인쇄소의 슬롯별 선택지 반환"""
    
    shop = dummy_data.get_shop_by_id(shop_id)
    if not shop:
        return get_choices_for_slot(slot_name, item_type)
    
    if slot_name == "material":
        return list(shop["paper_types"].keys()) + ["맞춤 입력"]
    
    elif slot_name == "finishing":
        return shop["post_processing"]["coating"] + ["없음"]
    
    elif slot_name == "cutting":
        return shop["post_processing"]["cutting"] + ["없음"]
    
    elif slot_name == "special":
        return shop["post_processing"]["special"] + ["없음"]
    
    else:
        return get_choices_for_slot(slot_name, item_type)

# 인쇄소 데이터 기반 용어 사전 (동적 생성)
def _generate_terms_from_shops() -> Dict:
    """인쇄소 데이터에서 사용되는 모든 용어를 분석하여 용어사전 생성"""
    
    # 기본 용어 사전
    base_terms = {
        "후가공": {
            "summary": "인쇄 후 외관/내구성/기능을 높이기 위해 추가로 진행하는 공정의 총칭",
            "effects": ["스크래치/오염 방지", "색감 보강", "형태 가공(재단/도무송 등)"],
            "cost_impact": "옵션 추가 비용이 발생할 수 있음",
            "leadtime_impact": "일부 공정은 납기를 0~1일 늘릴 수 있음"
        },
        "코팅": {
            "summary": "표면 보호와 생활 방수 수준의 내수성을 제공하는 후가공(무광/유광)",
            "effects": ["스크래치/오염 감소", "색감 선명도 향상", "물 번짐 감소(생활 방수)"],
            "cost_impact": "면수/수량에 비례해 추가 비용",
            "leadtime_impact": "가공/건조로 납기 +0~1일"
        },
        "무광": {
            "summary": "빛 반사가 적어 차분한 질감의 마감",
            "effects": ["지문/반사에 둔감", "은은한 색감"],
            "cost_impact": "유광과 유사하거나 동일",
            "leadtime_impact": "코팅 포함 시 +0~1일"
        },
        "유광": {
            "summary": "광택이 있어 색이 쨍하게 보이는 마감",
            "effects": ["선명/반짝임", "지문/반사 주의"],
            "cost_impact": "무광과 유사하거나 동일",
            "leadtime_impact": "코팅 포함 시 +0~1일"
        },
        "도무송": {
            "summary": "원하는 임의의 외곽 형태로 재단하는 공정",
            "effects": ["자유 형태 구현", "금형/칼선 필요"],
            "cost_impact": "소량은 고정 비용 영향 큼",
            "leadtime_impact": "금형 준비 시 납기 +0~1일"
        },
        "귀도리": {
            "summary": "각진 모서리를 둥글게 만드는 후가공 공정",
            "effects": ["부드러운 느낌", "고급스러운 외관", "안전성 향상"],
            "cost_impact": "기본 후가공으로 합리적인 가격",
            "leadtime_impact": "가공으로 납기 +0~1일"
        },
        "아트지": {
            "summary": "인쇄용지 중 가장 일반적으로 사용되는 고급 종이",
            "effects": ["뛰어난 인쇄 품질", "적당한 두께와 질감", "다양한 후가공 가능"],
            "cost_impact": "기본 재질로 합리적인 가격",
            "leadtime_impact": "재고 품목으로 빠른 납기 가능"
        },
        "스노우지": {
            "summary": "아트지보다 더 고급스러운 질감의 인쇄용지",
            "effects": ["부드럽고 고급스러운 질감", "뛰어난 색감 표현", "지문에 둔감"],
            "cost_impact": "아트지 대비 약간 높은 가격",
            "leadtime_impact": "재고 품목으로 빠른 납기 가능"
        },
        "PP": {
            "summary": "플라스틱 재질로 내구성이 뛰어난 소재",
            "effects": ["높은 내구성/내수성", "투명도 조절 가능", "다양한 두께 선택"],
            "cost_impact": "종이 대비 높은 가격",
            "leadtime_impact": "일반적으로 빠른 납기 가능"
        },
        "PET": {
            "summary": "PP보다 더 강한 내구성을 가진 플라스틱 소재",
            "effects": ["최고 수준의 내구성", "투명도 조절 가능", "고온/화학 저항"],
            "cost_impact": "PP 대비 더 높은 가격",
            "leadtime_impact": "일반적으로 빠른 납기 가능"
        }
    }
    
    # 인쇄소 데이터에서 추가 용어 수집
    shops = dummy_data.get_all_shops()
    
    # 후가공 용어 수집
    coating_terms = set()
    cutting_terms = set()
    special_terms = set()
    material_terms = set()
    
    for shop in shops:
        # 코팅 용어
        coating_terms.update(shop["post_processing"]["coating"])
        # 재단 용어
        cutting_terms.update(shop["post_processing"]["cutting"])
        # 특수 가공 용어
        special_terms.update(shop["post_processing"]["special"])
        # 재질 용어
        material_terms.update(shop["paper_types"].keys())
    
    # 추가 용어 정의
    additional_terms = {
        # 코팅 관련 추가 용어
        "스팟 UV": {
            "summary": "특정 부분에만 UV 코팅을 적용하는 고급 후가공",
            "effects": ["부분적 광택 효과", "고급스러운 외관", "브랜드 강조"],
            "cost_impact": "일반 코팅 대비 높은 비용",
            "leadtime_impact": "정밀 작업으로 납기 +1일"
        },
        "에폭시": {
            "summary": "표면에 두꺼운 코팅을 적용하는 고급 후가공",
            "effects": ["입체감 있는 마감", "뛰어난 내구성", "고급스러운 느낌"],
            "cost_impact": "가장 높은 비용의 코팅",
            "leadtime_impact": "건조 시간으로 납기 +2일"
        },
        "UV 코팅": {
            "summary": "자외선으로 경화되는 코팅 재료",
            "effects": ["빠른 건조", "뛰어난 내구성", "환경 친화적"],
            "cost_impact": "일반 코팅 대비 약간 높음",
            "leadtime_impact": "빠른 건조로 납기 영향 적음"
        },
        "매트 코팅": {
            "summary": "무광 코팅의 한 종류로 차분한 마감",
            "effects": ["지문에 둔감", "은은한 색감", "고급스러운 느낌"],
            "cost_impact": "일반 코팅과 유사",
            "leadtime_impact": "일반 코팅과 동일"
        },
        
        # 재단 관련 추가 용어
        "타공": {
            "summary": "종이에 구멍을 뚫는 후가공",
            "effects": ["바인더 삽입 가능", "정리 용이", "실용성 향상"],
            "cost_impact": "기본 후가공으로 합리적",
            "leadtime_impact": "가공으로 납기 +0~1일"
        },
        "라미네이팅": {
            "summary": "표면에 필름을 붙이는 후가공",
            "effects": ["뛰어난 내구성", "방수 효과", "색감 보호"],
            "cost_impact": "일반 코팅 대비 높음",
            "leadtime_impact": "가공으로 납기 +1일"
        },
        
        # 특수 가공 관련 추가 용어
        "오시": {
            "summary": "표면에 홈을 파는 후가공",
            "effects": ["접기 용이", "정확한 접기선", "고급스러운 느낌"],
            "cost_impact": "기본 후가공으로 합리적",
            "leadtime_impact": "가공으로 납기 +0~1일"
        },
        "절취선": {
            "summary": "찢을 수 있도록 미리 선을 파는 후가공",
            "effects": ["사용자 편의성", "정확한 분리", "실용성 향상"],
            "cost_impact": "기본 후가공으로 합리적",
            "leadtime_impact": "가공으로 납기 +0~1일"
        },
        "박": {
            "summary": "표면에 입체감을 만드는 후가공",
            "effects": ["입체감 있는 디자인", "고급스러운 느낌", "브랜드 강조"],
            "cost_impact": "일반 후가공 대비 높음",
            "leadtime_impact": "가공으로 납기 +1일"
        },
        "3D 박": {
            "summary": "깊은 입체감을 만드는 고급 박 가공",
            "effects": ["뛰어난 입체감", "고급스러운 느낌", "시각적 임팩트"],
            "cost_impact": "일반 박 대비 매우 높음",
            "leadtime_impact": "정밀 작업으로 납기 +2일"
        },
        "넘버링": {
            "summary": "연속된 번호를 인쇄하는 후가공",
            "effects": ["순서 표시", "관리 용이", "고급스러운 느낌"],
            "cost_impact": "수량에 비례한 추가 비용",
            "leadtime_impact": "인쇄로 납기 +0~1일"
        },
        "실크스크린": {
            "summary": "실크 스크린 인쇄 방식으로 특수 효과 적용",
            "effects": ["특수 잉크 사용 가능", "입체감 있는 인쇄", "고급스러운 느낌"],
            "cost_impact": "일반 인쇄 대비 높음",
            "leadtime_impact": "특수 공정으로 납기 +1일"
        },
        "접지": {
            "summary": "종이를 접는 후가공",
            "effects": ["공간 절약", "정리 용이", "실용성 향상"],
            "cost_impact": "기본 후가공으로 합리적",
            "leadtime_impact": "가공으로 납기 +0~1일"
        },
        
        # 배너 관련 추가 용어
        "아일렛": {
            "summary": "배너에 고리를 끼우기 위한 금속 링",
            "effects": ["고정 용이", "내구성 향상", "실용성"],
            "cost_impact": "기본 후가공으로 합리적",
            "leadtime_impact": "가공으로 납기 +0~1일"
        },
        "재봉": {
            "summary": "천 재질을 바느질로 연결하는 후가공",
            "effects": ["뛰어난 내구성", "안전한 연결", "전문적인 느낌"],
            "cost_impact": "수작업으로 인한 높은 비용",
            "leadtime_impact": "수작업으로 납기 +1일"
        },
        "고리": {
            "summary": "배너를 걸기 위한 금속 고리",
            "effects": ["고정 용이", "내구성", "실용성"],
            "cost_impact": "기본 후가공으로 합리적",
            "leadtime_impact": "가공으로 납기 +0~1일"
        },
        "지퍼": {
            "summary": "배너를 연결하기 위한 지퍼 장치",
            "effects": ["연결 용이", "분리 가능", "실용성"],
            "cost_impact": "일반 후가공 대비 높음",
            "leadtime_impact": "가공으로 납기 +1일"
        },
        "벨크로": {
            "summary": "접착 테이프로 배너를 연결하는 방식",
            "effects": ["연결 용이", "분리 가능", "가벼운 무게"],
            "cost_impact": "일반 후가공으로 합리적",
            "leadtime_impact": "가공으로 납기 +0~1일"
        },
        
        # 재질 관련 추가 용어
        "반누보 186g": {
            "summary": "가장 보편적으로 사용되는 명함용 종이",
            "effects": ["내추럴한 느낌", "합리적인 가격", "다양한 후가공 가능"],
            "cost_impact": "기본 재질로 가장 저렴",
            "leadtime_impact": "재고 품목으로 빠른 납기"
        },
        "휘라레 216g": {
            "summary": "격자 무늬가 있는 고급 종이",
            "effects": ["부드러운 색감", "고급스러운 질감", "특별한 느낌"],
            "cost_impact": "반누보 대비 약간 높음",
            "leadtime_impact": "재고 품목으로 빠른 납기"
        },
        "스타드림쿼츠 240g": {
            "summary": "은은한 펄 효과가 있는 고급 종이",
            "effects": ["펄 효과", "고급스러운 느낌", "특별한 외관"],
            "cost_impact": "일반 종이 대비 높음",
            "leadtime_impact": "재고 품목으로 빠른 납기"
        },
        "키칼라아이스골드 230g": {
            "summary": "골드 펄 효과가 있는 프리미엄 종이",
            "effects": ["골드 펄 효과", "고급스러운 느낌", "브랜드 강조"],
            "cost_impact": "가장 높은 비용의 종이",
            "leadtime_impact": "재고 품목으로 빠른 납기"
        },
        "벨벳 300g": {
            "summary": "벨벳 질감의 고급 종이",
            "effects": ["부드러운 촉감", "고급스러운 느낌", "특별한 외관"],
            "cost_impact": "일반 종이 대비 매우 높음",
            "leadtime_impact": "재고 품목으로 빠른 납기"
        },
        "PP 250gsm": {
            "summary": "플라스틱 재질로 내구성이 뛰어난 소재",
            "effects": ["높은 내구성", "방수 효과", "다양한 용도"],
            "cost_impact": "종이 대비 높은 가격",
            "leadtime_impact": "재고 품목으로 빠른 납기"
        },
        "PET 250gsm": {
            "summary": "PP보다 더 강한 내구성을 가진 플라스틱 소재",
            "effects": ["최고 수준의 내구성", "방수 효과", "고온 저항"],
            "cost_impact": "PP 대비 더 높은 가격",
            "leadtime_impact": "재고 품목으로 빠른 납기"
        },
        "반투명 PP": {
            "summary": "반투명 효과가 있는 PP 재질",
            "effects": ["반투명 효과", "특별한 외관", "창문 부착 가능"],
            "cost_impact": "일반 PP 대비 높음",
            "leadtime_impact": "재고 품목으로 빠른 납기"
        },
        "메탈 PP": {
            "summary": "메탈릭 효과가 있는 PP 재질",
            "effects": ["메탈릭 효과", "고급스러운 느낌", "특별한 외관"],
            "cost_impact": "일반 PP 대비 높음",
            "leadtime_impact": "재고 품목으로 빠른 납기"
        },
        "배너천": {
            "summary": "배너 제작용 천 재질",
            "effects": ["가벼운 무게", "접기 용이", "내구성"],
            "cost_impact": "기본 배너 재질로 합리적",
            "leadtime_impact": "재고 품목으로 빠른 납기"
        },
        "타프린": {
            "summary": "고급 배너용 천 재질",
            "effects": ["뛰어난 내구성", "고급스러운 느낌", "장기간 사용 가능"],
            "cost_impact": "배너천 대비 높음",
            "leadtime_impact": "재고 품목으로 빠른 납기"
        },
        "메쉬천": {
            "summary": "통기성이 있는 배너용 천 재질",
            "effects": ["바람 저항", "통기성", "실외용 적합"],
            "cost_impact": "배너천 대비 약간 높음",
            "leadtime_impact": "재고 품목으로 빠른 납기"
        },
        "실크천": {
            "summary": "고급 실크 재질의 배너용 천",
            "effects": ["고급스러운 느낌", "부드러운 질감", "특별한 외관"],
            "cost_impact": "가장 높은 비용의 배너 재질",
            "leadtime_impact": "재고 품목으로 빠른 납기"
        },
        "PVC": {
            "summary": "내구성이 뛰어난 플라스틱 재질",
            "effects": ["뛰어난 내구성", "방수 효과", "다양한 용도"],
            "cost_impact": "일반 재질 대비 높음",
            "leadtime_impact": "재고 품목으로 빠른 납기"
        }
    }
    
    # 기본 용어와 추가 용어 합치기
    all_terms = {**base_terms, **additional_terms}
    
    return all_terms

# 용어 사전 (동적 생성)
TERMS = _generate_terms_from_shops()

def explain_term(term: str) -> Dict:
    """용어 설명 반환"""
    key = term.strip()
    
    # 여러 용어가 쉼표로 구분된 경우
    if "," in key:
        terms = [t.strip() for t in key.split(",")]
        all_facts = {}
        for t in terms:
            data = TERMS.get(t) or TERMS.get(_alias_to_key(t))
            if data:
                all_facts[t] = data
        if all_facts:
            return {"term": key, "facts": all_facts}
        else:
            return {"term": term, "facts": None, "message": f"'{term}'에 대한 정보가 아직 준비되지 않았습니다."}
    
    # 단일 용어
    data = TERMS.get(key) or TERMS.get(_alias_to_key(key))
    if not data:
        return {"term": term, "facts": None, "message": f"'{term}'에 대한 정보가 아직 준비되지 않았습니다."}
    return {"term": key, "facts": data}

def _alias_to_key(word: str) -> Optional[str]:
    """별칭을 키로 변환"""
    aliases = {
        # 코팅 관련
        "matte": "무광",
        "gloss": "유광",
        "코팅(무광)": "무광",
        "코팅(유광)": "유광",
        "무광코팅": "무광 코팅",
        "유광코팅": "유광 코팅",
        "스팟uv": "스팟 UV",
        "spot uv": "스팟 UV",
        "uv코팅": "UV 코팅",
        "uv 코팅": "UV 코팅",
        "매트코팅": "매트 코팅",
        "매트 코팅": "매트 코팅",
        
        # 재단 관련
        "kiss-cut": "도무송",
        "kiss cut": "도무송",
        "도무송기": "도무송",
        "라미네이션": "라미네이팅",
        "라미네이션": "라미네이팅",
        
        # 특수 가공
        "오시선": "오시",
        "절취": "절취선",
        "3d박": "3D 박",
        "3d 박": "3D 박",
        "실크스크린": "실크스크린",
        "실크 스크린": "실크스크린",
        
        # 배너 관련
        "아일렛": "아일렛",
        "grommet": "아일렛",
        "재봉": "재봉",
        "sewing": "재봉",
        "지퍼": "지퍼",
        "zipper": "지퍼",
        "벨크로": "벨크로",
        "velcro": "벨크로",
        
        # 재질 관련
        "아트지": "아트지",
        "art paper": "아트지",
        "스노우지": "스노우지",
        "snow paper": "스노우지",
        "pp": "PP 250gsm",
        "pet": "PET 250gsm",
        "반누보": "반누보 186g",
        "휘라레": "휘라레 216g",
        "스타드림": "스타드림쿼츠 240g",
        "키칼라": "키칼라아이스골드 230g",
        "벨벳": "벨벳 300g",
        "배너천": "배너천",
        "타프린": "타프린",
        "메쉬천": "메쉬천",
        "실크천": "실크천",
        "pvc": "PVC"
    }
    return aliases.get(word.lower()) or aliases.get(word)

def _maybe_parse_quantity(text: str) -> Optional[int]:
    """텍스트에서 수량 추출"""
    s = (text or "").strip().lower()
    s = s.replace(",", "").replace("부", "").replace("개", "").replace("장", "")
    numbers = re.findall(r'\d+', s)
    if numbers:
        return int(numbers[0])
    return None

def merge_and_normalize(slots: Dict, new_vals: Dict) -> Dict:
    """슬롯 병합 및 정규화"""
    out = {**(slots or {}), **(new_vals or {})}
    
    # 사용자 입력에서 수량 추출
    user_text = (new_vals or {}).get("_user_text", "")
    if not out.get("quantity"):
        q = _maybe_parse_quantity(user_text)
        if q is not None:
            out["quantity"] = q
    
    # 표준 사이즈 자동 설정
    if not out.get("size") and user_text:
        if any(keyword in user_text for keyword in ["보통", "표준", "일반적인", "기본"]):
            if "사이즈" in user_text or "크기" in user_text:
                out["size"] = "90x50mm"
    
    # 아이템 타입 표준화
    if t := out.get("item_type"):
        out["item_type"] = _normalize_item_type(t)
    
    # 수량 정규화
    if "quantity" in out and out["quantity"] not in (None, ""):
        out["quantity"] = _to_int(out["quantity"])
    
    # 사이즈 정규화
    if s := out.get("size"):
        out["size"] = _normalize_size(s)
    
    # 재질 정규화
    if m := out.get("material"):
        out["material"] = _normalize_material(m)
    
    # 마감 정규화
    if f := out.get("finishing"):
        out["finishing"] = _normalize_finishing(f)
    
    # 색상 모드 정규화
    if c := out.get("color_mode"):
        out["color_mode"] = _normalize_color_mode(c)
    
    # 납기일 정규화
    if "due_days" in out and out["due_days"] not in (None, ""):
        out["due_days"] = _to_int(out["due_days"])
    
    # 지역 정규화
    if r := out.get("region"):
        out["region"] = _normalize_region(r)
    
    return out

def find_missing(slots: Dict) -> List[str]:
    """누락된 슬롯 찾기"""
    item_type = slots.get("item_type") or "BUSINESS_CARD"
    req = REQUIRED_SLOTS.get(item_type, REQUIRED_SLOTS["BUSINESS_CARD"])
    return [k for k in req if not slots.get(k)]

def validate(slots: Dict) -> Tuple[bool, Dict[str, str]]:
    """슬롯 검증"""
    errors = {}
    missing = find_missing(slots)
    if missing:
        errors["_missing"] = ", ".join(missing)
    
    q = slots.get("quantity")
    if q is not None and (q <= 0 or q > 1_000_000):
        errors["quantity"] = "수량 범위를 확인해주세요 (1 ~ 1,000,000)"
    
    size = slots.get("size")
    if size and not re.match(r"^\d{2,4}x\d{2,4}mm$", size):
        errors["size"] = "사이즈 형식을 '90x50mm'처럼 입력해주세요"
    
    due = slots.get("due_days")
    if due is not None and (due <= 0 or due > 30):
        errors["due_days"] = "납기는 1~30일 사이로 설정해주세요"
    
    return (len(errors) == 0), errors

def next_question(slots: Dict) -> Dict:
    """다음 질문 결정"""
    missing = find_missing(slots)
    if not missing:
        return {
            "question": "모든 견적 정보가 수집되었습니다. 이대로 진행하시겠습니까?",
            "choices": ["네, 맞습니다", "수정할 부분이 있습니다"]
        }
    
    # 아이템 타입이 없으면 기본값 설정
    if "item_type" not in slots or not slots["item_type"]:
        slots["item_type"] = "BUSINESS_CARD"
    
    # 질문 순서 정의
    order = ["quantity", "size", "material", "finishing", "color_mode", "shape", "lamination", "grommet", "due_days", "region"]
    target = next((k for k in order if k in missing), missing[0] if missing else "quantity")
    
    # 질문 매핑 (용어사전에 있는 용어들만 예시로 사용)
    qmap = {
        "quantity": "몇 부 필요하신가요? (예: 100부, 200부, 500부, 1000부)",
        "size": "사이즈는 어떻게 하시겠어요? (예: 90x50mm, 86x54mm, A4, A3, A1, A0)",
        "material": "재질은 무엇으로 할까요? (예: 아트지, 스노우지, 반누보 186g, 휘라레 216g, 스타드림쿼츠 240g, 키칼라아이스골드 230g, 벨벳 300g, PP 250gsm, PET 250gsm, 반투명 PP, 메탈 PP, 배너천, 타프린, 메쉬천, 실크천, PVC)",
        "finishing": "마감(코팅)은 무엇으로 할까요? (예: 무광, 유광, 스팟 UV, 에폭시, UV 코팅, 매트 코팅)",
        "color_mode": "인쇄 색상은 어떻게 할까요? (예: 단면 컬러, 양면 컬러, 단면 흑백)",
        "shape": "스티커 모양은 어떻게 할까요? (예: 사각, 원형, 자유형(도무송))",
        "lamination": "라미네이팅(필름)은 적용할까요? (예: 무광 라미, 유광 라미)",
        "grommet": "배너 고리(아일렛)는 어디에 뚫을까요? (예: 모서리 4개, 상단 2개)",
        "due_days": "납기는 며칠 후면 좋을까요? (예: 1일, 2일, 3일, 5일, 7일)",
        "region": "지역은 어디로 설정할까요? (예: 서울-중구, 서울-종로, 경기-성남)"
    }
    
    # 선택지 가져오기 (인쇄소별 필터링 고려)
    choices = get_choices_for_slot(target, slots.get("item_type"))
    
    # 특정 인쇄소가 선택된 경우 해당 인쇄소의 옵션만 제공
    if "shop_id" in slots and slots["shop_id"]:
        shop_choices = get_choices_for_slot_by_shop(target, slots["shop_id"], slots.get("item_type"))
        if shop_choices:
            choices = shop_choices
    
    return {
        "question": qmap.get(target, f"{target} 값을 알려주세요"),
        "choices": choices
    }

def render_summary(slots: Dict) -> str:
    """견적 요약 생성"""
    item_type = slots.get("item_type", "BUSINESS_CARD")
    item_names = {
        "BUSINESS_CARD": "명함",
        "STICKER": "스티커",
        "BANNER": "배너",
        "SIGN": "간판"
    }
    item_name = item_names.get(item_type, item_type)
    
    lines = [
        f"📋 견적 요약",
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"품목: {item_name}",
        f"수량: {slots.get('quantity', '미정')}부",
        f"사이즈: {slots.get('size', '미정')}",
        f"재질: {slots.get('material', '미정')}",
        f"마감: {slots.get('finishing', '미정')}",
    ]
    
    if item_type == "BUSINESS_CARD":
        lines.append(f"색상: {slots.get('color_mode', '미정')}")
    elif item_type == "STICKER":
        lines.append(f"형태: {slots.get('shape', '미정')}")
        lines.append(f"라미네이팅: {slots.get('lamination', '미정')}")
    elif item_type == "BANNER":
        lines.append(f"아일렛: {slots.get('grommet', '미정')}")
    
    lines += [
        f"납기: {slots.get('due_days', '미정')}일",
        f"지역: {slots.get('region', '미정')}",
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    ]
    
    return "\n".join(lines)

# 내부 정규화 함수들
def _normalize_item_type(val: str) -> str:
    mapping = {
        "명함": "BUSINESS_CARD",
        "스티커": "STICKER",
        "배너": "BANNER",
        "현수막": "BANNER",
        "간판": "SIGN"
    }
    return mapping.get(val, val.upper())

def _to_int(v) -> int:
    if isinstance(v, int):
        return v
    s = str(v)
    s = re.sub(r"[^\d]", "", s)
    return int(s) if s else 0

def _normalize_size(s: str) -> str:
    s = s.strip().lower().replace(" ", "")
    
    # 일반명함크기 관련 모든 변형 처리
    if re.match(r"^(일반명함크기|일반명함|일반크기|기본크기|기본사이즈|표준|표준사이즈|standard|보통명함크기|보통명함|보통크기).*", s):
        return "90x50mm"
    
    s = s.replace("*", "x")
    m = re.match(r"^(\d{2,4})x(\d{2,4})(mm)?$", s)
    if not m:
        return s.upper()
    return f"{m.group(1)}x{m.group(2)}mm"

def _normalize_material(m: str) -> str:
    m = m.strip().lower()
    if re.fullmatch(r"\d{2,4}", m) or re.fullmatch(r"\d{2,4}\s*g", m):
        return ""
    return m

def _normalize_finishing(f: str) -> str:
    f = f.strip().lower()
    if "무광" in f or "matte" in f:
        return "MATTE"
    if "유광" in f or "gloss" in f:
        return "GLOSS"
    if "없" in f:
        return "NONE"
    return f.upper()

def _normalize_color_mode(c: str) -> str:
    c = c.strip().lower()
    if "양면" in c and ("컬러" in c or "color" in c):
        return "DOUBLE_COLOR"
    if "단면" in c and ("컬러" in c or "color" in c):
        return "SINGLE_COLOR"
    if "흑백" in c or "mono" in c or "bw" in c:
        return "MONO"
    return c.upper()

def _normalize_region(r: str) -> str:
    r = r.strip().replace(" ", "")
    r = r.replace("/", "-").replace("_", "-")
    return r
