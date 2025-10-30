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
# 콘솔에만 로그 출력 (파일 생성 안 함)
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s][%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler()  # 콘솔 출력만
    ]
)

# matplotlib 로그 레벨을 WARNING으로 설정 (폰트 검색 로그 차단!)
logging.getLogger('matplotlib').setLevel(logging.WARNING)
logging.getLogger('matplotlib.font_manager').setLevel(logging.WARNING)
logging.getLogger('PIL').setLevel(logging.WARNING)

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
        
        # 마지막 차트 데이터 캐싱 (파싱 시 사용)
        self.last_chart_data = None
        
        # 배치 테스트 모드 (기본: False)
        self._batch_test_mode = False
        
        print(f"[OK] Agent v4 초기화 완료 (모델: {self.model_name})")
    
    # [개선3] with 구문 지원
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def _load_prompt_template(self, template_path):
        """system_prompt.json에서 특정 프롬프트 템플릿을 로드"""
        try:
            prompt_json_path = os.path.join(self.base_dir, 'system_prompt.json')
            with open(prompt_json_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Nested path 처리 (예: "internal_prompts.no_data_response.template")
            keys = template_path.split('.')
            value = config
            for key in keys:
                value = value[key]
            return value
        except Exception as e:
            logging.warning(f"Failed to load prompt template '{template_path}': {e}")
            return None
    
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
            "analysis_type": {},
            "comparison_type": {}  # 새로 추가: 계획-실적 비교
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
        
        # 비교 타입 (계획-실적)
        plan_vs_actual = self.config.get('relationships', {}).get('contextual_relationships', {}).get('PLAN_VS_ACTUAL', {})
        if plan_vs_actual:
            for alias in plan_vs_actual.get('aliases', []):
                if alias:
                    nlu["comparison_type"][alias.lower()] = "PLAN_VS_ACTUAL"
        
        return nlu
    
    def _create_system_prompt(self):
        """GDB의 지능을 100% 활용하는 시스템 프롬프트"""
        # 구조화된 JSON 파일에서 System Prompt 구성
        prompt_json_path = os.path.join(self.base_dir, 'system_prompt.json')
        try:
            with open(prompt_json_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # JSON 구조를 텍스트 프롬프트로 변환
            prompt = f"""{config['role']}

**Core Principles:**
{chr(10).join(f"- {p}" for p in config['core_principles'])}

**🚨 Multi-Part Query: 2-Tier Decision Tree 🚨**

**TIER 1: IMPOSSIBLE Query (Must Ask User to Split)**
{config['query_classification']['tier1_impossible']['description']}

Criteria:
{chr(10).join(f"- {c}" for c in config['query_classification']['tier1_impossible']['criteria'])}

Your Action: {config['query_classification']['tier1_impossible']['action']}

Response Template:
```
{config['query_classification']['tier1_impossible']['response_template']}
```

**TIER 2: SOLVABLE Query (Execute Immediately)**
{config['query_classification']['tier2_solvable']['description']}

Examples:
{chr(10).join(f"✅ {ex}" for ex in config['query_classification']['tier2_solvable']['examples'])}

Action: {config['query_classification']['tier2_solvable']['action']}

**🎯 Primary Decision Flow:**

1. **Follow-up Action?**
   Keywords: {', '.join(config['request_types']['follow_up']['keywords'])}
   Action: {config['request_types']['follow_up']['action']}

2. **Data Query?**
   Keywords: {', '.join(config['request_types']['data_query']['keywords'])}
   Action: {config['request_types']['data_query']['action']}

3. **Knowledge Question?**
   Keywords: {', '.join(config['request_types']['knowledge_question']['keywords'])}
   Action: {config['request_types']['knowledge_question']['action']}

**💎 ANSWER FORMAT:**

For DATA QUERIES - 4-Part Report:
{chr(10).join(f"{i+1}. {sec['name']}: {', '.join(sec['requirements'])}" for i, sec in enumerate(config['answer_format']['data_queries']['sections']))}

Number Format:
- Summary: {config['answer_format']['data_queries']['number_format']['summary']}
- Table (>1T): {config['answer_format']['data_queries']['number_format']['table_over_1trillion']}
- Table (<1T): {config['answer_format']['data_queries']['number_format']['table_under_1trillion']}

For KNOWLEDGE QUESTIONS:
{config['answer_format']['knowledge_questions']['format']}

**📋 QUERY PATTERNS:**

**CORPORATE Level:**
{config['query_patterns']['corporate']['description']}
Critical Notes:
{chr(10).join(f"- {note}" for note in config['query_patterns']['corporate']['critical_notes'])}

Basic Query Template:
```cypher
{config['query_patterns']['corporate']['basic_monthly']}
```

**SEGMENT Level:**
{config['query_patterns']['segment']['description']}
Critical Rules:
{chr(10).join(f"- {rule}" for rule in config['query_patterns']['segment']['critical_rules'])}

**🔍 Pattern 1: 사업 목록 조회 (IMPORTANT - DATA QUERY!)**
{config['query_patterns']['segment']['list_segments_pattern']['description']}

Keywords: {', '.join(config['query_patterns']['segment']['list_segments_pattern']['keywords'])}

Examples:
{chr(10).join(f"- {ex}" for ex in config['query_patterns']['segment']['list_segments_pattern']['examples'])}

Query Template:
```cypher
{config['query_patterns']['segment']['list_segments_pattern']['query']}
```

For CIC:
```cypher
{config['query_patterns']['segment']['list_segments_pattern']['cic_query']}
```

**🔍 Pattern 2: 개별 사업 데이터 조회**
Basic Query:
```cypher
{config['query_patterns']['segment']['basic_query']}
```

**🔍 Pattern 3: 국내/해외 매출액 조회 (CRITICAL!):**
{config['query_patterns']['segment']['domestic_international']['description']}
Key Points:
{chr(10).join(f"- {p}" for p in config['query_patterns']['segment']['domestic_international']['key_points'])}

Query Template:
```cypher
{config['query_patterns']['segment']['domestic_international']['query']}
```

Account Mapping:
{chr(10).join(f"- {k} → {v}" for k, v in config['query_patterns']['segment']['account_mapping'].items())}

Data Structure:
{chr(10).join(f"- {k}: {v}" for k, v in config['query_patterns']['segment']['data_structure'].items())}

Warnings:
{chr(10).join(f"- {w}" for w in config['query_patterns']['segment']['warnings'])}

For No Data:
```
{config['query_patterns']['segment']['no_data_guidance']}
```

**🚨 SPECIAL RULES:**

Group Queries: {config['special_rules']['group_queries']['description']}
Pattern: {config['special_rules']['group_queries']['pattern']}

Special Accounts:
{chr(10).join(f"- {k}: {v}" for k, v in config['special_rules']['special_accounts'].items())}

**📊 DATA AVAILABILITY:**
- CORPORATE: Years {config['data_availability']['corporate']['years']}, No region property
- SEGMENT: Primary year {config['data_availability']['segment']['primary_year']}, Has region: {config['data_availability']['segment']['regions']}

**🔧 TOOLS:**
{chr(10).join(f"- {tool['name']}: {tool['description']}" for tool in config['tools'])}

**💡 MANDATORY CLARIFICATIONS:**
- If 조정영업이익 used: {config['mandatory_clarifications']['조정영업이익_used']}
- If CONSOLIDATED default: {config['mandatory_clarifications']['consolidated_default']}

**Config Integration:**
{chr(10).join(f"- {item}" for item in config['config_integration']['items'])}
"""
            return prompt
            
        except FileNotFoundError:
            logging.warning(f"system_prompt.json not found at {prompt_json_path}, using fallback prompt")
            return """You are 'GMIS Agent v4', a financial expert navigating a powerful Knowledge Graph (v5).

**Core Principle: ASK THE GRAPH. DO NOT ASSUME.**

(Full prompt not loaded - check system_prompt.json)"""
        except Exception as e:
            logging.error(f"Error loading system_prompt.json: {e}", exc_info=True)
            return """You are 'GMIS Agent v4', a financial expert navigating a powerful Knowledge Graph (v5).

**Core Principle: ASK THE GRAPH. DO NOT ASSUME.**

(Error loading system_prompt.json)"""
    
    # === Tools (v3 기능 유지 + 개선) ===
    
    def run_cypher_query(self, query: str) -> dict:
        """Neo4j Cypher 쿼리 실행 (환각 방지 강화)"""
        
        # 디버깅: 실제 실행되는 쿼리 출력 (logging 사용 - stdout 캡처의 영향 안 받음)
        logging.info("="*80)
        logging.info("Executing Cypher Query:")
        logging.info(query)
        logging.info("="*80)
        
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
    
    def data_visualization(self, data: list = None, chart_type: str = 'bar', title: str = '', x_col: str = '', y_cols: list = None, company_filter: str = None, account_filter: str = None, year_filter: int = None, show_trendline: bool = False, return_base64: bool = True) -> dict:
        """
        차트 생성 및 PNG 저장 (필터링 기능 강화)
        - company_filter: 특정 회사 데이터만 필터링
        - account_filter: 특정 계정 데이터만 필터링
        - year_filter: 특정 연도 데이터만 필터링 (예: 2022, 2023)
        - return_base64: True면 base64 인코딩된 이미지 반환 (API용)
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
            
            if year_filter:
                # 연도 필터링
                if 'p.year' in df.columns:
                    df = df[df['p.year'] == year_filter]
                    print(f"[DEBUG] 연도 필터({year_filter}) 적용 후: {len(df)}개 레코드")
                    logging.info(f"연도 필터 적용: {year_filter}년만")

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
            
            # [전문 차트] Seaborn 스타일 + 고급 설정
            import seaborn as sns
            sns.set_style("whitegrid", {
                'axes.grid': True,
                'grid.color': '#e5e7eb',
                'grid.linewidth': 0.8,
                'axes.edgecolor': '#9ca3af',
                'axes.linewidth': 1.2
            })
            
            plt.rcParams['font.family'] = 'sans-serif'
            plt.rcParams['axes.unicode_minus'] = False
            
            fig, ax = plt.subplots(figsize=(16, 9), facecolor='white', dpi=120)
            ax.set_facecolor('#fafafa')
            
            # 값을 억원 단위로 변환 (가독성 향상)
            def convert_to_eok(value):
                """값을 억원 단위로 변환"""
                return value / 100000000 if pd.notna(value) else 0
            
            # 한글-영문 변환 함수
            def translate_to_english(text):
                """한글 재무 용어를 영문으로 변환"""
                translations = {
                    # 회사명
                    'LS전선': 'LS Cable',
                    'LS일렉트릭': 'LS ELECTRIC',
                    'LS MnM': 'LS MnM',
                    'LS엠앤엠': 'LS MnM',
                    # 재무 계정
                    '매출액 합계': 'Total Revenue',
                    '매출액': 'Revenue',
                    '영업이익': 'Operating Profit',
                    '조정영업이익': 'Adjusted OP',
                    '당기순이익': 'Net Income',
                    '자산총계': 'Total Assets',
                    '부채총계': 'Total Liabilities',
                    '자기자본': 'Equity',
                    '매출총이익': 'Gross Profit',
                    '세전이익': 'Pre-tax Income',
                    # 일반 용어
                    '월별': 'Monthly',
                    '년': ' ',
                    '의': ' ',
                    '연결': 'Consolidated',
                    '별도': 'Separate'
                }
                result = text
                for kr, en in translations.items():
                    result = result.replace(kr, en)
                # 여러 공백을 하나로
                import re
                result = re.sub(r'\s+', ' ', result).strip()
                return result
            
            # [세련된 색상 팔레트] Desaturated professional palette
            # Seaborn의 'muted' 팔레트 사용 (차분하고 전문적)
            colors = sns.color_palette("muted", 10).as_hex()
            
            # [핵심 수정 2] y_cols를 동적으로 설정하여 여러 계정 그리기 지원
            if not y_cols or y_cols == ['v.value']:
                # y_cols가 지정되지 않았으면, 필터링된 데이터의 모든 계정을 그림
                if 'a.name' in df.columns and 'v.value' in df.columns:
                    unique_accounts = df['a.name'].unique()
                    for idx, account in enumerate(unique_accounts):
                        subset = df[df['a.name'] == account].copy()
                        subset['v.value_eok'] = subset['v.value'].apply(convert_to_eok)
                        color = colors[idx % len(colors)]
                        account_en = translate_to_english(account)
                        
                        if chart_type == 'line':
                            # [세련된 스타일] 적당한 굵기의 라인
                            line = ax.plot(subset[x_col], subset['v.value_eok'], 
                                   marker='o', label=account_en, linewidth=1.5, 
                                   markersize=7, color=color, alpha=0.85,
                                   markeredgecolor='white', markeredgewidth=1.2)
                            # [개선된 값 표시] 흰색 배경 + 검은 테두리로 가독성 극대화
                            for x, y in zip(subset[x_col], subset['v.value_eok']):
                                ax.text(x, y, f'{int(y)}', 
                                       ha='center', va='bottom',
                                       fontsize=10,
                                       color='#000000',
                                       fontweight='bold',
                                       bbox=dict(facecolor='white', 
                                               edgecolor='#d1d5db',
                                               boxstyle='round,pad=0.4',
                                               alpha=0.95))
                        elif chart_type == 'bar':
                            bars = ax.bar(subset[x_col], subset['v.value_eok'], 
                                  label=account_en, alpha=0.9, color=color, 
                                  edgecolor='white', linewidth=2)
                            # [개선된 값 표시] 흰색 배경으로 가독성 향상
                            for bar in bars:
                                height = bar.get_height()
                                ax.text(bar.get_x() + bar.get_width() / 2, height,
                                       f'{int(height)}',
                                       ha='center', va='bottom',
                                       fontsize=10,
                                       color='#000000',
                                       fontweight='bold',
                                       bbox=dict(facecolor='white', 
                                               edgecolor='#d1d5db',
                                               boxstyle='round,pad=0.4',
                                               alpha=0.95))
                    if len(unique_accounts) > 1:
                        ax.legend(fontsize=12, frameon=True, shadow=False, 
                                 fancybox=False, loc='upper left',
                                 edgecolor='#d1d5db', facecolor='white',
                                 framealpha=0.95)
                else:
                    # 기본 단순 차트
                    df['v.value_eok'] = df['v.value'].apply(convert_to_eok)
                    if chart_type == 'line':
                        ax.plot(df[x_col], df['v.value_eok'], marker='o', 
                               linewidth=1.5, markersize=7, color=colors[0], alpha=0.85,
                               markeredgecolor='white', markeredgewidth=1.2)
                        # [개선된 값 표시]
                        for x, y in zip(df[x_col], df['v.value_eok']):
                            ax.text(x, y, f'{int(y)}', 
                                   ha='center', va='bottom',
                                   fontsize=10,
                                   color='#000000',
                                   fontweight='bold',
                                   bbox=dict(facecolor='white', 
                                           edgecolor='#d1d5db',
                                           boxstyle='round,pad=0.4',
                                           alpha=0.95))
                    elif chart_type == 'bar':
                        bars = ax.bar(df[x_col], df['v.value_eok'], 
                              alpha=0.9, color=colors[0], edgecolor='white', linewidth=2)
                        # [개선된 값 표시]
                        for bar in bars:
                            height = bar.get_height()
                            ax.text(bar.get_x() + bar.get_width() / 2, height,
                                   f'{int(height)}',
                                   ha='center', va='bottom',
                                   fontsize=10,
                                   color='#000000',
                                   fontweight='bold',
                                   bbox=dict(facecolor='white', 
                                           edgecolor='#d1d5db',
                                           boxstyle='round,pad=0.4',
                                           alpha=0.95))
            else:
                # y_cols가 명시적으로 주어지면 기존 방식대로 그림
                for idx, y_col in enumerate(y_cols):
                    color = colors[idx % len(colors)]
                    y_col_en = translate_to_english(y_col)
                    
                    if chart_type == 'line':
                        ax.plot(df[x_col], df[y_col], marker='o', label=y_col_en,
                               linewidth=1.5, markersize=7, color=color, alpha=0.85,
                               markeredgecolor='white', markeredgewidth=1.2)
                        # [개선된 값 표시]
                        for x, y in zip(df[x_col], df[y_col]):
                            ax.text(x, y, f'{int(y)}', 
                                   ha='center', va='bottom',
                                   fontsize=10,
                                   color='#000000',
                                   fontweight='bold',
                                   bbox=dict(facecolor='white', 
                                           edgecolor='#d1d5db',
                                           boxstyle='round,pad=0.4',
                                           alpha=0.95))
                    elif chart_type == 'bar':
                        bars = ax.bar(df[x_col], df[y_col], label=y_col_en, 
                              alpha=0.9, color=color, edgecolor='white', linewidth=2)
                        # [개선된 값 표시]
                        for bar in bars:
                            height = bar.get_height()
                            ax.text(bar.get_x() + bar.get_width() / 2, height,
                                   f'{int(height)}',
                                   ha='center', va='bottom',
                                   fontsize=10,
                                   color='#000000',
                                   fontweight='bold',
                                   bbox=dict(facecolor='white', 
                                           edgecolor='#d1d5db',
                                           boxstyle='round,pad=0.4',
                                           alpha=0.95))
                if len(y_cols) > 1:
                    ax.legend(fontsize=12, frameon=True, shadow=False, 
                             fancybox=False, loc='upper left',
                             edgecolor='#d1d5db', facecolor='white',
                             framealpha=0.95)

            # [차트 타이틀 제거] 한글 폰트 문제 완전 해결 + 미니멀 디자인
            # 타이틀 없이 축 레이블만으로 충분
            
            ax.set_xlabel('Month', fontsize=14, fontweight='600', color='#374151')
            ax.set_ylabel('Amount (100M KRW)', fontsize=14, fontweight='600', color='#374151')
            
            # [Seaborn 그리드] 이미 적용됨 (whitegrid)
            ax.grid(True, alpha=0.3, linestyle='-', linewidth=0.8)
            
            # [전문 축 스타일]
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['left'].set_color('#9ca3af')
            ax.spines['left'].set_linewidth(1.2)
            ax.spines['bottom'].set_color('#9ca3af')
            ax.spines['bottom'].set_linewidth(1.2)
            
            # Y축 포맷팅 (천 단위 구분 쉼표)
            from matplotlib.ticker import FuncFormatter
            def format_with_comma(x, p):
                return f'{int(x):,}'
            ax.yaxis.set_major_formatter(FuncFormatter(format_with_comma))
            
            # 추세선 추가 (선형 회귀)
            if show_trendline and chart_type == 'line' and 'v.value' in df.columns:
                import numpy as np
                
                if not y_cols or y_cols == ['v.value']:
                    if 'a.name' in df.columns:
                        # 여러 계정이 있는 경우 각각 추세선
                        for idx, account in enumerate(df['a.name'].unique()):
                            subset = df[df['a.name'] == account].copy()
                            # v.value_eok 재계산
                            subset['v.value_eok'] = subset['v.value'].apply(convert_to_eok)
                            x_vals = subset[x_col].values
                            y_vals = subset['v.value_eok'].values
                            
                            if len(x_vals) > 1:  # 최소 2개 이상의 포인트 필요
                                # 선형 회귀
                                z = np.polyfit(x_vals, y_vals, 1)
                                p = np.poly1d(z)
                                
                                # 추세선 그리기
                                ax.plot(x_vals, p(x_vals), "--", 
                                       color=colors[idx % len(colors)], 
                                       linewidth=1.5, 
                                       alpha=0.6,
                                       label=f'{translate_to_english(account)} Trend')
                    else:
                        # 단일 데이터
                        df_copy = df.copy()
                        df_copy['v.value_eok'] = df_copy['v.value'].apply(convert_to_eok)
                        x_vals = df_copy[x_col].values
                        y_vals = df_copy['v.value_eok'].values
                        
                        if len(x_vals) > 1:
                            z = np.polyfit(x_vals, y_vals, 1)
                            p = np.poly1d(z)
                            ax.plot(x_vals, p(x_vals), "--", 
                                   color=colors[0], 
                                   linewidth=1.5, 
                                   alpha=0.6,
                                   label='Trend')
                            ax.legend(fontsize=11, frameon=True, shadow=True, fancybox=True)
            
            plt.tight_layout()
            
            # [개선2] 통합 경로 사용
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"chart_{timestamp}.png"
            filepath = os.path.join(self.output_dir, filename)
            
            # [전문 품질] 고해상도 저장
            plt.savefig(filepath, dpi=200, bbox_inches='tight', 
                       facecolor='white', edgecolor='none',
                       pad_inches=0.2)
            plt.close(fig)
            
            logging.info(f"차트 저장 완료: {filename}")
            
            result = {
                "status": "success",
                "file_path": os.path.abspath(filepath)
            }
            
            # API 호출 시 base64 인코딩된 이미지도 함께 반환
            if return_base64:
                import base64
                with open(filepath, 'rb') as img_file:
                    img_base64 = base64.b64encode(img_file.read()).decode('utf-8')
                    result["image_base64"] = img_base64
                    logging.info("차트 이미지를 base64로 인코딩 완료")
            
            return result
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
    
    def calculate_financial_ratio(self, ratio_id: str, company_id: str, period: str = '2023') -> dict:
        """
        config.json의 formula를 읽고 재무비율 자동 계산
        
        Args:
            ratio_id: 'ROE', '매출채권회전율' 등
            company_id: 'ELECTRIC', 'MnM' 등
            period: '2023', '2024' 등
        
        Returns:
            {"status": "success", "ratio_name": "ROE", "value": 15.2, ...}
        """
        try:
            ratio_config = self.config['financial_ratios']['ratios'].get(ratio_id)
            
            if not ratio_config:
                return {"status": "error", "message": f"'{ratio_id}' 비율을 찾을 수 없습니다."}
            
            if ratio_config['type'] != 'CALCULATED':
                return {"status": "error", "message": f"'{ratio_id}'는 이미 저장된 값입니다. 직접 조회하세요."}
            
            # 1. 구성 요소별로 aggregation 타입에 맞게 조회
            components = ratio_config['components']
            component_values = {}
            
            for comp_account_id in components:
                account_config = self.config['entities']['accounts'].get(comp_account_id)
                if not account_config:
                    return {"status": "error", "message": f"구성 요소 '{comp_account_id}'의 설정을 찾을 수 없습니다."}
                
                agg_type = account_config.get('aggregation', 'SUM')
                
                # 집계 유형에 따라 다른 쿼리 생성
                if agg_type == 'SUM':
                    # IS 항목: 전체 기간 합계
                    query = f"""
                    MATCH (c:Company {{id: '{company_id}'}})-[:HAS_STATEMENT]->(fs:FinancialStatement)
                    WHERE fs.id CONTAINS '{period}' AND fs.id CONTAINS 'ACTUAL'
                    MATCH (fs)-[:HAS_SCOPE]->(scope:StatementScope {{id: 'CONSOLIDATED'}})
                    MATCH (fs)-[:CONTAINS]->(m:Metric)-[:INSTANCE_OF_RULE]->(a:Account {{id: '{comp_account_id}'}})
                    MATCH (m)-[:HAS_OBSERVATION]->(v:ValueObservation)
                    RETURN sum(v.value) as value
                    """
                elif agg_type == 'LAST':
                    # BS 항목: 마지막 월 값
                    query = f"""
                    MATCH (c:Company {{id: '{company_id}'}})-[:HAS_STATEMENT]->(fs:FinancialStatement)
                    WHERE fs.id CONTAINS '{period}' AND fs.id CONTAINS 'ACTUAL'
                    MATCH (fs)-[:HAS_SCOPE]->(scope:StatementScope {{id: 'CONSOLIDATED'}})
                    MATCH (fs)-[:FOR_PERIOD]->(p:Period)
                    MATCH (fs)-[:CONTAINS]->(m:Metric)-[:INSTANCE_OF_RULE]->(a:Account {{id: '{comp_account_id}'}})
                    MATCH (m)-[:HAS_OBSERVATION]->(v:ValueObservation)
                    RETURN v.value as value
                    ORDER BY p.year DESC, p.month DESC
                    LIMIT 1
                    """
                else:
                    return {"status": "error", "message": f"'{comp_account_id}'의 집계 유형 '{agg_type}'은 지원되지 않습니다."}
                
                # 쿼리 실행
                result = self.run_cypher_query(query)
                
                if result['status'] == 'success' and result.get('data') and len(result['data']) > 0:
                    value = result['data'][0].get('value')
                    if value is not None:
                        component_values[comp_account_id] = value
                        logging.info(f"{comp_account_id} ({agg_type}): {value}")
                    else:
                        return {"status": "error", "message": f"'{comp_account_id}' 값이 null입니다."}
                else:
                    return {"status": "error", "message": f"'{comp_account_id}' 조회 실패"}
            
            if len(component_values) != len(components):
                return {"status": "error", "message": f"일부 구성 요소를 찾지 못했습니다. 필요: {components}, 조회됨: {list(component_values.keys())}"}
            
            # 2. 공식 파싱 및 계산
            formula = ratio_config['formula_human']
            
            # 공식에서 계정명을 실제 값으로 치환
            expr = formula.replace(" ", "")  # 공백 제거
            
            # 디버깅 로그
            logging.info(f"원본 공식: {formula}")
            logging.info(f"공백 제거 후: {expr}")
            logging.info(f"Component values: {component_values}")
            
            # 각 구성 요소를 값으로 치환
            # 모든 가능한 이름을 수집하고 길이순으로 정렬 (긴 것부터 치환)
            substitutions = []
            
            for comp_id, value in component_values.items():
                account_config = self.config['entities']['accounts'].get(comp_id, {})
                possible_names = [
                    comp_id,
                    account_config.get('official_name', ''),
                ] + account_config.get('aliases', [])
                
                for name in possible_names:
                    if name:
                        name_no_space = name.replace(" ", "")
                        substitutions.append((name_no_space, str(value)))
            
            # 길이순 정렬 (긴 것부터) - 부분 매칭 문제 방지
            substitutions.sort(key=lambda x: len(x[0]), reverse=True)
            
            # 치환 실행
            for name_no_space, value in substitutions:
                if name_no_space in expr:
                    expr = expr.replace(name_no_space, value)
                    logging.info(f"치환 성공: '{name_no_space}' -> '{value}'")
            
            logging.info(f"최종 expression: {expr}")
            
            # 안전한 eval 실행
            try:
                import re
                # 숫자, 소수점, 연산자, 괄호, 과학적 표기법만 허용
                if not re.match(r'^[0-9eE\.\+\-\*\/\(\)]+$', expr):
                    logging.error(f"허용되지 않은 문자 포함: {expr}")
                    return {"status": "error", "message": "공식에 허용되지 않은 문자 포함", "expression": expr, "formula": formula}
                
                calculated_value = eval(expr)
                logging.info(f"계산 결과: {calculated_value}")
                
            except Exception as e:
                logging.error(f"계산 실패: {e}")
                return {"status": "error", "message": f"계산 실패: {str(e)}", "expression": expr}
            
            return {
                "status": "success",
                "ratio_name": ratio_config['official_name'],
                "ratio_id": ratio_id,
                "value": round(calculated_value, 2),
                "unit": ratio_config.get('unit', ''),
                "formula": formula,
                "components": component_values,
                "period": period,
                "company": company_id
            }
            
        except Exception as e:
            logging.error(f"재무비율 계산 오류: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}
    
    def get_ratios_by_viewpoint(self, viewpoint_name: str) -> dict:
        """
        특정 분석 관점의 모든 재무비율 반환
        
        Args:
            viewpoint_name: "수익성", "안정성", "활동성", "성장성"
        
        Returns:
            {"found": True, "viewpoint": "수익성", "ratios": [...]}
        """
        viewpoint_name_lower = viewpoint_name.lower()
        
        # 1. Viewpoint ID 찾기
        viewpoint_id = None
        viewpoint_official_name = None
        for vid, vdata in self.config['financial_ratios']['viewpoints'].items():
            all_names = [vdata['name']] + vdata.get('aliases', [])
            if any(viewpoint_name_lower == name.lower() for name in all_names):
                viewpoint_id = vid
                viewpoint_official_name = vdata['name']
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
                    "description": rdata.get('description'),
                    "unit": rdata.get('unit')
                })
        
        return {
            "found": True,
            "viewpoint": viewpoint_official_name,
            "viewpoint_id": viewpoint_id,
            "ratios": ratios,
            "count": len(ratios)
        }
    
    def get_definition(self, term: str) -> dict:
        """
        재무 용어의 정의를 config.json에서 조회
        
        Args:
            term: "영업이익", "ROE", "부채비율" 등
        
        Returns:
            {"found": True, "type": "account", "definition": {...}}
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
            "message": f"'{term}'에 대한 정의를 config.json에서 찾을 수 없습니다. 일반 지식으로 답변하세요."
        }
    
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
            
            # JSON에서 프롬프트 템플릿 로드
            prompt_template = self._load_prompt_template('internal_prompts.general_knowledge_qa_prompt.template')
            if not prompt_template:
                prompt_template = "당신은 재무/경영 전문가입니다. 다음 질문에 답변해주세요:\n\n{question}"
            
            response = model_simple.generate_content(
                prompt_template.format(question=question),
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
        최종 마크다운 답변을 프론트엔드가 요구하는 JSON 구조로 유연하게 파싱합니다.
        '### 숫자. 제목' 형식의 모든 섹션을 인식합니다.
        """
        import re
        
        content_blocks = []
        
        # 0. 차트가 생성되었는지 확인 (최우선)
        if self.last_chart_data and self.last_chart_data.get('image_base64'):
            if "차트" in final_answer or "그래프" in final_answer:
                content_blocks.append({
                    "type": "chart",
                    "content": {
                        "image_base64": self.last_chart_data['image_base64'],
                        "file_path": self.last_chart_data.get('file_path', '')
                    }
                })
                # 차트 포함 시 간단한 텍스트만 추가
                simple_text = re.sub(r'파일 경로:.*', '', final_answer).strip()
                if simple_text:
                    content_blocks.append({"type": "text", "content": simple_text})
                
                # 차트 데이터 초기화 (재사용 방지)
                self.last_chart_data = None
                
                return content_blocks
        
        # 1. '### 숫자.' 패턴을 기준으로 전체 답변을 섹션으로 분리 (유연성)
        sections = re.split(r'\n(?=###\s*\d+\.\s*)', final_answer.strip())
        
        for section in sections:
            section_content = section.strip()
            if not section_content:
                continue
            
            # 2. 각 섹션이 테이블인지 검사 (지능)
            lines = [line.strip() for line in section_content.split('\n') if line.strip()]
            
            # 테이블 판단: 섹션 내에 마크다운 테이블 패턴이 있는지 확인
            is_table_section = False
            table_start = -1
            
            # 어느 줄이든 헤더 + 구분자 패턴 찾기
            for i in range(len(lines) - 1):
                if '|' in lines[i] and '---' in lines[i+1] and '|' in lines[i+1]:
                    is_table_section = True
                    table_start = i
                    break
            
            if is_table_section:
                # 3-A. 테이블이면 구조화된 JSON으로 변환
                try:
                    # 테이블 시작 인덱스 찾기 (제목 제외)
                    table_start = 0
                    for i, line in enumerate(lines):
                        if '|' in line and i < len(lines) - 1 and '---' in lines[i+1]:
                            table_start = i
                            break
                    
                    # 헤더와 행 파싱
                    columns = [h.strip() for h in lines[table_start].strip('|').split('|')]
                    rows = []
                    for line in lines[table_start+2:]:  # 헤더와 구분자 건너뛰기
                        if '|' in line:
                            # 구분자 행 필터링 (:--, :---, 등)
                            if not all(cell.strip().replace(':', '').replace('-', '').strip() == '' for cell in line.strip('|').split('|')):
                                rows.append([r.strip() for r in line.strip('|').split('|')])
                    
                    # InteractiveTable을 위한 구조
                    content_blocks.append({
                        "type": "table",
                        "content": {"columns": columns, "rows": rows}
                    })
                    
                    # 테이블 위의 제목이 있으면 별도 텍스트로 추가
                    if table_start > 0:
                        prefix = '\n'.join(lines[:table_start])
                        if prefix.strip():
                            # 제목을 테이블 앞에 추가
                            content_blocks.insert(-1, {"type": "text", "content": prefix.strip()})
                    
                except Exception as e:
                    logging.warning(f"테이블 파싱 실패, 텍스트로 처리: {e}")
                    content_blocks.append({"type": "text", "content": section_content})
            else:
                # 3-B. 테이블 아니면 텍스트로
                content_blocks.append({"type": "text", "content": section_content})
        
        # 2. 안내 메시지 (💡로 시작) - 별도 처리
        notice_match = re.search(r"(💡.*?)(?=\n\n|\Z)", final_answer, re.DOTALL)
        if notice_match:
            # 이미 텍스트 블록에 포함되었을 수 있으므로, 중복 체크
            notice_text = notice_match.group(1).strip()
            # 마지막 블록에 이미 포함되어 있지 않으면 추가
            if not content_blocks or notice_text not in content_blocks[-1].get("content", ""):
                content_blocks.append({"type": "notice", "content": notice_text})
        
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
            
            # 파싱 결과 상세 로깅
            logging.info(f"파싱된 컨텐츠 블록 수: {len(structured_content)}")
            for i, block in enumerate(structured_content):
                block_type = block.get('type', 'unknown')
                if block_type == 'table':
                    cols = len(block.get('content', {}).get('columns', []))
                    rows = len(block.get('content', {}).get('rows', []))
                    logging.info(f"  블록 {i}: type=table, columns={cols}, rows={rows}")
                else:
                    content_len = len(str(block.get('content', '')))
                    logging.info(f"  블록 {i}: type={block_type}, length={content_len}")
            
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
        """LLM을 활용한 전사 vs 사업별 레벨 판단 (JSON 기반)"""
        # system_prompt.json에서 level_detection 프롬프트 로드
        prompt_json_path = os.path.join(self.base_dir, 'system_prompt.json')
        try:
            with open(prompt_json_path, 'r', encoding='utf-8') as f:
                prompt_config = json.load(f)
            level_detection_prompt = prompt_config['level_detection']['prompt_template'].format(user_query=user_query)
        except Exception as e:
            logging.warning(f"Failed to load level_detection from system_prompt.json: {e}")
            # Fallback to hardcoded prompt
            level_detection_prompt = f"""Analyze this user query: "{user_query}"

Determine if the user wants:
- CORPORATE: Company-wide totals
- SEGMENT: Business unit/segment queries

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
        """Cypher 쿼리 사전 검증 + available_data 체크"""
        warnings = []
        
        if "fs.year" in query or "fs.month" in query:
            warnings.append("⚠️ FinancialStatement에는 year/month 속성이 없습니다. fs.id CONTAINS 사용")
        
        if ("c.name =" in query or "company.name =" in query) and "Company" in query:
            warnings.append("⚠️ Company는 c.id로 매칭하세요. 예: {id: 'ELECTRIC'}")
        
        if "v.region" in query and "HAS_STATEMENT" in query and "FOR_SEGMENT" not in query:
            warnings.append("⚠️ CORPORATE 데이터에는 v.region 속성이 없습니다. 필터 제거 필요")
        
        # Phase 6: available_data 체크
        import re
        # 쿼리에서 회사 ID 추출
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
                    if ':BS' in query and 'BS' not in avail_data:
                        warnings.append(f"⚠️ {company_config.get('official_name', cid)}은(는) BS 데이터가 제공되지 않습니다.")
                    
                    # IS 데이터 요청했는데 없는 경우  
                    if ':IS' in query and 'IS' not in avail_data:
                        warnings.append(f"⚠️ {company_config.get('official_name', cid)}은(는) IS 데이터가 제공되지 않습니다.")
        
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
            
            # JSON에서 프롬프트 템플릿 로드
            prompt_template = self._load_prompt_template('internal_prompts.history_summary_prompt.template')
            if not prompt_template:
                prompt_template = "다음 대화를 3-5문장으로 요약:\n\n{history_text}\n\n핵심만 간결하게:"
            
            summary_prompt = prompt_template.format(history_text=history_text)
            
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
        
        # 그룹 추출 (우선 처리)
        mentioned_groups = {}
        for alias, group_id in self.nlu['group'].items():
            if alias in query_lower:
                mentioned_groups[alias] = group_id
        
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
            "groups": mentioned_groups,
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
                
                # 추출된 엔티티 로깅
                if entities.get("groups"):
                    print(f"[추출] 그룹: {entities['groups']}")
                    logging.info(f"추출된 그룹: {entities['groups']}")
                if entities.get("companies"):
                    print(f"[추출] 회사: {entities['companies']}")
                    logging.info(f"추출된 회사: {entities['companies']}")
                
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
            
            # 그룹이 언급되었으면 해당 그룹의 회사 목록을 명시적으로 제공
            if entities.get("groups"):
                entity_context += "\n**🎯 사용자가 언급한 회사 그룹 (CRITICAL!):**\n"
                for alias, group_id in entities["groups"].items():
                    group_name = self.config.get('business_rules', {}).get('company_groups', {}).get(group_id, {}).get('name', group_id)
                    # 해당 그룹의 모든 회사 ID 추출
                    group_company_ids = []
                    for company_id, company_data in self.config.get('entities', {}).get('companies', {}).items():
                        if group_id in company_data.get('groups', []):
                            group_company_ids.append(company_id)
                    
                    # 로깅으로 확인
                    print(f"[그룹 매핑] '{alias}' → {group_company_ids}")
                    logging.info(f"그룹 '{alias}' ({group_id})의 회사 목록: {group_company_ids}")
                    
                    entity_context += f"- User said: '{alias}' → Group: '{group_name}'\n"
                    entity_context += f"  **YOU MUST USE ALL THESE COMPANY IDs: {group_company_ids}**\n"
                    entity_context += f"  Example: WHERE c.id IN {group_company_ids}\n"
                    entity_context += f"  ⚠️ Do NOT omit any company! Include ALL {len(group_company_ids)} companies!\n\n"
            
            if entities.get("companies"):
                entity_context += "\n**🎯 사용자가 언급한 회사 (NLU 매핑 완료):**\n"
                for alias, company_id in entities["companies"].items():
                    entity_context += f"- '{alias}' → Company ID: '{company_id}' (이 ID를 쿼리에 사용하세요!)\n"
            
            if entities.get("accounts"):
                entity_context += "\n**🎯 사용자가 언급한 계정 (NLU 매핑 완료):**\n"
                for alias, account_id in entities["accounts"].items():
                    entity_context += f"- '{alias}' → Account ID: '{account_id}' (이 ID를 쿼리에 사용하세요!)\n"
            
            # Phase 7: contextual_ids 추가 (SEGMENT 레벨 시)
            if level == "SEGMENT":
                contextual_id_info = {}
                for cid, cdata in self.config['entities']['companies'].items():
                    if 'contextual_ids' in cdata and 'segment_data' in cdata['contextual_ids']:
                        contextual_id_info[cid] = {
                            "use_id": cdata['contextual_ids']['segment_data'],
                            "reason": "연결 재무제표 회사의 사업별 데이터는 별도 ID 사용"
                        }
                
                if contextual_id_info:
                    entity_context += "\n**🎯 Contextual ID Mapping (SEGMENT 데이터용):**\n"
                    entity_context += "일부 회사는 사업별 데이터 조회 시 다른 ID를 사용합니다:\n"
                    for cid, info in contextual_id_info.items():
                        entity_context += f"- '{cid}' → Use '{info['use_id']}' for segment queries\n"
                    entity_context += "\n"
            
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
            
            # Tools (모든 도구 포함)
            tools = [
                self.run_cypher_query,
                self.data_visualization,
                self.generate_downloadable_link,
                self.calculate_financial_ratio,  # Phase 3: 재무비율 계산
                self.get_ratios_by_viewpoint,    # Phase 5: 관점별 비율 목록
                self.get_definition,             # Phase 4: 용어 정의
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
                # JSON에서 프롬프트 템플릿 로드
                prompt_template = self._load_prompt_template('internal_prompts.follow_up_action.template')
                if prompt_template:
                    current_prompt = prompt_template.format(
                        user_query=user_query,
                        available_columns=available_columns
                    )
                else:
                    # Fallback
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
       account_filter='계정명',   # IMPORTANT! Extract from user request
       year_filter=2022 or 2023,  # CRITICAL! If user specifies year
       show_trendline=True  # If user asks for "추세선", "trendline", "회귀선"
   )
   ```

3. **Extract filters from user's request**:
   - "전선의 매출" → company_filter='전선', account_filter='매출'
   - "ELECTRIC 영업이익" → company_filter='ELECTRIC', account_filter='영업이익'
   - "2022년 매출" → year_filter=2022, account_filter='매출'
   - "2023년 일렉트릭" → year_filter=2023, company_filter='ELECTRIC'
   
4. **CRITICAL for year filters**:
   - If user says "2022년", "2023년", "2024년" → ALWAYS use year_filter
   - Do NOT show multiple years when user asks for one specific year
   
5. **DO NOT try to find combined column names** like 'LS전선(연결) 매출액 합계'!
   The data has separate columns: c.name, a.name, v.value
   Use filters to select specific company and account.

6. After tool success: Simple confirmation only!

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
                        
                        # WHERE c.id IN 부분을 로깅해서 엠트론 포함 여부 확인
                        if "WHERE c.id IN" in query_text or "WHERE c.id =" in query_text:
                            import re
                            where_match = re.search(r"WHERE c\.id (?:IN\s*\[(.*?)\]|=\s*'(.*?)')", query_text)
                            if where_match:
                                company_ids = where_match.group(1) or where_match.group(2)
                                print(f"[확인] 쿼리에 포함된 회사: {company_ids}")
                                logging.warning(f"쿼리에 사용된 회사 ID: {company_ids}")
                                if '엠트론' not in company_ids:
                                    print(f"[경고] 엠트론이 쿼리에서 누락되었습니다!")
                                    logging.error("엠트론이 WHERE 절에 포함되지 않음!")
                        
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
                            
                            # JSON에서 프롬프트 템플릿 로드
                            prompt_template = self._load_prompt_template('internal_prompts.no_data_response.template')
                            if prompt_template:
                                final_answer = prompt_template.format(items_text=items_text)
                            else:
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
                            # JSON에서 프롬프트 템플릿 로드
                            prompt_template = self._load_prompt_template('internal_prompts.error_recovery.query_error')
                            hints_text = chr(10).join('- ' + h for h in result.get('hints', []))
                            if prompt_template:
                                retry_guidance = prompt_template.format(
                                    error_type=result.get('error_type'),
                                    error_message=result.get('error', '')[:300],
                                    hints=hints_text
                                )
                            else:
                                retry_guidance = f"""
[CRITICAL ERROR] Previous Cypher query FAILED.

Error Type: {result.get('error_type')}
Error Message: {result.get('error')[:300]}

Hints:
{hints_text}

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
                            image_base64 = result.get('image_base64')
                            print(f"[완료] 차트 저장: {file_path}\n")
                            
                            # 차트 정보를 캐시에 저장 (파싱 시 사용)
                            self.last_chart_data = {
                                "file_path": file_path,
                                "image_base64": image_base64
                            }
                            
                            # 간결한 확인 메시지만 요청
                            prompt_template = self._load_prompt_template('internal_prompts.tool_responses.chart_created')
                            current_prompt = prompt_template if prompt_template else """The data_visualization tool successfully created a chart.

Your ONLY job now is to inform the user that the chart has been created.
Just say: "요청하신 차트를 생성했습니다."

Keep it simple and short.
"""
                            continue
                        else:
                            print(f"[오류] {result.get('error')}\n")
                            prompt_template = self._load_prompt_template('internal_prompts.error_recovery.chart_error')
                            current_prompt = prompt_template.format(error=result.get('error')) if prompt_template else f"Chart generation failed: {result.get('error')}. Inform the user."
                            continue
                            
                    elif tool_name == "generate_downloadable_link":
                        print("[작업] 파일을 생성하고 있습니다...")
                        result = self.generate_downloadable_link(**tool_args)
                        if result.get("status") == "success":
                            file_path = result['file_path']
                            print(f"[완료] 파일 저장: {file_path}\n")
                            # 간결한 확인 메시지만 요청
                            prompt_template = self._load_prompt_template('internal_prompts.tool_responses.file_created')
                            current_prompt = prompt_template.format(file_path=file_path) if prompt_template else f"""File successfully saved.
Path: {file_path}

Inform the user that the file has been created. Simple confirmation only.
"""
                            continue
                        else:
                            print(f"[오류] {result.get('error')}\n")
                            prompt_template = self._load_prompt_template('internal_prompts.error_recovery.file_error')
                            current_prompt = prompt_template.format(error=result.get('error')) if prompt_template else f"File creation failed: {result.get('error')}. Inform the user."
                            continue
                    
                    elif tool_name == "calculate_financial_ratio":
                        print("[작업] 재무비율을 계산하고 있습니다...")
                        result = self.calculate_financial_ratio(**tool_args)
                        if result.get("status") == "success":
                            print(f"[완료] {result['ratio_name']}: {result['value']}{result.get('unit', '')}\n")
                            prompt_template = self._load_prompt_template('internal_prompts.tool_responses.ratio_calculated')
                            current_prompt = prompt_template.format(
                                ratio_name=result['ratio_name'],
                                value=result['value'],
                                unit=result.get('unit', ''),
                                formula=result.get('formula', ''),
                                components=result.get('components', {})
                            ) if prompt_template else f"""Financial ratio calculated successfully:

Ratio: {result['ratio_name']}
Value: {result['value']}{result.get('unit', '')}
Formula: {result.get('formula', '')}
Components used: {result.get('components', {})}

Present this result to the user clearly, including the calculation details.
"""
                        else:
                            print(f"[오류] {result.get('message')}\n")
                            prompt_template = self._load_prompt_template('internal_prompts.error_recovery.ratio_error')
                            current_prompt = prompt_template.format(message=result.get('message')) if prompt_template else f"Calculation failed: {result.get('message')}. Inform the user."
                        continue
                    
                    elif tool_name == "get_definition":
                        print("[작업] 용어 정의를 조회하고 있습니다...")
                        result = self.get_definition(**tool_args)
                        if result.get("found"):
                            print(f"[완료] {result['official_name']} 정의 찾음\n")
                            prompt_template = self._load_prompt_template('internal_prompts.tool_responses.definition_found')
                            formula_line = f"Formula: {result.get('formula')}" if result.get('formula') else ""
                            current_prompt = prompt_template.format(
                                official_name=result['official_name'],
                                type=result.get('type'),
                                description=result.get('description'),
                                formula_line=formula_line
                            ) if prompt_template else f"""Definition found in config.json:

Term: {result['official_name']}
Type: {result.get('type')}
Description: {result.get('description')}
{formula_line}

Present this definition to the user. This is our system's official definition, so it's more accurate than general knowledge.
"""
                        else:
                            print(f"[정보] Config에서 찾을 수 없음. 일반 지식 사용\n")
                            # Fallback to general_knowledge_qa
                            knowledge_answer = self.general_knowledge_qa(tool_args.get("term", user_query))
                            prompt_template = self._load_prompt_template('internal_prompts.tool_responses.definition_not_found')
                            current_prompt = prompt_template.format(
                                knowledge_answer=knowledge_answer
                            ) if prompt_template else f"""Definition not in config, but here's general knowledge:

{knowledge_answer}

Present this to the user.
"""
                        continue
                    
                    elif tool_name == "get_ratios_by_viewpoint":
                        print("[작업] 분석 관점별 비율 목록을 조회하고 있습니다...")
                        result = self.get_ratios_by_viewpoint(**tool_args)
                        if result.get("found"):
                            ratios_list = "\n".join([f"- {r['name']} ({r['type']})" for r in result['ratios']])
                            print(f"[완료] {result['viewpoint']} 관점 비율 {result['count']}개 찾음\n")
                            prompt_template = self._load_prompt_template('internal_prompts.tool_responses.viewpoint_ratios')
                            current_prompt = prompt_template.format(
                                count=result['count'],
                                viewpoint=result['viewpoint'],
                                ratios_list=ratios_list
                            ) if prompt_template else f"""Found {result['count']} ratios for {result['viewpoint']} viewpoint:

{ratios_list}

Present this list to the user. You can also ask which specific ratio they want to analyze.
"""
                        else:
                            print(f"[정보] {result.get('message')}\n")
                            prompt_template = self._load_prompt_template('internal_prompts.error_recovery.viewpoint_error')
                            current_prompt = prompt_template.format(message=result.get('message')) if prompt_template else f"Viewpoint not found: {result.get('message')}. Inform the user."
                            continue
                    
                    elif tool_name == "general_knowledge_qa":
                        print("[작업] 재무/경영 지식을 검색하고 있습니다...")
                        question = tool_args.get("question", user_query)
                        knowledge_answer = self.general_knowledge_qa(question)
                        result = {"status": "success", "answer": knowledge_answer}
                        print(f"[완료] 지식 답변 생성\n")
                        # 지식 답변은 그 자체가 최종 답변
                        prompt_template = self._load_prompt_template('internal_prompts.tool_responses.general_knowledge')
                        current_prompt = prompt_template.format(
                            knowledge_answer=knowledge_answer
                        ) if prompt_template else f"""General knowledge answer retrieved:

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
                            
                            # 컬럼명 표준화 (LLM이 다양한 별칭 사용 가능)
                            # 1. 동적 감지
                            company_col = None
                            if 'c.name' in df.columns:
                                company_col = 'c.name'
                            elif 'company_name' in df.columns:
                                company_col = 'company_name'
                            elif 'company' in df.columns:
                                company_col = 'company'
                            
                            account_col = None
                            if 'a.name' in df.columns:
                                account_col = 'a.name'
                            elif 'account_name' in df.columns:
                                account_col = 'account_name'
                            elif 'account' in df.columns:
                                account_col = 'account'
                            
                            # 2. 표준 이름으로 rename (코드 단순화)
                            rename_mapping = {}
                            if company_col and company_col != 'c.name':
                                rename_mapping[company_col] = 'c.name'
                            if account_col and account_col != 'a.name':
                                rename_mapping[account_col] = 'a.name'
                            
                            # 기타 시간 관련 컬럼도 표준화
                            if 'year' in df.columns and 'p.year' not in df.columns:
                                rename_mapping['year'] = 'p.year'
                            if 'month' in df.columns and 'p.month' not in df.columns:
                                rename_mapping['month'] = 'p.month'
                            if 'value' in df.columns and 'v.value' not in df.columns and 'plan' not in df.columns:
                                rename_mapping['value'] = 'v.value'
                            
                            if rename_mapping:
                                df.rename(columns=rename_mapping, inplace=True)
                                logging.info(f"컬럼명 표준화 완료: {rename_mapping}")
                            else:
                                logging.info(f"컬럼명이 이미 표준 형식입니다")
                            
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
                                
                                # [숫자 포맷 개선] v.value가 있으면 억원 단위로 변환
                                if 'v.value' in df.columns:
                                    df['v.value_억원'] = df['v.value'].apply(
                                        lambda x: f"{x/100000000:,.1f}" if pd.notna(x) and x != 0 else "0"
                                    )
                                
                                # CSV로 변환
                                data_csv = df.to_csv(index=False)
                                
                                # JSON에서 프롬프트 템플릿 로드
                                prompt_template = self._load_prompt_template('internal_prompts.segment_data_delivery.template')
                                if prompt_template:
                                    tool_result_text = prompt_template.format(data_csv=data_csv)
                                else:
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
                            
                            # 집계할 값 컬럼을 동적으로 결정
                            value_columns = []
                            calculation_columns = ['variance_pct', 'achievement_rate', 'ytd_total', 'quarterly_value']
                            
                            for col in df.columns:
                                if col in calculation_columns:
                                    continue  # 이미 계산된 컬럼은 집계하지 않음
                                if 'value' in col.lower() or col in ['plan', 'actual']:
                                    value_columns.append(col)
                            
                            if not value_columns:
                                raise ValueError("집계할 값 컬럼을 찾을 수 없습니다.")
                            
                            print(f"[DEBUG] 감지된 값 컬럼: {value_columns}")
                            logging.info(f"동적 컬럼 감지: {value_columns}")
                            
                            summary_parts = []
                            
                            # SUM 항목 집계 (IS 계정: 매출, 영업이익 등)
                            if not df_sum.empty:
                                # 연도별로 구분하여 집계
                                group_cols = [col for col in ['c.name', 'p.year', 'a.name', 'statement_scope'] if col in df_sum.columns]
                                # 존재하는 값 컬럼만 집계
                                sum_value_cols = [col for col in value_columns if col in df_sum.columns]
                                if sum_value_cols:
                                    summary_sum = df_sum.groupby(group_cols)[sum_value_cols].sum().reset_index()
                                    summary_parts.append(summary_sum)
                                    logging.info(f"SUM 집계 완료: {len(df_sum)}개 레코드 → {len(summary_sum)}개 연도별 집계 (컬럼: {sum_value_cols})")
                            
                            # LAST 항목 집계 (BS 계정: 자산, 부채, 자기자본 등)
                            if not df_last.empty:
                                # 연도와 월 기준으로 정렬 후 그룹별 마지막 값 선택
                                group_cols = [col for col in ['c.name', 'p.year', 'a.name', 'statement_scope'] if col in df_last.columns]
                                last_value_cols = [col for col in value_columns if col in df_last.columns]
                                summary_last = df_last.sort_values(['p.year', 'p.month']).groupby(group_cols, as_index=False).last()
                                keep_cols = group_cols + last_value_cols
                                summary_last = summary_last[[col for col in keep_cols if col in summary_last.columns]]
                                summary_parts.append(summary_last)
                                logging.info(f"LAST 집계 완료: {len(df_last)}개 레코드 → {len(summary_last)}개 연도별 기말값 (컬럼: {last_value_cols})")
                            
                            # 결과 병합
                            if summary_parts:
                                summary_df = pd.concat(summary_parts, ignore_index=True)
                                # [숫자 포맷 개선] 억원 단위로 변환 + 포맷팅
                                for col in value_columns:
                                    if col in summary_df.columns:
                                        summary_df[col] = summary_df[col].apply(
                                            lambda x: f"{x/100000000:,.1f}억원" if isinstance(x, (int, float)) and x != 0 else "0"
                                        )
                                summary_md = summary_df.to_markdown(index=False)
                                logging.info("지능적 집계 완료 (SUM/LAST 규칙, 동적 컬럼, 억원 단위 변환)")
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
                            # 연도가 여러 개인지 확인
                            has_multiple_years = 'p.year' in df.columns and len(df['p.year'].unique()) > 1
                            
                            if len(df['c.name'].unique()) > 1:
                                # 다중 회사: PIVOT 테이블
                                # 연도가 여러 개면 index에 year 포함
                                index_cols = ['p.year', 'p.month'] if has_multiple_years else ['p.month']
                                pivot_df = df.pivot_table(
                                    index=index_cols, 
                                    columns=['c.name', 'a.name'], 
                                    values='v.value', 
                                    aggfunc='sum'
                                )
                                monthly_csv = pivot_df.to_csv()
                                monthly_format = "PIVOT_CSV"
                            else:
                                # 단일 회사: 일반 CSV
                                # year 컬럼을 포함
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
                        
                        # JSON에서 프롬프트 템플릿 로드
                        prompt_template = self._load_prompt_template('internal_prompts.corporate_data_delivery.template')
                        if prompt_template:
                            tool_result_text = prompt_template.format(
                                summary_md=summary_md,
                                monthly_format=monthly_format,
                                monthly_csv=monthly_csv
                            )
                        else:
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

'''
# CLI interface removed - use main_api.py for API server
# For standalone testing, create a separate test script
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
'''