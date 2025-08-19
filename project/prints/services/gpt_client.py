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
        if not openai:
            return {
                "error": "OpenAI 모듈이 설치되지 않았습니다.",
                "action": "error",
                "message": "죄송합니다. AI 서비스가 일시적으로 사용할 수 없습니다.",
                "slots": {}
            }
        
        if not self.api_key:
            return {
                "error": "OpenAI API 키가 설정되지 않았습니다.",
                "action": "error", 
                "message": "죄송합니다. AI 서비스가 일시적으로 사용할 수 없습니다.",
                "slots": {}
            }
        
        try:
            # OpenAI API 1.0.0+ 버전용 코드
            client = openai.OpenAI(api_key=self.api_key)
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system", 
                        "content": "당신은 인쇄 전문가입니다. DB 정보만을 바탕으로 정확하고 친근한 응답을 제공하세요."
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
            return json.loads(response_content)
            
        except json.JSONDecodeError as e:
            # JSON 파싱 오류 시 기본 응답
            return {
                "action": "ask",
                "message": "죄송합니다. 다시 한 번 말씀해주세요.",
                "slots": {}
            }
        except Exception as e:
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
