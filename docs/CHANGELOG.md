# GMIS Knowledge Graph - 변경 이력

## v5.0 Final (2024-10-23) 🎉

### 🆕 새로운 기능
- **사업별 손익 데이터 통합**
  - BusinessSegment 노드 추가 (50+ 사업 부문)
  - Wide → Long 변환으로 동적 처리
  - 누계/당월 값 자동 분리
  - 국내/해외/전체 지역 구분

- **CIC 자동 분류**
  - 키워드 기반 사업 부문 분류
  - ELECTRIC → 전력CIC/자동화CIC 자동 매핑
  - CIC 전용 파일 별도 처리

- **HAS_ALL_SEGMENTS 관계**
  - Company에서 모든 하위 사업 부문에 직접 접근
  - 쿼리 복잡도 대폭 감소

### 🔧 주요 개선
- APOC 플러그인 의존성 완전 제거
- BusinessSegment ID 고유성 확보 (name → id)
- ValueObservation 구조 개선 (하나의 노드에 value + cumulative_value)
- Account 매핑 테이블 (segment_to_main_account_mapping)
- 파싱 로직 견고성 강화
- 자동 인코딩 감지 (UTF-8, CP949, EUC-KR)
- "합계" 사업 부문 필터링
- 이모지 제거 (UnicodeError 방지)

### 📁 새로운 파일
- `gmisknowledgegraphetl_v5_final.py` - v5 ETL 파이프라인
- `config_v11.json` - v5용 설정 파일
- `run_etl_v5.bat` - v5 실행 스크립트
- `TECHNICAL_DOCUMENTATION.md` - 상세 기술 문서
- `CHANGELOG.md` - 이 파일

### 🗂️ 데이터 파일 추가
- `사업별손익_LS전선.csv`
- `사업별손익_LS일렉트릭.csv`
- `사업별손익_LS일렉트릭_전력CIC.csv`
- `사업별손익_LS일렉트릭_자동화CIC.csv`
- `사업별손익_LS메탈.csv`
- `사업별손익_가온전선.csv`

### 📊 데이터 규모
- 노드: ~105,000개 (v3: ~50,000개)
- 관계: ~250,000개 (v3: ~120,000개)
- 노드 타입: 17개 (v3: 16개)
- 관계 타입: 16개 (v3: 15개)

---

## v4.0 (2024-10-23)

### 🆕 기능
- BusinessSegment 노드 도입
- 사업별 손익 파일 처리 (초안)
- Dynamic file discovery

### ⚠️ 문제점
- APOC 의존성
- BusinessSegment name 충돌
- ValueObservation 중복 생성
- CIC 전용 파일 미처리

---

## v3.0 Final (2024-10-22)

### 🆕 기능
- Agent Session ID 추가
- PNG/CSV 파일 저장
- NLU 확장 (그룹, 비율, 관점)
- general_knowledge_qa Tool

### 🔧 개선
- Python 예약어 문제 해결 (class, type → stmt_class, stmt_type)
- Cypher MERGE/MATCH 순서 최적화
- OPTIONAL MATCH null 처리
- 시간 관계 방향 명시
- comment 키 처리
- CompanyGroup aliases 매핑

---

## v3.0 (2024-10-22)

### 🆕 기능
- AI Agent 통합 (Gemini 1.5 Flash)
- Function Calling (ReAct 패턴)
- 데이터 시각화
- CSV/JSON 다운로드

---

## v2.0 (2024-10)

### 🔧 개선
- Cypher 쿼리 최적화
- 관계 방향 명시
- 성능 개선

---

## v1.0 (2024-10)

### 🆕 초기 버전
- 기본 ETL 파이프라인
- IS/BS 연결/별도 재무제표 처리
- 13개 회사 + 2개 CIC
- 86개 계정
- 시간 계층 구축

---

**문서 버전**: 1.0  
**마지막 업데이트**: 2024-10-23

