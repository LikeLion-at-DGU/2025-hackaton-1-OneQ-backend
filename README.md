# 2025-hackaton-1-OneQ-backend


# 🖨️ OneQ (원큐) - AI 기반 인쇄소 추천 서비스

<div align="center">

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![Django](https://img.shields.io/badge/Django-5.2.5-green.svg)
![DRF](https://img.shields.io/badge/Django%20REST%20Framework-3.16.0-red.svg)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4-orange.svg)

**AI가 추천하는 최적의 인쇄소를 찾아드립니다** 🎯

[![OneQ Demo](https://img.shields.io/badge/🚀-Live%20Demo-brightgreen?style=for-the-badge)](https://your-demo-link.com)

</div>

---

## 📋 목차

- [✨ 서비스 소개](#-서비스-소개)
- [🚀 주요 기능](#-주요-기능)
- [🛠️ 기술 스택](#️-기술-스택)
- [📁 프로젝트 구조](#-프로젝트-구조)
- [⚡ 빠른 시작](#-빠른-시작)
- [🔧 설치 및 설정](#-설치-및-설정)
- [📊 OneQ Score 시스템](#-oneq-score-시스템)
- [🤖 AI 기능](#-ai-기능)
- [📱 API 문서](#-api-문서)
- [👥 기여하기](#-기여하기)

---

## ✨ 서비스 소개

**OneQ**는 사용자의 인쇄 요구사항을 AI가 분석하여 최적의 인쇄소를 추천해주는 스마트한 서비스입니다.

### 🎯 핵심 가치

- **정확한 추천**: OneQ Score 알고리즘으로 최적의 인쇄소 매칭
- **AI 기반 상담**: GPT-4를 활용한 지능형 견적 상담
- **다양한 인쇄물 지원**: 명함, 포스터, 배너, 현수막, 브로슈어, 스티커
- **실시간 견적**: 즉시 생성되는 상세한 견적서

---

## 🚀 주요 기능

### 🤖 AI 상담 시스템

- **자연어 대화**: 사용자 요구사항을 자연스럽게 파악
- **스마트 견적 생성**: AI가 자동으로 상세한 견적서 작성
- **맞춤형 추천**: 사용자 상황에 최적화된 인쇄소 추천

### 📊 OneQ Score 시스템

```
OneQ Score = 0.40 × 가격점수 + 0.30 × 납기점수 + 0.30 × 작업적합도점수
```

- **가격 점수 (40%)**: 예산 대비 최적 가격
- **납기 점수 (30%)**: 요청 납기일 충족도
- **작업 적합도 점수 (30%)**: 인쇄소의 작업 능력과 경험

### 🖨️ 지원 인쇄물 종류

| 카테고리     | 주요 옵션                  | 특화 기능                   |
| ------------ | -------------------------- | --------------------------- |
| **명함**     | 용지종류, 인쇄방식, 후가공 | 비즈니스 카드 사이즈 최적화 |
| **포스터**   | 용지종류, 코팅, 사이즈     | 고품질 인쇄 옵션            |
| **배너**     | 사이즈, 거치대, 수량       | 실외용 내구성 고려          |
| **현수막**   | 사이즈, 추가가공, 수량     | 대형 인쇄 전문              |
| **브로슈어** | 용지종류, 사이즈, 접지     | 다단 접지 옵션              |
| **스티커**   | 종류, 사이즈, 수량         | 다양한 접착 옵션            |

---

## 🛠️ 기술 스택

### Backend

- **Django 5.2.5** - 웹 프레임워크
- **Django REST Framework 3.16.0** - API 개발
- **SQLite** - 데이터베이스
- **OpenAI GPT-4** - AI 상담 및 견적 생성

### Frontend (예정)

- **React.js** - 사용자 인터페이스
- **TypeScript** - 타입 안정성
- **Tailwind CSS** - 스타일링

### DevOps

- **Python 3.8+** - 런타임 환경
- **Docker** - 컨테이너화 (예정)
- **Git** - 버전 관리

---

## 📁 프로젝트 구조

```
oneqq/
├── project/                 # Django 프로젝트 루트
│   ├── prints/             # 메인 앱
│   │   ├── models.py       # 데이터 모델
│   │   ├── views.py        # API 뷰
│   │   ├── serializers.py  # DRF 시리얼라이저
│   │   ├── services/       # 비즈니스 로직
│   │   │   ├── ai_client.py    # OpenAI 클라이언트
│   │   │   └── oneq_score.py   # OneQ Score 계산
│   │   └── migrations/     # 데이터베이스 마이그레이션
│   ├── project/            # Django 설정
│   │   ├── settings.py     # 프로젝트 설정
│   │   └── urls.py         # URL 라우팅
│   ├── requirements.txt    # Python 의존성
│   └── manage.py          # Django 관리 명령어
└── README.md              # 프로젝트 문서
```

---

## ⚡ 빠른 시작

### 1. 저장소 클론

```bash
git clone https://github.com/your-username/oneqq.git
cd oneqq/project
```

### 2. 가상환경 생성 및 활성화

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### 3. 의존성 설치

```bash
pip install -r requirements.txt
```

### 4. 환경 변수 설정

```bash
cp .env.example .env
# .env 파일에 OpenAI API 키 등 설정
```

### 5. 데이터베이스 마이그레이션

```bash
python manage.py migrate
```

### 6. 개발 서버 실행

```bash
python manage.py runserver
```

---

## 🔧 설치 및 설정

### 필수 요구사항

- Python 3.8 이상
- OpenAI API 키
- Git

### 환경 변수 설정

`.env` 파일을 생성하고 다음 변수들을 설정하세요:

```env
SECRET_KEY=your-django-secret-key
DEBUG=True
OPENAI_API_KEY=your-openai-api-key
```

### 데이터베이스 설정

기본적으로 SQLite를 사용합니다. PostgreSQL 등으로 변경하려면 `settings.py`를 수정하세요.

---

## 📊 OneQ Score 시스템

### 점수 계산 방식

OneQ Score는 다음 공식으로 계산됩니다:

```
OneQ Score = 0.40 × Price_i + 0.30 × Deadline_i + 0.30 × WorkFit_i
```

### 세부 점수 항목

#### 1. 가격 점수 (Price_i, 40%)

- **최저가 비율 (50%)**: 시장 최저가 대비 가격
- **예산 적합도 (25%)**: 사용자 예산 범위 내 여부
- **수량 할인 (25%)**: 대량 주문 할인 혜택

#### 2. 납기 점수 (Deadline_i, 30%)

- **납기일 충족도 (60%)**: 요청 납기일 준수 가능성
- **생산 능력 (40%)**: 인쇄소의 생산 용량

#### 3. 작업 적합도 점수 (WorkFit_i, 30%)

- **카테고리 전문성 (40%)**: 해당 인쇄물 전문성
- **품질 보증 (30%)**: 품질 관리 시스템
- **고객 만족도 (30%)**: 이전 고객 리뷰

---

## 🤖 AI 기능

### GPT-4 기반 상담 시스템

- **자연어 이해**: 사용자의 요구사항을 정확히 파악
- **맥락 인식**: 대화 흐름을 고려한 응답
- **견적서 자동 생성**: 구조화된 견적서 생성

### AI 응답 예시

```
사용자: "명함 100장 만들어야 하는데, 고급스럽게 하고 싶어요"

AI: "고급스러운 명함 제작을 도와드리겠습니다!
다음 정보를 알려주시면 최적의 견적을 제공해드릴게요:

1. 예산 범위는 어느 정도인가요?
2. 언제까지 필요하신가요?
3. 특별히 원하시는 용지나 후가공이 있나요?

현재 100장 기준으로 고급 용지 + 특수 후가공 옵션을 추천드립니다."
```

---

## 📱 API 문서

### 주요 엔드포인트

#### 채팅 세션 관리

- `POST /api/chat/session/` - 새 채팅 세션 생성
- `POST /api/chat/message/` - 메시지 전송
- `GET /api/chat/session/{session_id}/` - 세션 정보 조회

#### 인쇄소 관리

- `GET /api/printshops/` - 인쇄소 목록 조회
- `POST /api/printshops/` - 인쇄소 등록
- `GET /api/printshops/{id}/` - 인쇄소 상세 정보
- `PUT /api/printshops/{id}/` - 인쇄소 정보 수정

#### OneQ Score

- `POST /api/oneq-score/calculate/` - OneQ Score 계산
- `GET /api/oneq-score/recommendations/` - 추천 인쇄소 목록

### API 응답 예시

```json
{
  "oneq_score": 85,
  "price_score": 90,
  "deadline_score": 80,
  "workfit_score": 85,
  "recommendation_reason": "가격이 합리적이고 납기일을 충분히 맞출 수 있는 인쇄소입니다.",
  "printshop": {
    "id": 1,
    "name": "프리미엄 인쇄소",
    "phone": "02-1234-5678",
    "address": "서울시 강남구..."
  }
}
```

---

## 👥 기여하기

프로젝트에 기여하고 싶으시다면 다음 단계를 따라주세요:

### 1. Fork & Clone

```bash
git clone https://github.com/your-username/oneqq.git
cd oneqq
```

### 2. 브랜치 생성

```bash
git checkout -b feature/your-feature-name
```

### 3. 변경사항 커밋

```bash
git add .
git commit -m "Add: 새로운 기능 추가"
```

### 4. Pull Request 생성

GitHub에서 Pull Request를 생성해주세요.

### 기여 가이드라인

- 코드 스타일을 일관성 있게 유지해주세요
- 새로운 기능은 테스트 코드와 함께 작성해주세요
- 문서화를 잊지 마세요

---


<div align="center">

**OneQ와 함께 최적의 인쇄소를 찾아보세요! 🎨**

[![GitHub stars](https://img.shields.io/github/stars/your-username/oneqq?style=social)](https://github.com/your-username/oneqq)
[![GitHub forks](https://img.shields.io/github/forks/your-username/oneqq?style=social)](https://github.com/your-username/oneqq)

</div>


