# prints/services/conversation_manager.py
from typing import Dict, List, Optional
from datetime import datetime

class ConversationManager:
    """대화 히스토리 및 상태 관리"""
    
    def __init__(self):
        self.conversation_history = []
        self.current_slots = {}
        self.conversation_state = 'collecting'  # collecting, confirming, modifying
    
    def add_message(self, role: str, content: str):
        """대화 히스토리 추가"""
        self.conversation_history.append({
            'role': role,
            'content': content,
            'timestamp': datetime.now().isoformat()
        })
    
    def get_recent_context(self, max_messages: int = 10) -> str:
        """대화 컨텍스트 생성 (더 많은 메시지 포함)"""
        if not self.conversation_history:
            return ""
        
        # 더 많은 메시지를 포함하여 맥락 유지
        recent_messages = self.conversation_history[-max_messages:]
        context = ""
        
        for msg in recent_messages:
            context += f"{msg['role']}: {msg['content']}\n"
        
        return context.strip()
    
    def update_slots(self, slots: Dict):
        """슬롯 정보 업데이트"""
        self.current_slots.update(slots)
    
    def get_slots(self) -> Dict:
        """현재 슬롯 정보 반환"""
        return self.current_slots.copy()
    
    def clear_slot(self, slot_name: str):
        """특정 슬롯 초기화 (수정 시 사용)"""
        if slot_name in self.current_slots:
            del self.current_slots[slot_name]
    
    def set_state(self, state: str):
        """대화 상태 설정"""
        self.conversation_state = state
    
    def get_state(self) -> str:
        """현재 대화 상태 반환"""
        return self.conversation_state
    
    def is_all_slots_filled(self, required_slots: List[str]) -> bool:
        """필요한 모든 슬롯이 채워졌는지 확인"""
        for slot in required_slots:
            if slot not in self.current_slots or not self.current_slots[slot]:
                return False
        return True
    
    def get_missing_slots(self, required_slots: List[str]) -> List[str]:
        """아직 채워지지 않은 슬롯들 반환"""
        missing = []
        for slot in required_slots:
            if slot not in self.current_slots or not self.current_slots[slot]:
                missing.append(slot)
        return missing
    
    def reset_conversation(self):
        """대화 초기화"""
        self.conversation_history = []
        self.current_slots = {}
        self.conversation_state = 'collecting'
    
    def get_conversation_summary(self) -> str:
        """대화 요약 생성"""
        if not self.conversation_history:
            return "대화 기록이 없습니다."
        
        summary = f"총 {len(self.conversation_history)}개의 메시지\n"
        summary += f"현재 상태: {self.conversation_state}\n"
        summary += f"수집된 정보: {self.current_slots}\n"
        
        return summary
