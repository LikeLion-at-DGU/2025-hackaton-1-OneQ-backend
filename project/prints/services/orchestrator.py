# prints/services/orchestrator.py
from __future__ import annotations
from typing import Dict, List
from . import ai, spec, dummy_data
from datetime import datetime

def handle_message(history: List[Dict], slots: Dict, user_msg: str) -> Dict:
    """
    메인 메시지 처리 함수
    """
    # 히스토리에 현재 입력 추가
    history = (history or []) + [{"role": "user", "content": user_msg}]
    
    # AI가 다음 액션 결정
    action_payload = ai.ask_action(history, slots)
    act = action_payload.get("action", "ASK")
    
    print(f"DEBUG: AI action={act}, payload={action_payload}")
    
    # ASK: 견적 정보 수집
    if act == "ASK":
        return _handle_ask_action(action_payload, slots, user_msg)
    
    # EXPLAIN: 용어 설명
    elif act == "EXPLAIN":
        return _handle_explain_action(action_payload, slots, user_msg)
    
    # CONFIRM: 최종 확인
    elif act == "CONFIRM":
        return _handle_confirm_action(action_payload, slots, user_msg)
    
    # MATCH: 견적 리포트 생성
    elif act == "MATCH":
        return _handle_match_action(action_payload, slots)
    
    # 기본: 다음 질문
    else:
        return _handle_default_action(slots)

def _handle_ask_action(action_payload: Dict, slots: Dict, user_msg: str) -> Dict:
    """ASK 액션 처리"""
    # 수정 요청인지 확인
    modification_request = _check_modification_request(user_msg)
    if modification_request:
        # 해당 슬롯 초기화
        slots[modification_request] = None
        print(f"DEBUG: 수정 요청 감지 - {modification_request} 슬롯 초기화")
    
    # 사용자 입력을 슬롯에 병합
    filled_slots = action_payload.get("filled_slots", {})
    filled_slots["_user_text"] = user_msg
    slots = spec.merge_and_normalize(slots or {}, filled_slots)
    
    # 누락된 슬롯 확인
    missing = spec.find_missing(slots)
    
    # 다음 질문 결정
    next_q = spec.next_question(slots)
    question = action_payload.get("question") or next_q["question"]
    choices = next_q.get("choices", [])
    
    print(f"DEBUG: ASK - missing={missing}, question={question}")
    
    return {
        "type": "ask",
        "question": question,
        "choices": choices,
        "slots": slots,
        "missing": missing
    }

def _check_modification_request(user_msg: str) -> str:
    """수정 요청 감지 및 해당 슬롯 반환"""
    user_msg = user_msg.lower()
    
    # 수정 요청 키워드 매핑
    modification_keywords = {
        "수량": ["수량", "몇 부", "부수", "개수"],
        "size": ["사이즈", "크기", "규격"],
        "material": ["재질", "종이", "용지"],
        "finishing": ["마감", "코팅", "후가공"],
        "color_mode": ["색상", "컬러", "색깔"],
        "due_days": ["납기", "기간", "일정"],
        "region": ["지역", "위치", "장소"]
    }
    
    for slot, keywords in modification_keywords.items():
        for keyword in keywords:
            if keyword in user_msg and ("다시" in user_msg or "수정" in user_msg or "바꿀" in user_msg):
                return slot
    
    return None

def _handle_explain_action(action_payload: Dict, slots: Dict, user_msg: str) -> Dict:
    """EXPLAIN 액션 처리"""
    term = action_payload.get("term", "")
    term_data = spec.explain_term(term)
    
    # 용어 설명 생성
    explanation = ai.cached_polish(term, term_data.get("facts", {}), user_msg)
    
    # 사용자가 용어 설명 후 결정을 내렸는지 확인
    decision_keywords = [
        "로 하겠습니다", "로 할래", "로 해줘", "로 하겠어", "로 할게",
        "그거로 할게요", "그거로요", "네 그거요", "그거로 하겠어요", 
        "그걸로 할게요", "그걸로요", "그거로 하겠습니다", "그걸로 하겠습니다",
        "그거로 할게", "그걸로 할게", "그거로요", "그걸로요"
    ]
    is_decision = any(keyword in user_msg for keyword in decision_keywords)
    
    if is_decision:
        # 사용자가 결정을 내렸으므로 해당 정보를 슬롯에 저장하고 다음 질문으로
        filled_slots = action_payload.get("filled_slots", {})
        filled_slots["_user_text"] = user_msg
        slots = spec.merge_and_normalize(slots or {}, filled_slots)
        
        # 다음 질문 결정
        next_q = spec.next_question(slots)
        
        return {
            "type": "ask",
            "question": next_q["question"],
            "choices": next_q.get("choices", []),
            "slots": slots,
            "missing": spec.find_missing(slots)
        }
    
    return {
        "type": "explain",
        "term": term_data["term"],
        "text": explanation,
        "slots": slots
    }

def _handle_match_action(action_payload: Dict, slots: Dict) -> Dict:
    """MATCH 액션 처리 - 최종 견적서 생성 및 인쇄소 추천"""
    # 최종 견적서 생성
    quote_report = ai.generate_quote_report(slots)
    
    # 조건에 맞는 인쇄소 TOP 3 추천
    recommended_shops = ai.recommend_shops(slots)
    
    # 추천 인쇄소 정보 포맷팅
    shop_recommendations = []
    for i, shop in enumerate(recommended_shops, 1):
        shop_info = ai.format_shop_recommendation(shop)
        shop_recommendations.append(f"🥇 {i}위\n{shop_info}")
    
    # 최종 메시지 조합
    final_message = f"""{quote_report}

🎯 추천 인쇄소
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{chr(10).join(shop_recommendations)}

💡 다음 단계:
1. 추천 인쇄소에 직접 연락하여 당신만의 인쇄를 즐기세요! 🎨✨"""
    
    return {
        "type": "match",
        "quote_report": quote_report,
        "recommended_shops": recommended_shops,
        "message": final_message,
        "slots": slots
    }

def _handle_confirm_action(action_payload: Dict, slots: Dict, user_msg: str) -> Dict:
    """CONFIRM 액션 처리"""
    # 슬롯 병합
    filled_slots = action_payload.get("filled_slots", {})
    slots = spec.merge_and_normalize(slots or {}, filled_slots)
    
    # 사용자가 긍정 응답을 했는지 확인
    positive_keywords = [
        "네 맞습니다", "네 맞아요", "맞습니다", "맞아요", "그래요", "좋아요", 
        "괜찮아요", "네 그렇습니다", "그렇습니다", "네 그렇네요", "그렇네요", 
        "네 맞아", "맞아", "네", "맞아요", "그래", "좋아", "괜찮아"
    ]
    
    is_positive = any(keyword in user_msg for keyword in positive_keywords)
    
    if is_positive:
        # 긍정 응답이면 MATCH 액션으로 넘어가기
        return _handle_match_action({}, slots)
    
    # 검증
    is_valid, errors = spec.validate(slots)
    
    if not is_valid:
        # 오류가 있으면 수정 모드로
        next_q = spec.next_question(slots)
        return {
            "type": "ask",
            "question": next_q["question"],
            "choices": next_q.get("choices", []),
            "slots": slots,
            "missing": spec.find_missing(slots),
            "errors": errors
        }
    
    # 모든 정보가 완료되면 최종 확인
    summary = spec.render_summary(slots)
    
    return {
        "type": "confirm",
        "summary": summary,
        "slots": slots,
        "choices": ["네 맞습니다", "네 맞아요", "맞습니다", "맞아요", "그래요", "좋아요", "괜찮아요", "네 그렇습니다", "수정할 부분이 있습니다", "아니요", "수정할게요", "바꿀 부분이 있어요"]
    }

def _handle_default_action(slots: Dict) -> Dict:
    """기본 액션 처리"""
    next_q = spec.next_question(slots or {})
    return {
        "type": "ask",
        "question": next_q["question"],
        "choices": next_q.get("choices", []),
        "slots": slots or {}
    }
