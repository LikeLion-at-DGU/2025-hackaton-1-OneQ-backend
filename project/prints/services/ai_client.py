# prints/services/ai_client.py
import os
import json
from typing import Dict, Optional, List
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

try:
    import openai
except ImportError:
    openai = None

class AIClient:
    """간단한 AI 연결 클라이언트"""
    
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.model = os.getenv('GPT_MODEL', 'gpt-4o-mini')
        self.temperature = float(os.getenv('GPT_TEMPERATURE', '0.7'))
        
        print(f"=== AI 클라이언트 초기화 ===")
        print(f"API 키: {'설정됨' if self.api_key else '설정되지 않음'}")
        print(f"모델: {self.model}")
        print(f"온도: {self.temperature}")
    
    def is_available(self) -> bool:
        """AI 사용 가능 여부 확인"""
        if not openai:
            print("❌ OpenAI 모듈이 설치되지 않음")
            return False
        
        if not self.api_key:
            print("❌ OpenAI API 키가 설정되지 않음")
            return False
        
        print("✅ AI 클라이언트 사용 가능")
        return True
    
    def _get_common_prompt(self) -> str:
        """공통 프롬프트 반환"""
        return """사용자가 질문을 하면 먼저 그 질문에 친근하고 전문적으로 답변해주세요.
답변 후에는 상황에 맞게 자연스럽게 다음 단계로 안내해주세요:
- "도움이 되셨을까요? 궁금한 점이 있으면 더 물어보세요!"
- "이해가 되셨나요? 더 궁금한 점이 있으시면 언제든 말씀해주세요!"
- "혹시 다른 궁금한 점이 있으시면 언제든 물어보세요!"
- "고민해보시고 천천히 선택해보세요!"
- "편하게 고민해보시고 결정해주세요!"
등 상황에 맞는 자연스러운 표현을 사용해주세요.

모든 필요한 정보가 수집되면, 수집된 정보를 정리해서 사용자에게 보여주고 확인받아주세요:
"수집된 정보를 정리해드릴게요:
- [수집된 정보들 나열]
이 정보가 맞는지 확인해주세요! 혹시 수정할 부분이 있으시면 말씀해주세요."

사용자가 정보가 맞다고 확인하면, 최종 견적 생성을 제안해주세요:
"이 정보를 바탕으로 최종 견적을 생성할까요?"

최종 견적을 생성할 때는 다음 형식으로 응답해주세요:
"=== 최종 견적서 ===

📋 요청 정보:
- [사용자가 입력한 모든 정보를 나열]

견적서가 완성되었습니다! 

이제 요청하신 정보에 맞는 인쇄소를 추천해드리겠습니다."

이미 수집된 정보는 다시 묻지 마세요.
지역을 물어볼 때는 "어떤 지역의 인쇄소를 원하는지"를 묻도록 해주세요.
납기일을 물어볼 때는 "며칠 내에 필요하신가요?" 또는 "언제까지 필요하신가요?"와 같이 물어보세요.
예산을 물어볼 때는 "예산은 어느 정도로 생각하고 계신가요?" 또는 "예산 범위를 알려주세요"와 같이 물어보세요.
답변은 순수 텍스트로만 작성하고 마크다운을 사용하지 마세요."""
    
    def _get_category_info(self, category: str) -> str:
        """카테고리별 정보 수집 순서 반환"""
        category_info = {
                         "명함": """명함 제작에 필요한 정보를 다음 순서로 수집해주세요:
1. 용지 종류 (일반지, 고급지, 아트지, 코팅지)
2. 명함 사이즈 (90×54mm, 85×54mm, 90×50mm, 85×50mm 등)
3. 인쇄 방식 (단면 흑백, 단면 컬러, 양면 흑백, 양면 컬러)
4. 후가공 (무광, 유광, 스팟, 엠보싱)
5. 수량 (몇 부)
6. 납기일 (며칠 내에 필요한지)
7. 지역
8. 예산""",
            
                         "배너": """배너 제작에 필요한 정보를 다음 순서로 수집해주세요:
1. 배너 사이즈 (1x3m, 2x4m, 3x6m 등)
2. 배너 거치대 종류 (X자형, A자형, 롤업형)
3. 배너 수량 (몇 개)
4. 납기일 (며칠 내에 필요한지)
5. 지역
6. 예산""",
            
                         "포스터": """포스터 제작에 필요한 정보를 다음 순서로 수집해주세요:
1. 용지 종류 (일반지, 아트지, 코팅지, 합지)
2. 포스터 사이즈 (A4, A3, A2 등)
3. 포스터 코팅 종류 (무광, 유광, 스팟, 없음)
4. 포스터 수량 (몇 부)
5. 납기일 (며칠 내에 필요한지)
6. 지역
7. 예산""",
            
                         "스티커": """스티커 제작에 필요한 정보를 다음 순서로 수집해주세요:
1. 스티커 종류 (일반스티커, 방수스티커, 반사스티커, 전사스티커)
2. 사이즈 (50x50mm, 100x100mm, 200x200mm / 원형은 지름)
3. 수량 (몇 개)
4. 납기일 (며칠 내에 필요한지)
5. 지역
6. 예산""",
            
                         "현수막": """현수막 제작에 필요한 정보를 다음 순서로 수집해주세요:
1. 현수막 사이즈 (1x3m, 2x4m, 3x6m 등)
2. 현수막 추가 가공 (고리, 지퍼, 없음)
3. 현수막 수량 (몇 개)
4. 납기일 (며칠 내에 필요한지)
5. 지역
6. 예산""",
            
                         "브로슈어": """브로슈어 제작에 필요한 정보를 다음 순서로 수집해주세요:
1. 용지 종류 (일반지, 아트지, 코팅지, 합지)
2. 사이즈 종류 (A4, A5, B5, 명함크기)
3. 접지 종류 (2단접지, 3단접지, Z접지, 없음)
4. 수량 (몇 부)
5. 납기일 (며칠 내에 필요한지)
6. 지역
7. 예산"""
        }
        return category_info.get(category, "")
    
    def _get_category_title(self, category: str) -> str:
        """카테고리별 제목 반환"""
        titles = {
            "명함": "명함 제작 전문 챗봇",
            "배너": "배너 제작 전문 챗봇", 
            "포스터": "포스터 제작 전문 챗봇",
            "스티커": "스티커 제작 전문 챗봇",
            "현수막": "현수막 제작 전문 챗봇",
            "브로슈어": "브로슈어 제작 전문 챗봇"
        }
        return titles.get(category, "인쇄 전문 챗봇")
    
    def _build_system_prompt(self, category: str = None) -> str:
        """시스템 프롬프트 구성"""
        if category:
            title = self._get_category_title(category)
            info = self._get_category_info(category)
            common = self._get_common_prompt()
            
            return f"""너는 {title}입니다. 

{info}

{common}"""
        else:
            return f"""너는 인쇄 전문가 챗봇입니다. 
사용자의 질문에 친근하고 정확하게 답변해주세요. 
답변은 순수 텍스트로만 작성하고 마크다운을 사용하지 마세요."""
    
    def chat(self, message: str, system_prompt: str = None, category: str = None) -> Dict:
        """간단한 채팅 요청"""
        if not self.is_available():
            return {
                "error": "AI 서비스를 사용할 수 없습니다.",
                "message": "API 키나 모듈이 설정되지 않았습니다."
            }
        
        try:
            # 시스템 프롬프트 구성
            if not system_prompt:
                system_prompt = self._build_system_prompt(category)
            
            # OpenAI API 호출
            client = openai.OpenAI(api_key=self.api_key)
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                temperature=self.temperature
            )
            
            content = response.choices[0].message.content
            
            return {
                "success": True,
                "message": content,
                "model": self.model
            }
            
        except Exception as e:
            print(f"❌ AI 호출 오류: {e}")
            return {
                "error": str(e),
                "message": "AI 응답 중 오류가 발생했습니다."
            }
    
    def chat_with_history(self, conversation_history: List[Dict], category: str = None) -> Dict:
        """대화 히스토리를 포함한 채팅 요청"""
        if not self.is_available():
            return {
                "error": "AI 서비스를 사용할 수 없습니다.",
                "message": "API 키나 모듈이 설정되지 않았습니다."
            }
        
        try:
            # 시스템 프롬프트 구성
            system_prompt = self._build_system_prompt(category)
            
            # 메시지 구성 (시스템 프롬프트 + 대화 히스토리)
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(conversation_history)
            
            # OpenAI API 호출
            client = openai.OpenAI(api_key=self.api_key)
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature
            )
            
            content = response.choices[0].message.content
            
            return {
                "success": True,
                "message": content,
                "model": self.model
            }
            
        except Exception as e:
            print(f"❌ AI 호출 오류: {e}")
            return {
                "error": str(e),
                "message": "AI 응답 중 오류가 발생했습니다."
            }
    
    def extract_info(self, message: str, category: str) -> Dict:
        """사용자 메시지에서 정보 추출"""
        if not self.is_available():
            return {"error": "AI 서비스를 사용할 수 없습니다."}
        
        try:
            # 카테고리별 프롬프트 (정해진 순서대로)
            category_prompts = {
                                 "스티커": """
스티커 제작 정보를 다음 순서대로 추출해주세요:
1. paper: 스티커 종류 (일반스티커, 방수스티커, 반사스티커, 전사스티커)
2. size: 사이즈 (50x50mm, 100x100mm, 200x200mm / 원형은 지름)
3. quantity: 수량 (숫자만)
4. due_days: 납기일 (며칠 내에 필요한지 숫자만, 예: 3일, 7일, 14일)
5. region: 지역
6. budget: 예산 (숫자만, 원 단위)
""",
                                 "명함": """
명함 제작 정보를 다음 순서대로 추출해주세요:
1. paper: 용지 종류 (일반지, 고급지, 아트지, 코팅지)
2. size: 명함 사이즈 (90×54mm, 85×54mm, 90×50mm, 85×50mm 등)
3. printing: 인쇄 방식 (단면 흑백, 단면 컬러, 양면 흑백, 양면 컬러)
4. finishing: 후가공 (무광, 유광, 스팟, 엠보싱)
5. quantity: 수량 (숫자만)
6. due_days: 납기일 (며칠 내에 필요한지 숫자만, 예: 3일, 7일, 14일)
7. region: 지역
8. budget: 예산 (숫자만, 원 단위)
""",
                                 "포스터": """
포스터 제작 정보를 다음 순서대로 추출해주세요:
1. paper: 용지 종류 (일반지, 아트지, 코팅지, 합지)
2. size: 포스터 사이즈 (A4, A3, A2 등)
3. coating: 포스터 코팅 종류 (무광, 유광, 스팟, 없음)
4. quantity: 포스터 수량 (숫자만)
5. due_days: 납기일 (며칠 내에 필요한지 숫자만, 예: 3일, 7일, 14일)
6. region: 지역
7. budget: 예산 (숫자만, 원 단위)
""",
                                 "브로슈어": """
브로슈어 제작 정보를 다음 순서대로 추출해주세요:
1. paper: 용지 종류 (일반지, 아트지, 코팅지, 합지)
2. size: 사이즈 종류 (A4, A5, B5, 명함크기)
3. folding: 접지 종류 (2단접지, 3단접지, Z접지, 없음)
4. quantity: 수량 (숫자만)
5. due_days: 납기일 (며칠 내에 필요한지 숫자만, 예: 3일, 7일, 14일)
6. region: 지역
7. budget: 예산 (숫자만, 원 단위)
""",
                "배너": """
배너 제작 정보를 다음 순서대로 추출해주세요:
1. size: 배너 사이즈 (1x3m, 2x4m, 3x6m 등)
2. stand: 배너 거치대 종류 (X자형, A자형, 롤업형)
3. quantity: 배너 수량 (숫자만)
4. due_days: 납기일 (며칠 내에 필요한지 숫자만, 예: 3일, 7일, 14일)
5. region: 지역
6. budget: 예산 (숫자만, 원 단위)
""",
                                 "현수막": """
현수막 제작 정보를 다음 순서대로 추출해주세요:
1. size: 현수막 사이즈 (1x3m, 2x4m, 3x6m 등)
2. processing: 현수막 추가 가공 (고리, 지퍼, 없음)
3. quantity: 현수막 수량 (숫자만)
4. due_days: 납기일 (며칠 내에 필요한지 숫자만, 예: 3일, 7일, 14일)
5. region: 지역
6. budget: 예산 (숫자만, 원 단위)
"""
            }
            
            system_prompt = category_prompts.get(category, "정보를 추출해주세요.")
            system_prompt += "\n\n사용자 메시지에서 실제로 명시된 정보만 추출해주세요. 질문이나 추천 요청 등에는 빈 값으로 응답하세요.\n\n예산 추출 시 주의사항:\n- '30만원 근처' → '25~35만원'\n- '20만원 이하' → '20만원 이하'\n- '50만원 이상' → '50만원 이상'\n- '10~20만원' → '10~20만원'\n- '약 15만원' → '13~17만원'\n- '대략 25만원' → '22~28만원'\n\nJSON 형태로 응답해주세요:\n{\"filled_slots\": {\"paper\": \"일반지\", \"size\": \"90x54mm\"}, \"action\": \"ASK\"}"
            
            client = openai.OpenAI(api_key=self.api_key)
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                temperature=0.3  # 정확한 추출을 위해 낮은 온도
            )
            
            content = response.choices[0].message.content
            
            try:
                result = json.loads(content)
                return result
            except json.JSONDecodeError:
                return {
                    "error": "JSON 파싱 실패",
                    "raw_response": content
                }
                
        except Exception as e:
            return {"error": f"정보 추출 오류: {str(e)}"}

# 테스트 함수
def test_ai_connection():
    """AI 연결 테스트"""
    ai = AIClient()
    
    if not ai.is_available():
        print("❌ AI 연결 실패")
        return False
    
    print("✅ AI 연결 성공")
    
    # 간단한 채팅 테스트
    response = ai.chat("안녕하세요! 명함 제작에 대해 궁금한 점이 있어요.")
    print(f"채팅 응답: {response}")
    
    # 정보 추출 테스트
    info = ai.extract_info("명함 100부, 90x54mm, 고급지로 만들어주세요", "명함")
    print(f"정보 추출: {info}")
    
    return True

if __name__ == "__main__":
    test_ai_connection()
