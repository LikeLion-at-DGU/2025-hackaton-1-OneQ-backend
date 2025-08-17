# prints/services/ai.py
from __future__ import annotations
import os, json, time, random
from typing import List, Dict, Optional
from openai import OpenAI, APIError

_client: OpenAI | None = None
_EXPLAIN_CACHE = {}  # 용어 설명 캐시

def _get_client() -> OpenAI:
    global _client
    if _client is None:
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY 미설정")
        _client = OpenAI(api_key=key)
    return _client

def _chat_with_backoff(**kwargs):
    """백오프가 적용된 LLM 호출 (타임아웃 포함)"""
    delay = 1.0
    for attempt in range(3):
        try:
            kwargs.setdefault('timeout', 30)
            return _get_client().chat.completions.create(**kwargs)
        except Exception as e:
            msg = str(e).lower()
            if "rate limit" in msg or "429" in msg:
                if attempt < 2:
                    time.sleep(delay + random.uniform(0, 0.3))
                    delay = min(delay * 2, 10)
                    continue
            raise
    raise RuntimeError("LLM rate limit: retries exhausted")

def prune_history(history: List[Dict], keep: int = 8) -> List[Dict]:
    """히스토리 자르기 - 마지막 N턴만 보내"""
    return (history or [])[-keep:]

# 견적 위저드 시스템 프롬프트
_SYSTEM = """
당신은 인쇄 견적 전문 챗봇입니다. 사용자와 대화하면서 견적 정보를 수집하고, 최종 견적서를 제공합니다.

**주요 기능:**
1. 견적 정보 수집 (수량, 사이즈, 재질, 후가공 등)
2. 용어 설명 (사용자가 모르는 용어 질문 시)
3. 최종 확인 및 수정
4. 견적 리포트 생성

**대화 플로우:**
1. ASK: 견적 정보 수집 (다음 질문)
2. EXPLAIN: 용어 설명
3. CONFIRM: 최종 확인
4. MATCH: 견적 리포트 생성

**의도 판단:**
- "뭐야?", "설명해", "차이점" → EXPLAIN (용어 설명)
- "~로 할래", "~로 해줘", "~로 하겠습니다", "그거로 할게요", "그거로요", "네 그거요", "그거로 하겠어요", "그걸로 할게요", "그걸로요", "그거로 하겠습니다", "그걸로 하겠습니다", 숫자/구체정보 → ASK (정보 수집)
- "네", "맞아요", "확인", "네 맞습니다", "네 맞아요", "맞습니다", "맞아요", "그래요", "그래", "좋아요", "좋아", "괜찮아요", "괜찮아", "네 그렇습니다", "그렇습니다", "네 그렇네요", "그렇네요", "네 맞아", "맞아", "네 맞습니다", "맞습니다" → MATCH (최종 견적서 생성 및 인쇄소 추천)
- "아니요", "수정", "바꿀래", "다시", "재질 다시", "수량 다시", "사이즈 다시", "마감 다시", "색상 다시", "납기 다시", "지역 다시" → ASK (수정 모드)

**중요한 규칙:**
- 사용자가 이미 설명받은 용어에 대해 "~로 하겠습니다"라고 결정하면, 그 용어를 다시 설명하지 말고 다음 정보 수집으로 넘어가세요
- 용어 설명 후 사용자가 결정을 내리면, 그 정보를 filled_slots에 추가하고 다음 질문을 하세요
- 선택지를 제공할 때는 해당 인쇄소가 실제로 보유하고 있는 옵션만 제시하세요
- 예: 코팅 옵션은 해당 인쇄소의 post_processing.coating 목록에서만 선택
- 질문에서 예시를 들 때는 반드시 용어사전에 있는 용어들만 언급하세요
- 용어사전에 없는 용어는 절대 제안하지 마세요 (예: 모조지, 크라프트지 등)

**질문별 용어사전 예시 (반드시 이 용어들만 사용):**
- 수량 질문: "몇 부 필요하신가요? (예: 100부, 200부, 500부, 1000부)"
- 사이즈 질문: "사이즈는 어떻게 하시겠어요? (예: 90x50mm, 86x54mm, A4, A3, A1, A0)"
- 재질 질문: "재질은 무엇으로 할까요? (예: 아트지, 스노우지, 반누보 186g, 휘라레 216g, 스타드림쿼츠 240g, 키칼라아이스골드 230g, 벨벳 300g, PP 250gsm, PET 250gsm, 반투명 PP, 메탈 PP, 배너천, 타프린, 메쉬천, 실크천, PVC)"
- 마감/코팅 질문: "마감(코팅)은 무엇으로 할까요? (예: 무광, 유광, 스팟 UV, 에폭시, UV 코팅, 매트 코팅)"
- 색상 질문: "인쇄 색상은 어떻게 할까요? (예: 단면 컬러, 양면 컬러, 단면 흑백)"
- 스티커 형태 질문: "스티커 모양은 어떻게 할까요? (예: 사각, 원형, 자유형(도무송))"
- 라미네이팅 질문: "라미네이팅(필름)은 적용할까요? (예: 무광 라미, 유광 라미)"
- 배너 고리 질문: "배너 고리(아일렛)는 어디에 뚫을까요? (예: 모서리 4개, 상단 2개)"
- 납기 질문: "납기는 며칠 후면 좋을까요? (예: 1일, 2일, 3일, 5일, 7일)"
- 지역 질문: "지역은 어디로 설정할까요? (예: 서울-중구, 서울-종로, 경기-성남)"

**중요 규칙:**
- 사용자가 이미 제공한 정보는 다시 묻지 마세요
- 용어 설명 요청 시 친절하고 자세히 설명하세요
- 용어 설명 후 사용자가 "~로 하겠습니다"라고 결정하면, 그 정보를 슬롯에 저장하고 다음 질문으로 넘어가세요
- 최종 확인 시 모든 정보를 정리해서 보여주세요
- 수정 요청 시 해당 부분으로 돌아가세요
- **질문 생성 시 반드시 위의 예시 형식을 그대로 사용하세요 (괄호와 예시 포함)**

JSON 응답 형식:
{
  "action": "ASK|EXPLAIN|CONFIRM|MATCH",
  "question": "ASK일 때 질문",
  "filled_slots": {"slot_name": "value"},
  "term": "EXPLAIN일 때 용어명",
  "choices": ["선택지1", "선택지2"]
}

**용어 설명 후 결정 처리:**
- 사용자가 용어 설명 후 "~로 하겠습니다", "그거로 할게요", "그거로요", "네 그거요", "그거로 하겠어요", "그걸로 할게요", "그걸로요", "그거로 하겠습니다", "그걸로 하겠습니다" 등으로 결정하면:
  - action: "EXPLAIN" 유지
  - filled_slots에 해당 결정 정보 포함
  - 예: {"action": "EXPLAIN", "term": "아트지", "filled_slots": {"material": "아트지 230g"}}

**슬롯 매핑 규칙:**
- 재질 관련: material 슬롯에 저장
- 마감/코팅 관련: finishing 슬롯에 저장
- 색상 관련: color_mode 슬롯에 저장
- 수량 관련: quantity 슬롯에 저장
- 사이즈 관련: size 슬롯에 저장
- 납기 관련: due_days 슬롯에 저장
- 지역 관련: region 슬롯에 저장

**현재 질문 슬롯 파악:**
- "재질은 무엇으로 할까요?" → material 슬롯
- "마감(코팅)은 무엇으로 할까요?" → finishing 슬롯
- "인쇄 색상은 어떻게 할까요?" → color_mode 슬롯
- "몇 부 필요하신가요?" → quantity 슬롯
- "사이즈는 어떻게 하시겠어요?" → size 슬롯
- "납기는 며칠 후면 좋을까요?" → due_days 슬롯
- "지역은 어디로 설정할까요?" → region 슬롯
"""

def ask_action(history: List[Dict], current_slots: Dict = None) -> Dict:
    """
    AI가 사용자 입력을 분석하여 다음 액션을 결정
    """
    pruned_history = prune_history(history, keep=8)
    
    # 현재 슬롯 상태를 컨텍스트로 추가
    context = f"현재 견적 정보: {current_slots or {}}"
    messages = [
        {"role": "system", "content": _SYSTEM},
        {"role": "system", "content": context}
    ] + pruned_history
    
    res = _chat_with_backoff(
        model="gpt-4o-mini",
        temperature=0.1,
        max_tokens=200,
        response_format={"type": "json_object"},
        messages=messages
    )
    
    result = json.loads(res.choices[0].message.content)
    print(f"DEBUG: AI response = {result}")
    
    return result

def polish_explanation(term: str, facts: Dict, user_question: str = "") -> str:
    """
    용어 설명을 자연스러운 문장으로 다듬기
    """
    if not facts:
        return f"'{term}'에 대한 정보가 아직 준비되지 않았습니다."
    
    # 차이점 비교 요청인지 확인
    is_comparison = any(keyword in user_question for keyword in ["차이", "비교", "다르다"])
    
    if is_comparison:
        sys_prompt = "인쇄 용어 비교 설명: 각 용어의 정의와 주요 차이점을 명확하게 설명하세요."
    else:
        sys_prompt = "인쇄 용어 설명: 정의, 효과, 비용, 사용처를 포함하여 친절하게 설명하세요."
    
    user_content = json.dumps({
        "term": term, 
        "facts": facts, 
        "user_question": user_question
    }, ensure_ascii=False)
    
    res = _chat_with_backoff(
        model="gpt-4o-mini",
        temperature=0.1,
        max_tokens=200,
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_content}
        ]
    )
    
    return (res.choices[0].message.content or "").strip()

def cached_polish(term: str, facts: Dict, user_question: str = "") -> str:
    """캐시된 용어 설명"""
    cache_key = f"{term}:{user_question}"
    if cache_key in _EXPLAIN_CACHE:
        return _EXPLAIN_CACHE[cache_key]
    
    text = polish_explanation(term, facts, user_question)
    _EXPLAIN_CACHE[cache_key] = text
    return text

def generate_quote_report(slots: Dict) -> str:
    """최종 견적서 생성"""
    item_type = slots.get("item_type", "BUSINESS_CARD")
    item_names = {
        "BUSINESS_CARD": "명함",
        "STICKER": "스티커",
        "BANNER": "배너",
        "SIGN": "간판"
    }
    item_name = item_names.get(item_type, item_type)
    
    lines = [
        f"📋 최종 견적서",
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

def recommend_shops(slots: Dict) -> List[Dict]:
    """조건에 맞는 최적의 인쇄소 추천 (상호명만)"""
    from . import dummy_data
    
    item_type = slots.get("item_type", "BUSINESS_CARD")
    region = slots.get("region", "")
    material = slots.get("material", "")
    finishing = slots.get("finishing", "")
    due_days = slots.get("due_days", 0)
    
    print(f"DEBUG: Searching for item_type={item_type}, region={region}, material={material}, finishing={finishing}, due_days={due_days}")
    
    all_shops = dummy_data.get_all_shops()
    print(f"DEBUG: Total shops available: {len(all_shops)}")
    
    scored_shops = []
    
    for shop in all_shops:
        try:
            score = 0
            shop_name = shop.get("shop_name", "Unknown")
            
            # 카테고리 매칭 (30점)
            services = shop.get("services", {})
            categories = services.get("categories", [])
            if isinstance(categories, list):
                item_type_lower = item_type.lower()
                if any(item_type_lower in cat.lower() for cat in categories):
                    score += 30
                    print(f"DEBUG: {shop_name} - 카테고리 매칭 +30점")
            
            # 지역 매칭 (20점)
            shop_location = shop.get("location", "")
            if region and region in shop_location:
                score += 20
                print(f"DEBUG: {shop_name} - 지역 정확 매칭 +20점")
            elif region and region.split('-')[0] in shop_location:
                score += 10
                print(f"DEBUG: {shop_name} - 지역 부분 매칭 +10점")
            
            # 재질 매칭 (20점)
            paper_types = shop.get("paper_types", {})
            if isinstance(paper_types, dict) and material and material in paper_types:
                score += 20
                print(f"DEBUG: {shop_name} - 재질 매칭 +20점")
            
            # 후가공 매칭 (15점)
            post_processing = shop.get("post_processing", {})
            coating_options = post_processing.get("coating", [])
            if isinstance(coating_options, list) and finishing:
                if finishing in coating_options:
                    score += 15
                    print(f"DEBUG: {shop_name} - 후가공 매칭 +15점")
            
            # 납기 매칭 (10점)
            avg_production_time = services.get("avg_production_time", 999)
            if due_days and isinstance(avg_production_time, (int, float)) and avg_production_time <= due_days:
                score += 10
                print(f"DEBUG: {shop_name} - 납기 매칭 +10점")
            
            # 평점 보너스 (5점)
            rating = shop.get("rating", 0)
            if isinstance(rating, (int, float)):
                score += rating * 5
                print(f"DEBUG: {shop_name} - 평점 보너스 +{rating * 5}점 (총점: {score})")
            
            # 최소 점수 조건 완화 - 모든 인쇄소를 추천 대상으로 포함
            scored_shops.append({
                "shop_name": shop_name,
                "match_score": score
            })
            print(f"DEBUG: {shop_name} - 추천 목록에 추가됨 (점수: {score})")
            
        except Exception as e:
            print(f"Error processing shop {shop.get('shop_name', 'Unknown')}: {e}")
            continue
    
    print(f"DEBUG: 최종 추천 인쇄소 수: {len(scored_shops)}")
    
    # 점수순으로 정렬하고 최고점 1개 반환
    scored_shops.sort(key=lambda x: x["match_score"], reverse=True)
    return scored_shops[:1]

def format_shop_recommendation(shop: Dict) -> str:
    """인쇄소 추천 정보 포맷팅"""
    return f"🏢 {shop['shop_name']}"
