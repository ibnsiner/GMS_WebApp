# GMIS Knowledge Graph 시스템

> **LS 그룹 재무 데이터 기반 지능형 지식 그래프 및 AI Agent 시스템**

![Version](https://img.shields.io/badge/version-5.0_Final-blue)
![Python](https://img.shields.io/badge/python-3.11+-green)
![Neo4j](https://img.shields.io/badge/neo4j-5.20.0-brightgreen)
![License](https://img.shields.io/badge/license-Proprietary-red)

---

## 📋 목차

1. [프로젝트 개요](#-프로젝트-개요)
2. [주요 기능](#-주요-기능)
3. [시스템 아키텍처](#-시스템-아키텍처)
4. [설치 방법](#-설치-방법)
5. [사용 방법](#-사용-방법)
6. [데이터 구조](#-데이터-구조)
7. [예제 쿼리](#-예제-쿼리)
8. [트러블슈팅](#-트러블슈팅)
9. [기여 및 라이선스](#-기여-및-라이선스)

---

## 🎯 프로젝트 개요

**GMIS (Group Management Information System) Knowledge Graph**는 LS 그룹 계열사들의 재무 데이터를 지식 그래프로 구조화하여, 자연어 질의응답과 고급 재무 분석을 가능하게 하는 시스템입니다.

### 핵심 가치

- **📊 데이터의 의미 구조화**: 단순 테이블이 아닌 개념과 관계로 표현
- **🤖 자연어 질의응답**: "ELECTRIC의 전년 대비 매출 증가율은?" 같은 자연어로 질문
- **🔗 자동 관계 추론**: 계획-실적 비교, 전년 동기 비교 등 자동 연결
- **📈 시계열 분석**: Period → Quarter → HalfYear → Year 계층 구조
- **🧮 계산 투명성**: 영업이익 = 매출총이익 - 판매관리비 등 계산 관계 추적
- **🏢 사업별 상세 분석**: 회사 내 사업 부문별 손익 추적 **(v5 신규!)**
- **🎯 CIC 자동 분류**: ELECTRIC의 사업을 전력/자동화CIC로 자동 분류 **(v5 신규!)**

---

## 🌟 주요 기능

### 1. **ETL 파이프라인** (`gmisknowledgegraphetl_v5_final.py`)
- CSV 재무 데이터를 Neo4j 지식 그래프로 자동 변환
- **전사 레벨**: 13개 회사 + 2개 CIC + 86개 계정 + IS/BS 재무제표
- **사업 레벨**: 50+ 사업 부문 + 사업별 손익 데이터 **(v5 신규!)**
- 시간 계층, 계정 계층, 계산 관계 자동 구축
- CIC 자동 분류 (키워드 기반) **(v5 신규!)**
- 누계/당월 값 자동 분리 **(v5 신규!)**

### 2. **AI Agent** (`agent_rebuilt.py`)
- Google Gemini 1.5 Flash 기반 재무 전문가 Agent
- Cypher 쿼리 자동 생성 및 실행
- 자연어 질의응답
- 데이터 시각화 (PNG 차트 자동 생성)
- CSV/JSON 다운로드 기능

### 3. **지식 레이어** (`config.json`)
- 회사/계정/재무비율의 별칭 관리
- 계정 계층 구조 정의
- 비즈니스 규칙 (그룹 정의, 조정영업이익 등)
- 시간 관계 및 분석 유형 정의

---

## 🏗️ 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                        사용자 (User)                          │
└─────────────────────┬───────────────────────────────────────┘
                      │ 자연어 질문
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              AI Agent (agent_rebuilt.py)                     │
│  - Google Gemini 1.5 Flash                                   │
│  - Function Calling (ReAct Pattern)                          │
│  - NLU (별칭 → ID 매핑)                                        │
└─────────────┬───────────────────────┬───────────────────────┘
              │                       │
              ▼                       ▼
    ┌─────────────────┐     ┌──────────────────────┐
    │  Tools Module   │     │  Config.json          │
    │ (tools_rebuilt) │     │  - 회사/계정 별칭       │
    │  - Cypher 실행   │     │  - 계층 구조           │
    │  - 시각화        │     │  - 비즈니스 규칙        │
    │  - 파일 저장     │     └──────────────────────┘
    └────────┬────────┘
             │ Cypher Query
             ▼
    ┌─────────────────────────────────┐
    │   Neo4j Knowledge Graph (GDB)   │
    │  - 13개 회사 + 2개 CIC            │
    │  - 86개 계정                      │
    │  - 수만 개 Metric                 │
    │  - 15+ 관계 타입                  │
    └─────────┬───────────────────────┘
              │ 
              ▼
    ┌─────────────────────────────────┐
    │  ETL Pipeline                    │
    │  (gmisknowledgegraphetl_v3_final)│
    │  - CSV → Graph 변환               │
    │  - 관계 자동 구축                  │
    └─────────────────────────────────┘
              ▲
              │ Raw Data
    ┌─────────────────────────────────┐
    │  CSV Files (data/)               │
    │  - IS_BS_연결 combined_data.csv  │
    │  - IS_BS_별도 combined_data.csv  │
    └─────────────────────────────────┘
```

---

## 💻 설치 방법

### 사전 요구사항

- **Python 3.11+**
- **Neo4j Desktop** 또는 **Neo4j Server 5.x**
- **Windows** (배치 파일 사용 시)

### 1단계: Neo4j 설정

1. Neo4j Desktop 설치: https://neo4j.com/download/
2. 새 데이터베이스 생성
3. 데이터베이스 시작
4. 접속 정보 확인:
   - URI: `bolt://127.0.0.1:7687`
   - User: `neo4j`
   - Password: 설정한 비밀번호

### 2단계: Python 환경 설정

#### Windows (자동 설치)
```batch
# 1. ETL 실행 (자동으로 가상환경 생성 및 패키지 설치)
run_etl.bat
```

#### 수동 설치
```bash
# 1. 가상환경 생성
python -m venv venv

# 2. 가상환경 활성화
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

# 3. 패키지 설치
pip install -r requirements.txt
```

### 3단계: 설정 파일 수정

#### `gmisknowledgegraphetl_v3_final.py` (Line 10-14)
```python
NEO4J_URI = "bolt://127.0.0.1:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "your_password_here"  # ← 수정
```

#### `agent_rebuilt.py` (Line 10, 14)
```python
GOOGLE_AI_API_KEY = "your_gemini_api_key_here"  # ← 수정

def __init__(self, ..., db_pass="your_password_here"):  # ← 수정
```

### 4단계: Gemini API 키 발급

1. https://ai.google.dev/ 접속
2. "Get API Key" 클릭
3. API 키 복사하여 `agent_rebuilt.py`에 붙여넣기

---

## 🚀 사용 방법

### 1. ETL 파이프라인 실행 (최초 1회)

```batch
# Windows
run_etl.bat

# 또는 직접 실행
python gmisknowledgegraphetl_v3_final.py
```

**실행 결과**:
```
--- ETL 파이프라인 시작 ---
--- 1. 데이터베이스 초기화 ---
   - 완료: 모든 노드와 관계가 삭제되었습니다.
--- 2. 제약 조건 및 인덱스 생성 ---
   - 완료: 모든 핵심 노드에 고유성 제약 조건이 생성되었습니다.
--- 3. 지식 레이어 (메타데이터) 구축 ---
   - 완료: Company, Account, Dimensions 등 개념 노드 및 관계가 생성되었습니다.
--- 4. 메인 데이터 (IS/BS) 처리 ---
   - 파일 처리 중: IS_BS_연결 combined_data_수정.csv
     IS_BS_연결 combined_data_수정.csv: 100%|███████| 576/576 [00:45<00:00, 12.7 rows/s]
   - 파일 처리 중: IS_BS_별도 combined_data_수정.csv
     IS_BS_별도 combined_data_수정.csv: 100%|███████| 1238/1238 [01:38<00:00, 12.6 rows/s]
--- 5. 후처리 관계 (시간, 계획-실적) 구축 ---
   - 완료: 시간 계층 및 기간 비교 관계가 생성되었습니다.
   - 완료: 계획-실적 비교 관계가 생성되었습니다.

✅ 모든 ETL 파이프라인 작업이 성공적으로 완료되었습니다.
```

### 2. AI Agent 실행

```batch
# Windows
run_agent.bat

# 또는 직접 실행
python agent_rebuilt.py
```

**대화 예시**:
```
🤖 GMIS Agent Rebuilt가 시작되었습니다. (종료: 'exit')
🔑 Session ID: abc123-def456-ghi789

[USER]: ELECTRIC의 2023년 영업이익률은?

[🔧 Tool Call]: run_cypher_query
[📝 Args]: {
  "query": "MATCH (c:Company {id: 'ELECTRIC'})-[:HAS_STATEMENT]->(fs:FinancialStatement)..."
}
[✅ Result]: [{'avg_opm': 8.5}]...

[GMIS Agent]:
LS ELECTRIC의 2023년 평균 영업이익률은 8.5%입니다.

[USER]: 제조4사의 부채비율을 비교해줘

[🔧 Tool Call]: run_cypher_query
...
```

---

## 📚 데이터 구조

### 노드 타입 (16개)

| 노드 레이블 | 설명 | 개수 | 주요 속성 |
|-----------|------|------|----------|
| `Company` | 일반 회사 | 13개 | id, name, available_data |
| `CIC` | 사업부문 (전력/자동화) | 2개 | id, name, parent_company |
| `CompanyGroup` | 회사 그룹 | 4개 | id, name |
| `BusinessSegment` | **사업 부문** | **50+개** | **id, name, company_id** ← **v5 신규!** |
| `Account` | 계정 과목 | 100+개 | id, name, category, aggregation |
| `Term` | 별칭 용어 | 300+ | value |
| `FinancialStatement` | 재무제표 | 2,000+ | id (회사_기간_유형_범위_데이터구분) |
| `Metric` | 개별 재무 지표 | 50,000+ | id (재무제표_계정[_사업부문]) |
| `ValueObservation` | 실제 값 | 50,000+ | **value, cumulative_value, region** ← **v5 개선!** |
| `Period` | 월 | 수십 개 | id, year, month |
| `Quarter` | 분기 | 수십 개 | id (YYYY-Q#) |
| `HalfYear` | 반기 | 수십 개 | id (YYYY-H#) |
| `Year` | 년 | 수개 | year |
| `StatementType` | 재무제표 유형 | 2개 | id (IS/BS) |
| `StatementScope` | 연결 범위 | 2개 | id (CONSOLIDATED/SEPARATE) |
| `DataClass` | 데이터 구분 | 2개 | id (ACTUAL/PLAN) |
| `FinancialRatio` | 재무비율 정의 | 5개 | id, name, type, formula |
| `AnalysisViewpoint` | 분석 관점 | 4개 | id, name |

### 관계 타입 (15개)

| 관계 타입 | 방향 | 설명 |
|----------|------|------|
| `ALSO_KNOWN_AS` | Company/Account → Term | 별칭 매핑 |
| `PART_OF` | CIC → Company, **BusinessSegment → Company/CIC**, 시간 계층 | 소속 관계 |
| `HAS_ALL_SEGMENTS` | **Company → BusinessSegment** | **단축 관계** ← **v5 신규!** |
| `FOR_SEGMENT` | **Metric → BusinessSegment** | **사업 부문 지정** ← **v5 신규!** |
| `MEMBER_OF` | Company → CompanyGroup | 그룹 소속 |
| `HAS_STATEMENT` | Company/CIC → FinancialStatement | 재무제표 보유 |
| `FOR_PERIOD` | FinancialStatement → Period | 기간 지정 |
| `HAS_TYPE` | FinancialStatement → StatementType | IS/BS 구분 |
| `HAS_SCOPE` | FinancialStatement → StatementScope | 연결/별도 구분 |
| `HAS_CLASS` | FinancialStatement → DataClass | 실적/계획 구분 |
| `CONTAINS` | FinancialStatement → Metric | 지표 포함 |
| `INSTANCE_OF_RULE` | Metric → Account | 계정 인스턴스 |
| `HAS_OBSERVATION` | Metric → ValueObservation | 실제 값 |
| `SUM_OF` | Account/Metric → Account/Metric | 계산 관계 (ADD/SUBTRACT) |
| `DERIVED_FROM` | Metric → Metric | KPI 파생 관계 |
| `PREVIOUS` | Period/Quarter/... → 이전 | 순차 관계 |
| `PRIOR_YEAR_EQUIV` | Period/Quarter/... → 전년 동기 | YoY 비교 |
| `COMPARISON_FOR` | ACTUAL → PLAN | 계획-실적 비교 |
| `PART_OF_VIEWPOINT` | FinancialRatio → AnalysisViewpoint | 분석 관점 분류 |
| `REQUIRES_ACCOUNT` | FinancialRatio → Account | 필요 계정 |

---

## 📦 설치 방법

### 자동 설치 (Windows)

```batch
# 1. ETL 실행 (가상환경 자동 생성)
run_etl.bat

# 2. Agent 실행
run_agent.bat
```

### 수동 설치

```bash
# 1. 저장소 클론
git clone [repository_url]
cd GMS_GDB

# 2. 가상환경 생성
python -m venv venv

# 3. 가상환경 활성화
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

# 4. 패키지 설치
pip install -r requirements.txt

# 5. Neo4j 데이터베이스 연결 정보 설정
# gmisknowledgegraphetl_v3_final.py 파일 수정

# 6. Gemini API 키 설정
# agent_rebuilt.py 파일 수정

# 7. ETL 실행
python gmisknowledgegraphetl_v3_final.py

# 8. Agent 실행
python agent_rebuilt.py
```

---

## 🎮 사용 방법

### ETL 파이프라인

```python
# gmisknowledgegraphetl_v3_final.py
from gmisknowledgegraphetl_v3_final import GMISKnowledgeGraphETL

# 초기화
etl = GMISKnowledgeGraphETL(
    uri="bolt://127.0.0.1:7687",
    user="neo4j",
    password="your_password",
    config=config_data
)

# 전체 파이프라인 실행 (DB 초기화 포함)
etl.run_etl_pipeline(clear_db=True)

# 또는 단계별 실행
etl._create_constraints_and_indexes()
etl._load_knowledge_layer()
etl._process_main_files()
etl._build_post_relations()

etl.close()
```

### AI Agent

```python
# agent_rebuilt.py
from agent_rebuilt import GmisAgentRebuilt

# Agent 초기화
agent = GmisAgentRebuilt(
    config_path='config.json',
    db_uri="bolt://127.0.0.1:7687",
    db_user="neo4j",
    db_pass="your_password",
    session_id="user_session_123"  # 선택사항
)

# 대화형 실행
agent.run("ELECTRIC의 2023년 매출액은?")

# 종료
agent.close()
```

### Tools 직접 사용

```python
from tools_rebuilt import GmisToolsRebuilt

tools = GmisToolsRebuilt(
    uri="bolt://127.0.0.1:7687",
    user="neo4j",
    password="your_password",
    session_id="my_session"
)

# Cypher 쿼리 실행
result = tools.run_cypher_query("MATCH (c:Company) RETURN c.name LIMIT 5")

# 데이터 시각화
tools.data_visualization(
    data=result,
    chart_type='bar',
    title='회사별 매출액',
    x_col='company',
    y_cols=['revenue']
)
# → outputs/my_session/chart_20240122_153045.png

# CSV 생성
tools.generate_downloadable_link(
    data=result,
    file_name='companies',
    file_type='csv'
)
# → outputs/my_session/companies_20240122_153050.csv

tools.close()
```

---

## 📊 데이터 구조

### 대상 회사 (13개 + 2개 CIC)

#### 제조 4사
- LS전선
- LS ELECTRIC
- LS MnM
- LS엠트론

#### 기타 계열사
- E1
- 가온전선
- LS아이앤디
- LS 인베니
- LS 글로벌
- LS 네트웍스
- LS 메탈

#### CIC (사업부문)
- 전력CIC (LS ELECTRIC 소속)
- 자동화CIC (LS ELECTRIC 소속)

### 재무 데이터 범위

- **기간**: 2022년 1월 ~ 최신 (월별)
- **재무제표**: 손익계산서(IS), 재무상태표(BS)
- **범위**: 연결, 별도
- **구분**: 실적, 계획
- **계정**: 86개 (매출, 비용, 자산, 부채, 자본 등)
- **KPI**: 11개 (영업이익률, 부채비율, 회전일 등)

---

## 🔍 예제 쿼리

### 1. 기본 조회

#### Neo4j Browser (Cypher)
```cypher
// ELECTRIC의 2023년 1월 매출액
MATCH (c:Company {id: 'ELECTRIC'})-[:HAS_STATEMENT]->(fs:FinancialStatement)
WHERE fs.id CONTAINS '202301_IS_CONSOLIDATED_ACTUAL'
MATCH (fs)-[:CONTAINS]->(m:Metric)-[:INSTANCE_OF_RULE]->(:Account {id: '매출액_합계'})
MATCH (m)-[:HAS_OBSERVATION]->(v:ValueObservation)
RETURN v.value AS revenue
```

#### AI Agent (자연어)
```
ELECTRIC의 2023년 1월 매출액은?
```

### 2. 시계열 비교

#### Neo4j Browser
```cypher
// ELECTRIC의 YoY 매출 성장률
MATCH (c:Company {id: 'ELECTRIC'})-[:HAS_STATEMENT]->(fs_current)
MATCH (fs_current)-[:FOR_PERIOD]->(p_current:Period {year: 2023, month: 1})
MATCH (p_current)-[:PRIOR_YEAR_EQUIV]->(p_prior:Period)
MATCH (c)-[:HAS_STATEMENT]->(fs_prior)-[:FOR_PERIOD]->(p_prior)
WHERE fs_current.id CONTAINS 'IS_CONSOLIDATED_ACTUAL'
  AND fs_prior.id CONTAINS 'IS_CONSOLIDATED_ACTUAL'
MATCH (fs_current)-[:CONTAINS]->(m_curr)-[:INSTANCE_OF_RULE]->(:Account {id: '매출액_합계'})
MATCH (fs_prior)-[:CONTAINS]->(m_prior)-[:INSTANCE_OF_RULE]->(:Account {id: '매출액_합계'})
MATCH (m_curr)-[:HAS_OBSERVATION]->(v_curr)
MATCH (m_prior)-[:HAS_OBSERVATION]->(v_prior)
RETURN 
    v_curr.value AS current_revenue,
    v_prior.value AS prior_year_revenue,
    ((v_curr.value - v_prior.value) / v_prior.value * 100) AS yoy_growth_rate
```

#### AI Agent
```
ELECTRIC의 2023년 1월 매출액을 전년 동월과 비교해줘
```

### 3. 그룹 집계

#### Neo4j Browser
```cypher
// 제조4사 전체 매출 합계
MATCH (cg:CompanyGroup {name: '제조4사'})<-[:MEMBER_OF]-(c:Company)
MATCH (c)-[:HAS_STATEMENT]->(fs:FinancialStatement)
WHERE fs.id CONTAINS '202301_IS_CONSOLIDATED_ACTUAL'
MATCH (fs)-[:CONTAINS]->(m:Metric)-[:INSTANCE_OF_RULE]->(:Account {id: '매출액_합계'})
MATCH (m)-[:HAS_OBSERVATION]->(v:ValueObservation)
RETURN 
    c.name AS company,
    v.value AS revenue,
    sum(v.value) OVER () AS total_revenue
ORDER BY v.value DESC
```

#### AI Agent
```
제조4사의 2023년 1월 매출액을 비교해줘
```

### 4. 계산 관계 추적

#### Neo4j Browser
```cypher
// 영업이익 구성 요소 확인
MATCH (fs:FinancialStatement {id: 'ELECTRIC_202301_IS_CONSOLIDATED_ACTUAL'})
MATCH (fs)-[:CONTAINS]->(parent:Metric)-[:INSTANCE_OF_RULE]->(:Account {id: '영업이익'})
MATCH (parent)-[r:SUM_OF]->(child:Metric)
MATCH (child)-[:INSTANCE_OF_RULE]->(child_account:Account)
MATCH (child)-[:HAS_OBSERVATION]->(v)
RETURN 
    parent.id,
    r.operation,
    child_account.name,
    v.value
```

#### AI Agent
```
ELECTRIC의 영업이익은 어떻게 계산되는지 보여줘
```

### 5. 계획-실적 비교

#### Neo4j Browser
```cypher
// 계획 대비 실적 달성률
MATCH (actual:FinancialStatement)-[:COMPARISON_FOR]->(plan:FinancialStatement)
WHERE actual.id = 'ELECTRIC_202301_IS_CONSOLIDATED_ACTUAL'
MATCH (actual)-[:CONTAINS]->(m_actual:Metric)-[:INSTANCE_OF_RULE]->(a:Account {id: '영업이익'})
MATCH (plan)-[:CONTAINS]->(m_plan:Metric)-[:INSTANCE_OF_RULE]->(a)
MATCH (m_actual)-[:HAS_OBSERVATION]->(v_actual)
MATCH (m_plan)-[:HAS_OBSERVATION]->(v_plan)
RETURN 
    v_plan.value AS plan_value,
    v_actual.value AS actual_value,
    (v_actual.value / v_plan.value * 100) AS achievement_rate
```

#### AI Agent
```
ELECTRIC의 2023년 1월 영업이익 계획 대비 실적은?
```

---

## 🛠️ 트러블슈팅

### 문제 1: "Neo4j 연결 실패"
```
❌ 데이터베이스 연결 실패: Failed to establish connection
```

**해결 방법**:
1. Neo4j Desktop에서 데이터베이스가 시작되었는지 확인
2. URI가 올바른지 확인 (`bolt://127.0.0.1:7687`)
3. 사용자명/비밀번호 확인
4. 방화벽 확인

### 문제 2: "파이썬 패키지 설치 오류"
```
ERROR: Could not find a version that satisfies the requirement neo4j==5.20.0
```

**해결 방법**:
```bash
# pip 업그레이드
python -m pip install --upgrade pip

# 패키지 재설치
pip install -r requirements.txt
```

### 문제 3: "CSV 파일을 찾을 수 없음"
```
- 경고: 'IS_BS_연결 combined_data_수정.csv' 파일을 찾을 수 없어 건너뜁니다.
```

**해결 방법**:
1. `data/` 폴더 존재 확인
2. CSV 파일명 정확히 확인
3. 파일 인코딩 확인 (UTF-8-sig)

### 문제 4: "Gemini API 키 오류"
```
ValueError: GOOGLE_AI_API_KEY가 코드에 설정되지 않았습니다.
```

**해결 방법**:
1. https://ai.google.dev/ 에서 API 키 발급
2. `agent_rebuilt.py` Line 10에 API 키 입력
3. 따옴표 안에 정확히 입력

### 문제 5: "한글 폰트 깨짐 (차트)"
```
차트에 한글이 □□□ 로 표시됨
```

**해결 방법**:
- Windows: 'Malgun Gothic' 자동 사용
- macOS: 'AppleGothic' 자동 사용
- Linux: `sudo apt-get install fonts-nanum` 후 시스템 재부팅

### 문제 6: "구문 오류 (SyntaxError)"
```
SyntaxError: invalid syntax (line 192)
```

**이미 수정됨**: Python 예약어 (`class`, `type`) 문제는 모두 해결되었습니다.

---

## 📂 프로젝트 구조

```
GMS_GDB/
│
├── 📄 README.md                              # 이 파일
├── 📄 TECHNICAL_DOCUMENTATION.md             # 상세 기술 문서
├── 📄 requirements.txt                       # Python 패키지 의존성
├── 📄 config.json                            # 지식 레이어 설정
├── 📄 .gitignore                             # Git 제외 파일
│
├── 🐍 gmisknowledgegraphetl_v3_final.py      # ETL 파이프라인
├── 🤖 agent_rebuilt.py                       # AI Agent 메인
├── 🛠️ tools_rebuilt.py                       # Agent 도구 모듈
│
├── 🚀 run_etl.bat                            # ETL 실행 스크립트 (Windows)
├── 🚀 run_agent.bat                          # Agent 실행 스크립트 (Windows)
│
├── 📁 data/                                  # 원본 CSV 데이터
│   ├── IS_BS_연결 combined_data_수정.csv
│   └── IS_BS_별도 combined_data_수정.csv
│
├── 📁 outputs/                               # 생성된 파일 (자동 생성)
│   ├── [session_id]/
│   │   ├── chart_*.png
│   │   └── *.csv
│   └── ...
│
└── 📁 venv/                                  # Python 가상환경 (자동 생성)
```

---

## 🎓 학습 리소스

### Cypher 쿼리 학습
- [Neo4j Cypher 공식 문서](https://neo4j.com/docs/cypher-manual/current/)
- [Graph Academy](https://graphacademy.neo4j.com/)

### Neo4j 브라우저 접속
```
http://localhost:7474/browser/
```

### 유용한 검증 쿼리
```cypher
// 1. 전체 노드 개수
MATCH (n)
RETURN labels(n)[0] AS node_type, count(n) AS count
ORDER BY count DESC

// 2. 전체 관계 개수
MATCH ()-[r]->()
RETURN type(r) AS relationship_type, count(r) AS count
ORDER BY count DESC

// 3. 특정 회사의 재무제표 개수
MATCH (c:Company {id: 'ELECTRIC'})-[:HAS_STATEMENT]->(fs)
RETURN count(fs) AS statement_count

// 4. 데이터 기간 범위
MATCH (p:Period)
RETURN min(p.year) AS start_year, max(p.year) AS end_year,
       min(p.month) AS start_month, max(p.month) AS end_month
```

---

## 📈 성능

- **ETL 처리 속도**: ~2,000 행 → 약 2-3분
- **Neo4j 쿼리 응답**: 평균 < 100ms
- **Agent 응답**: 평균 3-10초 (Gemini API 호출 포함)

---

## 🔐 보안 주의사항

⚠️ **민감 정보**:
- `gmisknowledgegraphetl_v3_final.py`: Neo4j 비밀번호
- `agent_rebuilt.py`: Neo4j 비밀번호, Gemini API 키

**권장 사항**:
1. 실제 운영 환경에서는 환경 변수 사용
   ```python
   import os
   NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
   GOOGLE_AI_API_KEY = os.getenv("GOOGLE_AI_API_KEY")
   ```
2. `.env` 파일 사용 (python-dotenv)
3. Git에 커밋하지 않기 (.gitignore에 추가됨)

---

## 🤝 기여 및 라이선스

### 버전 히스토리
- **v5.0 Final** (2024-10-23): 사업별 손익 데이터 통합, CIC 자동 분류, HAS_ALL_SEGMENTS
- **v4.0** (2024-10-23): BusinessSegment 도입 (초안)
- **v3.0 Final** (2024-10-22): Session ID, 파일 저장, NLU 확장
- **v3.0** (2024-10-22): Agent 통합, Function Calling
- **v2.0** (2024-10): Cypher 쿼리 최적화
- **v1.0** (2024-10): 초기 ETL 파이프라인

### 개발팀
- ETL Pipeline: GMIS Team
- AI Agent: GMIS Team
- Knowledge Graph Design: GMIS Team

### 라이선스
Proprietary - LS 그룹 내부 사용 전용

---

## 📞 지원

문제가 발생하거나 질문이 있으시면:
1. Neo4j 브라우저에서 데이터 확인
2. `outputs/` 폴더의 로그 파일 확인
3. 팀에 문의

---

## 🎯 로드맵

### 완료됨 ✅
- [x] **v5.0**: 사업별 손익 데이터 통합
- [x] **v5.0**: CIC 자동 분류 시스템
- [x] **v5.0**: 누계/당월 값 분리
- [x] **v5.0**: HAS_ALL_SEGMENTS 단축 관계

### 진행 중 🚧
- [ ] Agent v2 업그레이드 (사업별 데이터 인식)
- [ ] 웹 UI 통합 (Streamlit/Gradio)

### 단기 (1개월)
- [ ] 실시간 데이터 업데이트 파이프라인
- [ ] 추가 재무비율 계산 (ROA, ROIC 등)
- [ ] 사업별 BS (재무상태표) 데이터 추가

### 중기 (3개월)
- [ ] 외부 데이터 통합 (금리, 환율, 산업 벤치마크)
- [ ] 고급 분석 기능 (듀폰분석, EVA 등)
- [ ] 사업 포트폴리오 최적화 분석

### 장기 (6개월)
- [ ] 예측 모델 통합 (사업별 매출 예측)
- [ ] 이상 탐지 (Anomaly Detection)
- [ ] 자동 인사이트 생성

---

**마지막 업데이트**: 2024-10-23  
**문서 버전**: 2.0 (v5.0 반영)


