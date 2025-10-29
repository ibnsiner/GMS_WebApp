# GMS WebApp - 경영정보 분석 시스템

GMIS(Group Management Information System) 웹 애플리케이션 모노레포입니다.

## 📁 프로젝트 구조

```
GMS_WebApp/
├── packages/           # 애플리케이션 패키지
│   ├── frontend/      # Next.js 프론트엔드
│   └── backend/       # FastAPI 백엔드
├── scripts/           # 개발 및 운영 스크립트
│   ├── etl.py        # ETL 파이프라인
│   └── test_*.py     # 테스트 스크립트
├── data/              # 데이터 파일
├── docs/              # 문서
│   └── segment_descriptions/  # 사업별 설명
└── .gitignore         # Git 제외 파일 설정
```

## 🚀 시작하기

### ⚡ 빠른 시작 (권장)

**처음 프로젝트를 클론한 경우 또는 완전히 새로 설치:**

```bash
# 1. 저장소 클론
git clone https://github.com/ibnsiner/GMS_WebApp.git
cd GMS_WebApp

# 2. 초기 설정 (최초 1회만, 3-5분 소요)
setup.bat
```

**개발 서버 실행 (매일 사용):**

```bash
# 백엔드 + 프론트엔드 동시 실행 (권장)
run_dev_servers.bat

# 또는 개별 실행
run_backend.bat    # 백엔드만
run_frontend.bat   # 프론트엔드만
```

서버가 시작되면:
- **프론트엔드**: http://localhost:3000
- **백엔드 API**: http://localhost:8000

### 📋 사전 요구사항

- **Python 3.10 이상**
- **Node.js 18 이상**
- **Neo4j Database** (실행 중이어야 함)
- **Git**

### 🛠️ 수동 설정 (선택사항)

#### Backend

```bash
cd packages/backend
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
uvicorn main_api:app --reload
```

#### Frontend

```bash
cd packages/frontend
npm install
npm run dev
```

## 📚 문서

상세 문서는 `docs/` 폴더를 참고하세요.

- [README.md](docs/README.md) - 전체 프로젝트 개요
- [TECHNICAL_DOCUMENTATION.md](docs/TECHNICAL_DOCUMENTATION.md) - 기술 문서
- [CHANGELOG.md](docs/CHANGELOG.md) - 변경 이력

## 🛠️ 주요 기능

- **지식 그래프 기반 재무 분석**: Neo4j 기반 지식 그래프
- **LLM 에이전트**: Google Gemini를 활용한 자연어 쿼리
- **대화형 인터페이스**: Next.js 기반 채팅 UI
- **시각화**: 차트 및 테이블 기반 데이터 시각화
- **재무비율 자동 계산**: ROE, 회전율 등 자동 계산
- **계획-실적 비교**: 목표 달성률 분석
- **YTD/누계 분석**: 연초부터 누적 데이터

---

## 📊 재무 데이터 집계 원리

GMS WebApp Agent는 재무 데이터의 성격에 따라 올바른 집계 방식을 자동으로 적용합니다.

### 집계 방식 (Aggregation Types)

#### **SUM (합계) - 손익계산서 항목**

손익계산서(IS) 항목은 **일정 기간 동안의 성과**를 나타냅니다.

**예시**: 매출액, 영업이익, 당기순이익 등

**집계 방법**: 
- 연간 값 = 1월 + 2월 + ... + 12월 (합산)
- 분기 값 = 해당 분기 3개월 합산

```python
# 예: 2023년 당기순이익
sum(1월 당기순이익 + 2월 당기순이익 + ... + 12월 당기순이익)
```

#### **LAST (기말값) - 재무상태표 항목**

재무상태표(BS) 항목은 **특정 시점의 상태**를 나타냅니다.

**예시**: 자산총계, 부채총계, 자기자본_합계 등

**집계 방법**:
- 연간 값 = 12월 31일 시점 값 (기말값)
- 분기 값 = 해당 분기 마지막 월 값

```python
# 예: 2023년 자기자본_합계
2023년 12월 시점의 자기자본_합계 (합산 ❌)
```

### 재무비율 계산 예시

**ROE (자기자본이익률) 계산**:

```
ROE = (당기순이익 / 자기자본_합계) × 100

구성 요소:
- 당기순이익 (IS, SUM): 2023년 1~12월 합계 = 1,841억원
- 자기자본_합계 (BS, LAST): 2023년 12월 기말값 = 23,077억원

결과: (1,841 / 23,077) × 100 = 7.98%
```

**중요**: "자기자본_**합계**"라는 용어에서 "합계"는 시간상 합계가 아니라, 자본금+이익잉여금 등 **자기자본 구성항목들의 합계**를 의미합니다.

### Config.json의 aggregation 정의

모든 계정의 집계 방식은 `packages/backend/config.json`에 정의되어 있습니다:

```json
{
  "매출액_합계": {"aggregation": "SUM"},
  "당기순이익": {"aggregation": "SUM"},
  "자기자본_합계": {"aggregation": "LAST"},
  "자산_합계": {"aggregation": "LAST"}
}
```

Agent는 이 설정을 자동으로 읽어 올바른 집계 방식을 적용합니다.

