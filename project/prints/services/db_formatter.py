# prints/services/db_formatter.py
from typing import Dict, List

class DBFormatter:
    """DB 정보를 GPT 컨텍스트로 포맷팅"""
    
    def __init__(self, category_info: Dict, category: str):
        self.category_info = category_info
        self.category = category
    
    def format_context_for_gpt(self) -> str:
        """DB 정보를 GPT가 이해하기 쉽게 포맷팅"""
        if not self.category_info:
            return f"카테고리: {self.category}\n등록된 인쇄소 정보가 없습니다."
        
        context = f"📋 {self.category} 제작 가능한 옵션들\n\n"
        
        # 카테고리별 필드 매핑
        field_mapping = self._get_field_mapping()
        
        if self.category in field_mapping:
            for field_name, db_field in field_mapping[self.category].items():
                if db_field in self.category_info:
                    content = self.category_info[db_field]
                    if content.strip():  # 내용이 있는 경우만 추가
                        # 필드명을 한글로 변환
                        korean_name = self._get_korean_field_name(field_name)
                        context += f"🔹 {korean_name}:\n{content}\n\n"
        
        context += "💡 위 정보를 바탕으로 사용자의 질문에 답변하고, 해당 옵션들을 추천해주세요."
        
        return context
    
    def _get_korean_field_name(self, field_name: str) -> str:
        """영어 필드명을 한글로 변환"""
        korean_names = {
            'papers': '용지 종류',
            'quantities': '수량 옵션',
            'printing': '인쇄 방식',
            'finishing': '후가공 옵션',
            'sizes': '사이즈 옵션',
            'stands': '거치대 옵션',
            'coating': '코팅 옵션',
            'types': '종류 옵션',
            'processing': '가공 옵션',
            'folding': '접지 옵션'
        }
        return korean_names.get(field_name, field_name)
    
    def _get_field_mapping(self) -> Dict:
        """카테고리별 필드 매핑"""
        return {
            '명함': {
                'papers': 'business_card_paper_options',
                'printing': 'business_card_printing_options',
                'finishing': 'business_card_finishing_options',
                'min_quantity': 'business_card_min_quantity'
            },
            '배너': {
                'sizes': 'banner_size_options',
                'stands': 'banner_stand_options',
                'min_quantity': 'banner_min_quantity'
            },
            '포스터': {
                'papers': 'poster_paper_options',
                'coating': 'poster_coating_options',
                'min_quantity': 'poster_min_quantity'
            },
            '스티커': {
                'types': 'sticker_type_options',
                'sizes': 'sticker_size_options',
                'min_quantity': 'sticker_min_quantity'
            },
            '현수막': {
                'sizes': 'banner_large_size_options',
                'processing': 'banner_large_processing_options',
                'min_quantity': 'banner_large_min_quantity'
            },
            '브로슈어': {
                'papers': 'brochure_paper_options',
                'folding': 'brochure_folding_options',
                'sizes': 'brochure_size_options',
                'min_quantity': 'brochure_min_quantity'
            }
        }
    
    def get_available_options(self, field_name: str) -> List[str]:
        """특정 필드의 사용 가능한 옵션들 추출"""
        field_mapping = self._get_field_mapping()
        
        if self.category not in field_mapping:
            return []
        
        db_field = field_mapping[self.category].get(field_name)
        if not db_field or db_field not in self.category_info:
            return []
        
        content = self.category_info[db_field]
        if not content:
            return []
        
        # 간단한 옵션 추출 (콜론 앞부분)
        options = []
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if ':' in line:
                option = line.split(':')[0].strip()
                if option:
                    options.append(option)
        
        return list(set(options))  # 중복 제거
