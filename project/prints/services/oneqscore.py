# prints/services/oneqscore.py
from __future__ import annotations
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import math
import re

from ..models import PrintShop

# ---------- 유틸: 슬롯 정규화 ----------
def _to_int(v, default=0) -> int:
    if v is None: return default
    if isinstance(v, int): return v
    s = str(v)
    s = re.sub(r"[^\d]", "", s)
    return int(s) if s else default

def _parse_size_mm(size: str) -> Tuple[Optional[int], Optional[int]]:
    """'90x50mm', '600×1800mm', 'A4' 등 처리 (A4/A3 등은 대략 mm로 맵핑)"""
    if not size: return (None, None)
    s = size.lower().replace(" ", "").replace("×", "x")
    m = re.match(r"^(\d{2,4})x(\d{2,4})(mm)?$", s)
    if m:
        return int(m.group(1)), int(m.group(2))
    # 간단 규격 치수(대표값)
    map_mm = {
        'a0': (841, 1189), 'a1': (594, 841), 'a2': (420, 594),
        'a3': (297, 420),  'a4': (210, 297), 'a5': (148, 210),
        'b3': (353, 500),  'b4': (250, 353), 'b5': (176, 250),
    }
    s2 = s.upper()
    if s2 in map_mm:
        return map_mm[s2]
    return (None, None)

def _area_cm2(w_mm: Optional[int], h_mm: Optional[int]) -> float:
    if not w_mm or not h_mm: return 0.0
    return (w_mm * h_mm) / 100.0

def _norm_finishing(finishing: str) -> str:
    f = (finishing or "").strip().lower()
    if "무광" in f or "matte" in f: return "MATTE"
    if "유광" in f or "gloss" in f: return "GLOSS"
    if "없"   in f: return "NONE"
    return f.upper() if f else "NONE"

# ---------- 인쇄소 규칙 로딩(없으면 기본값) ----------
def _shop_rules(shop: PrintShop, category: str) -> Dict:
    """temp_step2_data.pricing_rules / leadtime_profile 등에서 읽고, 없으면 기본값."""
    data = shop.temp_step2_data or {}
    pricing = (data.get("pricing_rules") or {}).get(category, {})
    lead = data.get("leadtime_profile") or {}
    capacity = data.get("capacity_info") or {}

    # 카테고리별 기본 단가/방식(휴리스틱)
    default_pricing = {
        "명함": {
            "mode": "unit",                 # 'unit' or 'area'
            "base_unit_price": 300,         # 1부 기본(원)
            "color_multiplier": 1.2,        # 컬러 가중치
            "duplex_multiplier": 1.5,       # 양면 가중치
            "finishing_prices": {"GLOSS": 50, "MATTE": 80, "NONE": 0}
        },
        "포스터": {
            "mode": "area",
            "rate_per_cm2": 0.02,           # cm²당 원
            "color_multiplier": 1.2,
            "duplex_multiplier": 1.7,
            "finishing_prices": {"GLOSS": 200, "MATTE": 250, "NONE": 0}
        },
        "배너": {
            "mode": "area",
            "rate_per_cm2": 0.015,
            "color_multiplier": 1.15,
            "duplex_multiplier": 1.0,       # 배너는 양면 거의 없음
            "finishing_prices": {"NONE": 0}
        },
        "스티커": {
            "mode": "area",
            "rate_per_cm2": 0.03,
            "color_multiplier": 1.2,
            "duplex_multiplier": 1.0,
            "finishing_prices": {"GLOSS": 60, "MATTE": 80, "NONE": 0}
        },
        "현수막": {
            "mode": "area",
            "rate_per_cm2": 0.012,
            "color_multiplier": 1.0,
            "duplex_multiplier": 1.0,
            "finishing_prices": {"NONE": 0}
        },
        "브로슈어": {
            "mode": "unit",
            "base_unit_price": 700,
            "color_multiplier": 1.2,
            "duplex_multiplier": 1.6,
            "finishing_prices": {"NONE": 0}
        }
    }

    # 납기 기본(시간)
    default_lead = {
        "base_hours": 24,                  # 샵 기본 리드타임
        "per_100_units": 1.5,              # 100부 당 추가
        "rush_multiplier": 0.85,           # 급행 여지(작아질수록 빠름)
        "finishing_add_hours": {           # 후가공에 따른 추가시간
            "GLOSS": 6, "MATTE": 8
        }
    }

    # 용량/처리량(작업 적합도 계산에 사용)
    default_capacity = {
        "daily_capacity_units": 2000
    }

    return {
        "pricing": {**default_pricing.get(category, {}), **pricing},
        "lead":    {**default_lead, **lead},
        "capacity": {**default_capacity, **capacity},
    }

# ---------- 가격 추정 ----------
def _estimate_price(shop: PrintShop, category: str, slots: Dict) -> int:
    q = _to_int(slots.get("quantity"), 1)
    size = slots.get("size")
    w, h = _parse_size_mm(size)
    finishing = _norm_finishing(slots.get("finishing"))
    printing = (slots.get("printing") or "").lower()

    rules = _shop_rules(shop, category)
    pr = rules["pricing"]
    mode = pr.get("mode", "unit")

    color_mul = pr.get("color_multiplier", 1.0)
    duplex_mul = pr.get("duplex_multiplier", 1.0)
    is_color = "컬러" in printing or "color" in printing or slots.get("coating")  # 포스터/스티커 등 컬러 기본 가정
    is_duplex = "양면" in printing

    if mode == "area":
        area = _area_cm2(w, h)
        base = area * float(pr.get("rate_per_cm2", 0.02))
    else:
        base = float(pr.get("base_unit_price", 300))

    if is_color:  base *= color_mul
    if is_duplex: base *= duplex_mul

    fin_prices = pr.get("finishing_prices", {})
    base += float(fin_prices.get(finishing, fin_prices.get("NONE", 0)))

    total = int(round(base * q))
    return max(total, 0)

# ---------- 납기 ETA ----------
def _estimate_eta_hours(shop: PrintShop, category: str, slots: Dict) -> float:
    q = _to_int(slots.get("quantity"), 1)
    finishing = _norm_finishing(slots.get("finishing"))
    user_region = (slots.get("region") or "").replace(" ", "")
    w, h = _parse_size_mm(slots.get("size"))

    rules = _shop_rules(shop, category)
    lead = rules["lead"]
    base = float(lead.get("base_hours", 24))
    per100 = float(lead.get("per_100_units", 1.5))
    rush = float(lead.get("rush_multiplier", 0.85))
    fin_add = float((lead.get("finishing_add_hours") or {}).get(finishing, 0))

    # 수량에 따른 증가(간단)
    qty_term = (q / 100.0) * per100

    # 대형물(배너/현수막/포스터) 면적에 따른 가중(간단)
    area_term = 0.0
    if category in ("배너", "현수막", "포스터"):
        area = _area_cm2(w, h)
        area_term = min(24.0, area / 10000.0)  # 면적 10k cm² 당 +1h, 최대 +24h

    eta = (base + qty_term + area_term + fin_add) * rush

    # 같은 구/동이면(주소에 지역 문자열 포함 시) 물류 여지로 약간 단축
    if user_region and shop.address and user_region in shop.address.replace(" ", ""):
        eta = max(0.0, eta - 6.0)

    return eta

def _due_fit(now: datetime, eta_hours: float, due_days: int) -> float:
    """요청 납기(due_days일) 내 가능성으로 0~100점."""
    finish_time = now + timedelta(hours=eta_hours)
    deadline = now + timedelta(days=int(max(due_days, 1)))

    gap_h = (deadline - finish_time).total_seconds() / 3600.0  # +면 여유
    if gap_h >= 0:   return 100.0
    if gap_h >= -24: return 70.0
    if gap_h >= -48: return 40.0
    if gap_h >= -72: return 10.0
    return 0.0

# ---------- 작업 적합도 ----------
def _contains(text: str, needle: str) -> bool:
    return (text or "").lower().find((needle or "").lower()) >= 0

def _work_fit(shop: PrintShop, category: str, slots: Dict) -> float:
    """카테고리별 텍스트 필드에서 매칭(용지/후가공/사이즈) + 수량 여유 기반 간단 0~100."""
    s = 0.0
    q = _to_int(slots.get("quantity"), 1)
    finishing = _norm_finishing(slots.get("finishing"))
    size = slots.get("size") or ""
    paper = (slots.get("paper") or slots.get("material") or "")

    # 카테고리별 텍스트 소스(현재 모델의 문자열 필드 활용)
    if category == "명함":
        paper_src = shop.business_card_papers
        fin_src   = shop.business_card_finishing
        size_src  = shop.business_card_quantities  # 사이즈 전용 필드가 없어서 대체/없으면 0점 처리
    elif category == "포스터":
        paper_src = shop.poster_papers
        fin_src   = shop.poster_coating
        size_src  = shop.poster_quantities
    elif category == "배너":
        paper_src = shop.banner_sizes  # 배너는 소재보다 사이즈/거치대를 주로 확인
        fin_src   = shop.banner_stands
        size_src  = shop.banner_quantities
    elif category == "스티커":
        paper_src = shop.sticker_types
        fin_src   = shop.sticker_sizes
        size_src  = shop.sticker_quantities
    elif category == "현수막":
        paper_src = shop.banner_large_sizes
        fin_src   = shop.banner_large_processing
        size_src  = shop.banner_large_quantities
    elif category == "브로슈어":
        paper_src = shop.brochure_papers
        fin_src   = shop.brochure_folding
        size_src  = shop.brochure_sizes
    else:
        paper_src = fin_src = size_src = ""

    # 용지/후가공/사이즈 문자열 매칭(있으면 가점)
    if paper and _contains(paper_src, paper): s += 35
    if finishing != "NONE" and _contains(fin_src, finishing): s += 25
    if size and _contains(size_src, size): s += 20

    # 처리량 여유
    cap = (shop.temp_step2_data or {}).get("capacity_info", {})
    daily = int(cap.get("daily_capacity_units", 2000))
    margin = max(0.0, (daily - q) / max(1, daily))  # 0~1
    s += 20 * margin

    return round(min(100.0, s), 1)

# ---------- 가격 점수(상대) ----------
def _price_fit_scores(total_prices: Dict[int, int], budget: Optional[int]) -> Dict[int, float]:
    vals = list(total_prices.values())
    mn, mx = min(vals), max(vals)
    rng = (mx - mn) or 1
    scores: Dict[int, float] = {}
    for pid, price in total_prices.items():
        base = 100.0 * (mx - price) / rng  # 싸면 높음
        if budget and budget > 0 and price > budget:
            over = (price - budget) / float(budget)
            penalty = min(100.0, over * 200.0)  # 초과율 50%면 100점 감점
            base = max(0.0, base - penalty)
        scores[pid] = round(base, 1)
    return scores

# ---------- 메인: 점수 계산 + Top3 ----------
def score_and_rank(slots: Dict, shops: List[PrintShop]) -> Dict:
    category = slots.get("category") or slots.get("item_type") or "명함"
    # ChatSession에는 '명함/배너/포스터...' 한글 카테고리로 저장되는 구조
    due_days = _to_int(slots.get("due_days"), 3)
    budget = _to_int(slots.get("budget"), 0)

    # 후보: 해당 카테고리를 지원하는 활성/완료 인쇄소(views/AI서비스와 동일 기준)
    candidates = []
    for s in shops:
        try:
            if s.is_active and s.registration_status == "completed" and category in (s.available_categories or []):
                candidates.append(s)
        except Exception:
            continue
    if not candidates:
        return {"items": [], "count": 0, "all": []}

    # 가격/납기/작업 추정
    total_prices: Dict[int, int] = {}
    due_scores: Dict[int, float] = {}
    work_scores: Dict[int, float] = {}

    now = datetime.now()
    rows = []

    for shop in candidates:
        price = _estimate_price(shop, category, slots)
        total_prices[shop.id] = price
        eta = _estimate_eta_hours(shop, category, slots)
        due_scores[shop.id] = _due_fit(now, eta, due_days)
        work_scores[shop.id] = _work_fit(shop, category, slots)

        rows.append({
            "shop_id": shop.id,
            "shop_name": shop.name,
            "total_price": price,
            "eta_hours": round(eta, 1),
            "due_score": due_scores[shop.id],
            "work_score": work_scores[shop.id],
            "phone": shop.phone,
            "production_time": shop.production_time,
            "delivery_options": shop.delivery_options,
            "is_verified": shop.is_verified,
        })

    price_scores = _price_fit_scores(total_prices, budget)

    # 가중합(40/30/30)
    for r in rows:
        sid = r["shop_id"]
        total = 0.4 * price_scores[sid] + 0.3 * due_scores[sid] + 0.3 * work_scores[sid]
        r["scores"] = {
            "price": price_scores[sid],
            "due": due_scores[sid],
            "work": work_scores[sid],
            "oneq_total": round(total, 2)
        }

    rows_sorted = sorted(rows, key=lambda x: x["scores"]["oneq_total"], reverse=True)
    top3 = rows_sorted[:3]

    return {
        "count": len(top3),
        "items": top3,
        "all": rows_sorted
    }
