# Config.json 완전 활용 개선 로드맵

> **작성일**: 2025-10-29  
> **목적**: GMS_WebApp Agent가 config.json의 모든 정의를 완전히 활용하도록 개선  
> **현재 상태**: 부분 활용 중 (~60% 활용도)

---

## 📊 현황 분석

### ✅ 현재 잘 활용되는 항목

| 항목 | 위치 | 활용 방식 |
|------|------|-----------|
| **Companies** | `entities.companies` | NLU 사전, 별칭 매핑, 그룹 인식 |
| **Accounts** | `entities.accounts` | NLU 사전, 집계 규칙(SUM/LAST) |
| **Company Groups** | `business_rules.company_groups` | 제조4사 등 그룹 쿼리 |
| **Special Handling** | `business_rules.special_handling` | 조정영업이익 규칙 |
| **Segment Mapping** | `segment_to_main_account_mapping` | 사업별 계정 매핑 |
| **Dimensions** | `dimensions` | StatementType, Scope, DataClass |

### ⚠️ 부분 활용 또는 미활용 항목

| 항목 | 위치 | 현재 상태 | 잠재력 |
|------|------|-----------|--------|
| **Financial Ratios** | `financial_ratios.ratios` | NLU만 | 자동 계산, 설명 제공 |
| **Viewpoints** | `financial_ratios.viewpoints` | NLU만 | 관점별 지표 조회 |
| **PLAN_VS_ACTUAL** | `contextual_relationships` | **미사용** | 계획 대비 실적 분석 |
| **YTD/RECENT** | `temporal_classifiers.analysis_type` | NLU만 | 누계, 최근 N개월 |
| **Quarter/HalfYear** | `temporal_classifiers.unit_aliases` | 방금 추가 | 분기/반기 집계 |
| **Relationship Aliases** | `temporal_classifiers.relationship_aliases` | 일부 | 전년 대비, 전월 대비 |
| **Available Data** | `entities.companies[].available_data` | **미사용** | 데이터 존재 여부 체크 |
| **Contextual IDs** | `entities.companies[].contextual_ids` | ETL만 | Agent 미활용 |

---

## 🎯 개선 계획

### Phase 1: 계획-실적 비교 (High Priority)

**목표**: "계획 대비", "목표 달성률", "예산 대비" 질문 지원

#### 구현 단계

**1.1 System Prompt 추가**
```markdown
위치: _create_system_prompt() 메서드, Query Pattern Templates 섹션

추가 내용:
**계획-실적 비교 패턴 (PLAN vs ACTUAL):**

When user asks "계획 대비", "실적 대비", "목표 달성률", "예산 대비":

```cypher
MATCH (c:Company {id: 'ELECTRIC'})-[:HAS_STATEMENT]->(fs_actual:FinancialStatement)
WHERE fs_actual.id CONTAINS '2023' AND fs_actual.id CONTAINS 'ACTUAL'
MATCH (fs_actual)-[:COMPARISON_FOR]->(fs_plan:FinancialStatement)
MATCH (fs_actual)-[:FOR_PERIOD]->(p:Period)
MATCH (fs_actual)-[:CONTAINS]->(m_actual:Metric)-[:INSTANCE_OF_RULE]->(a:Account)
WHERE a.id = '매출액_합계'
MATCH (fs_plan)-[:CONTAINS]->(m_plan:Metric)-[:INSTANCE_OF_RULE]->(a)
MATCH (m_actual)-[:HAS_OBSERVATION]->(v_actual:ValueObservation)
MATCH (m_plan)-[:HAS_OBSERVATION]->(v_plan:ValueObservation)
RETURN 
  c.name, 
  p.month, 
  a.name,
  v_plan.value as planned,
  v_actual.value as actual,
  ((v_actual.value - v_plan.value) / v_plan.value * 100) as variance_pct
ORDER BY p.month
```

Keywords: ["계획 대비", "실적 대비", "목표 달성률", "달성률", "예산 대비", "계획비"]
```

**1.2 NLU 추가**
```python
# _build_nlu() 메서드에 추가
nlu["comparison_type"] = {}
for comp_type, aliases in self.config.get('contextual_relationships', {}).get('PLAN_VS_ACTUAL', {}).get('aliases', []):
    for alias in aliases:
        nlu["comparison_type"][alias.lower()] = "PLAN_VS_ACTUAL"
```

**1.3 Python 후처리**
```python
# run() 메서드의 데이터 처리 부분
if 'planned' in df.columns and 'actual' in df.columns:
    df['achievement_rate'] = (df['actual'] / df['planned'] * 100).round(1)
    df['variance'] = df['actual'] - df['planned']
```

#### 테스트 케이스
```
- "2023년 매출액 계획 대비 실적을 알려줘"
- "1분기 목표 달성률은?"
- "예산 대비 실제 영업이익 차이는?"
```

---

### Phase 2: YTD/누계 지원 (High Priority)

**목표**: "연초부터", "누계", "YTD" 질문 지원

#### 구현 단계

**2.1 System Prompt 추가 (최적화된 단일 쿼리 방식)**
```markdown
**YTD (Year-to-Date) 패턴:**

When user asks "누계", "연초부터", "YTD", "~월까지":

Use a single optimized Cypher query that automatically finds latest month:

```cypher
// 사용자가 월 지정 안 한 경우: 자동으로 최신 월까지 누계
MATCH (c:Company {id: 'MnM'})-[:HAS_STATEMENT]->(fs:FinancialStatement)
WHERE fs.id CONTAINS '2023' AND fs.id CONTAINS 'ACTUAL'
MATCH (fs)-[:FOR_PERIOD]->(p:Period)
MATCH (fs)-[:CONTAINS]->(m:Metric)-[:INSTANCE_OF_RULE]->(a:Account)
WHERE a.id = '매출액_합계'
MATCH (m)-[:HAS_OBSERVATION]->(v:ValueObservation)
WITH c, a, max(p.month) as latest_month, collect({month: p.month, value: v.value}) as monthly_data
UNWIND monthly_data as md
RETURN c.name, a.name, sum(md.value) as ytd_total, latest_month
```

// 사용자가 월 지정한 경우: "9월까지"
```cypher
WHERE p.month <= 9  // 명시적 필터
```

**Performance benefit**: Single query, no extra round-trips to DB

Keywords: ["누계", "누적", "연초부터", "YTD", "~까지"]
```

**2.2 최신 월 자동 감지**
```python
# run() 메서드에 추가
if "누계" in user_query or "YTD" in user_query.upper():
    # 데이터의 최신 월 찾기
    latest_month_query = """
    MATCH (p:Period) 
    WHERE p.year = 2024
    RETURN max(p.month) as latest_month
    """
    latest = self.run_cypher_query(latest_month_query)
    # LLM에게 전달
```

#### 테스트 케이스
```
- "2023년 9월까지 누계 매출액"
- "올해 연초부터 영업이익 누계"
- "YTD 당기순이익은?"
```

---

### Phase 3: 재무비율 자동 계산 (Medium Priority)

**목표**: ROE, 회전율 등 CALCULATED 타입 비율 자동 계산

#### 구현 단계

**3.1 새로운 Tool 추가**
```python
def calculate_financial_ratio(self, ratio_id: str, company_id: str, period: str) -> dict:
    """
    config.json의 formula를 읽고 재무비율 자동 계산
    
    Args:
        ratio_id: 'ROE', '매출채권회전율' 등
        company_id: 'ELECTRIC', 'MnM' 등
        period: '2023', '2023-Q4' 등
    
    Returns:
        {"ratio_name": "ROE", "value": 15.2, "unit": "%", "components": {...}}
    """
    ratio_config = self.config['financial_ratios']['ratios'].get(ratio_id)
    
    if not ratio_config or ratio_config['type'] != 'CALCULATED':
        return {"error": "계산 가능한 비율이 아닙니다"}
    
    # 1. 구성 요소 조회 (최적화: 한 번에 모두 조회)
    components = ratio_config['components']
    component_values = {}
    
    # 여러 번의 쿼리 대신 하나의 쿼리로 모든 구성요소 조회
    query = f"""
    MATCH (c:Company {{id: '{company_id}'}})-[:HAS_STATEMENT]->(fs)
    WHERE fs.id CONTAINS '{period}'
    MATCH (fs)-[:CONTAINS]->(m)-[:INSTANCE_OF_RULE]->(a:Account)
    WHERE a.id IN {components}
    MATCH (m)-[:HAS_OBSERVATION]->(v)
    RETURN a.id as account_id, v.value as value
    """
    result = self.run_cypher_query(query)
    
    if result['status'] == 'success':
        for row in result['data']:
            component_values[row['account_id']] = row['value']
    
    # 2. 공식 파싱 및 계산
    formula = ratio_config['formula_human']
    # 간단한 공식 파서 (예: "(당기순이익 / 자기자본_합계) * 100")
    # 실제 값으로 치환하여 계산
    
    # 3. 결과 반환
    return {
        "ratio_name": ratio_config['official_name'],
        "value": calculated_value,
        "unit": ratio_config.get('unit', ''),
        "components": component_values,
        "formula": formula
    }
```

**3.2 System Prompt 추가**
```markdown
**CALCULATED Financial Ratios:**

For ratios marked as "CALCULATED" in config.json:
- ROE, 매출채권회전율 등은 직접 저장되지 않음
- Use calculate_financial_ratio() tool
- Tool will automatically fetch components and calculate

Example:
```python
calculate_financial_ratio(
    ratio_id='ROE',
    company_id='ELECTRIC',
    period='2023'
)
```
```

**3.3 Tools 리스트에 추가**
```python
def run(self, user_query: str):
    tools = [
        self.run_cypher_query,
        self.data_visualization,
        self.generate_downloadable_link,
        self.general_knowledge_qa,
        self.calculate_financial_ratio  # 추가
    ]
```

#### 테스트 케이스
```
- "MnM의 2023년 ROE를 계산해줘"
- "전선의 매출채권회전율은?"
- "일렉트릭의 자기자본수익률 추이"
```

---

### Phase 4: 계정/비율 설명 도구 (Medium Priority)

**목표**: config.json의 정확한 정의 제공

#### 구현 단계

**4.1 새로운 Tool 추가**
```python
def get_definition(self, term: str) -> dict:
    """
    재무 용어의 정의를 config.json에서 조회
    
    Args:
        term: "영업이익", "ROE", "부채비율" 등
    
    Returns:
        {
            "term": "영업이익",
            "official_name": "영업이익",
            "category": "IS",
            "description": "매출총이익에서 판매관리비를 차감한...",
            "aggregation": "SUM",
            "formula": null or "..."
        }
    """
    term_lower = term.lower()
    
    # 1. Accounts 검색
    for aid, adata in self.config['entities']['accounts'].items():
        all_names = [adata['official_name']] + adata.get('aliases', [])
        if any(term_lower == name.lower() for name in all_names):
            return {
                "found": True,
                "type": "account",
                "term": term,
                "official_name": adata['official_name'],
                "category": adata['category'],
                "description": adata.get('description', '설명 없음'),
                "aggregation": adata.get('aggregation'),
                "id": aid
            }
    
    # 2. Financial Ratios 검색
    for rid, rdata in self.config['financial_ratios']['ratios'].items():
        all_names = [rdata['official_name']] + rdata.get('aliases', [])
        if any(term_lower == name.lower() for name in all_names):
            return {
                "found": True,
                "type": "ratio",
                "term": term,
                "official_name": rdata['official_name'],
                "viewpoint": rdata['viewpoint'],
                "description": rdata.get('description', '설명 없음'),
                "ratio_type": rdata['type'],
                "formula": rdata.get('formula_human'),
                "unit": rdata.get('unit'),
                "id": rid
            }
    
    # 3. 못 찾음
    return {
        "found": False,
        "message": f"'{term}'에 대한 정의를 config.json에서 찾을 수 없습니다."
    }
```

**4.2 System Prompt 수정**
```markdown
**Definition Questions:**

When user asks "XXX이 뭐야?", "XXX 의미는?", "XXX 정의":

1. **First, try get_definition(term=XXX)**
   - If found in config.json: Use that definition (more accurate!)
   - Example: get_definition(term="영업이익")

2. **If not found, use general_knowledge_qa()**
   - For general financial concepts not in our config
```

**4.3 Tools 리스트에 추가**
```python
tools = [
    self.run_cypher_query,
    self.data_visualization,
    self.generate_downloadable_link,
    self.general_knowledge_qa,
    self.calculate_financial_ratio,
    self.get_definition  # 추가
]
```

**4.4 우선순위 변경**
```python
# 현재: general_knowledge_qa가 모든 정의 질문 처리
# 개선 후: get_definition → general_knowledge_qa (fallback)
```

#### 테스트 케이스
```
- "영업이익이 뭐야?" → config.json 정의 반환
- "ROE 의미는?" → config.json 정의 + 계산 공식
- "EBITDA란?" → config.json 정의
```

---

### Phase 5: Viewpoints 활용 (Medium Priority)

**목표**: "수익성 지표 전체", "안정성 분석" 같은 상위 레벨 질문 지원

#### 구현 단계

**5.1 새로운 Tool 추가**
```python
def get_ratios_by_viewpoint(self, viewpoint_name: str) -> dict:
    """
    특정 분석 관점의 모든 재무비율 반환
    
    Args:
        viewpoint_name: "수익성", "안정성", "활동성", "성장성"
    
    Returns:
        {
            "viewpoint": "수익성",
            "ratios": [
                {"id": "영업이익률", "name": "영업이익률", "type": "STORED"},
                {"id": "ROE", "name": "자기자본이익률", "type": "CALCULATED"},
                ...
            ]
        }
    """
    viewpoint_name_lower = viewpoint_name.lower()
    
    # 1. Viewpoint ID 찾기
    viewpoint_id = None
    for vid, vdata in self.config['financial_ratios']['viewpoints'].items():
        all_names = [vdata['name']] + vdata.get('aliases', [])
        if any(viewpoint_name_lower == name.lower() for name in all_names):
            viewpoint_id = vid
            break
    
    if not viewpoint_id:
        return {"found": False, "message": f"'{viewpoint_name}' 관점을 찾을 수 없습니다."}
    
    # 2. 해당 viewpoint의 모든 ratios 수집
    ratios = []
    for rid, rdata in self.config['financial_ratios']['ratios'].items():
        if rdata.get('viewpoint') == viewpoint_id:
            ratios.append({
                "id": rid,
                "name": rdata['official_name'],
                "type": rdata['type'],
                "description": rdata.get('description')
            })
    
    return {
        "found": True,
        "viewpoint": viewpoint_name,
        "viewpoint_id": viewpoint_id,
        "ratios": ratios,
        "count": len(ratios)
    }
```

**5.2 System Prompt 추가**
```markdown
**Viewpoint-based Analysis:**

When user asks for metrics by analytical viewpoint:
- "수익성 지표", "안정성 지표", "성장성 지표"

Use get_ratios_by_viewpoint() to get complete list, then:
1. Present the list to user
2. Ask which specific ratio they want to analyze
3. Or query all if user wants comprehensive analysis

Viewpoints:
- PROFITABILITY (수익성): 영업이익률, ROE 등
- STABILITY (안정성): 부채비율 등
- ACTIVITY (활동성): 매출채권회전율 등
- GROWTH (성장성): 총자산증가율 등
```

#### 테스트 케이스
```
- "우리 회사의 수익성 지표를 보여줘"
- "안정성 관련 비율들은?"
- "성장성 분석에 필요한 지표는?"
```

---

### Phase 6: available_data 체크 (Low Priority)

**목표**: 친절한 안내 메시지

#### 구현 단계

**6.1 _validate_query() 확장**
```python
def _validate_query(self, query):
    """Cypher 쿼리 사전 검증"""
    warnings = []
    
    # 기존 검증...
    
    # 새로 추가: available_data 체크
    # 쿼리에서 회사 ID 추출
    import re
    company_match = re.search(r"c\.id\s*=\s*'([^']+)'|c\.id\s*IN\s*\[([^\]]+)\]", query)
    if company_match:
        company_ids = []
        if company_match.group(1):
            company_ids = [company_match.group(1)]
        else:
            # IN [...] 형식
            ids_str = company_match.group(2)
            company_ids = [cid.strip().strip("'\"") for cid in ids_str.split(',')]
        
        # 각 회사의 available_data 체크
        for cid in company_ids:
            company_config = self.config['entities']['companies'].get(cid)
            if company_config:
                avail_data = company_config.get('available_data', [])
                
                # BS 데이터 요청했는데 없는 경우
                if 'BS' in query and 'BS' not in avail_data:
                    warnings.append(f"⚠️ {company_config['official_name']}은(는) BS 데이터가 제공되지 않습니다.")
                
                # IS 데이터 요청했는데 없는 경우
                if 'IS' in query and 'IS' not in avail_data:
                    warnings.append(f"⚠️ {company_config['official_name']}은(는) IS 데이터가 제공되지 않습니다.")
    
    return warnings
```

#### 테스트 케이스
```
- (만약 특정 회사가 BS 데이터 없다면)
  "X회사의 자산총계는?" → "X회사는 BS 데이터가 제공되지 않습니다"
```

---

### Phase 7: contextual_ids 활용 (Low Priority)

**목표**: 사업별 데이터 조회 시 올바른 ID 사용

#### 현재 상황
```json
"LSCNS_C": {
  "contextual_ids": { "segment_data": "LSCNS_S" }
}
```

**의미**: LS전선(연결)의 사업별 데이터는 실제로 LS전선(별도) ID로 저장됨

**ETL**: 이미 활용 중 ✅
**Agent**: 미활용 ❌

#### 구현 단계

**7.1 System Prompt 추가**
```markdown
**Contextual ID Mapping (SEGMENT data only):**

Some companies use different IDs for segment data:
- LSCNS_C (연결) → Use LSCNS_S for segment queries

When querying segment data, check contextual_ids in runtime context.
```

**7.2 Runtime Context에 추가**
```python
# run() 메서드의 컨텍스트 생성 부분
if level == "SEGMENT":
    contextual_id_info = {}
    for cid, cdata in self.config['entities']['companies'].items():
        if 'contextual_ids' in cdata and 'segment_data' in cdata['contextual_ids']:
            contextual_id_info[cid] = cdata['contextual_ids']['segment_data']
    
    if contextual_id_info:
        entity_context += f"\n**Contextual ID Mapping (SEGMENT):**\n"
        entity_context += f"{json.dumps(contextual_id_info, ensure_ascii=False, indent=2)}\n"
```

---

### Phase 8: 테스트 자동화 및 회귀 테스트 (Critical for Long-term)

**목표**: 새 기능 추가 시 기존 기능 보호, 자동 검증

#### 구현 단계

**8.1 테스트 스크립트 확장**
```python
# scripts/test_config_features.py (신규 생성)

test_cases = {
    "PLAN_VS_ACTUAL": [
        {
            "query": "2023년 MnM 매출액 계획 대비 실적",
            "expected_keywords": ["계획", "실적", "달성률", "%"],
            "expected_data": {"plan": True, "actual": True}
        }
    ],
    "YTD": [
        {
            "query": "2023년 9월까지 누계 매출액",
            "expected_keywords": ["누계", "9월"],
            "min_value_check": True
        }
    ],
    "CALCULATED_RATIOS": [
        {
            "query": "MnM의 2023년 ROE를 계산해줘",
            "expected_keywords": ["ROE", "%", "자기자본"],
            "calculation_check": True
        }
    ],
    "VIEWPOINTS": [
        {
            "query": "수익성 지표를 모두 보여줘",
            "expected_keywords": ["영업이익률", "ROE"],
            "list_check": True
        }
    ]
}

def run_regression_tests():
    """모든 Phase의 테스트 케이스 실행"""
    agent = GmisAgentV4()
    results = {}
    
    for phase, cases in test_cases.items():
        phase_results = []
        for case in cases:
            result = agent.run_and_get_structured_output(case['query'])
            # 검증 로직
            passed = verify_result(result, case)
            phase_results.append({"case": case['query'], "passed": passed})
        results[phase] = phase_results
    
    return results
```

**8.2 CI/CD 통합**
```yaml
# .github/workflows/test.yml (선택사항)
name: Agent Feature Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run regression tests
        run: python scripts/test_config_features.py
```

#### 기대 효과
- 각 Phase 완료 후 전체 기능 자동 검증
- 회귀 버그 조기 발견
- 프로젝트 안정성 향상

---

## 📅 구현 일정 제안 (Updated)

### Week 1 (최우선)
- [x] ~~Quarter/HalfYear 지원~~ (완료!)
- [ ] **Phase 1: PLAN_VS_ACTUAL**
- [ ] **Phase 4: get_definition() Tool**

### Week 2 (고급 기능)
- [ ] **Phase 2: YTD/누계** (최적화된 쿼리 적용)
- [ ] **Phase 3: calculate_financial_ratio() Tool** (일괄 조회 방식)

### Week 3 (완성도)
- [ ] **Phase 5: Viewpoints**
- [ ] **Phase 6: available_data 체크**
- [ ] **Phase 7: contextual_ids**

### Week 4 (품질 보증)
- [ ] **Phase 8: 테스트 자동화**
- [ ] 전체 회귀 테스트
- [ ] 성능 최적화

---

## 🎯 예상 효과

**개선 전 (현재)**:
- 기본 데이터 조회: ⭐⭐⭐⭐⭐
- 고급 분석: ⭐⭐
- 계산 기능: ⭐
- 설명 정확도: ⭐⭐⭐

**개선 후**:
- 기본 데이터 조회: ⭐⭐⭐⭐⭐
- 고급 분석: ⭐⭐⭐⭐⭐ (계획대비, 누계, 관점별)
- 계산 기능: ⭐⭐⭐⭐⭐ (자동 계산)
- 설명 정확도: ⭐⭐⭐⭐⭐ (config 기반)

---

## 📝 다음 단계

이 문서를 다른 LLM에게 보여주시고:
1. 놓친 항목이 있는지
2. 우선순위가 적절한지
3. 구현 방법이 합리적인지

검토받으신 후, 바로 구현을 시작할 수 있습니다!

---

## 📝 검토 및 개선 이력

### v1.1 (2025-10-29) - 외부 검토 반영

**검토자 피드백**:
1. ✅ YTD 쿼리 최적화 - 단일 쿼리로 최신 월 자동 감지
2. ✅ calculate_financial_ratio 성능 개선 - IN 절로 일괄 조회
3. ✅ Phase 8 추가 - 테스트 자동화 및 회귀 테스트

**반영 내용**:
- Phase 2: WITH 절 활용한 최적화된 YTD 쿼리 패턴 추가
- Phase 3: for 루프 → IN 절 일괄 조회로 변경
- Phase 8: 새로 추가 (테스트 자동화)
- 구현 일정: Week 4 추가

---

**작성자**: GMS_WebApp Development Team  
**최종 업데이트**: 2025-10-29  
**검토 상태**: ✅ 외부 검토 완료 및 피드백 반영  
**다음 단계**: Phase 1부터 순차적 구현 시작

