# prints/services/gpt_client.py
import json
import os
from typing import Dict, Optional
from dotenv import load_dotenv

try:
    import openai
except ImportError:
    openai = None

# .env 파일 로드
load_dotenv()

class GPTClient:
    """GPT API 클라이언트"""
    
    def __init__(self):
        # OpenAI API 키 설정
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.model = os.getenv('GPT_MODEL', 'gpt-4o-mini')
        self.temperature = float(os.getenv('GPT_TEMPERATURE', '0.7'))
    
    def process_conversation(self, prompt: str) -> Dict:
        """GPT API 호출하여 대화 처리"""
        print(f"=== GPT API 호출 시작 ===")
        print(f"모델: {self.model}")
        print(f"온도: {self.temperature}")
        
        if not openai:
            print("OpenAI 모듈이 설치되지 않음")
            return {
                "error": "OpenAI 모듈이 설치되지 않았습니다.",
                "action": "error",
                "message": "죄송합니다. AI 서비스가 일시적으로 사용할 수 없습니다.",
                "slots": {}
            }
        
        if not self.api_key:
            print("OpenAI API 키가 설정되지 않음")
            return {
                "error": "OpenAI API 키가 설정되지 않았습니다.",
                "action": "error", 
                "message": "죄송합니다. AI 서비스가 일시적으로 사용할 수 없습니다.",
                "slots": {}
            }
        
        try:
            print("OpenAI API 호출 중...")
            # OpenAI API 1.0.0+ 버전용 코드
            client = openai.OpenAI(api_key=self.api_key)
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system", 
                        "content": (
                            "너는 인쇄 전문가 챗봇이다. DB 정보만을 바탕으로 정확하고 친근한 응답을 제공한다.. 답변은 '순수 텍스트'로만 작성한다. "
                            "마크다운 금지(굵게 **, _이탤릭_, # 헤더, ``` 코드블록, 표, 링크 포맷 전부 금지). "
                            "강조가 필요하면 문장으로 자연스럽게 표현한다. "
                            "요청이 추천/선택지라면 반드시 '왜 그게 맞는지'를 1~3문장으로 설명하고, "
                            "상황 바뀔 때의 '대안 1~2개'와 '다음 행동'까지 안내한다. "
                            "목록이 필요하면 하이픈(-) 기반 짧은 불릿만 사용한다."
                        )
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                temperature=self.temperature
            )
            
            # JSON 응답 파싱
            response_content = response.choices[0].message.content
            print(f"GPT 원본 응답: {response_content}")
            
            try:
                parsed_response = json.loads(response_content)
                print(f"JSON 파싱 성공: {parsed_response}")
                return parsed_response
            except json.JSONDecodeError as e:
                print(f"JSON 파싱 오류: {e}")
                print(f"파싱 실패한 응답: {response_content}")
                # JSON 파싱 오류 시 기본 응답
                return {
                    "action": "ask",
                    "message": "죄송합니다. 다시 한 번 말씀해주세요.",
                    "slots": {}
                }
            
        except Exception as e:
            print(f"GPT API 호출 중 오류: {e}")
            # 기타 오류 시 에러 응답
            return {
                "error": str(e),
                "action": "error",
                "message": "죄송합니다. 일시적인 오류가 발생했습니다.",
                "slots": {}
            }
    
    def is_available(self) -> bool:
        """GPT API 사용 가능 여부 확인"""
        return bool(os.getenv('OPENAI_API_KEY'))
