# prints/services/dummy_data.py
from typing import Dict, List

# 더미 인쇄소 데이터 (사용자 제공 구조 기반)
DUMMY_SHOPS = [
    {
        "shop_id": "shop_001",
        "shop_name": "프리미엄인쇄",
        "location": "서울-중구",
        "rating": 4.8,
        "review_count": 156,
        "description": "고품질 인쇄 서비스 전문업체로, 최신 장비와 숙련된 기술진을 보유하고 있습니다. 명함, 현수막, 포스터 등 다양한 인쇄물 제작이 가능하며, 빠른 납기와 합리적인 가격으로 고객 만족도를 높이고 있습니다.",
        "contact": {
            "phone": "02-1234-5678",
            "email": "info@premiumprint.co.kr",
            "business_hours": "09:00 ~ 18:00",
            "address": "서울특별시 중구 을지로 123 프리미엄빌딩 3층"
        },
        "equipment": [
            "디지털 프린터 (HP Indigo 7900)",
            "오프셋 프레스 (Heidelberg Speedmaster)",
            "레이저 커터 (Graphtec FC9000)",
            "형압기 (Hot Stamping Machine)",
            "박기 (Embossing Machine)",
            "코팅기 (UV Coating Machine)"
        ],
        "printable_sizes": {
            "A4": {"price": 500, "description": "장당 500원"},
            "A3": {"price": 800, "description": "장당 800원"},
            "A2": {"price": 1200, "description": "장당 1200원"},
            "A1": {"price": 2000, "description": "장당 2000원"},
            "A0": {"price": 3000, "description": "장당 3000원"},
            "custom": {"price": 1000, "description": "맞춤 사이즈 +1000원"}
        },
        "post_processing": {
            "coating": ["무광 코팅", "유광 코팅", "스팟 UV", "에폭시"],
            "cutting": ["일반 재단", "도무송", "귀도리", "타공"],
            "special": ["형압", "오시", "절취선", "박", "넘버링", "3D 박"]
        },
        "paper_types": {
            "반누보 186g": {"price": 0, "description": "가장 보편적, 내추럴한 느낌"},
            "휘라레 216g": {"price": 500, "description": "격자 무늬, 부드러운 색감"},
            "스타드림쿼츠 240g": {"price": 1000, "description": "은은한 펄 효과"},
            "키칼라아이스골드 230g": {"price": 1200, "description": "고급스러운 골드 펄"},
            "아트지 230g": {"price": 2000, "description": "코팅 가능, 매끄럽고 광택"},
            "스노우지 250g": {"price": 2500, "description": "비코팅, 차분한 무광"},
            "벨벳 300g": {"price": 3000, "description": "부드러운 촉감"},
            "PP 250gsm": {"price": 1500, "description": "플라스틱 재질, 내구성 우수"},
            "PET 250gsm": {"price": 2000, "description": "고급 플라스틱 재질"}
        },
        "services": {
            "categories": ["명함", "현수막", "포스터", "책자", "스티커"],
            "min_order": {"명함": 100, "현수막": 1, "포스터": 10, "책자": 50, "스티커": 100},
            "avg_production_time": 3,
            "delivery": ["직접 수령", "택배", "퀵", "화물"],
            "pricing_type": "고정가"
        },
        "discounts": {
            "100개 이상": "10% 할인",
            "500개 이상": "20% 할인",
            "1000개 이상": "30% 할인"
        },
        "score_breakdown": {
            "price": 0.85,
            "quality": 0.92,
            "speed": 0.88,
            "location": 0.95,
            "reliability": 0.90
        }
    },
    {
        "shop_id": "shop_002",
        "shop_name": "빠른인쇄",
        "location": "서울-종로",
        "rating": 4.5,
        "review_count": 89,
        "description": "빠른 납기와 합리적인 가격으로 고객의 니즈를 충족시키는 인쇄 전문업체입니다. 디지털 인쇄 기술을 활용하여 소량 주문부터 대량 주문까지 빠르고 정확하게 처리합니다.",
        "contact": {
            "phone": "02-2345-6789",
            "email": "contact@fastprint.co.kr",
            "business_hours": "08:00 ~ 20:00",
            "address": "서울특별시 종로구 종로 456 빠른빌딩 2층"
        },
        "equipment": [
            "디지털 프린터 (Canon imagePRESS)",
            "레이저 커터 (Graphtec FC8600)",
            "코팅기 (Lamination Machine)",
            "재단기 (Guillotine Cutter)"
        ],
        "printable_sizes": {
            "A4": {"price": 400, "description": "장당 400원"},
            "A3": {"price": 700, "description": "장당 700원"},
            "A2": {"price": 1000, "description": "장당 1000원"},
            "custom": {"price": 800, "description": "맞춤 사이즈 +800원"}
        },
        "post_processing": {
            "coating": ["무광 코팅", "유광 코팅"],
            "cutting": ["일반 재단", "귀도리"],
            "special": ["형압", "박"]
        },
        "paper_types": {
            "반누보 186g": {"price": 0, "description": "기본 재질"},
            "아트지 230g": {"price": 1500, "description": "코팅 가능"},
            "스노우지 250g": {"price": 2000, "description": "비코팅"},
            "PP 250gsm": {"price": 1200, "description": "플라스틱 재질"}
        },
        "services": {
            "categories": ["명함", "포스터", "스티커"],
            "min_order": {"명함": 50, "포스터": 5, "스티커": 50},
            "avg_production_time": 2,
            "delivery": ["직접 수령", "택배"],
            "pricing_type": "고정가"
        },
        "discounts": {
            "100개 이상": "15% 할인",
            "500개 이상": "25% 할인"
        },
        "score_breakdown": {
            "price": 0.92,
            "quality": 0.78,
            "speed": 0.95,
            "location": 0.85,
            "reliability": 0.75
        }
    },
    {
        "shop_id": "shop_003",
        "shop_name": "퀄리티인쇄",
        "location": "경기-성남",
        "rating": 4.9,
        "review_count": 234,
        "description": "최고 품질의 인쇄 서비스를 제공하는 프리미엄 인쇄소입니다. 최신 장비와 20년 경력의 기술진이 함께하여 고객의 기대를 뛰어넘는 결과물을 만들어냅니다.",
        "contact": {
            "phone": "031-3456-7890",
            "email": "hello@qualityprint.co.kr",
            "business_hours": "09:00 ~ 19:00",
            "address": "경기도 성남시 분당구 정자로 789 퀄리티빌딩 4층"
        },
        "equipment": [
            "디지털 프린터 (HP Indigo 12000)",
            "오프셋 프레스 (Heidelberg Speedmaster XL)",
            "레이저 커터 (Graphtec FC9000)",
            "형압기 (Hot Stamping Machine)",
            "박기 (Embossing Machine)",
            "에폭시기 (UV Coating Machine)",
            "제본기 (Perfect Binding Machine)"
        ],
        "printable_sizes": {
            "A4": {"price": 600, "description": "장당 600원"},
            "A3": {"price": 1000, "description": "장당 1000원"},
            "A2": {"price": 1500, "description": "장당 1500원"},
            "A1": {"price": 2500, "description": "장당 2500원"},
            "A0": {"price": 4000, "description": "장당 4000원"},
            "custom": {"price": 1200, "description": "맞춤 사이즈 +1200원"}
        },
        "post_processing": {
            "coating": ["무광 코팅", "유광 코팅", "스팟 UV", "에폭시", "매트 코팅"],
            "cutting": ["일반 재단", "도무송", "귀도리", "타공", "라미네이팅"],
            "special": ["형압", "오시", "절취선", "박", "넘버링", "3D 박", "접지"]
        },
        "paper_types": {
            "반누보 186g": {"price": 0, "description": "기본 재질"},
            "휘라레 216g": {"price": 800, "description": "격자 무늬"},
            "스타드림쿼츠 240g": {"price": 1500, "description": "펄 효과"},
            "키칼라아이스골드 230g": {"price": 1800, "description": "골드 펄"},
            "아트지 230g": {"price": 2500, "description": "코팅 가능"},
            "스노우지 250g": {"price": 3000, "description": "비코팅"},
            "벨벳 300g": {"price": 4000, "description": "벨벳 질감"},
            "PP 250gsm": {"price": 2000, "description": "플라스틱 재질"},
            "PET 250gsm": {"price": 2500, "description": "고급 플라스틱 재질"}
        },
        "services": {
            "categories": ["명함", "현수막", "포스터", "책자", "스티커", "카탈로그"],
            "min_order": {"명함": 200, "현수막": 1, "포스터": 20, "책자": 50, "스티커": 200, "카탈로그": 100},
            "avg_production_time": 4,
            "delivery": ["직접 수령", "택배", "퀵", "화물"],
            "pricing_type": "맞춤견적"
        },
        "discounts": {
            "200개 이상": "5% 할인",
            "500개 이상": "15% 할인",
            "1000개 이상": "25% 할인"
        },
        "score_breakdown": {
            "price": 0.75,
            "quality": 0.98,
            "speed": 0.82,
            "location": 0.65,
            "reliability": 0.95
        }
    },
    {
        "shop_id": "shop_004",
        "shop_name": "스티커전문인쇄",
        "location": "서울-강남",
        "rating": 4.7,
        "review_count": 98,
        "description": "스티커와 라벨 전문 인쇄소로, 다양한 재질과 특수 후가공 기술을 보유하고 있습니다. 소량부터 대량까지 정확하고 빠른 제작이 가능합니다.",
        "contact": {
            "phone": "02-4567-8901",
            "email": "sticker@stickerprint.co.kr",
            "business_hours": "09:00 ~ 18:00",
            "address": "서울특별시 강남구 테헤란로 456 스티커빌딩 5층"
        },
        "equipment": [
            "디지털 프린터 (Epson SureColor)",
            "레이저 커터 (Graphtec FC8600)",
            "도무송기 (Kiss Cutting Machine)",
            "라미네이터 (Lamination Machine)",
            "재단기 (Guillotine Cutter)"
        ],
        "printable_sizes": {
            "A4": {"price": 300, "description": "장당 300원"},
            "A3": {"price": 500, "description": "장당 500원"},
            "A2": {"price": 800, "description": "장당 800원"},
            "custom": {"price": 600, "description": "맞춤 사이즈 +600원"}
        },
        "post_processing": {
            "coating": ["무광 코팅", "유광 코팅", "UV 코팅"],
            "cutting": ["일반 재단", "도무송", "귀도리", "라미네이팅"],
            "special": ["형압", "박", "실크스크린"]
        },
        "paper_types": {
            "PP 250gsm": {"price": 0, "description": "기본 재질"},
            "PET 250gsm": {"price": 1000, "description": "고급 재질"},
            "아트지 230g": {"price": 800, "description": "종이 재질"},
            "반투명 PP": {"price": 1200, "description": "반투명 효과"},
            "메탈 PP": {"price": 1500, "description": "메탈릭 효과"}
        },
        "services": {
            "categories": ["스티커", "라벨", "데칼"],
            "min_order": {"스티커": 50, "라벨": 100, "데칼": 50},
            "avg_production_time": 2,
            "delivery": ["직접 수령", "택배"],
            "pricing_type": "고정가"
        },
        "discounts": {
            "100개 이상": "10% 할인",
            "500개 이상": "20% 할인"
        },
        "score_breakdown": {
            "price": 0.88,
            "quality": 0.85,
            "speed": 0.90,
            "location": 0.80,
            "reliability": 0.85
        }
    },
    {
        "shop_id": "shop_005",
        "shop_name": "배너전문인쇄",
        "location": "서울-마포",
        "rating": 4.6,
        "review_count": 67,
        "description": "대형 배너와 현수막 전문 인쇄소로, 최신 대형 프린터와 전문 장비를 보유하고 있습니다. 실외용 내구성 재질과 다양한 마감 옵션을 제공합니다.",
        "contact": {
            "phone": "02-5678-9012",
            "email": "banner@bannerprint.co.kr",
            "business_hours": "08:00 ~ 19:00",
            "address": "서울특별시 마포구 합정로 789 배너빌딩 2층"
        },
        "equipment": [
            "대형 프린터 (HP Latex 3600)",
            "레이저 커터 (Graphtec FC9000)",
            "아일렛기 (Grommet Machine)",
            "재봉틀 (Sewing Machine)",
            "재단기 (Guillotine Cutter)",
            "코팅기 (UV Coating Machine)"
        ],
        "printable_sizes": {
            "A1": {"price": 2000, "description": "장당 2000원"},
            "A0": {"price": 3000, "description": "장당 3000원"},
            "B1": {"price": 2500, "description": "장당 2500원"},
            "B0": {"price": 4000, "description": "장당 4000원"},
            "custom": {"price": 4000, "description": "맞춤 사이즈 +4000원"}
        },
        "post_processing": {
            "coating": ["무광 코팅", "유광 코팅", "UV 코팅"],
            "cutting": ["일반 재단", "아일렛", "재봉"],
            "special": ["고리", "지퍼", "벨크로"]
        },
        "paper_types": {
            "배너천": {"price": 0, "description": "기본 재질"},
            "타프린": {"price": 500, "description": "고급 재질"},
            "메쉬천": {"price": 800, "description": "통기성 재질"},
            "실크천": {"price": 1200, "description": "고급 실크 재질"},
            "PVC": {"price": 1000, "description": "내구성 PVC 재질"}
        },
        "services": {
            "categories": ["배너", "현수막", "플래카드", "롤업"],
            "min_order": {"배너": 1, "현수막": 1, "플래카드": 5, "롤업": 1},
            "avg_production_time": 3,
            "delivery": ["직접 수령", "택배", "화물"],
            "pricing_type": "고정가"
        },
        "discounts": {
            "5개 이상": "10% 할인",
            "10개 이상": "20% 할인"
        },
        "score_breakdown": {
            "price": 0.85,
            "quality": 0.88,
            "speed": 0.85,
            "location": 0.75,
            "reliability": 0.82
        }
    }
]

def get_all_shops() -> List[Dict]:
    """모든 인쇄소 데이터 반환"""
    return DUMMY_SHOPS

def get_shop_by_id(shop_id: str) -> Dict:
    """ID로 인쇄소 찾기"""
    for shop in DUMMY_SHOPS:
        if shop["shop_id"] == shop_id:
            return shop
    return None

def get_shops_by_category(category: str) -> List[Dict]:
    """카테고리별 인쇄소 찾기"""
    result = []
    for shop in DUMMY_SHOPS:
        if category in shop["services"]["categories"]:
            result.append(shop)
    return result

def calculate_price(shop: Dict, item_type: str, quantity: int, material: str, finishing: str = None) -> Dict:
    """가격 계산"""
    base_price = 0
    
    # 기본 가격 (아이템 타입별)
    if item_type == "BUSINESS_CARD":
        base_price = 50000  # 100부 기준
    elif item_type == "STICKER":
        base_price = 30000  # 100부 기준
    elif item_type == "BANNER":
        base_price = 80000  # 1개 기준
    elif item_type == "POSTER":
        base_price = 20000  # 10부 기준
    
    # 수량에 따른 가격 조정
    if item_type in ["BUSINESS_CARD", "STICKER", "POSTER"]:
        quantity_factor = max(1, quantity // 100)
        base_price *= quantity_factor
    
    # 재질 추가 비용
    material_cost = 0
    if material in shop["paper_types"]:
        material_cost = shop["paper_types"][material]["price"] * quantity
    
    # 후가공 비용
    finishing_cost = 0
    if finishing and finishing != "NONE":
        finishing_cost = 5000 * quantity  # 예시 비용
    
    total_price = base_price + material_cost + finishing_cost
    
    # 할인 적용
    discount_rate = 0
    if quantity >= 1000:
        discount_rate = 0.3
    elif quantity >= 500:
        discount_rate = 0.2
    elif quantity >= 100:
        discount_rate = 0.1
    
    final_price = int(total_price * (1 - discount_rate))
    
    return {
        "base_price": base_price,
        "material_cost": material_cost,
        "finishing_cost": finishing_cost,
        "total_price": final_price,
        "discount_rate": discount_rate,
        "price_per_unit": final_price / quantity if quantity > 0 else 0
    }
