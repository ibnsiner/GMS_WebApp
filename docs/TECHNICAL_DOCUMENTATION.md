# GMIS Knowledge Graph - 기술 문서

> **GMIS Knowledge Graph ETL Pipeline v5 상세 기술 문서**

**작성일**: 2024-10-23  
**버전**: v5 Final  
**대상 독자**: 개발자, 데이터 엔지니어, 시스템 관리자

---

## 📑 목차

1. [시스템 개요](#1-시스템-개요)
2. [아키텍처](#2-아키텍처)
3. [데이터 모델](#3-데이터-모델)
4. [ETL 파이프라인 상세](#4-etl-파이프라인-상세)
5. [설정 파일 가이드](#5-설정-파일-가이드)
6. [Cypher 쿼리 패턴](#6-cypher-쿼리-패턴)
7. [개발 히스토리](#7-개발-히스토리)
8. [트러블슈팅](#8-트러블슈팅)
9. [성능 최적화](#9-성능-최적화)
10. [확장 가이드](#10-확장-가이드)

---

## 1. 시스템 개요

### 1.1 목적

GMIS (Group Management Information System) Knowledge Graph는 LS 그룹 계열사들의 재무 데이터를 **의미론적 지식 그래프**로 변환하여, 복잡한 재무 분석과 자연어 질의응답을 가능하게 하는 시스템입니다.

### 1.2 핵심 가치 제안

#### 기존 시스템 (관계형 DB)
```sql
SELECT revenue FROM financial_data 
WHERE company = 'ELECTRIC' AND year = 2024;
```
- ❌ 관계 추론 불가
- ❌ 계층 구조 표현 어려움
- ❌ 자연어 질의 불가

#### Knowledge Graph
```cypher
MATCH (c:Company {id: 'ELECTRIC'})-[:HAS_STATEMENT]->(fs)
  -[:FOR_PERIOD]->(p:Period {year: 2024})
MATCH (p)-[:PRIOR_YEAR_EQUIV]->(prior:Period)
MATCH (fs_prior)-[:FOR_PERIOD]->(prior)
...
```
- ✅ 전년 동기 자동 연결
- ✅ 계층 구조 자연스럽게 표현
- ✅ 관계 기반 추론 가능

### 1.3 버전별 진화

| 버전 | 기능 | 주요 개선 |
|------|------|----------|
| **v1** | 기본 ETL | CSV → Graph 변환 |
| **v2** | Cypher 최적화 | MATCH/MERGE 순서, 관계 방향 |
| **v3** | 안정화 | Python 예약어 수정, comment 처리 |
| **v4** | 사업별 추가 (초안) | BusinessSegment 도입 |
| **v5** | 완성 | APOC 제거, 누계 처리, CIC 분류, HAS_ALL_SEGMENTS |

---

## 2. 아키텍처

### 2.1 전체 시스템 구조

```
┌─────────────────────────────────────────────────────────┐
│                    Data Sources                          │
│  - IS_BS_연결 combined_data.csv                          │
│  - IS_BS_별도 combined_data.csv                          │
│  - 사업별손익_*.csv (6개 파일)                              │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│           ETL Pipeline (gmisknowledgegraphetl_v5)       │
│  1. 데이터베이스 초기화                                     │
│  2. 제약 조건/인덱스 생성                                   │
│  3. 지식 레이어 구축 (메타데이터)                            │
│  4. 메인 데이터 처리 (IS/BS)                               │
│  5. 사업별 손익 처리 ← v5 신규!                            │
│  6. 후처리 관계 구축                                       │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│              Neo4j Knowledge Graph                       │
│  - 105,000+ 노드                                         │
│  - 250,000+ 관계                                         │
│  - 17개 노드 타입                                         │
│  - 16개 관계 타입                                         │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│                 Application Layer                        │
│  - AI Agent (Gemini 1.5 Flash)                          │
│  - Cypher 쿼리 인터페이스                                   │
│  - 데이터 시각화                                           │
└─────────────────────────────────────────────────────────┘
```

### 2.2 기술 스택

| 레이어 | 기술 | 버전 |
|-------|------|------|
| **그래프 DB** | Neo4j Community Edition | 5.20.0 |
| **ETL 언어** | Python | 3.11+ |
| **데이터 처리** | Pandas | 2.2.2 |
| **DB 드라이버** | neo4j-driver | 5.20.0 |
| **AI Model** | Google Gemini 1.5 Flash | - |
| **시각화** | matplotlib | 3.8.4 |

---

## 3. 데이터 모델

### 3.1 노드 타입 (17개)

#### **3.1.1 조직 계층**

```
Company (13개)
  ├─ available_data: ["IS", "BS"]
  ├─ name: "LS ELECTRIC"
  └─ id: "ELECTRIC"

CIC (2개)
  ├─ type: "CIC"
  ├─ parent_company: "ELECTRIC"
  └─ available_data: ["IS"]

CompanyGroup (4개)
  ├─ name: "제조4사"
  └─ id: "manufacturing_4"

BusinessSegment (50+개) ← v5 신규!
  ├─ id: "ELECTRIC_전력기기" (회사별 고유)
  ├─ name: "전력기기"
  └─ company_id: "ELECTRIC"
```

#### **3.1.2 재무 개념**

```
Account (86+개)
  ├─ id: "매출액_합계"
  ├─ name: "매출액 합계"
  ├─ category: "IS" | "BS" | "KPI" | "SEGMENT_IS"
  ├─ aggregation: "SUM" | "LAST" | "AVERAGE"
  └─ description: "..."

FinancialRatio (5개)
  ├─ type: "STORED" | "CALCULATED" | "TIME_COMPARISON"
  ├─ formula_human: "..."
  └─ components: [...]

AnalysisViewpoint (4개)
  ├─ name: "수익성" | "안정성" | "활동성" | "성장성"
  └─ id: "PROFITABILITY" | "STABILITY" | ...
```

#### **3.1.3 재무제표 및 데이터**

```
FinancialStatement (2,000+개)
  └─ id: "{company_id}_{YYYYMM}_{IS|BS}_{CONSOLIDATED|SEPARATE}_{ACTUAL|PLAN}"
     예: "ELECTRIC_202401_IS_SEPARATE_ACTUAL"

Metric (50,000+개)
  └─ id: "{fs_id}_{account_id}"
     또는 "{fs_id}_{segment_name}_{account_name}" (사업별)

ValueObservation (50,000+개)
  ├─ value: 당월 값
  ├─ cumulative_value: 누계 값 ← v5 개선!
  ├─ region: "전체" | "국내" | "해외" ← v5 신규!
  └─ source_file: "..."
```

#### **3.1.4 시간 계층**

```
Year (3+개)
  └─ year: 2024

HalfYear (6+개)
  └─ id: "2024-H1"

Quarter (12+개)
  └─ id: "2024-Q1"

Period (30+개)
  ├─ id: "202401"
  ├─ year: 2024
  └─ month: 1
```

#### **3.1.5 차원 및 기타**

```
StatementType (2개): IS, BS
StatementScope (2개): CONSOLIDATED, SEPARATE
DataClass (2개): ACTUAL, PLAN
Term (250+개): 별칭 저장
```

---

### 3.2 관계 타입 (16개)

#### **3.2.1 조직 관계**

| 관계 | From | To | 설명 |
|------|------|----|----|
| `PART_OF` | CIC | Company | CIC가 본사에 소속 |
| `PART_OF` | BusinessSegment | Company/CIC | 사업 부문 소속 |
| `PART_OF` | Period/Quarter/... | 상위 시간 | 시간 계층 |
| `MEMBER_OF` | Company | CompanyGroup | 그룹 소속 |
| `HAS_ALL_SEGMENTS` | Company | BusinessSegment | **단축 관계** ← v5 신규! |

#### **3.2.2 재무제표 관계**

| 관계 | From | To | 설명 |
|------|------|----|----|
| `HAS_STATEMENT` | Company/CIC | FinancialStatement | 재무제표 보유 |
| `FOR_PERIOD` | FinancialStatement | Period | 기간 지정 |
| `HAS_TYPE` | FinancialStatement | StatementType | IS/BS 구분 |
| `HAS_SCOPE` | FinancialStatement | StatementScope | 연결/별도 |
| `HAS_CLASS` | FinancialStatement | DataClass | 실적/계획 |

#### **3.2.3 데이터 관계**

| 관계 | From | To | 설명 |
|------|------|----|----|
| `CONTAINS` | FinancialStatement | Metric | 지표 포함 |
| `INSTANCE_OF_RULE` | Metric | Account | 계정 인스턴스 |
| `HAS_OBSERVATION` | Metric | ValueObservation | 실제 값 |
| `FOR_SEGMENT` | Metric | BusinessSegment | **사업 부문 지정** ← v5 신규! |

#### **3.2.4 지식 관계**

| 관계 | From | To | 설명 |
|------|------|----|----|
| `ALSO_KNOWN_AS` | Company/Account | Term | 별칭 |
| `SUM_OF` | Account/Metric | Account/Metric | 계산 관계 (ADD/SUBTRACT) |
| `DERIVED_FROM` | Metric(KPI) | Metric | KPI 파생 |
| `PART_OF_VIEWPOINT` | FinancialRatio | AnalysisViewpoint | 분석 관점 |
| `REQUIRES_ACCOUNT` | FinancialRatio | Account | 필요 계정 |

#### **3.2.5 시간 관계**

| 관계 | From | To | 설명 |
|------|------|----|----|
| `PREVIOUS` | Period/Quarter/... | 이전 기간 | 순차 관계 (MoM, QoQ) |
| `PRIOR_YEAR_EQUIV` | Period/Quarter/... | 전년 동기 | YoY 비교 |
| `COMPARISON_FOR` | ACTUAL | PLAN | 계획-실적 비교 |

---

### 3.3 그래프 스키마 다이어그램

```
┌─────────────────┐
│  CompanyGroup   │
└────────┬────────┘
         │ [:MEMBER_OF]
         ▼
┌─────────────────┐        ┌──────────────┐
│     Company     │◄─────┤│      CIC     │
└────┬────┬───────┘       └──────┬───────┘
     │    │ [:HAS_ALL_SEGMENTS]  │
     │    │                      │ [:PART_OF]
     │    └──────────┬───────────┘
     │               ▼
     │    ┌───────────────────┐
     │    │ BusinessSegment   │ ← v5 신규!
     │    └────────┬──────────┘
     │             │ [:FOR_SEGMENT]
     │             ▼
     │    [:HAS_STATEMENT]
     │             │
     ▼             ▼
┌──────────────────────────┐
│  FinancialStatement      │
│  ├─ [:FOR_PERIOD] ────┐  │
│  ├─ [:HAS_TYPE]       │  │
│  ├─ [:HAS_SCOPE]      │  │
│  └─ [:HAS_CLASS]      │  │
└────────┬───────────────┘  │
         │ [:CONTAINS]      │
         ▼                  ▼
    ┌─────────┐      ┌──────────┐
    │  Metric │      │  Period  │
    └────┬────┘      └────┬─────┘
         │                │ [:PART_OF]
         │ [:INSTANCE_OF_RULE]  ▼
         │           ┌──────────┐
         ▼           │ Quarter  │
    ┌─────────┐     └────┬─────┘
    │ Account │          │ [:PART_OF]
    └─────────┘          ▼
         │          ┌──────────┐
         │ [:SUM_OF]│ HalfYear │
         │          └────┬─────┘
         ▼               │ [:PART_OF]
    ┌─────────┐          ▼
    │ Account │     ┌──────────┐
    └─────────┘     │   Year   │
                    └──────────┘
```

---

## 4. ETL 파이프라인 상세

### 4.1 전체 흐름

```python
run_etl_pipeline(clear_db=True):
    1. _clear_database()              # DB 초기화
    2. _create_constraints_and_indexes()  # 제약 조건
    3. _load_knowledge_layer()        # 메타데이터
    4. _process_main_files()          # IS/BS 데이터
    5. _process_segment_files()       # 사업별 손익 ← v5!
    6. _build_post_relations()        # 시간/비교 관계
       └─ _tx_build_segment_shortcuts()  # HAS_ALL_SEGMENTS ← v5!
```

### 4.2 각 단계 상세 설명

#### **4.2.1 데이터베이스 초기화**

```python
def _clear_database(self):
    self._execute_write(lambda tx: tx.run("MATCH (n) DETACH DELETE n"))
```

**주의**: 모든 노드와 관계를 삭제합니다. 운영 환경에서는 `clear_db=False` 사용 권장.

#### **4.2.2 제약 조건 및 인덱스 생성**

```python
queries = [
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Company) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:BusinessSegment) REQUIRE n.id IS UNIQUE",
    # ... 총 17개
]
```

**목적**:
- 노드 고유성 보장
- 조회 성능 향상 (자동 인덱스 생성)

**v5 추가**:
- `BusinessSegment.id` 고유성 (name이 아님!)

#### **4.2.3 지식 레이어 구축**

```python
def _tx_build_knowledge_layer(self, tx):
    # 1. 차원 노드 (StatementType, StatementScope, DataClass)
    # 2. 회사, CIC (Company, CIC 노드 + Term 별칭)
    # 3. 회사 그룹 (CompanyGroup)
    # 4. 계정 (Account + Term 별칭)
    # 5. 계정 계층 (SUM_OF 관계)
    # 6. 재무비율 (FinancialRatio + 관점)
```

**특징**:
- config.json 기반으로 동적 생성
- 모든 별칭 Term 노드로 관리
- 계정 계층 관계 미리 구축

#### **4.2.4 메인 데이터 처리** (IS/BS)

**입력**: IS_BS_연결/별도 CSV

**처리 흐름**:
```python
1. CSV 로드 (UTF-8-sig)
2. 회사명 → ID 매핑 (별칭 활용)
   "전선(홍치제외)" → "LSCNS_C"
   "전선" → "LSCNS_S"
3. FinancialStatement 생성
   - Period 생성/연결
   - 차원 연결 (Type, Scope, Class)
4. Metric 생성 (일괄 처리)
5. 계산 관계 구축 (SUM_OF, DERIVED_FROM)
```

**핵심 로직**:
```python
company_name_to_id = {
    alias.lower(): canonical_id 
    for canonical_id, data in config['entities']['companies'].items() 
    for alias in [data['official_name']] + data.get('aliases', [])
}
```

**FinancialStatement ID 구조**:
```
{company_id}_{YYYYMM}_{type}_{scope}_{class}
예: ELECTRIC_202401_IS_SEPARATE_ACTUAL
```

#### **4.2.5 사업별 손익 처리** ← **v5 핵심!**

**입력**: 사업별손익_*.csv (6개 파일)

**처리 흐름**:
```python
1. 파일 발견
   ├─ Dynamic Discovery
   │  └─ 템플릿: "사업별손익_{file_name_id}.csv"
   └─ Overrides
      └─ ELECTRIC: CIC 전용 파일 포함

2. Wide → Long 변환
   Wide: | 회사 | year | 전력기기 매출액 | 자동화기기 매출액 |
         | ELECTRIC | 2024 | 100 | 200 |
   
   ↓ melt()
   
   Long: | 회사 | year | raw_metric_name | value |
         | ELECTRIC | 2024 | 전력기기 매출액 | 100 |
         | ELECTRIC | 2024 | 자동화기기 매출액 | 200 |

3. 컬럼명 파싱
   "전력기기 매출액 누계(국내)" 
   → segment: "전력기기"
   → account: "매출액"
   → region: "국내"
   → is_cumulative: True

4. CIC 자동 분류 (ELECTRIC만)
   "전력기기" → 키워드 매칭 → 전력CIC
   "PLC" → 키워드 매칭 → 자동화CIC
   "기타" → 매칭 실패 → ELECTRIC 본사

5. BusinessSegment, Metric, ValueObservation 생성
```

**CIC 전용 파일 처리**:
```python
format_type = "CIC_DIRECT"
target_company_override = "전력CIC"

# 모든 사업 부문을 해당 CIC에 직접 연결
# 키워드 추론 건너뜀
```

**ValueObservation 구조** (v5 개선):
```cypher
// 하나의 노드에 당월 + 누계 저장
ValueObservation {
  id: "{metric_id}_{region}",
  region: "전체",
  value: 100,              // 당월
  cumulative_value: 500    // 누계
}
```

#### **4.2.6 후처리 관계 구축**

1. **시간 계층 생성**: Period → Quarter → HalfYear → Year
2. **순차 관계**: PREVIOUS (MoM, QoQ, ...)
3. **전년 동기**: PRIOR_YEAR_EQUIV (YoY)
4. **계획-실적**: COMPARISON_FOR (ACTUAL → PLAN)
5. **사업 부문 단축**: HAS_ALL_SEGMENTS ← v5 신규!

```cypher
// HAS_ALL_SEGMENTS 생성 로직
MATCH (company:Company)
OPTIONAL MATCH (company)<-[:PART_OF]-(bs_direct:BusinessSegment)
WHERE NOT (bs_direct)<-[:PART_OF]-(:CIC)
OPTIONAL MATCH (company)<-[:PART_OF]-(cic:CIC)<-[:PART_OF]-(bs_cic:BusinessSegment)
WITH company, collect(DISTINCT bs_direct) + collect(DISTINCT bs_cic) AS all_segments
UNWIND all_segments AS bs
WITH company, bs
WHERE bs IS NOT NULL
MERGE (company)-[:HAS_ALL_SEGMENTS]->(bs)
```

---

### 4.3 주요 알고리즘

#### **4.3.1 Contextual Mapper**

```python
def _build_contextual_mapper(self, context='main_data'):
    mapper = {}
    
    # 기본 매핑
    for company_id, data in config['entities']['companies'].items():
        for alias in [data['official_name']] + data.get('aliases', []):
            mapper[alias.lower()] = company_id
    
    # 사업별 데이터용 특별 처리
    if context == 'segment_data':
        for company_id, data in config['entities']['companies'].items():
            context_id = data.get('contextual_ids', {}).get('segment_data')
            if context_id:
                # LSCNS_C의 별칭들을 LSCNS_S로 재매핑
                for alias in [data['official_name']] + data.get('aliases', []):
                    mapper[alias.lower()] = context_id
    
    return mapper
```

**동작**:
```python
# main_data 컨텍스트:
"전선(홍치제외)" → "LSCNS_C" (연결)
"전선" → "LSCNS_S" (별도)

# segment_data 컨텍스트:
"전선(홍치제외)" → "LSCNS_S" (사업별은 별도 기준!)
"전선" → "LSCNS_S"
```

#### **4.3.2 사업 부문명 파싱**

```python
def _parse_segment_column_header(self, col_name):
    # 예: "전력기기 매출액 누계(국내)"
    
    # 1. 누계 여부
    is_cumulative = '누계' in col_name
    work_str = col_name.replace('누계', '').strip()
    
    # 2. 지역
    region = '전체'
    if work_str.endswith('(국내)'):
        region = '국내'
        work_str = work_str[:-4].strip()
    elif work_str.endswith('(해외)'):
        region = '해외'
        work_str = work_str[:-4].strip()
    
    # 3. 공백 정규화
    work_str = re.sub(r'\s+', ' ', work_str).strip()
    
    # 4. 분리
    parts = work_str.split(' ')
    account_name = parts[-1]        # "매출액"
    segment_name = ' '.join(parts[:-1])  # "전력기기"
    
    return segment_name, account_name, region, is_cumulative
```

#### **4.3.3 CIC 자동 분류**

```python
def _infer_cic_for_segment(self, company_id, segment_name):
    segment_keywords = {
        "전력CIC": ["전력기기", "배전기기", "저압기기", ...],
        "자동화CIC": ["PLC", "Inverter", "SERVO", ...]
    }
    
    for cic_id, keywords in segment_keywords.items():
        if any(keyword in segment_name for keyword in keywords):
            return cic_id
    
    return None  # 본사 귀속
```

**예시**:
- "저압기기 매출액" → "저압기기" 포함 → 전력CIC ✅
- "PLC 영업이익" → "PLC" 포함 → 자동화CIC ✅
- "기타 매출액" → 매칭 실패 → ELECTRIC 본사 ✅

---

## 5. 설정 파일 가이드

### 5.1 config_v11.json 구조

```json
{
  "data_sources": {
    "main_files": [...],
    "segment_files": {
      "dynamic_discovery": {
        "enabled": true,
        "file_name_template": "사업별손익_{file_name_id}.csv",
        "exclude_companies": [...]
      },
      "overrides": {
        "ELECTRIC": {
          "file": "사업별손익_LS일렉트릭.csv",
          "format": "ELECTRIC_CIC",
          "cic_mapping_files": {...}
        }
      }
    }
  },
  "entities": {
    "companies": {...},
    "accounts": {...}
  },
  "dimensions": {...},
  "context_classifiers": {...},
  "relationships": {...},
  "financial_ratios": {...},
  "segment_to_main_account_mapping": {...},  // ← v5 신규!
  "business_rules": {
    "company_groups": {...},
    "special_handling": {...},
    "cic_mapping_rules": {...}  // ← v5 신규!
  }
}
```

### 5.2 주요 설정 항목 설명

#### **5.2.1 data_sources.segment_files**

```json
"segment_files": {
  "dynamic_discovery": {
    "enabled": true,
    "file_name_template": "사업별손익_{file_name_id}.csv",
    "exclude_companies": ["글로벌"]
  },
  "overrides": {
    "ELECTRIC": {
      "file": "사업별손익_LS일렉트릭.csv",
      "format": "ELECTRIC_CIC",
      "cic_mapping_files": {
        "전력CIC": "사업별손익_LS일렉트릭_전력CIC.csv",
        "자동화CIC": "사업별손익_LS일렉트릭_자동화CIC.csv"
      }
    }
  }
}
```

**동작**:
1. `enabled: true` → 자동 파일 발견 활성화
2. 템플릿으로 파일명 생성
3. `exclude_companies`에 있으면 건너뜀
4. `overrides`에 있으면 특별 처리

#### **5.2.2 companies.contextual_ids**

```json
"LSCNS_C": {
  "official_name": "LS전선(연결)",
  "file_name_id": "LS전선",
  "contextual_ids": {"segment_data": "LSCNS_S"},  // ← 중요!
  "aliases": ["전선(홍치제외)", ...]
}
```

**의미**:
- 연결 재무제표는 LSCNS_C
- 사업별 데이터는 LSCNS_S (별도 기준)

#### **5.2.3 segment_to_main_account_mapping**

```json
"segment_to_main_account_mapping": {
  "매출액": "매출액_합계",
  "영업이익": "영업이익",
  "영업이익률": "영업이익률"
}
```

**목적**: 사업별 손익의 계정명을 기존 Account ID로 매핑

**효과**:
- 기존 Account 재사용 → 일관성 유지
- 계정 계층 관계 자동 활용
- 쿼리 단순화

#### **5.2.4 cic_mapping_rules**

```json
"cic_mapping_rules": {
  "ELECTRIC": {
    "method": "DATA_BASED_INFERENCE",
    "inference_columns": ["매출액(국내)", "매출액(해외)"],
    "target_cics": ["전력CIC", "자동화CIC"]
  }
}
```

**활용**: `_infer_cic_for_segment()` 함수에서 참조

---

## 6. Cypher 쿼리 패턴

### 6.1 기본 패턴

#### **전사 레벨 조회**
```cypher
MATCH (c:Company {id: 'ELECTRIC'})-[:HAS_STATEMENT]->(fs:FinancialStatement)
WHERE fs.id CONTAINS '202401_IS_SEPARATE_ACTUAL'
MATCH (fs)-[:CONTAINS]->(m:Metric)-[:INSTANCE_OF_RULE]->(a:Account {id: '매출액_합계'})
MATCH (m)-[:HAS_OBSERVATION]->(v:ValueObservation)
RETURN v.value
```

#### **사업별 상세 조회** ← v5!
```cypher
MATCH (c:Company {id: 'ELECTRIC'})-[:HAS_ALL_SEGMENTS]->(bs:BusinessSegment)
MATCH (m:Metric)-[:FOR_SEGMENT]->(bs)
MATCH (m)-[:INSTANCE_OF_RULE]->(a:Account {id: '매출액_합계'})
MATCH (m)-[:HAS_OBSERVATION]->(v:ValueObservation)
WHERE v.region = '전체' AND v.value IS NOT NULL
RETURN bs.name, v.value, v.cumulative_value
```

### 6.2 고급 패턴

#### **계층 탐색**
```cypher
// ELECTRIC → 전력CIC → 배전반
MATCH path = (c:Company {id: 'ELECTRIC'})
  <-[:PART_OF]-(cic:CIC {id: '전력CIC'})
  <-[:PART_OF]-(bs:BusinessSegment {name: '배전반'})
RETURN path
```

#### **시계열 비교**
```cypher
// 전년 동월 비교
MATCH (p1:Period {year: 2024, month: 1})-[:PRIOR_YEAR_EQUIV]->(p2:Period)
MATCH (fs1:FinancialStatement)-[:FOR_PERIOD]->(p1)
MATCH (fs2:FinancialStatement)-[:FOR_PERIOD]->(p2)
WHERE fs1.id CONTAINS 'ELECTRIC' AND fs2.id CONTAINS 'ELECTRIC'
...
```

---

## 7. 개발 히스토리

### 7.1 주요 버전별 변경사항

#### **v3 → v4**
- ✅ BusinessSegment 노드 도입
- ✅ Wide → Long 변환
- ✅ 동적 파일 발견
- ⚠️ APOC 의존성 (문제)

#### **v4 → v5**
- ✅ APOC 의존성 제거
- ✅ BusinessSegment ID 고유성 (name → id)
- ✅ ValueObservation 누계/당월 통합
- ✅ CIC 전용 파일 처리
- ✅ "합계" 필터링
- ✅ HAS_ALL_SEGMENTS 관계
- ✅ Account 매핑 테이블
- ✅ 자동 인코딩 감지
- ✅ 이모지 제거 (UnicodeError 방지)

### 7.2 해결된 주요 이슈

| 이슈 | v4 | v5 |
|------|----|----|
| APOC 필수 | ❌ | ✅ 제거 |
| BusinessSegment 충돌 | ❌ | ✅ ID로 해결 |
| 누계 값 손실 | ❌ | ✅ CASE 구문 |
| CIC "기타" 누락 | ❌ | ✅ 전용 파일 |
| "합계" 중복 | ❌ | ✅ 필터링 |
| 쿼리 복잡도 | 🟡 | ✅ 단축 관계 |

---

## 8. 트러블슈팅

### 8.1 일반적인 문제

#### **문제: UnicodeEncodeError (이모지)**
```
UnicodeEncodeError: 'cp949' codec can't encode character '\u2705'
```

**해결**: v5에서 모든 이모지를 텍스트로 변경
```python
# ✅ → [OK]
# ❌ → [ERROR]
```

#### **문제: UnicodeDecodeError (CSV)**
```
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xb1
```

**해결**: 자동 인코딩 감지
```python
for encoding in ['utf-8-sig', 'cp949', 'euc-kr', 'utf-8']:
    try:
        df = pd.read_csv(file_path, encoding=encoding)
        break
    except UnicodeDecodeError:
        continue
```

#### **문제: KeyError: 'file'**
```
KeyError: 'file'
```

**원인**: config의 override에 `file` 키 누락

**해결**: config_v11.json 수정
```json
"ELECTRIC": {
  "file": "사업별손익_LS일렉트릭.csv",  // ← 추가!
  ...
}
```

---

## 9. 성능 최적화

### 9.1 실행 시간

| 단계 | 처리량 | 소요 시간 (예상) |
|------|--------|---------------|
| 지식 레이어 | 86 accounts + 15 companies | ~2초 |
| IS/BS 연결 | ~576 rows | ~45초 |
| IS/BS 별도 | ~1,238 rows | ~1분 38초 |
| 사업별손익 (합계) | ~30,000 metrics | ~5-8분 |
| 후처리 | 시간/비교 관계 | ~5초 |
| **전체** | - | **~8-10분** |

### 9.2 최적화 팁

1. **배치 처리**: 한 행씩 transaction → 배치 처리
   ```python
   # 현재: 1 row = 1 transaction
   # 개선: 100 rows = 1 transaction
   ```

2. **인덱스 활용**: Constraint가 자동 인덱스 생성

3. **UNWIND 사용**: 벌크 삽입
   ```cypher
   UNWIND $metrics AS m_data
   MERGE (m:Metric {id: ...})
   ```

---

## 10. 확장 가이드

### 10.1 새로운 회사 추가

```json
// config_v11.json
"companies": {
  "신규회사": {
    "official_name": "LS 신규",
    "file_name_id": "LS신규",
    "aliases": ["신규", "new"],
    "groups": ["ls_affiliates"],
    "available_data": ["IS", "BS"]
  }
}
```

데이터 파일:
- `IS_BS_연결/별도.csv`에 추가
- `사업별손익_LS신규.csv` 생성 (선택)

### 10.2 새로운 계정 추가

```json
// config_v11.json
"accounts": {
  "신규계정": {
    "official_name": "신규 계정",
    "aliases": ["new account"],
    "category": "IS",
    "aggregation": "SUM",
    "description": "..."
  }
}
```

CSV에 컬럼 추가:
- `IS_BS_*.csv`에 "신규계정" 컬럼 추가

### 10.3 새로운 사업 부문 추가

CSV에만 추가하면 자동 처리:
```csv
..., 신규사업 매출액, 신규사업 매출액(국내), ...
```

CIC 분류가 필요하면:
```python
# gmisknowledgegraphetl_v5_final.py
segment_keywords = {
    "전력CIC": [..., "신규사업"],  # 추가
    ...
}
```

---

## 부록 A. 파일 목록

### ETL 관련
- `gmisknowledgegraphetl_v5_final.py` - 최신 ETL 파이프라인
- `gmisknowledgegraphetl_v3_final.py` - 이전 버전 (참고용)
- `config_v11.json` - 설정 파일
- `config.json` - 이전 설정 (참고용)

### 데이터 파일
- `data/IS_BS_연결 combined_data_수정.csv`
- `data/IS_BS_별도 combined_data_수정.csv`
- `data/사업별손익_LS전선.csv`
- `data/사업별손익_LS일렉트릭.csv`
- `data/사업별손익_LS일렉트릭_전력CIC.csv`
- `data/사업별손익_LS일렉트릭_자동화CIC.csv`
- `data/사업별손익_LS메탈.csv`
- `data/사업별손익_가온전선.csv`

### 실행 스크립트
- `run_etl_v5.bat` - v5 실행 배치 파일
- `run_etl.bat` - 기본 실행 파일

### Agent 관련
- `agent_rebuilt.py` - AI Agent
- `tools_rebuilt.py` - Agent 도구
- `run_agent.bat` - Agent 실행

### 문서
- `README.md` - 사용자 가이드
- `TECHNICAL_DOCUMENTATION.md` - 이 문서

---

## 부록 B. 주요 ID 구조

### FinancialStatement ID
```
{company_id}_{YYYYMM}_{type}_{scope}_{class}

예시:
- ELECTRIC_202401_IS_SEPARATE_ACTUAL
- LSCNS_C_202401_IS_CONSOLIDATED_ACTUAL
- 전력CIC_202401_IS_SEPARATE_PLAN
```

### Metric ID

**메인 데이터**:
```
{fs_id}_{account_id}

예: ELECTRIC_202401_IS_SEPARATE_ACTUAL_매출액_합계
```

**사업별 데이터**:
```
{fs_id}_{segment_name}_{account_name}

예: 전력CIC_202401_IS_SEPARATE_ACTUAL_배전반_매출액
```

### BusinessSegment ID
```
{company_id}_{segment_name}

예시:
- ELECTRIC_기타
- 전력CIC_배전반
- 자동화CIC_PLC
- LSCNS_S_소재
```

### ValueObservation ID
```
{metric_id}_{region}

예: ...배전반_매출액_국내
```

---

## 부록 C. CSV 데이터 형식

### C.1 메인 재무제표 (IS_BS)

```csv
그룹,4개사,11개사,CIC,회사,year,month,반기,분기,계정,항목,매출액_합계,국내_매출액,...
Y,Y,Y,N,ELECTRIC,2024,1,상반기,1분기,IS(연결),실적,100000,60000,...
```

**주요 컬럼**:
- `회사`: 회사명 (별칭으로 매핑)
- `계정`: "IS(연결)", "IS(별도)", "BS(연결)", "BS(별도)"
- `항목`: "실적", "계획"
- 이후 컬럼: 86개 계정 값

### C.2 사업별 손익

```csv
그룹,회사,year,month,항목,전력기기 매출액,전력기기 매출액(국내),전력기기 매출액 누계,...
Y,ELECTRIC,2024,1,실적,100,60,500,...
```

**특징**:
- Wide 형식 (사업별로 컬럼 분리)
- 누계 컬럼 별도 존재
- 국내/해외 분리

---

## 부록 D. 검증 체크리스트

### 실행 전
- [ ] Neo4j Desktop 실행 중
- [ ] config_v11.json 존재
- [ ] 모든 CSV 파일 존재
- [ ] Python 가상환경 활성화
- [ ] 패키지 설치 완료

### 실행 후
- [ ] 노드 개수 확인 (105,000+)
- [ ] BusinessSegment 생성 확인
- [ ] HAS_ALL_SEGMENTS 관계 확인
- [ ] CIC 자동 분류 확인
- [ ] 3개 "기타" 구분 확인
- [ ] 누계/당월 값 확인
- [ ] 전사 vs 사업별 합계 일치 확인

---

## 부록 E. 연락처 및 지원

**개발팀**: GMIS Team  
**문의**: [내부 채널]  
**문서 버전**: 1.0 (2024-10-23)

---

**마지막 업데이트**: 2024-10-23  
**다음 업데이트 예정**: Agent v2 통합 후

