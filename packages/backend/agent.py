import google.generativeai as genai
import json
import os
import uuid
import logging
from neo4j import GraphDatabase
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

# --- 로깅 설정 ---
# 파일과 콘솔 양쪽에 로그 출력 (터미널 종료 시에도 로그 확인 가능!)
log_filename = f"agent_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,  # DEBUG → INFO로 변경 (matplotlib 로그 차단)
    format='[%(asctime)s][%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(log_filename, mode='w', encoding='utf-8'),
        logging.StreamHandler()  # 콘솔 출력도 유지
    ]
)

# matplotlib 로그 레벨을 WARNING으로 설정 (폰트 검색 로그 차단!)
logging.getLogger('matplotlib').setLevel(logging.WARNING)
logging.getLogger('matplotlib.font_manager').setLevel(logging.WARNING)
logging.getLogger('PIL').setLevel(logging.WARNING)

print(f"[시스템] 로그 파일: {log_filename}")

# --- API 키 설정 ---
GOOGLE_AI_API_KEY = "AIzaSyB-8Bz4sHoYxz88LKT7rWpF298C5vFCj4s"

class GmisAgentV4:
    """
    GMIS Knowledge Graph v5 전용 AI Agent (v4 Final)
    
    v3 기반 + 5가지 핵심 개선:
    1. 통합 경로 관리 (base_dir, output_dir)
    2. with 구문 지원 (__enter__, __exit__)
    3. 차트 컬럼 검증
    4. 모델명/반복횟수 파라미터화
    5. logging 모듈 (시스템 로그)
    
    핵심 철학:
    - ASK THE GRAPH, DO NOT ASSUME
    - GDB의 지능을 100% 신뢰
    - Tool 연계 호출 지원 (ReAct 패턴)
    """
    
    def __init__(self, 
                 config_path='config.json',
                 db_uri="bolt://127.0.0.1:7687",
                 db_user="neo4j",
                 db_pass="vlvmffoq1!",
                 session_id=None,
                 model_name='models/gemini-2.5-flash',  # [정확도 우선]
                 max_iterations=10):  # [개선1] 파라미터화
        
        # Session ID
        self.session_id = session_id or str(uuid.uuid4())
        
        # [개선2] 통합 경로 관리
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.output_dir = os.path.join(self.base_dir, "outputs", self.session_id)
        os.makedirs(self.output_dir, exist_ok=True)
        
        print(f"[Session ID] {self.session_id}")
        logging.info(f"결과 저장 경로: {self.output_dir}")
        
        # Config 로드
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        
        # NLU 구축
        self.nlu = self._build_nlu()
        
        # Neo4j 연결
        self.driver = GraphDatabase.driver(db_uri, auth=(db_user, db_pass))
        logging.info("Neo4j 데이터베이스 연결 성공")
        
        # Gemini 설정
        if not GOOGLE_AI_API_KEY or GOOGLE_AI_API_KEY.startswith("여러분의_"):
            raise ValueError("GOOGLE_AI_API_KEY를 설정해주세요.")
        genai.configure(api_key=GOOGLE_AI_API_KEY)
        
        self.model_name = model_name
        self.max_iterations = max_iterations
        
        self.model = genai.GenerativeModel(
            self.model_name,
            safety_settings=[
                {"category": c, "threshold": "BLOCK_NONE"} 
                for c in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH",
                         "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]
            ]
        )
        
        # 시스템 프롬프트
        self.system_prompt = self._create_system_prompt()
        
        # [핵심 수정] Gemini chat 객체를 인스턴스 변수로 유지
        self.chat = None  # 첫 run() 호출 시 초기화
        
        # 대화 히스토리 (Gemini API 형식)
        self.chat_history = []
        self.max_history_turns = 20  # 히스토리 제한 완화 (요약 기능 비활성화)
        
        # 마지막 쿼리 결과 캐싱 (실제 데이터는 여기에)
        self.last_query_result = None
        
        # 배치 테스트 모드 (기본: False)
        self._batch_test_mode = False
        
        print(f"[OK] Agent v4 초기화 완료 (모델: {self.model_name})")
    
    # [개선3] with 구문 지원
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def _build_nlu(self):
        """완전한 NLU 사전 구축 (v3 동일)"""
        nlu = {
            "company": {},
            "account": {},
            "group": {},
            "ratio": {},
            "viewpoint": {},
            "temporal_relation": {},
            "temporal_unit": {},
            "analysis_type": {}
        }
        
        # 회사 별칭
        for cid, data in self.config.get('entities', {}).get('companies', {}).items():
            for alias in [data.get('official_name')] + data.get('aliases', []):
                if alias:
                    nlu["company"][alias.lower()] = cid
        
        # 계정 별칭
        for aid, data in self.config.get('entities', {}).get('accounts', {}).items():
            for alias in [data.get('official_name')] + data.get('aliases', []):
                if alias:
                    nlu["account"][alias.lower()] = aid
        
        # 그룹 별칭
        for gid, data in self.config.get('business_rules', {}).get('company_groups', {}).items():
            for alias in [data.get('name')] + data.get('aliases', []):
                if alias:
                    nlu["group"][alias.lower()] = gid
        
        # 재무비율
        for rid, data in self.config.get('financial_ratios', {}).get('ratios', {}).items():
            for alias in [data.get('official_name')] + data.get('aliases', []):
                if alias:
                    nlu["ratio"][alias.lower()] = rid
        
        # 분석 관점
        for vid, data in self.config.get('financial_ratios', {}).get('viewpoints', {}).items():
            for alias in [data.get('name')] + data.get('aliases', []):
                if alias:
                    nlu["viewpoint"][alias.lower()] = vid
        
        # 시간 관계
        for rel_type, aliases in self.config.get('context_classifiers', {}).get('temporal_classifiers', {}).get('relationship_aliases', {}).items():
            if isinstance(aliases, list):
                for alias in aliases:
                    if alias:
                        nlu["temporal_relation"][alias.lower()] = rel_type
        
        # 시간 단위
        for unit_id, aliases in self.config.get('context_classifiers', {}).get('temporal_classifiers', {}).get('unit_aliases', {}).items():
            if isinstance(aliases, list):
                for alias in aliases:
                    if alias:
                        nlu["temporal_unit"][alias.lower()] = unit_id
        
        # 분석 타입
        for analysis_type, aliases in self.config.get('context_classifiers', {}).get('temporal_classifiers', {}).get('analysis_type_aliases', {}).items():
            if isinstance(aliases, list):
                for alias in aliases:
                    if alias:
                        nlu["analysis_type"][alias.lower()] = analysis_type
        
        return nlu
    
    def _create_system_prompt(self):
        """GDB의 지능을 100% 활용하는 시스템 프롬프트"""
        return """You are 'GMIS Agent v4', a financial expert navigating a powerful Knowledge Graph (v5).

**Core Principle: ASK THE GRAPH. DO NOT ASSUME.**

**🎯 Primary Decision Flow (MANDATORY FIRST STEP!):**

Before doing ANYTHING else, classify the user's request:

1. **Follow-up Action?** (후속 작업)
   - Keywords: "그래프", "차트로", "시각화", "CSV로", "파일로", "저장", "다운로드"
   - Check: Does `last_query_result` exist from previous turn?
   - **If YES**:
     * DO NOT run new query!
     * Call data_visualization or generate_downloadable_link immediately
     * Use cached data (omit `data` parameter)
     * After tool success: Simple confirmation only ("차트 생성 완료. 경로: ...")
     * **NO 4-part report!**

2. **New Data Query?** (새 데이터 조회)
   - Keywords: company names, account names, time periods
   - NOT a follow-up action
   - **If YES**: run_cypher_query → pre-process → 4-part report

3. **Knowledge Question?** (지식 질문)
   - Keywords: "뭐야?", "의미는?", "왜?", "차이는?"
   - **If YES**: general_knowledge_qa → natural explanation

The Knowledge Graph contains ALL business logic, relationships, and calculation rules.
Your job is to translate user questions into graph traversals, NOT to memorize rules.

**💡 How to Leverage the Graph's Intelligence:**

1. **Time Comparisons:** Use pre-built relationships
   - YoY: `MATCH (p1:Period)-[:PRIOR_YEAR_EQUIV]->(p2:Period)`
   - MoM: `MATCH (p1:Period)-[:PREVIOUS]->(p2:Period)`

2. **Formula Discovery:** Ask the graph for calculation structure
   - `MATCH (parent:Metric)-[r:SUM_OF]->(child:Metric) RETURN r.operation, child`

3. **Aggregation Rules:** Get from Account.aggregation property
   - `MATCH (a:Account {id: 'XXX'}) RETURN a.aggregation` → 'SUM' or 'LAST'

4. **Two Data Levels:**
   - CORPORATE: `(c:Company)-[:HAS_STATEMENT]->(fs:FinancialStatement)`
   - SEGMENT: `(c:Company)-[:HAS_ALL_SEGMENTS]->(bs:BusinessSegment)`

**💎 GENEROUS ANSWER STRATEGY (데이터 조회 질문만!):**

**ONLY for DATA QUERIES** (run_cypher_query 사용 시):

### 1. 요약 (Executive Summary)
- Direct answer with actual numbers
- **CRITICAL**: You MUST specify the financial scope ('연결' or '별도') from `statement_scope` column!
  Example: "LS MnM(연결)의 2023년 연간 매출액은..."

### 2. 집계 데이터 (Aggregated Table)
- Markdown table format
- Include all metrics
- If all data is from the same scope, mention it in title: `| 지표 (2023년 연결 기준) |`

### 3. 월별 상세 (Monthly Evidence)
- ALWAYS show monthly breakdown
- This proves the summary
- **Format Guidelines:**
  * Single company: Vertical table (current format) ✅
  * Multiple companies: **PIVOT table** (companies as columns for easy comparison)
    | 월 | 회사A | 회사B | 회사C |
    |:---|---:|---:|---:|
  * Keep table concise (max 15-20 rows)

### 4. 인사이트 (Brief Insights)
- 2-3 sentences of analysis

**NEVER skip sections 2 and 3! Users need to see the evidence!**

**🔢 Number Format Guidelines:**
- **요약**: 조/억 혼용 (예: "6조 2,171억원")
- **테이블**: 
  * 1조 이상: "6.2조원" or "6조 2,171억"
  * 1조 미만: "5,001억원" (억 단위)
- **일관성**: 같은 테이블 내에서는 동일 단위 사용!

**For KNOWLEDGE QUESTIONS** (general_knowledge_qa 사용 시):
- Simple, clear explanation
- 3-5 paragraphs in natural Korean
- NO need for tables or structured format
- Just answer naturally and helpfully

**Example of CORRECT Answer Format:**

**Single Company:**
```
### 1. 요약
LS전선(연결)의 2023년 연간 매출액은 **6조 2,171억원**, 영업이익은 **2,325억원**입니다.

### 2. 집계 데이터
| 지표 (2023년) | 값 |
|:---|:---|
| 매출액 | 6.2조원 |
| 영업이익 | 2,325억원 |
| 영업이익률 | 3.74% |

### 3. 월별 상세
| 월 | 매출액 (억원) | 영업이익 (억원) |
|:---|---:|---:|
| 1월 | 5,001 | 93 |
| 2월 | 5,123 | 148 |
...
| 12월 | 5,890 | 267 |

### 4. 인사이트
하반기로 갈수록 매출과 이익이 증가하는 추세를 보였습니다.
```

**Multiple Companies (PIVOT format):**
```
### 1. 요약
2023년 제조4사 중 매출액 1위는 MnM (10.2조원), 영업이익 1위는 ELECTRIC (3,120억원)입니다.

### 2. 집계 데이터  
| 회사 | 매출액 | 영업이익 | 영업이익률 |
|:---|---:|---:|---:|
| MnM | 10.2조 | 2,212억 | 2.18% |
| 전선 | 6.2조 | 2,326억 | 3.74% |
| ELECTRIC | 3.7조 | 3,120억 | 8.51% |

### 3. 월별 비교 (PIVOT)
| 월 | ELECTRIC | MnM | 전선 |
|:---|---:|---:|---:|
| 1월 | 264 | 353 | 126 |
| 2월 | 275 | -421 | 260 |
...
| 상반기 계 | 1,772 | 818 | 976 |
| 하반기 계 | 1,347 | 1,400 | 1,340 |

### 4. 인사이트
MnM과 전선은 상반기 대비 하반기 증가, ELECTRIC은 감소.
```


**Query Pattern Templates:**

**CORPORATE Level (전사 레벨):**

단일 회사 조회:
```cypher
MATCH (c:Company {id: 'ELECTRIC'})-[:HAS_STATEMENT]->(fs:FinancialStatement)
WHERE fs.id CONTAINS '2023' AND fs.id CONTAINS 'ACTUAL'
MATCH (fs)-[:HAS_SCOPE]->(scope:StatementScope {id: 'CONSOLIDATED'})
MATCH (fs)-[:FOR_PERIOD]->(p:Period)
MATCH (fs)-[:CONTAINS]->(m:Metric)-[:INSTANCE_OF_RULE]->(a:Account)
WHERE a.id IN ['매출액_합계', '영업이익']
MATCH (m)-[:HAS_OBSERVATION]->(v:ValueObservation)
RETURN c.name, p.year, p.month, a.name, v.value, scope.id AS statement_scope
ORDER BY p.month
```
**CRITICAL**: ALWAYS include `scope.id AS statement_scope` in RETURN!


다중 회사 비교 (패턴 - NLU 컨텍스트 활용):
```cypher
// STEP 1: Get Company/Account IDs from NLU context
//   Example: User asks "전선과 MnM의 매출과 영업이익"
//   NLU provides: '전선' → 'LSCNS_C', 'MnM' → 'MnM'
//   Accounts: '매출' → '매출액_합계', '영업이익' → '영업이익'
//   Special Rule: MnM → use '조정영업이익' instead

MATCH (c:Company)-[:HAS_STATEMENT]->(fs:FinancialStatement)
WHERE c.id IN [/* company_ids_from_nlu */]
  AND fs.id CONTAINS '2023' AND fs.id CONTAINS 'ACTUAL'
MATCH (fs)-[:HAS_SCOPE]->(scope:StatementScope {id: 'CONSOLIDATED'})
MATCH (fs)-[:FOR_PERIOD]->(p:Period)
MATCH (fs)-[:CONTAINS]->(m:Metric)-[:INSTANCE_OF_RULE]->(a:Account)
WHERE (c.id = /* company_1 */ AND a.id IN [/* account_ids_for_company_1 */])
   OR (c.id = /* company_2 */ AND a.id IN [/* account_ids_for_company_2_with_special_rules */])
MATCH (m)-[:HAS_OBSERVATION]->(v:ValueObservation)
RETURN c.name, p.year, p.month, a.name, v.value, scope.id AS statement_scope
ORDER BY c.name, p.month, a.name
```
**CRITICAL**: Include `scope.id AS statement_scope` in RETURN!
→ Use NLU context and special rules to construct WHERE clauses!
```

**SEGMENT Level Patterns:**

**Pattern A: 사업 목록 조회 ("어떤 사업이 있어?", "사업 항목은?")**

기본 목록 (모든 사업 포함):
```cypher
MATCH (c:Company {id: 'ELECTRIC'})-[:HAS_ALL_SEGMENTS]->(bs:BusinessSegment)
RETURN DISTINCT bs.name
ORDER BY bs.name
```

CIC별 그룹화 ("CIC별로", "부문별로", "조직별로"):
```cypher
MATCH (company:Company {id: 'ELECTRIC'})
// 본사 직속 사업 (CIC 아닌 것)
OPTIONAL MATCH (company)<-[:PART_OF]-(bs_direct:BusinessSegment)
WHERE NOT (bs_direct)<-[:PART_OF]-(:CIC)
// 전력CIC 소속 사업
OPTIONAL MATCH (company)<-[:PART_OF]-(cic_power:CIC {id: '전력CIC'})<-[:PART_OF]-(bs_power:BusinessSegment)
// 자동화CIC 소속 사업
OPTIONAL MATCH (company)<-[:PART_OF]-(cic_auto:CIC {id: '자동화CIC'})<-[:PART_OF]-(bs_auto:BusinessSegment)

// 결과 조합
WITH 
  collect(DISTINCT bs_direct.name) AS 본사직속,
  collect(DISTINCT bs_power.name) AS 전력CIC,
  collect(DISTINCT bs_auto.name) AS 자동화CIC

RETURN 
  '본사직속' AS 소속, 본사직속 AS 사업목록
UNION
RETURN 
  '전력CIC' AS 소속, 전력CIC AS 사업목록  
UNION
RETURN
  '자동화CIC' AS 소속, 자동화CIC AS 사업목록
```

간단 버전 (CIC별만):
```cypher
MATCH (cic:CIC)<-[:PART_OF]-(bs:BusinessSegment)
WHERE cic.id IN ['전력CIC', '자동화CIC']
RETURN cic.name AS 소속, collect(bs.name) AS 사업목록
ORDER BY cic.name
```

**Pattern B: 사업별 손익 조회 ("사업별 매출은?", "부스닥트의 매출은?")**

특정 사업 아이템 상세:
```cypher
MATCH (bs:BusinessSegment {{name: '부스닥트'}})<-[:FOR_SEGMENT]-(m:Metric)
MATCH (m)-[:INSTANCE_OF_RULE]->(a:Account)
MATCH (m)-[:HAS_OBSERVATION]->(v:ValueObservation)
WHERE v.region = '전체' AND v.value IS NOT NULL
MATCH (m)-[:CONTAINS]-(fs:FinancialStatement)-[:FOR_PERIOD]->(p:Period)
WHERE fs.id CONTAINS '2023' AND fs.id CONTAINS 'ACTUAL'
RETURN bs.name, p.year, p.month, a.name, v.value
ORDER BY p.month, a.name
```

모든 사업 아이템 비교:
```cypher
MATCH (c:Company {{id: 'ELECTRIC'}})-[:HAS_ALL_SEGMENTS]->(bs:BusinessSegment)
MATCH (m:Metric)-[:FOR_SEGMENT]->(bs)
MATCH (m)-[:INSTANCE_OF_RULE]->(a:Account)
WHERE a.name = '매출액'  // SEGMENT data uses short names!
MATCH (m)-[:HAS_OBSERVATION]->(v:ValueObservation)
WHERE v.region = '전체' AND v.value IS NOT NULL
MATCH (m)-[:CONTAINS]-(fs:FinancialStatement)
WHERE fs.id CONTAINS '2023' AND fs.id CONTAINS 'ACTUAL'
RETURN bs.name, sum(v.value) AS total_revenue
ORDER BY total_revenue DESC
```

**CRITICAL for SEGMENT Accounts:**
사업별 데이터의 Account는 Term 노드를 통해 찾으세요:

Step 1: Term으로 Account 찾기
```cypher
MATCH (t:Term {{value: '매출액'}})<-[:ALSO_KNOWN_AS]-(a:Account)
RETURN a.id
```
→ '매출액_합계'

Step 2: 사업별 데이터 조회에 사용
```cypher
MATCH (bs:BusinessSegment {{name: '부스닥트'}})<-[:FOR_SEGMENT]-(m)
MATCH (m)-[:INSTANCE_OF_RULE]->(a:Account)
// Term으로 찾은 Account 사용
MATCH (t:Term)<-[:ALSO_KNOWN_AS]-(a)
WHERE t.value IN ['매출액', '영업이익', '세전이익']
...
```

**Critical for SEGMENT Accounts:**
To find the correct Account.id for segment data queries, use these methods in order:

1. **Use Term Node (BEST):** Query the graph to find Account linked to Term.
   `MATCH (t:Term {value: '매출액'})<-[:ALSO_KNOWN_AS]-(a:Account) RETURN a.id`

2. **Use Dynamic Context:** If Term fails, refer to 'Segment Account Mapping' in runtime context.

**용어**: "사업 아이템" or "사업 항목" (NOT "사업 부문"!)
```

**🏢 Company Groups:**
When a user mentions a group name (e.g., "제조4사"), refer to the **'Company Groups' mapping** 
provided in the dynamic context at runtime. The context will give you the exact list of company IDs.
DO NOT guess the members!

**CRITICAL for SEGMENT:**
- BusinessSegment has NO [:HAS_STATEMENT] relationship!
- Use [:FOR_SEGMENT] from Metric
- For data queries: MUST filter v.region = '전체' AND v.value IS NOT NULL
- For list queries: Just query BusinessSegment nodes directly
```

**Critical Notes:**
- Get monthly data first, then aggregate yourself
- CORPORATE data has NO v.region property!
- SEGMENT data REQUIRES v.region = '전체' filter
- Account.id: Korean names ('매출액_합계', '영업이익')

**🚨 Data Availability:**
- CORPORATE data (전사 레벨): 2022, 2023, 2024
- SEGMENT data (사업별): **2024년만 사용 가능**
- If SEGMENT query returns 0 records for 2023: Suggest "2024년 데이터를 조회해보시겠습니까?"

**Tools:**
- run_cypher_query(query: str) - LS Group 데이터 조회
- data_visualization(chart_type, title, x_col='p.month', y_cols=['v.value'], company_filter=None, account_filter=None) - 차트 생성
  * data parameter는 생략 (자동으로 캐시된 데이터 사용)
  * company_filter: 회사명 필터 (예: "전선", "ELECTRIC")
  * account_filter: 계정명 필터 (예: "매출", "영업이익")
- generate_downloadable_link(data, file_name, file_type) - CSV/JSON 저장
- general_knowledge_qa(question: str) - 재무/경영 지식 제공

**🎯 Two Types of Questions (중요!):**

A. **DATA QUERIES** (LS Group 데이터):
   - "전선의 매출은?" → run_cypher_query
   - "3분기 영업이익" → run_cypher_query
   - Use GDB for specific company data

B. **KNOWLEDGE QUESTIONS** (재무 지식):
   - "부채비율이 뭐야?" → general_knowledge_qa
   - "연결과 별도의 차이는?" → general_knowledge_qa
   - "왜 높아?" → general_knowledge_qa  
   - "일반적으로 좋은 수준은?" → general_knowledge_qa
   - Use LLM's built-in knowledge

**You can FREELY SWITCH between data queries and knowledge provision!**

When to use general_knowledge_qa:
- Definitions (정의)
- Explanations (설명)
- "왜?", "이유는?", "원인은?" questions
- Industry standards or benchmarks
- General financial concepts

**💡 Default Behavior Clarification (MANDATORY!):**
At the end of your answer for DATA QUERIES, you MUST add a clarification note about defaults:

- **If query used '조정영업이익' (MnM, E1, 글로벌)**:
  Add: `💡 [회사명]은(는) 조정영업이익 기준입니다. 일반 영업이익이 필요하시면 말씀해주세요.`

- **If result is 'CONSOLIDATED' and user didn't specify '별도'**:
  Add: `💡 연결 재무제표 기준입니다. 별도 기준이 필요하시면 말씀해주세요.`

- **If both apply, combine them**:
  `💡 [회사명]은(는) 조정영업이익 기준이며, 모든 데이터는 연결 재무제표 기준입니다.`

Example:
```
### 4. 인사이트
...하반기 증가 추세...

💡 LS MnM은 조정영업이익 기준이며, 모든 데이터는 연결 재무제표 기준입니다.
```

**💡 Using Previous Query Results (IMPORTANT!):**
When user asks "그래프로", "차트로", "시각화" after a data query:
- Check chat_history for "[쿼리 실행 완료]" message
- If found: **Call data_visualization WITHOUT the data parameter**
- System will automatically use the cached data
- You only need to specify: chart_type, title, x_col, y_cols
- Example Tool Call:
  ```
  data_visualization(
    chart_type="line",
    title="LS전선 2023년 월별 매출",
    x_col="p.month",
    y_cols=["v.value"]
  )
  ```
  (data parameter is optional - system fills it automatically!)
"""
    
    # === Tools (v3 기능 유지 + 개선) ===
    
    def run_cypher_query(self, query: str) -> dict:
        """Neo4j Cypher 쿼리 실행 (환각 방지 강화)"""
        try:
            with self.driver.session() as session:
                result = session.run(query)
                data = [record.data() for record in result]
                
                # [긴급 수정] 0개 레코드 시 명확한 실패 응답
                if len(data) == 0:
                    return {
                        "status": "no_data",
                        "data": [],
                        "message": "쿼리는 성공했으나 조회 결과가 0건입니다. 해당 데이터가 Knowledge Graph에 존재하지 않습니다."
                    }
                
                return {"status": "success", "data": data}
        except Exception as e:
            error_msg = str(e)
            error_type = type(e).__name__
            
            # 일반적인 오류 패턴 분석 및 힌트 제공
            hints = []
            if "c.name" in query or "company.name" in query:
                hints.append("Hint: Company 노드는 'c.id'로 조회해야 합니다. 예: {id: 'ELECTRIC'}")
            if "WHERE" in query and "year" in query and "fs.year" in query:
                hints.append("Hint: FinancialStatement에는 year 속성이 없습니다. fs.id CONTAINS '2023' 사용")
            if "v.region" in query and "HAS_STATEMENT" in query:
                hints.append("Hint: CORPORATE 레벨 데이터에는 v.region 속성이 없습니다. 필터 제거 필요")
            if "'Revenue'" in query or "'Sales'" in query:
                hints.append("Hint: Account ID는 한글입니다. '매출액_합계', '영업이익' 등 사용")
            
            return {
                "status": "error",
                "error": error_msg,
                "error_type": error_type,
                "hints": hints,
                "original_query": query
            }
    
    def data_visualization(self, data: list = None, chart_type: str = 'bar', title: str = '', x_col: str = '', y_cols: list = None, company_filter: str = None, account_filter: str = None) -> dict:
        """
        차트 생성 및 PNG 저장 (필터링 기능 강화)
        - company_filter: 특정 회사 데이터만 필터링
        - account_filter: 특정 계정 데이터만 필터링
        """
        # Gemini Function Call에서 타입 변환
        if y_cols and not isinstance(y_cols, list):
            y_cols = list(y_cols)

        # data가 없으면 last_query_result 사용 (후속 요청 처리)
        if not data and self.last_query_result:
            print("[힌트] 직전 조회 데이터를 사용하여 차트를 생성합니다.")
            data = self.last_query_result.get("data")
            if not x_col and self.last_query_result.get("columns"):
                cols = self.last_query_result["columns"]
                if 'p.month' in cols or 'month' in cols:
                    x_col = 'p.month' if 'p.month' in cols else 'month'
                if not y_cols and 'v.value' in cols:
                    y_cols = ['v.value']
        
        if not data:
            return {"error": "데이터가 없습니다."}

        try:
            df = pd.DataFrame(data)
            print(f"[DEBUG] 필터링 전 데이터: {len(df)}개 레코드")

            # [핵심 수정 1] 필터링 로직 강화 - (연결), (별도) 제거
            if company_filter:
                # LLM이 생성한 "(연결)" 등 불필요한 텍스트 제거
                clean_company_filter = company_filter.split('(')[0].strip()
                # regex=False로 특수문자 오류 방지 및 정확한 부분 문자열 매칭
                if 'c.name' in df.columns:
                    df = df[df['c.name'].str.contains(clean_company_filter, case=False, na=False, regex=False)]
                    print(f"[DEBUG] 회사 필터({clean_company_filter}) 적용 후: {len(df)}개 레코드")

            if account_filter:
                # 계정 이름도 마찬가지로 유연하게 필터링
                clean_account_filter = account_filter.split(' ')[0].strip()
                if 'a.name' in df.columns:
                    df = df[df['a.name'].str.contains(clean_account_filter, case=False, na=False, regex=False)]
                    print(f"[DEBUG] 계정 필터({clean_account_filter}) 적용 후: {len(df)}개 레코드")

            print(f"[DEBUG] 최종 필터링 완료: {len(df)}개 레코드")
            if df.empty:
                return {"error": "필터링 결과 데이터가 없습니다. 회사명이나 계정명을 확인해주세요."}

            # [개선4] 차트 생성 전 컬럼 검증
            required_cols = [x_col] + (y_cols if y_cols and y_cols != ['v.value'] else [])
            missing_cols = [col for col in required_cols if col and col not in df.columns]
            if missing_cols:
                error_msg = f"데이터에 필요한 컬럼이 없습니다. 누락: {missing_cols}"
                logging.error(error_msg)
                return {"error": error_msg}
            
            # [긴급 수정] 한글 폰트 설정 - 폰트 검색 최소화
            import platform
            system = platform.system()
            if system == 'Windows':
                # 직접 폰트 파일 경로 지정 (검색 생략)
                import matplotlib.font_manager as fm
                font_path = 'C:\\Windows\\Fonts\\malgun.ttf'
                font_prop = fm.FontProperties(fname=font_path)
                plt.rcParams['font.family'] = font_prop.get_name()
            elif system == 'Darwin':
                plt.rcParams['font.family'] = 'AppleGothic'
            else:
                plt.rcParams['font.family'] = 'DejaVu Sans'
            
            plt.rcParams['axes.unicode_minus'] = False
            
            fig, ax = plt.subplots(figsize=(12, 7))
            
            # [핵심 수정 2] y_cols를 동적으로 설정하여 여러 계정 그리기 지원
            if not y_cols or y_cols == ['v.value']:
                # y_cols가 지정되지 않았으면, 필터링된 데이터의 모든 계정을 그림
                if 'a.name' in df.columns and 'v.value' in df.columns:
                    unique_accounts = df['a.name'].unique()
                    for account in unique_accounts:
                        subset = df[df['a.name'] == account]
                        if chart_type == 'line':
                            ax.plot(subset[x_col], subset['v.value'], marker='o', label=account)
                        elif chart_type == 'bar':
                            ax.bar(subset[x_col], subset['v.value'], label=account, alpha=0.7)
                    if len(unique_accounts) > 1:
                        ax.legend()
                else:
                    # 기본 단순 차트
                    if chart_type == 'line':
                        ax.plot(df[x_col], df['v.value'], marker='o')
                    elif chart_type == 'bar':
                        ax.bar(df[x_col], df['v.value'])
            else:
                # y_cols가 명시적으로 주어지면 기존 방식대로 그림
                for y_col in y_cols:
                    if chart_type == 'line':
                        ax.plot(df[x_col], df[y_col], marker='o', label=y_col)
                    elif chart_type == 'bar':
                        ax.bar(df[x_col], df[y_col], label=y_col)
                if len(y_cols) > 1:
                    ax.legend()

            ax.set_title(title, fontsize=16)
            ax.set_xlabel(x_col, fontsize=12)
            ax.grid(True, alpha=0.3)
            plt.tight_layout()
            
            # [개선2] 통합 경로 사용
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"chart_{timestamp}.png"
            filepath = os.path.join(self.output_dir, filename)
            
            plt.savefig(filepath, dpi=150, bbox_inches='tight')
            plt.close(fig)
            
            logging.info(f"차트 저장 완료: {filename}")
            
            return {
                "status": "success",
                "file_path": os.path.abspath(filepath)
            }
        except Exception as e:
            logging.error(f"차트 생성 오류: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e)}
    
    def generate_downloadable_link(self, data: list, file_name: str, file_type: str = 'csv') -> dict:
        """CSV/JSON 파일 저장 (v3 + 개선2: 통합 경로)"""
        if not data:
            return {"error": "데이터가 없습니다."}
        
        try:
            df = pd.DataFrame(data)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            if file_type == 'csv':
                filename = f"{file_name}_{timestamp}.csv"
                # [개선2] 통합 경로 사용
                filepath = os.path.join(self.output_dir, filename)
                df.to_csv(filepath, index=False, encoding='utf-8-sig')
            elif file_type == 'json':
                filename = f"{file_name}_{timestamp}.json"
                filepath = os.path.join(self.output_dir, filename)
                df.to_json(filepath, orient='records', indent=2, force_ascii=False)
            else:
                return {"error": f"지원하지 않는 파일 형식: {file_type}"}
            
            logging.info(f"파일 저장 완료: {filename}")
            
            return {
                "status": "success",
                "file_path": os.path.abspath(filepath)
            }
        except Exception as e:
            logging.error(f"파일 생성 오류: {e}")
            return {"error": str(e)}
    
    def general_knowledge_qa(self, question: str) -> str:
        """일반 재무/경영 지식 제공"""
        try:
            print(f"\n[DEBUG] ========================================")
            print(f"[DEBUG] general_knowledge_qa 시작")
            print(f"[DEBUG] 질문: {question}")
            print(f"[DEBUG] ========================================")
            logging.info(f"general_knowledge_qa 호출: {question}")
            
            # [안전 조치 1] 모델 생성
            print(f"[DEBUG] Gemini 모델 생성 중...")
            model_simple = genai.GenerativeModel('models/gemini-flash-lite-latest')
            print(f"[DEBUG] Gemini 모델 생성 완료")
            
            # [안전 조치 2] API 호출 전 로그
            print(f"[DEBUG] Gemini API 호출 시작 (지식 제공)...")
            logging.debug("지식 제공 API 호출 중")
            
            response = model_simple.generate_content(
                f"""당신은 재무/경영 전문가입니다. 다음 질문에 상세하고 친절하게 한국어로 답변해주세요:

{question}

답변 시:
- 정의와 개념을 명확히 설명
- 실무적 의미와 활용 방법 제공
- 구체적인 예시 포함
- 일반적인 기준이나 업계 평균 언급 (있다면)
- 3-5 문단으로 충분히 상세하게

전문적이지만 이해하기 쉽게 설명해주세요.""",
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=1500,
                    temperature=0.3
                )
            )
            
            print(f"[DEBUG] Gemini API 응답 수신 완료")
            print(f"[DEBUG] 응답 텍스트 길이: {len(response.text)}자")
            print(f"[DEBUG] general_knowledge_qa 완료")
            logging.info("지식 제공 완료")
            
            return response.text
            
        except Exception as e:
            print(f"\n[CRITICAL ERROR] general_knowledge_qa 실패!")
            print(f"오류 타입: {type(e).__name__}")
            print(f"오류 메시지: {str(e)}")
            logging.error(f"일반 지식 제공 오류: {e}", exc_info=True)
            
            import traceback
            traceback.print_exc()
            
            return f"죄송합니다. 지식 제공 중 오류가 발생했습니다.\n오류: {type(e).__name__}\n질문을 다시 시도해주세요."
    
    def _parse_final_answer_to_structured_format(self, final_answer: str):
        """
        최종 마크다운 답변을 프론트엔드가 요구하는 JSON 구조로 파싱합니다.
        """
        import re
        
        content_blocks = []
        
        # 1. 요약 (### 1. 요약)
        summary_match = re.search(r"###\s*1\.\s*요약\s*\n(.*?)(?=\n###|\Z)", final_answer, re.DOTALL)
        if summary_match:
            content_blocks.append({"type": "text", "content": summary_match.group(1).strip()})

        # 2. 집계 데이터 (### 2. 집계 데이터) - 테이블 파싱
        table_match = re.search(r"###\s*2\.\s*집계 데이터\s*\n(.*?)(?=\n###|\Z)", final_answer, re.DOTALL)
        if table_match:
            table_md = table_match.group(1).strip()
            lines = [line.strip() for line in table_md.split('\n') if line.strip()]
            if len(lines) >= 2 and '|' in lines[0] and '---' in lines[1]:
                columns = [h.strip() for h in lines[0].strip('|').split('|')]
                rows = []
                for line in lines[2:]:
                    rows.append([r.strip() for r in line.strip('|').split('|')])
                
                content_blocks.append({
                    "type": "table", 
                    "content": {"columns": columns, "rows": rows}
                })

        # 3. 월별 상세 (### 3. 월별 상세) - 테이블로 파싱
        details_match = re.search(r"###\s*3\.\s*월별\s+(?:상세|비교|데이터).*?\n(.*?)(?=\n###|\Z)", final_answer, re.DOTALL)
        if details_match:
            details_md = details_match.group(1).strip()
            lines = [line.strip() for line in details_md.split('\n') if line.strip()]
            if len(lines) >= 2 and '|' in lines[0] and '---' in lines[1]:
                columns = [h.strip() for h in lines[0].strip('|').split('|')]
                rows = []
                for line in lines[2:]:
                    rows.append([r.strip() for r in line.strip('|').split('|')])
                
                content_blocks.append({
                    "type": "table",
                    "content": {"columns": columns, "rows": rows}
                })
            else:
                # 테이블 형식이 아니면 텍스트로 추가
                content_blocks.append({"type": "text", "content": f"### 3. 월별 상세\n{details_md}"})

        # 4. 인사이트 (### 4. 인사이트)
        insight_match = re.search(r"###\s*4\.\s*인사이트\s*\n(.*?)(?=\n💡|\Z)", final_answer, re.DOTALL)
        if insight_match:
            content_blocks.append({"type": "text", "content": insight_match.group(1).strip()})

        # 5. 안내 메시지 (💡로 시작)
        notice_match = re.search(r"(💡.*?)(?=\n\n|\Z)", final_answer, re.DOTALL)
        if notice_match:
            content_blocks.append({"type": "notice", "content": notice_match.group(1).strip()})
        
        # 파싱된 블록이 없으면, 전체 답변을 단일 텍스트 블록으로 반환
        if not content_blocks:
            return [{"type": "text", "content": final_answer}]
            
        return content_blocks
    
    def run_and_get_structured_output(self, user_query: str):
        """
        API용 실행 메서드 - 구조화된 JSON 반환
        기존 run() 메서드를 호출하되, 출력을 캡처하여 구조화된 형태로 반환합니다.
        """
        import io
        import sys
        
        # 표준 출력 캡처 준비
        old_stdout = sys.stdout
        sys.stdout = captured_output = io.StringIO()
        
        final_answer = None
        
        try:
            # 기존 run() 메서드의 로직을 재사용
            # run() 내부에서 최종 답변이 출력되므로 이를 캡처합니다
            
            # run() 메서드 실행
            self.run(user_query)
            
            # 출력된 내용 가져오기
            output = captured_output.getvalue()
            
            # [GMIS Agent v4] 이후의 내용을 최종 답변으로 추출
            if "[GMIS Agent v4]" in output:
                parts = output.split("[GMIS Agent v4]")
                if len(parts) > 1:
                    final_answer = parts[-1].strip()
            
            # 최종 답변이 없으면 전체 출력 사용
            if not final_answer:
                final_answer = output.strip()
            
            # 디버그/품질 경고 메시지 제거 (사용자에게 보이지 않아야 함)
            # 줄의 시작 부분에 있는 경우만 제거 (^ 사용)
            debug_patterns = [
                r'^\[품질 경고\].*?$',
                r'^\[DEBUG\].*?$',
                r'^\[경고\].*?$',
                r'^\[힌트\].*?$',
                r'^\[작업\].*?$',
                r'^\[사고\].*?$'
            ]
            import re
            for pattern in debug_patterns:
                final_answer = re.sub(pattern, '', final_answer, flags=re.MULTILINE)
            
            # 연속된 빈 줄 정리
            final_answer = re.sub(r'\n\n\n+', '\n\n', final_answer).strip()
            
            # API 응답 로깅 (디버깅용)
            logging.info(f"최종 답변 (파싱 전): {final_answer[:500]}...")  # 처음 500자만
                
        except Exception as e:
            logging.error(f"run_and_get_structured_output 오류: {e}", exc_info=True)
            final_answer = f"죄송합니다. 질문 처리 중 오류가 발생했습니다: {str(e)}"
        finally:
            # 표준 출력 복원
            sys.stdout = old_stdout
        
        # 마크다운 답변을 구조화된 형태로 파싱 시도
        try:
            structured_content = self._parse_final_answer_to_structured_format(final_answer)
            
            # 파싱 결과 로깅
            logging.info(f"파싱된 컨텐츠 블록 수: {len(structured_content)}")
            
            # 파싱 결과가 하나의 텍스트 블록뿐이고, 원본에 테이블이 있다면 파싱 실패로 간주
            if len(structured_content) == 1 and structured_content[0]['type'] == 'text':
                if '|' in final_answer and '---' in final_answer and '###' in final_answer:
                    logging.warning("테이블이 포함된 답변이지만 파싱 실패. 전체를 텍스트로 반환합니다.")
            
            return structured_content
            
        except Exception as parse_error:
            # 파싱 실패 시 전체 답변을 텍스트로 반환
            logging.error(f"파싱 실패: {parse_error}. 전체 답변을 텍스트로 반환합니다.")
            return [{"type": "text", "content": final_answer}]
    
    def _determine_level(self, user_query):
        """LLM을 활용한 전사 vs 사업별 레벨 판단 (개선)"""
        level_detection_prompt = f"""Analyze this user query: "{user_query}"

Determine if the user wants:
- CORPORATE: Company-wide totals (회사 전체, 연결/별도 기준, 분기/연간 합계)
  Keywords: 회사 비교, 전년 대비, 분기, 연간, 연결 기준, 별도 기준, 총매출, 전체
  Examples: "일렉트릭과 전선의 매출", "3분기 영업이익", "연결 기준 자산", "연간 매출"
  
- SEGMENT: Business unit/segment queries (사업 목록, 사업별 상세, 포트폴리오)
  Keywords: 사업별, 부문별, 제품군별, 포트폴리오, "어떤 사업", "사업 항목", "사업은", CIC별
  Examples: "어떤 사업이 있어?", "사업 항목은?", "사업별 매출", "CIC별로"

**IMPORTANT:** "어떤 사업", "사업 항목", "CIC별" → SEGMENT 레벨입니다!

Respond with ONLY one word: CORPORATE or SEGMENT"""

        try:
            print(f"[DEBUG] _determine_level 시작: {user_query[:50]}...")
            logging.debug(f"레벨 판단 질문: {user_query}")
            
            print(f"[DEBUG] Gemini 모델 생성 중 (레벨 판단)...")
            model_simple = genai.GenerativeModel('models/gemini-flash-lite-latest')
            
            print(f"[DEBUG] Gemini API 호출 중 (레벨 판단)...")
            response = model_simple.generate_content(
                level_detection_prompt,
                generation_config=genai.types.GenerationConfig(max_output_tokens=10, temperature=0.0)
            )
            
            print(f"[DEBUG] Gemini API 응답 수신 (레벨 판단)")
            level = response.text.strip().upper()
            
            if level not in ["CORPORATE", "SEGMENT"]:
                logging.warning(f"예상치 못한 레벨 응답: {level}, 기본값 사용")
                level = "CORPORATE"
            
            print(f"[분석] 쿼리 레벨: {level}")
            logging.info(f"레벨 판단 결과: {level}")
            return level
            
        except Exception as e:
            print(f"[경고] 레벨 판단 실패, 기본값(CORPORATE) 사용")
            print(f"  오류: {type(e).__name__}: {str(e)[:200]}")
            logging.warning(f"레벨 판단 실패: {e}", exc_info=True)
            return "CORPORATE"
    
    def _validate_query(self, query):
        """Cypher 쿼리 사전 검증 (v3 동일)"""
        warnings = []
        
        if "fs.year" in query or "fs.month" in query:
            warnings.append("⚠️ FinancialStatement에는 year/month 속성이 없습니다. fs.id CONTAINS 사용")
        
        if ("c.name =" in query or "company.name =" in query) and "Company" in query:
            warnings.append("⚠️ Company는 c.id로 매칭하세요. 예: {id: 'ELECTRIC'}")
        
        if "v.region" in query and "HAS_STATEMENT" in query and "FOR_SEGMENT" not in query:
            warnings.append("⚠️ CORPORATE 데이터에는 v.region 속성이 없습니다. 필터 제거 필요")
        
        return warnings
    
    def _validate_answer_format(self, answer):
        """GENEROUS 답변 전략 준수 여부 검증 (v3 동일)"""
        score = 0
        
        # 구조화된 섹션 확인
        if "###" in answer or "##" in answer:
            score += 1
        
        # 테이블 형식 확인
        if "|" in answer and "---" in answer:
            score += 1
        
        # 핵심 키워드 확인
        keywords = ["요약", "집계", "월별", "상세", "분석", "인사이트"]
        if any(kw in answer for kw in keywords):
            score += 1
        
        return score
    
    def _summarize_history(self):
        """[개선] 대화 히스토리 요약 (안전장치 + 자동 복구)"""
        try:
            print("[시스템] 대화 내용 요약 중...")
            logging.info(f"대화 히스토리 요약 시작 (현재: {len(self.chat_history)}개)")
            
            history_text = json.dumps(self.chat_history, ensure_ascii=False, indent=2)
            
            # 안전장치: 히스토리가 너무 크면 요약 시도하지 않음
            if len(history_text) > 20000:
                logging.warning(f"히스토리 크기 과다 ({len(history_text)}자). 요약 건너뛰고 초기화")
                raise ValueError("History text is too long to summarize safely.")
            
            summary_prompt = f"다음 대화를 3-5문장으로 요약:\n\n{history_text}\n\n핵심만 간결하게:"
            
            model_simple = genai.GenerativeModel('models/gemini-flash-lite-latest')
            response = model_simple.generate_content(
                summary_prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=500,
                    temperature=0.2
                )
            )
            
            # 응답 검증
            if not response.candidates or not response.candidates[0].content.parts:
                raise ValueError("LLM returned an empty response for summarization.")
            
            summary = response.text
            self.chat_history = [
                {"role": "system", "content": f"[이전 대화 요약] {summary}"}
            ]
            print("[완료] 요약 완료\n")
            logging.info("대화 히스토리 요약 완료")
            
        except Exception as e:
            print(f"[경고] 대화 히스토리 요약에 실패했습니다: {e}")
            logging.warning(f"히스토리 요약 실패: {e}", exc_info=True)
            
            # 상세 오류 스택 출력 (디버깅용)
            import traceback
            traceback.print_exc()
            
            # [핵심] 요약 실패 시 히스토리 초기화 (안전 복구)
            self.chat_history = []
            print("[시스템] 안정성을 위해 대화 히스토리를 초기화했습니다.\n")
            logging.warning("히스토리 요약 실패로 인한 자동 초기화")
    
    def _extract_entities(self, user_query):
        """사용자 질문에서 엔티티를 추출하고 NLU로 매핑"""
        query_lower = user_query.lower()
        
        # 회사 추출
        mentioned_companies = {}
        for alias, company_id in self.nlu['company'].items():
            if alias in query_lower:
                mentioned_companies[alias] = company_id
        
        # 계정 추출  
        mentioned_accounts = {}
        for alias, account_id in self.nlu['account'].items():
            if alias in query_lower:
                mentioned_accounts[alias] = account_id
        
        return {
            "companies": mentioned_companies,
            "accounts": mentioned_accounts
        }
    
    def run(self, user_query: str):
        """[개선] 상태 기반 의도 분류기 + 맞춤형 프롬프트"""
        
        # 전체 run() 메서드를 보호
        try:
            print(f"\n{'='*70}")
            print(f"[USER] {user_query}")
            print(f"{'='*70}")
            logging.info(f"사용자 질문: {user_query}")
            
            # [핵심 개선] 상태 기반 의도 분류
            print(f"[DEBUG] 후속 작업 여부 판단 중...")
            is_follow_up = False
            follow_up_keywords = ["그래프", "차트", "시각화", "csv", "파일", "저장", "다운로드"]
            
            if self.last_query_result and any(kw in user_query.lower() for kw in follow_up_keywords):
                is_follow_up = True
                print(f"[분석] 후속 작업 요청으로 판단")
                logging.info("후속 작업 요청으로 판단 (캐시 데이터 활용, 재조회 건너뛰기)")
            else:
                print(f"[분석] 새로운 데이터 조회 또는 질문으로 판단")
            
            # 엔티티 추출 및 NLU (새 조회 시에만 필요)
            if not is_follow_up:
                print(f"[DEBUG] 엔티티 추출 중...")
                entities = self._extract_entities(user_query)
                print(f"[DEBUG] 레벨 판단 중...")
                level = self._determine_level(user_query)
            else:
                entities = {}
                level = "CORPORATE"  # 임시값
            
            level_guide = {
                "CORPORATE": "\n[CONTEXT] Use CORPORATE level: (c:Company)-[:HAS_STATEMENT]->(fs)",
                "SEGMENT": "\n[CONTEXT] Use SEGMENT level: (c:Company)-[:HAS_ALL_SEGMENTS]->(bs)"
            }
            
            # NLU 컨텍스트 생성 (새 조회 시에만)
            priority_companies = ['전선', '전선(홍치제외)', 'ls전선', 'electric', 'ls일렉트릭', 
                                 'mnm', '엠앤엠', '앰엔엠', '엠트론', '앰트론',
                                 '전력cic', '전력', '자동화cic', '자동화']
            
            company_mapping_examples = {}
            for key in self.nlu['company'].keys():
                if any(p in key.lower() for p in priority_companies):
                    company_mapping_examples[key] = self.nlu['company'][key]
            
            for key, val in self.nlu['company'].items():
                if len(company_mapping_examples) >= 25:
                    break
                if key not in company_mapping_examples:
                    company_mapping_examples[key] = val
            
            # segment_to_main_account_mapping 정보 (config에서 동적으로)
            segment_account_mapping = self.config.get('segment_to_main_account_mapping', {})
            
            # 그룹 구성원 정보 (config에서 동적으로)
            group_members = {}
            for group_id, group_data in self.config.get('business_rules', {}).get('company_groups', {}).items():
                members = []
                for company_id, company_data in self.config.get('entities', {}).get('companies', {}).items():
                    if group_id in company_data.get('groups', []):
                        members.append(f"{company_id} ({company_data['official_name']})")
                group_members[group_data['name']] = members
            
            # Special Handling 규칙 (config에서 동적으로)
            special_rules = {}
            for rule_name, rule_data in self.config.get('business_rules', {}).get('special_handling', {}).items():
                if rule_name == 'use_adjusted_operating_income':
                    companies = rule_data.get('companies', [])
                    account_to_use = rule_data.get('account_to_use')
                    replaces = rule_data.get('replaces')
                    special_rules[rule_name] = {
                        "companies": companies,
                        "rule": f"For {', '.join(companies)}: Use '{account_to_use}' instead of '{replaces}'"
                    }
            
            # 추출된 엔티티 정보 (새 조회 시에만 필요)
            entity_context = ""
            if entities.get("companies"):
                entity_context += "\n**🎯 사용자가 언급한 회사 (NLU 매핑 완료):**\n"
                for alias, company_id in entities["companies"].items():
                    entity_context += f"- '{alias}' → Company ID: '{company_id}' (이 ID를 쿼리에 사용하세요!)\n"
            
            if entities.get("accounts"):
                entity_context += "\n**🎯 사용자가 언급한 계정 (NLU 매핑 완료):**\n"
                for alias, account_id in entities["accounts"].items():
                    entity_context += f"- '{alias}' → Account ID: '{account_id}' (이 ID를 쿼리에 사용하세요!)\n"
            
            # json.dumps 결과를 먼저 변수에 저장
            company_mapping_json = json.dumps(company_mapping_examples, ensure_ascii=False, indent=2)
            segment_mapping_json = json.dumps(segment_account_mapping, ensure_ascii=False, indent=2)
            group_members_json = json.dumps(group_members, ensure_ascii=False, indent=2)
            special_rules_json = json.dumps(special_rules, ensure_ascii=False, indent=2)
            
            # f-string 대신 문자열 연결 사용 (JSON 중괄호 충돌 방지)
            nlu_context = entity_context + """

**Available Entity Mappings (참고용):**

Company Name → ID:
""" + company_mapping_json + """

**Account ID 찾기:**
모든 계정은 Term 노드를 통해 조회하세요. 하드코딩 금지!

**Segment Account Mapping:**
""" + segment_mapping_json + """

**Company Groups:**
""" + group_members_json + """

**⚠️ Special Rules (특수 처리 규칙):**
""" + special_rules_json + """
→ 이 규칙을 반드시 적용하세요!

**💡 계정 ID 찾기 (비정형 표현 처리):**
사용자가 "자본총계", "총자본", "순자산" 등 다양하게 표현할 수 있습니다.
정확한 Account ID를 모르는 경우 **Term 노드를 활용**하세요:

Step 1: 사용자 표현으로 Account ID 찾기
```cypher
MATCH (t:Term {{value: '자본총계'}})<-[:ALSO_KNOWN_AS]-(a:Account)
RETURN a.id, a.name
```
→ Returns: {{'a.id': '자기자본_합계', 'a.name': '자기자본 합계'}}

Step 2: 찾은 a.id를 실제 데이터 쿼리에 사용

이 방법으로 **모든 계정의 별칭**을 자동으로 처리할 수 있습니다!

**🚨 CRITICAL: 연결/별도 처리 규칙 (일관성 필수!):**

**🎯 SIMPLE DEFAULT RULES (데이터 과부하 방지!):**

**Rule 1: 연결 우선 (별도는 명시 요청 시만)**
- **기본**: 연결(CONSOLIDATED) 데이터만 조회
- **예외**: 사용자가 "별도", "SEPARATE" 명시 시에만 별도 조회
- LS전선: 'LSCNS_C' (연결만)
- MnM, ELECTRIC 등: `WHERE c.id = 'MnM'`와 함께
  ```cypher
  MATCH (fs)-[:HAS_SCOPE]->(scope:StatementScope {id: 'CONSOLIDATED'})
  ```
  **주의**: `fs.scope` 속성은 없음! HAS_SCOPE 관계 사용!
- **답변 안내**: "💡 연결 재무제표 기준입니다. 별도 기준이 필요하시면 말씀해주세요."

**Rule 2: 조정영업이익 (Special Rules 참조)**
- 동적 컨텍스트의 **'Special Rules'** 섹션 확인
- 해당 회사가 조정영업이익 사용 회사인지 확인
- **기본**: 조정영업이익만 조회
- **예외**: 사용자가 "영업이익도" 또는 "둘 다" 명시 시
- **답변 안내**: "💡 [회사명]은 조정영업이익 기준입니다."

**Rule 3: 비교 요청 시만 확장**
- "비교", "차이", "둘 다" 명시 시:
  → 연결 + 별도 or 영업이익 + 조정영업이익
- 기본적으로는 **하나만** 조회 (속도 및 명확성 우선)

**Why?**
- 144개 레코드 → 48개 레코드 (70% 감소)
- Gemini 처리 부담 감소
- 빠르고 명확한 답변
- 필요 시 추가 조회 가능
"""
            
            # 히스토리는 Chat Session이 자동 관리 (수동 추가 불필요)
            
            # Tools (일반 지식 도구 추가)
            tools = [
                self.run_cypher_query,
                self.data_visualization,
                self.generate_downloadable_link,
                self.general_knowledge_qa
            ]
            
            # [핵심 개선] 상태에 따라 프롬프트 분기
            
            if is_follow_up:
                # [핵심 개선] 캐시 데이터의 실제 컬럼 목록 추출
                try:
                    if "columns" in self.last_query_result and self.last_query_result["columns"]:
                        available_columns = self.last_query_result["columns"]
                    else:
                        available_columns = list(pd.DataFrame(self.last_query_result["data"]).columns)
                except Exception as e:
                    logging.error(f"캐시 데이터 컬럼 추출 실패: {e}")
                    available_columns = []
                
                # Case 1: 후속 작업 - 기존 chat 객체 재사용
                current_prompt = f"""You are a focused tool-calling agent.

**Your ONLY task**: Fulfill this follow-up request using previously cached data.

User's request: "{user_query}"

**Available Data Columns in Cache**:
{available_columns}

**CRITICAL Instructions for Chart Generation**:
1. **DO NOT call run_cypher_query!** Use cached data only.

2. **For data_visualization**, use these parameters:
   ```python
   data_visualization(
       chart_type='line' or 'bar',
       title='차트 제목',
       x_col='p.month',  # Time axis
       y_cols=['v.value'],  # Value axis
       company_filter='회사명',  # IMPORTANT! Extract from user request
       account_filter='계정명'   # IMPORTANT! Extract from user request
   )
   ```

3. **Extract filters from user's request**:
   - "전선의 매출" → company_filter='전선', account_filter='매출'
   - "ELECTRIC 영업이익" → company_filter='ELECTRIC', account_filter='영업이익'
   - "MnM 자본" → company_filter='MnM', account_filter='자본'
   
4. **DO NOT try to find combined column names** like 'LS전선(연결) 매출액 합계'!
   The data has separate columns: c.name, a.name, v.value
   Use filters to select specific company and account.

5. After tool success: Simple confirmation only!

Example:
"요청하신 차트를 생성했습니다. 파일 경로: [path]"
"""
                logging.info(f"후속 작업 전용 프롬프트 사용. 사용 가능 컬럼: {available_columns}")
                
            else:
                # Case 2: 새 조회
                # [핵심 수정] chat 객체가 없으면 생성, 있으면 재사용
                if self.chat is None:
                    # 첫 대화 - 시스템 프롬프트로 초기화
                    logging.info("첫 대화 시작 - chat 객체 생성")
                    self.chat = self.model.start_chat(
                        history=[
                            {'role': 'user', 'parts': [self.system_prompt]},
                            {'role': 'model', 'parts': ["OK. I am GMIS Agent v4. Ready for user question."]}
                        ],
                        enable_automatic_function_calling=False
                    )
                else:
                    # 기존 chat 객체 재사용 (대화 맥락 유지)
                    logging.info(f"기존 chat 객체 재사용 (히스토리: {len(self.chat.history)}개 메시지)")
                
                current_prompt = f"{nlu_context}{level_guide.get(level, '')}\n\n[USER QUESTION]\n{user_query}"
                logging.info("새 데이터 조회 - 전체 시스템 프롬프트 사용")
            
            # [최종 수정] chat 변수 안전하게 참조
            # chat이 None이면 재생성 (히스토리 정리 후 시나리오)
            if self.chat is None:
                logging.warning("chat 객체가 None입니다. 재생성합니다.")
                print("[시스템] 새로운 대화 세션을 시작합니다.")
                self.chat = self.model.start_chat(
                    history=[
                        {'role': 'user', 'parts': [self.system_prompt]},
                        {'role': 'model', 'parts': ["OK. I am GMIS Agent v4. Ready for user question."]}
                    ],
                    enable_automatic_function_calling=False
                )
            
            chat = self.chat
            logging.info(f"chat 객체 사용 (히스토리: {len(chat.history) if hasattr(chat, 'history') else 'unknown'}개)")
            
            # [개선1] 파라미터화된 반복횟수 사용
            for iteration in range(self.max_iterations):
                logging.info(f"ReAct Iteration {iteration + 1}/{self.max_iterations}")
                print(f"[DEBUG] === Iteration {iteration + 1} 시작 ===")
                # [Turn X]는 사용자에게 보이지 않도록 logging으로 이동
                
                # [긴급 수정] Gemini API 호출을 try-except로 보호
                try:
                    print(f"[DEBUG] Gemini API 호출 중... (프롬프트 길이: {len(current_prompt)}자)")
                    logging.debug(f"현재 프롬프트 앞부분: {current_prompt[:200]}...")
                    
                    response = chat.send_message(
                        current_prompt,
                        tools=tools,
                        generation_config=genai.types.GenerationConfig(
                            max_output_tokens=6000,  # 답변 잘림 방지 (4000 → 6000)
                            temperature=0.1
                        )
                    )
                    print(f"[DEBUG] Gemini API 응답 수신 완료")
                    logging.debug("Gemini API 응답 성공")
                    
                except Exception as api_error:
                    print(f"\n[CRITICAL ERROR] Gemini API 호출 실패!")
                    print(f"오류 타입: {type(api_error).__name__}")
                    print(f"오류 메시지: {str(api_error)[:500]}")
                    logging.error(f"Gemini API 호출 실패: {api_error}", exc_info=True)
                    
                    # 사용자에게 오류 알림
                    print("\n[시스템] API 호출 중 오류가 발생했습니다. 질문을 다시 시도해주세요.")
                    return  # run 메서드 안전하게 종료
                
                # 응답 검증 (안전성 강화)
                if not response.candidates or not response.candidates[0].content.parts:
                    logging.warning("Gemini가 빈 응답을 반환했습니다. 다시 시도합니다.")
                    current_prompt = "Please provide your analysis or next action."
                    continue
                
                part = response.candidates[0].content.parts[0]
                
                # Function Call 확인
                if hasattr(part, 'function_call') and part.function_call:
                    function_call = part.function_call
                    tool_name = function_call.name
                    tool_args = dict(function_call.args)
                    
                    logging.info(f"Tool 호출: {tool_name}")
                    print(f"[사고] Tool '{tool_name}' 호출 필요")
                    
                    # 상태 메시지 (v3)
                    status_messages = {
                        "run_cypher_query": "[DB] 데이터베이스에서 정보를 조회하고 있습니다...",
                        "data_visualization": "[차트] 차트를 생성하고 있습니다...",
                        "generate_downloadable_link": "[파일] 파일을 생성하고 있습니다..."
                    }
                    if tool_name in status_messages:
                        print(f"[작업] {status_messages[tool_name]}")
                    
                    # Tool 실행
                    if tool_name == "run_cypher_query":
                        query_text = tool_args.get('query', '')
                        print(f"[Query]\n{query_text}\n")
                        
                        # 쿼리 사전 검증 (v3)
                        warnings = self._validate_query(query_text)
                        if warnings:
                            print("[검증]")
                            for warning in warnings:
                                print(f"  {warning}")
                            print()
                        
                        result = self.run_cypher_query(**tool_args)
                        
                        # [환각 방지] 데이터 없음 시 즉시 답변 생성 (LLM 우회)
                        if result.get("status") == "no_data":
                            print(f"[완료] 조회 결과 0건 (데이터 없음)")
                            logging.warning("쿼리 성공, 결과 0건 - 환각 방지 모드")
                            
                            # [핵심] LLM을 거치지 않고 직접 답변 생성 (환각 불가능!)
                            # 사용자 질문에서 요청한 항목 추출 (간단한 패턴)
                            requested_items = []
                            if "현금흐름" in user_query:
                                requested_items.append("현금흐름 관련 데이터")
                            if "EBITDA" in user_query.upper():
                                requested_items.append("EBITDA 데이터")
                            if "운전자본" in user_query:
                                requested_items.append("운전자본 관련 데이터")
                            if "ROE" in user_query.upper() or "ROA" in user_query.upper():
                                requested_items.append("ROE/ROA 데이터")
                            
                            items_text = ", ".join(requested_items) if requested_items else "요청하신 데이터"
                            
                            final_answer = f"""죄송합니다. {items_text}는 현재 Knowledge Graph에 존재하지 않습니다.

조회한 쿼리는 문법적으로 정확했으나, 해당 데이터가 재무제표에 포함되어 있지 않아 결과가 0건 반환되었습니다.

현재 조회 가능한 주요 항목:
- 재무 지표: 매출액, 영업이익, 당기순이익, 매출총이익
- 자산 항목: 자산총계, 유동자산, 비유동자산, 현금및현금성자산
- 부채 및 자본: 부채총계, 자기자본, 차입금
- 손익 항목: 영업외수익, 영업외비용, 법인세비용, 감가상각비

다른 항목으로 도와드릴까요?"""
                            
                            print(f"\n[GMIS Agent v4]")
                            print(f"\n{final_answer}\n")
                            
                            # 히스토리 업데이트
                            self.chat_history.append({"role": "user", "content": user_query})
                            self.chat_history.append({"role": "assistant", "content": final_answer})
                            
                            logging.info("데이터 없음 - 직접 답변 생성 (환각 차단)")
                            return  # 즉시 종료 (LLM에게 기회를 주지 않음!)
                        
                        if result.get("status") == "error":
                            print(f"[쿼리 오류] {result.get('error_type')}: {result.get('error')[:200]}")
                            if result.get("hints"):
                                for hint in result["hints"]:
                                    print(f"  - {hint}")
                            print("[시스템] LLM이 쿼리를 수정하여 재시도합니다...\n")
                            
                            # 재시도 안내 (v3)
                            retry_guidance = f"""
[CRITICAL ERROR] Previous Cypher query FAILED.

Error Type: {result.get('error_type')}
Error Message: {result.get('error')[:300]}

Hints:
{chr(10).join('- ' + h for h in result.get('hints', []))}

Please analyze the error carefully and generate a CORRECTED Cypher query.
Remember:
- Use c.id not c.name for Company
- Use fs.id CONTAINS 'YYYY' not fs.year
- Korean Account IDs: '매출액_합계', '영업이익'
- CORPORATE level: NO v.region filter
"""
                            # [개선: 명시적 재시도 안내]
                            logging.error(f"쿼리 실패, 재시도 유도: {result.get('error_type')}")
                            current_prompt = retry_guidance  # 명시적으로 수정 가이드 전달
                            continue
                            
                        else:
                            data_count = len(result.get('data', []))
                            print(f"[완료] {data_count}개 레코드 조회")
                            logging.info(f"쿼리 성공: {data_count}개 레코드")
                            
                            # 하이브리드 접근: 실제 데이터는 캐싱, 메타데이터만 히스토리
                            if data_count > 0:
                                # 실제 데이터 캐싱 (시각화/CSV 다운로드용)
                                self.last_query_result = {
                                    "data": result.get("data"),
                                    "columns": list(result['data'][0].keys()),
                                    "record_count": data_count,
                                    "query_text": user_query
                                }
                                logging.debug(f"데이터 캐싱 완료 ({data_count}개 레코드)")
                                
                                # 히스토리에는 메타데이터만 (토큰 효율성)
                                self.chat_history.append({
                                    "role": "system",
                                    "content": f"[쿼리 실행 완료] {data_count}개 레코드 조회 (컬럼: {', '.join(list(result['data'][0].keys()))})"
                                })

                            
                            # 샘플 데이터 구조화 출력
                            if data_count > 0:
                                sample = result['data'][0]
                                keys = list(sample.keys())
                                print(f"[컬럼] {', '.join(keys)}")
                                print(f"[샘플] {sample}\n")
                                
                                result['data_summary'] = {
                                    "record_count": data_count,
                                    "columns": keys,
                                    "first_record": sample
                                }
                    
                    elif tool_name == "data_visualization":
                        print("[작업] 차트를 생성하고 있습니다...")
                        result = self.data_visualization(**tool_args)
                        if result.get("status") == "success":
                            file_path = result['file_path']
                            print(f"[완료] 차트 저장: {file_path}\n")
                            # 간결한 확인 메시지만 요청
                            current_prompt = f"""The data_visualization tool successfully created a chart.
File path: {file_path}

Your ONLY job now is to inform the user that the chart has been created and provide the file path.
Do NOT generate a 4-part report. Just a simple, friendly confirmation message.
Example: "요청하신 차트를 생성했습니다. 파일 경로: {file_path}"
"""
                            continue
                        else:
                            print(f"[오류] {result.get('error')}\n")
                            current_prompt = f"Chart generation failed: {result.get('error')}. Inform the user."
                            continue
                            
                    elif tool_name == "generate_downloadable_link":
                        print("[작업] 파일을 생성하고 있습니다...")
                        result = self.generate_downloadable_link(**tool_args)
                        if result.get("status") == "success":
                            file_path = result['file_path']
                            print(f"[완료] 파일 저장: {file_path}\n")
                            # 간결한 확인 메시지만 요청
                            current_prompt = f"""File successfully saved.
Path: {file_path}

Inform the user that the file has been created. Simple confirmation only.
"""
                            continue
                        else:
                            print(f"[오류] {result.get('error')}\n")
                            current_prompt = f"File creation failed: {result.get('error')}. Inform the user."
                            continue
                    
                    elif tool_name == "general_knowledge_qa":
                        print("[작업] 재무/경영 지식을 검색하고 있습니다...")
                        question = tool_args.get("question", user_query)
                        knowledge_answer = self.general_knowledge_qa(question)
                        result = {"status": "success", "answer": knowledge_answer}
                        print(f"[완료] 지식 답변 생성\n")
                        # 지식 답변은 그 자체가 최종 답변
                        current_prompt = f"""General knowledge answer retrieved:

{knowledge_answer}

Present this information to the user in a clear and helpful way. No special format needed.
"""
                        continue
                    
                    else:
                        result = {"error": f"Unknown tool: {tool_name}"}
                        logging.error(f"알 수 없는 도구: {tool_name}")
                    
                    # [핵심 개선] Python 사전 집계: LLM 부담 감소
                    if tool_name == "run_cypher_query" and result.get("status") == "success" and result.get("data"):
                        print("[DEBUG] 데이터 사전 집계 시작...")
                        
                        try:
                            # [안정성 개선] 전체 데이터 처리를 try-except로 보호
                            df = pd.DataFrame(result["data"])
                            
                            # 데이터프레임 정보 로깅
                            record_count = len(df)
                            mem_usage = df.memory_usage(deep=True).sum() / (1024 * 1024)  # MB 단위
                            columns = list(df.columns)
                            print(f"[DEBUG] DataFrame 생성 완료. 레코드: {record_count}개, 메모리: {mem_usage:.2f} MB")
                            print(f"[DEBUG] 컬럼: {columns}")
                            logging.info(f"Python에서 {record_count}개 레코드 사전 집계 시작 (메모리: {mem_usage:.2f} MB, 컬럼: {columns})")
                            
                            # 빈 데이터 체크
                            if record_count == 0:
                                print("[DEBUG] 레코드가 없어 사전 집계 건너뜀.")
                                logging.warning("쿼리 결과가 비어있음")
                                current_prompt = "Query returned no data. Please inform the user that no data was found."
                                continue
                            
                            # 메모리 임계값 체크 (100MB 이상이면 경고)
                            if mem_usage > 100:
                                logging.warning(f"대용량 데이터 처리 중: {mem_usage:.2f} MB")
                                print(f"[경고] 대용량 데이터 처리 중: {mem_usage:.2f} MB")
                            
                            # [핵심 수정] 데이터 타입 판단 (CORPORATE vs SEGMENT)
                            is_corporate_data = 'c.name' in columns and 'a.name' in columns
                            is_segment_data = 'bs.name' in columns or '소속' in columns or '사업목록' in columns
                            
                            if is_segment_data and not is_corporate_data:
                                # SEGMENT 데이터는 집계하지 않고 바로 전달
                                print("[DEBUG] SEGMENT 데이터 감지 - 집계 건너뜀")
                                logging.info("SEGMENT 레벨 데이터 - 사전 집계 생략")
                                
                                # 간단한 CSV로 변환만
                                data_csv = df.to_csv(index=False)
                                tool_result_text = f"""
[SEGMENT Data - No Pre-processing]

The query returned SEGMENT-level data (business units/items).
This data structure is different from CORPORATE data.

Raw data (CSV format):
```csv
{data_csv}
```

Please present this data to the user in a clear, organized way.
For list queries (사업 목록), use bullet points.
For numerical queries, use tables.
"""
                                logging.info("SEGMENT 데이터 전달 준비 완료")
                                current_prompt = tool_result_text
                                continue
                            
                            # 1. 지능적 연간 요약 데이터 집계 (CORPORATE 전용!)
                            print("[DEBUG] 1. 연간 요약 집계 시작 (CORPORATE 데이터)...")
                        except Exception as df_error:
                            print(f"[CRITICAL] DataFrame 생성 실패: {df_error}")
                            logging.error(f"DataFrame 생성 실패: {df_error}", exc_info=True)
                            current_prompt = f"Failed to process query results: {df_error}. Please inform the user."
                            continue
                        
                        # 요약 집계 (CORPORATE 전용)
                        try:
                            # config에서 계정별 집계 규칙 가져오기
                            account_agg_map = {
                                data['official_name']: data.get('aggregation', 'SUM')
                                for _, data in self.config.get('entities', {}).get('accounts', {}).items()
                            }
                            
                            # 집계 규칙 매핑
                            df['aggregation_type'] = df['a.name'].map(account_agg_map)
                            
                            # SUM과 LAST 데이터 분리
                            df_sum = df[df['aggregation_type'] == 'SUM'].copy() if 'SUM' in df['aggregation_type'].values else pd.DataFrame()
                            df_last = df[df['aggregation_type'] == 'LAST'].copy() if 'LAST' in df['aggregation_type'].values else pd.DataFrame()
                            
                            summary_parts = []
                            
                            # SUM 항목 집계 (IS 계정: 매출, 영업이익 등)
                            if not df_sum.empty:
                                group_cols = [col for col in ['c.name', 'a.name', 'statement_scope'] if col in df_sum.columns]
                                summary_sum = df_sum.groupby(group_cols)['v.value'].sum().reset_index()
                                summary_parts.append(summary_sum)
                                logging.info(f"SUM 집계 완료: {len(df_sum)}개 레코드")
                            
                            # LAST 항목 집계 (BS 계정: 자산, 부채, 자기자본 등)
                            if not df_last.empty:
                                # 월 기준으로 정렬 후 그룹별 마지막 값 선택
                                group_cols = [col for col in ['c.name', 'a.name', 'statement_scope'] if col in df_last.columns]
                                summary_last = df_last.sort_values('p.month').groupby(group_cols, as_index=False).last()
                                summary_last = summary_last[group_cols + ['v.value']]
                                summary_parts.append(summary_last)
                                logging.info(f"LAST 집계 완료: {len(df_last)}개 레코드 → 기말값")
                            
                            # 결과 병합
                            if summary_parts:
                                summary_df = pd.concat(summary_parts, ignore_index=True)
                                summary_df['v.value'] = summary_df['v.value'].apply(lambda x: f"{x:,.0f}")
                                summary_md = summary_df.to_markdown(index=False)
                                logging.info("지능적 집계 완료 (SUM/LAST 규칙)")
                            else:
                                summary_md = "집계 불가"
                            print("[DEBUG] 1. 연간 요약 집계 완료.")
                        except Exception as e:
                            print(f"[ERROR] 요약 집계 실패: {e}")
                            logging.warning(f"요약 집계 실패: {e}", exc_info=True)
                            summary_md = str(df.head())
                        
                        # 2. 월별 상세 데이터 (PIVOT 시도)
                        print("[DEBUG] 2. 월별 상세 데이터 가공 시작...")
                        try:
                            if len(df['c.name'].unique()) > 1:
                                # 다중 회사: PIVOT 테이블
                                pivot_df = df.pivot_table(
                                    index='p.month', 
                                    columns=['c.name', 'a.name'], 
                                    values='v.value', 
                                    aggfunc='sum'
                                )
                                monthly_csv = pivot_df.to_csv()
                                monthly_format = "PIVOT_CSV"
                            else:
                                # 단일 회사: 일반 CSV
                                monthly_csv = df.to_csv(index=False)
                                monthly_format = "CSV"
                            print("[DEBUG] 2. 월별 상세 데이터 가공 완료.")
                        except Exception as e:
                            print(f"[ERROR] 월별 데이터 가공 실패: {e}")
                            logging.warning(f"PIVOT 실패: {e}, 일반 CSV 사용", exc_info=True)
                            monthly_csv = df.to_csv(index=False)
                            monthly_format = "CSV"
                        
                        # 3. LLM에게 가공된 데이터 전달
                        print("[DEBUG] 3. LLM 프롬프트 생성 시작...")
                        tool_result_text = f"""
[Pre-processed Data]

**Annual Summary (Pre-aggregated):**
Use this for sections 1 and 2 (요약, 집계 데이터):
```markdown
{summary_md}
```

**Monthly Details ({monthly_format}):**
Use this for section 3 (월별 상세):
```csv
{monthly_csv}
```

These are pre-calculated by Python with correct SUM/LAST rules.
Now generate your COMPLETE 4-part answer:
1. 요약
2. 집계 데이터
3. 월별 상세
4. 인사이트 + 💡 기본값 안내
"""
                        print("[DEBUG] 3. LLM 프롬프트 생성 완료.")
                        logging.info(f"사전 집계 완료: 요약 + {monthly_format}")
                        current_prompt = tool_result_text
                        continue
                
                # 최종 답변
                elif hasattr(part, 'text') and part.text:
                    final_answer = part.text
                    
                    # 배치 테스트 모드: 요약과 인사이트 제거 (속도 최적화)
                    if self._batch_test_mode:
                        import re
                        # 섹션 1 (요약) 제거
                        final_answer = re.sub(r'###\s*1\.\s*요약.*?(?=###|$)', '', final_answer, flags=re.DOTALL)
                        # 섹션 4 (인사이트) 제거  
                        final_answer = re.sub(r'###\s*4\.\s*인사이트.*?(?=###|$)', '', final_answer, flags=re.DOTALL)
                        # 💡 안내 제거
                        final_answer = re.sub(r'💡.*?(?=\n|$)', '', final_answer, flags=re.MULTILINE)
                        # 공백 정리
                        final_answer = re.sub(r'\n\n\n+', '\n\n', final_answer).strip()
                    
                    # 답변 품질 검증
                    quality_score = self._validate_answer_format(final_answer)
                    
                    print(f"\n[GMIS Agent v4]")
                    if not self._batch_test_mode and quality_score < 2:
                        print("[품질 경고] 답변이 GENEROUS 전략을 따르지 않을 수 있습니다.")
                        logging.warning("답변 품질 점수 낮음")
                    print(f"\n{final_answer}\n")
                    
                    # 히스토리 업데이트 (메타데이터용 - 실제 대화는 chat 객체가 관리)
                    self.chat_history.append({"role": "user", "content": user_query})
                    self.chat_history.append({"role": "assistant", "content": final_answer})
                    
                    # [긴급 수정] chat 히스토리 관리 - 완화된 기준
                    # Gemini chat 히스토리 길이 체크
                    if self.chat and hasattr(self.chat, 'history'):
                        chat_history_count = len(self.chat.history)
                        logging.info(f"현재 chat 히스토리: {chat_history_count}개 메시지")
                        
                        # 30개 메시지 (15턴) 초과 시만 재초기화 (완화!)
                        if chat_history_count > 30:
                            logging.warning(f"chat 히스토리 {chat_history_count}개 초과 → 재초기화")
                            print(f"[시스템] 대화가 길어져 히스토리를 정리합니다...")
                            # [안전한 재초기화] 바로 None으로 하지 않고 명시적으로 처리
                            try:
                                self.chat = self.model.start_chat(
                                    history=[
                                        {'role': 'user', 'parts': [self.system_prompt]},
                                        {'role': 'model', 'parts': ["OK. I am GMIS Agent v4. Ready."]}
                                    ],
                                    enable_automatic_function_calling=False
                                )
                                self.chat_history = self.chat_history[-6:]  # 최근 3턴만 유지
                                logging.info("chat 객체 재생성 완료")
                            except Exception as reset_error:
                                logging.error(f"chat 재생성 실패: {reset_error}")
                                # 실패하면 그냥 유지
                    
                    logging.info("최종 답변 생성 완료")
                    return
                
                else:
                    print("[경고] 예상치 못한 응답 형식")
                    logging.warning("예상치 못한 응답 형식")
                    break
            
            print("[경고] 최대 반복 횟수 도달")
            logging.warning(f"최대 반복 횟수({self.max_iterations}) 도달")
            print("[경고] 최대 반복 횟수에 도달했습니다. 답변을 생성하지 못했습니다.")
            
        except Exception as e:
            print(f"\n[ERROR] Agent 실행 중 오류: {e}")
            logging.error(f"Agent 실행 오류: {e}", exc_info=True)
            import traceback
            traceback.print_exc()
            # 오류를 다시 던지지 않음 (main의 except에서 처리)
    
    def close(self):
        """리소스 정리"""
        if self.driver:
            self.driver.close()
            print("\n[연결종료] Neo4j 연결 종료")
            logging.info("Neo4j 연결 종료")

if __name__ == "__main__":
    print("="*70)
    print("  GMIS Agent v4 Final - Knowledge Graph v5")
    print("="*70)
    print()
    
    agent = None
    try:
        agent = GmisAgentV4()
        print("대화를 시작합니다. (종료: 'exit')\n")
        
        question_count = 0  # 질문 카운터
        
        while True:
            try:
                # [긴급 수정] 입력 받기 전 상태 안정화
                question_count += 1
                logging.info(f"질문 {question_count}번 대기 중...")
                
                # [추가] 메모리 강제 정리 (Python GC)
                import gc
                gc.collect()
                logging.info("가비지 컬렉션 완료")
                
                print(f"\n[YOU] ", end='', flush=True)  # flush 추가
                
                try:
                    import sys
                    # Windows 표준 입력 버퍼 플러시
                    if hasattr(sys.stdin, 'flush'):
                        try:
                            sys.stdin.flush()
                        except:
                            pass
                    
                    user_input = sys.stdin.readline().strip()  # input() 대신 readline() 사용
                    
                    if not user_input:
                        continue
                        
                except (EOFError, KeyboardInterrupt) as input_error:
                    print(f"\n[입력 중단] {type(input_error).__name__}")
                    logging.warning(f"입력 중단: {input_error}")
                    break
                except Exception as input_error:
                    print(f"\n[입력 오류] {type(input_error).__name__}: {input_error}")
                    logging.error(f"input() 오류: {input_error}", exc_info=True)
                    import traceback
                    traceback.print_exc()
                    continue
                
                # [추가] 입력 성공 로그
                logging.info(f"입력 수신 완료: {user_input[:50]}...")
                print(f"[DEBUG] 입력 수신 완료: '{user_input}'")
                
                if user_input.lower() in ['exit', 'quit', '종료']:
                    logging.info("사용자 종료 요청")
                    break
                if not user_input.strip():
                    continue
                
                # run() 호출 전 안전 체크
                print(f"[DEBUG] run() 메서드 호출 준비...")
                logging.info(f"run() 호출 시작: {user_input}")
                
                # run() 호출 전체를 보호
                try:
                    agent.run(user_input)
                    print(f"[DEBUG] run() 메서드 정상 완료")
                    logging.info("run() 정상 완료")
                except Exception as run_error:
                    print(f"\n[오류 발생] 질문 처리 중 오류: {run_error}")
                    print(f"오류 타입: {type(run_error).__name__}")
                    logging.error(f"run() 실행 오류: {run_error}", exc_info=True)
                    import traceback
                    traceback.print_exc()
                    print("\n대화를 계속하시겠습니까? (계속하려면 Enter, 종료하려면 'exit')")
                    
                    try:
                        continue_choice = input()
                        if continue_choice.lower() in ['exit', 'quit', '종료']:
                            break
                    except:
                        print("입력 오류. 프로그램을 종료합니다.")
                        break
                
                # [안전장치] 메모리 정리
                if question_count % 3 == 0:
                    logging.info(f"{question_count}번째 질문 완료 - 메모리 정리 권장")
                    print(f"[시스템] {question_count}번의 질문을 처리했습니다.")
                
            except Exception as loop_error:
                print(f"\n[루프 오류] 예상치 못한 오류: {loop_error}")
                logging.error(f"while 루프 오류: {loop_error}", exc_info=True)
                import traceback
                traceback.print_exc()
                break
                
    except KeyboardInterrupt:
        print("\n\n사용자 중단")
    except Exception as e:
        logging.critical(f"치명적 오류: {e}", exc_info=True)
        print(f"\n[치명적 오류] {e}")
        import traceback
        traceback.print_exc()
    finally:
        if agent:
            agent.close()
        print("\nAgent v4를 종료합니다.")
        input("Press Enter to close...")  # 터미널 유지