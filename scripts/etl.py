import json
import os
import pandas as pd
from neo4j import GraphDatabase
import re
from tqdm import tqdm
from datetime import datetime
import uuid
import hashlib

# --- 1. 기본 설정 (Configuration) ---
NEO4J_URI = "bolt://127.0.0.1:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "vlvmffoq1!"

# 스크립트 파일 위치 기준으로 경로 계산
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
CONFIG_FILE = os.path.join(PROJECT_ROOT, "packages", "backend", "config.json")

class GMISKnowledgeGraphETL:
    """
    [V5 Final Version - Enhanced Segment Data Processing]
    사업별 손익 데이터를 포함한 모든 지식을 그래프에 통합하는 최종 ETL 클래스.
    
    주요 개선사항:
    - APOC 의존성 제거 (Python UUID 사용)
    - BusinessSegment ID 고유성 확보
    - ValueObservation 중복 방지
    - Account 매핑 테이블 활용
    - 파싱 로직 견고성 강화
    """
    
    def __init__(self, uri, user, password, config):
        self.config = config
        try:
            self._driver = GraphDatabase.driver(uri, auth=(user, password))
            self._driver.verify_connectivity()
            print("[OK] Neo4j 데이터베이스에 성공적으로 연결되었습니다.")
        except Exception as e:
            print(f"[ERROR] 데이터베이스 연결 실패: {e}")
            raise ConnectionError(f"Neo4j 연결 불가: {e}")

    def close(self):
        if self._driver:
            self._driver.close()
            print("\n[연결종료] Neo4j 데이터베이스 연결이 닫혔습니다.")

    def _execute_write(self, tx_function, **kwargs):
        with self._driver.session() as session:
            return session.execute_write(tx_function, **kwargs)

    def run_etl_pipeline(self, clear_db=True, only_segments=False):
        """
        ETL 파이프라인 전체를 순서대로 실행합니다.
        
        Args:
            clear_db: True면 전체 DB 삭제 후 재구축, False면 증분 업데이트
            only_segments: True면 사업별 데이터만 재처리 (속도 최적화)
        """
        print("\n" + "="*70)
        if only_segments:
            print("  GMIS Knowledge Graph ETL Pipeline v5 (Segment Only)")
        else:
            print("  GMIS Knowledge Graph ETL Pipeline v5")
        print("="*70)
        
        if clear_db: 
            self._clear_database()
        
        self._create_constraints_and_indexes()
        
        if not only_segments:
            self._load_knowledge_layer()
            self._process_main_files()
        else:
            print("\n[정보] Segment 데이터만 재처리합니다 (Main 데이터 건너뜀)")
        
        self._process_segment_files()
        self._build_post_relations()
        print("\n[완료] 모든 ETL 파이프라인 작업이 성공적으로 완료되었습니다.")

    def _clear_database(self):
        print("\n--- 1. 데이터베이스 초기화 ---")
        print("   - 대용량 데이터 삭제 중 (배치 처리)...")
        
        # [메모리 안전] 배치로 삭제
        with self._driver.session() as session:
            while True:
                result = session.run("""
                    MATCH (n)
                    WITH n LIMIT 10000
                    DETACH DELETE n
                    RETURN count(n) as deleted
                """)
                deleted = result.single()['deleted']
                if deleted == 0:
                    break
                print(f"      - {deleted}개 노드 삭제 완료...")
        
        print("   - 완료: 모든 노드와 관계가 삭제되었습니다.")

    def _create_constraints_and_indexes(self):
        print("\n--- 2. 제약 조건 및 인덱스 생성 ---")
        queries = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Company) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:CIC) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Account) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Term) REQUIRE n.value IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:CompanyGroup) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:FinancialStatement) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Metric) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:BusinessSegment) REQUIRE n.id IS UNIQUE",  # ← ID 기반으로 변경
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:StatementType) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:StatementScope) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:DataClass) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Period) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Quarter) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:HalfYear) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Year) REQUIRE n.year IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:FinancialRatio) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:AnalysisViewpoint) REQUIRE n.id IS UNIQUE"
        ]
        self._execute_write(lambda tx: [tx.run(q) for q in queries])
        print("   - 완료: 모든 핵심 노드에 고유성 제약 조건이 생성되었습니다.")

    def _load_knowledge_layer(self):
        print("\n--- 3. 지식 레이어 (메타데이터) 구축 ---")
        self._execute_write(self._tx_build_knowledge_layer)
        print("   - 완료: Company, Account, Dimensions 등 개념 노드 및 관계가 생성되었습니다.")

    def _build_contextual_mapper(self, context='main_data'):
        """
        회사명 별칭을 회사 ID로 매핑하는 사전을 생성합니다.
        
        context='main_data': 연결/별도 재무제표용 (기본 매핑)
        context='segment_data': 사업별 손익용 (contextual_ids 고려)
        """
        mapper = {}
        for company_id, data in self.config['entities']['companies'].items():
            for alias in [data['official_name']] + data.get('aliases', []):
                mapper[alias.lower()] = company_id
        
        if context == 'segment_data':
            # contextual_ids 처리: 연결 재무제표의 사업별 데이터는 별도 ID로 매핑
            for company_id, data in self.config['entities']['companies'].items():
                context_id = data.get('contextual_ids', {}).get('segment_data')
                if context_id:
                    # LSCNS_C의 aliases를 LSCNS_S로 매핑
                    for alias in [data['official_name']] + data.get('aliases', []):
                        mapper[alias.lower()] = context_id
        return mapper

    def _process_main_files(self):
        """메인 재무제표 파일(IS/BS 연결/별도)을 처리합니다."""
        print("\n--- 4. 메인 데이터 (IS/BS 연결/별도) 처리 ---")
        main_files = self.config.get('data_sources', {}).get('main_files', [])
        mapper = self._build_contextual_mapper(context='main_data')

        for file in main_files:
            file_path = os.path.join(DATA_DIR, file)
            if not os.path.exists(file_path):
                print(f"   - 경고: '{file}' 파일을 찾을 수 없어 건너뜁니다.")
                continue
            
            print(f"   - 파일 처리 중: {file}")
            df = pd.read_csv(file_path, encoding='utf-8-sig', low_memory=False)
            df.columns = [self._clean_column_name(col) for col in df.columns]
            df['company_id'] = df['회사'].str.lower().map(mapper)
            df.dropna(subset=['company_id'], inplace=True)
            
            meta_columns = ['그룹', '4개사', '11개사', 'CIC', '회사', 'year', 'month', '반기', '분기', '계정', '항목', 'company_id']
            account_columns = [col for col in df.columns if col not in meta_columns and col in self.config['entities']['accounts']]

            # Main 데이터는 복잡한 관계가 많아 행별 처리 유지 (Segment만 배치)
            for _, row in tqdm(df.iterrows(), total=len(df), desc=f"     {file}", unit=" rows"):
                self._execute_write(self._tx_process_main_row, row_data=row.to_dict(), account_columns=account_columns, file_name=file)

    def _process_segment_files(self):
        """사업별 손익 파일을 처리합니다."""
        print("\n--- 5. 사업별 손익 데이터 처리 ---")
        segment_config = self.config.get('data_sources', {}).get('segment_files', {})
        mapper = self._build_contextual_mapper(context='segment_data')
        
        files_to_process = {}
        overrides = segment_config.get('overrides', {})
        dynamic_config = segment_config.get('dynamic_discovery', {})

        # 동적 파일 발견
        if dynamic_config.get('enabled', False):
            template = dynamic_config.get('file_name_template')
            exclude_companies = dynamic_config.get('exclude_companies', [])
            
            for company_id, data in self.config['entities']['companies'].items():
                # CIC, 제외 대상, override 대상은 건너뛰기
                if data.get('type') == 'CIC':
                    continue
                if company_id in exclude_companies:
                    continue
                if company_id in overrides:
                    continue
                # contextual_ids가 있으면 건너뛰기 (LSCNS_C 같은 경우)
                if data.get('contextual_ids', {}).get('segment_data'):
                    continue

                file_name_id = data.get('file_name_id', company_id)
                file_name = template.format(file_name_id=file_name_id)
                file_path = os.path.join(DATA_DIR, file_name)
                
                if os.path.exists(file_path):
                    files_to_process[company_id] = {"file": file_name, "format": "DEFAULT"}
                else:
                    print(f"   - 정보: '{file_name}' 파일이 없어 건너뜁니다.")
        
        # Override 추가
        for company_id, override_info in overrides.items():
            # 기본 파일 추가
            if 'file' in override_info:
                files_to_process[company_id] = {
                    "file": override_info['file'],
                    "format": override_info.get('format', 'DEFAULT')
                }
            
            # CIC 매핑 파일 추가
            if 'cic_mapping_files' in override_info:
                for cic_id, cic_file in override_info['cic_mapping_files'].items():
                    files_to_process[cic_id] = {
                        "file": cic_file,
                        "format": "CIC_DIRECT",
                        "target_company": cic_id
                    }
        
        # 파일 처리
        for company_id_key, file_info in files_to_process.items():
            file_path = os.path.join(DATA_DIR, file_info['file'])
            if not os.path.exists(file_path):
                print(f"   - 경고: '{file_info['file']}' 파일을 찾을 수 없어 건너뜁니다.")
                continue

            print(f"   - 파일 처리 중: {file_info['file']} (대상: {company_id_key})")
            
            # 여러 인코딩 시도
            df_wide = None
            for encoding in ['utf-8-sig', 'cp949', 'euc-kr', 'utf-8']:
                try:
                    df_wide = pd.read_csv(file_path, encoding=encoding, low_memory=False)
                    print(f"      (인코딩: {encoding})")
                    break
                except UnicodeDecodeError:
                    continue
            
            if df_wide is None:
                print(f"   - 오류: '{file_info['file']}' 파일의 인코딩을 인식할 수 없습니다.")
                continue
            
            df_wide.columns = [self._clean_column_name(col) for col in df_wide.columns]
            
            # Wide → Long 변환
            meta_columns = ['그룹', '4개사', '11개사', 'CIC', '회사', 'year', 'month', '반기', '분기', '항목']
            data_columns = [col for col in df_wide.columns if col not in meta_columns]
            df_long = df_wide.melt(
                id_vars=meta_columns,
                value_vars=data_columns,
                var_name='raw_metric_name',
                value_name='value'
            )
            
            # 컬럼명 파싱
            parsed_data = df_long['raw_metric_name'].apply(self._parse_segment_column_header)
            df_long[['segment_name', 'account_name', 'region', 'is_cumulative']] = pd.DataFrame(parsed_data.tolist(), index=df_long.index)
            
            # 데이터 정제
            df_long.dropna(subset=['segment_name', 'account_name', 'value'], inplace=True)
            
            # "합계", "전사", "본사" 등 집계 행 제외 (이미 전사 데이터에 있음)
            exclude_segments = ['합계', '전사', '본사', '계', '총계', 'Total']
            df_long = df_long[~df_long['segment_name'].isin(exclude_segments)]
            df_long['value'] = df_long['value'].apply(self._parse_numeric)
            df_long.dropna(subset=['value'], inplace=True)
            
            # [속도 개선] 0 값 필터링 (NULL로 간주)
            df_long = df_long[df_long['value'] != 0]
            
            # 회사 ID 매핑
            df_long['company_id'] = df_long['회사'].str.lower().map(mapper)
            df_long.dropna(subset=['company_id'], inplace=True)

            # [대폭 속도 개선] 배치 처리 (100개씩 - 메모리 안전)
            batch_size = 100
            total_rows = len(df_long)
            batches = [df_long.iloc[i:i+batch_size] for i in range(0, total_rows, batch_size)]
            
            print(f"      총 {total_rows:,}개 레코드를 {len(batches)}개 배치로 처리")
            
            for batch_idx, batch_df in enumerate(tqdm(batches, desc=f"     {file_info['file']}", unit=" batch")):
                batch_data = batch_df.to_dict('records')
                self._execute_write(
                    self._tx_process_segment_batch, 
                    batch_data=batch_data,
                    file_name=file_info['file'],
                    format_type=file_info.get('format', 'DEFAULT'),
                    target_company_override=file_info.get('target_company')
                )

    def _build_post_relations(self):
        """시간 계층 및 계획-실적 비교 관계를 구축합니다."""
        print("\n--- 6. 후처리 관계 구축 ---")
        self._execute_write(self._tx_build_post_relations)
        print("   - 완료: 시간 계층 및 기간 비교 관계가 생성되었습니다.")
        print("   - 완료: 계획-실적 비교 관계가 생성되었습니다.")
        
        # 추가: Company가 모든 하위 사업 부문에 직접 접근할 수 있도록 가상 관계 생성
        self._execute_write(self._tx_build_segment_shortcuts)
        print("   - 완료: 사업 부문 단축 관계가 생성되었습니다.")

    def _clean_column_name(self, col_name):
        """컬럼명의 공백을 정규화합니다."""
        return re.sub(r'\s+', ' ', col_name).strip()

    def _parse_numeric(self, value):
        """문자열 숫자를 float로 변환합니다."""
        if isinstance(value, str):
            try:
                return float(value.replace(",", ""))
            except (ValueError, AttributeError):
                return None
        return value if pd.notna(value) else None

    def _parse_segment_column_header(self, col_name):
        """
        사업별 손익 컬럼명을 파싱합니다.
        
        형식: "[사업부문명] [계정명] [누계] [(지역)]"
        예시:
        - "전력기기 매출액" → ("전력기기", "매출액", "전체", False)
        - "자동화기기 영업이익(국내)" → ("자동화기기", "영업이익", "국내", False)
        - "전력기기 매출액 누계" → ("전력기기", "매출액", "전체", True)
        - "자동화기기 영업이익 누계(해외)" → ("자동화기기", "영업이익", "해외", True)
        """
        # 1. 누계 여부 확인
        is_cumulative = '누계' in col_name
        work_str = col_name.replace('누계', '').strip()
        
        # 2. 지역 확인
        region = '전체'
        if work_str.endswith('(국내)'):
            region = '국내'
            work_str = work_str[:-4].strip()
        elif work_str.endswith('(해외)'):
            region = '해외'
            work_str = work_str[:-4].strip()
        
        # 3. 공백 정규화
        work_str = re.sub(r'\s+', ' ', work_str).strip()
        
        # 4. 사업부문과 계정 분리
        parts = work_str.split(' ')
        if len(parts) == 0:
            return None, None, None, False
        elif len(parts) == 1:
            # 계정명만 있는 경우 (사업 부문 없음) → '전사' 사업으로 간주
            return '전사', parts[0], region, is_cumulative
        else:
            # 마지막 단어가 계정명, 나머지가 사업 부문
            account_name = parts[-1]
            segment_name = ' '.join(parts[:-1])
            return segment_name, account_name, region, is_cumulative

    def _get_account_id_for_segment(self, account_name):
        """
        사업별 계정명을 기존 Account ID로 매핑합니다.
        매핑되지 않으면 새 ID를 생성합니다.
        """
        # config에 매핑 테이블이 있으면 사용
        mapping = self.config.get('segment_to_main_account_mapping', {})
        if account_name in mapping:
            return mapping[account_name]
        
        # 매핑되지 않으면 결정론적 ID 생성
        # 재실행 시에도 같은 ID 보장
        return f"segment_{account_name.replace(' ', '_')}"

    def _infer_cic_for_segment(self, company_id, segment_name):
        """
        사업 부문명을 보고 어느 CIC에 속하는지 추론합니다.
        ELECTRIC의 사업 부문을 전력CIC/자동화CIC로 자동 분류합니다.
        """
        cic_rules = self.config.get('business_rules', {}).get('cic_mapping_rules', {})
        
        if company_id not in cic_rules:
            return None
        
        # 사업 부문 키워드 매핑 (config에서 로드 가능하도록 확장 가능)
        segment_keywords = {
            "전력CIC": [
                # 기기 관련
                "전력기기", "배전기기", "저압기기", "고압기기", "계량기기", "계전기기",
                "개폐기", "개폐기기", "차단기", "배전반",
                # 대형 설비
                "PSC", "GIS", "초고압GIS", "변압기", "초고압TR", "HVDC", "HVDC Valve",
                # 시스템 및 기타
                "스카다", "ES 설비", "ES설비", "태양광시스템", "태양광기기", "태양광",
                "EV-Cordset", "DC-Relay", "ESS", "교통", "연료전지",
                # 일반 키워드
                "배전", "송전", "전력", "초고압", "수배전"
            ],
            "자동화CIC": [
                # 제품군
                "자동화기기", "PLC", "Inverter", "SERVO", "HMI", "MC",
                "MC(양산)", "모션",
                # 시스템
                "Auto System", "FA System", "Drive System", "자동화시스템",
                "ES 시스템", "ES시스템",
                # 기타
                "철도", "RFID", "Drive"
            ]
        }
        
        rule = cic_rules[company_id]
        target_cics = rule.get('target_cics', [])
        
        for cic_id in target_cics:
            keywords = segment_keywords.get(cic_id, [])
            # 부분 문자열 매칭
            if any(keyword in segment_name for keyword in keywords):
                return cic_id
        
        # 매핑 불가 시 본사(ELECTRIC)에 귀속
        return None

    def _tx_build_knowledge_layer(self, tx):
        """지식 레이어(개념, 규칙, 관계)를 구축합니다."""
        # 1. 차원 노드 생성
        for dim_key, dim_data in self.config['dimensions'].items():
            if not isinstance(dim_data, dict):
                continue
            for val in dim_data.get('values', []):
                tx.run(f"MERGE (d:{dim_data['label']} {{id: $val}})", val=val)

        # 2. 회사, CIC, 용어 생성
        for company_id, data in self.config['entities']['companies'].items():
            node_label = "CIC" if data.get('type') == 'CIC' else "Company"
            tx.run(
                f"MERGE (c:{node_label} {{id: $id}}) SET c.name = $name, c.official_name = $official_name, c.file_name_id = $file_name_id, c.available_data = $avail_data",
                id=company_id,
                name=data['official_name'],
                official_name=data['official_name'],
                file_name_id=data.get('file_name_id', company_id),
                avail_data=data.get('available_data', ['IS', 'BS'])
            )
            for alias in [data['official_name']] + data.get('aliases', []):
                tx.run(
                    f"MATCH (c:{node_label} {{id: $c_id}}) MERGE (t:Term {{value: $alias}}) MERGE (c)-[:ALSO_KNOWN_AS]->(t)",
                    c_id=company_id,
                    alias=alias
                )
            if data.get('parent_company'):
                tx.run(
                    "MATCH (child:CIC {id: $child_id}), (parent:Company {id: $parent_id}) MERGE (child)-[:PART_OF]->(parent)",
                    child_id=company_id,
                    parent_id=data['parent_company']
                )

        # 3. 회사 그룹 생성
        for group_id, data in self.config['business_rules']['company_groups'].items():
            tx.run("MERGE (cg:CompanyGroup {id: $id, name: $name})", id=group_id, name=data['name'])

        # 4. 계정, 용어, 계층 관계 생성
        for acc_id, data in self.config['entities']['accounts'].items():
            tx.run(
                "MERGE (a:Account {id: $id}) SET a.name=$name, a.category=$cat, a.aggregation=$agg, a.description=$desc",
                id=acc_id,
                name=data['official_name'],
                cat=data['category'],
                agg=data['aggregation'],
                desc=data['description']
            )
            for alias in [data['official_name']] + data.get('aliases', []):
                tx.run(
                    "MATCH (a:Account {id: $acc_id}) MERGE (t:Term {value: $alias}) MERGE (a)-[:ALSO_KNOWN_AS]->(t)",
                    acc_id=acc_id,
                    alias=alias
                )

        # 5. 계정 계층 관계 생성
        for parent_id, components in self.config['relationships']['account_hierarchy'].items():
            if not isinstance(components, list):
                continue
            for comp_data in components:
                tx.run(
                    "MATCH (p:Account {id: $p_id}), (c:Account {id: $c_id}) MERGE (p)-[r:SUM_OF {operation: $op}]->(c)",
                    p_id=parent_id,
                    c_id=comp_data['account_id'],
                    op=comp_data['operation']
                )
        
        # 6. 재무 비율, 관점, 필요 계정 관계 생성
        for vp_id, data in self.config['financial_ratios']['viewpoints'].items():
            tx.run("MERGE (av:AnalysisViewpoint {id: $id, name: $name})", id=vp_id, name=data['name'])
        
        for ratio_id, data in self.config['financial_ratios']['ratios'].items():
            tx.run(
                "MERGE (fr:FinancialRatio {id: $id}) SET fr.name = $name, fr.description = $desc, fr.type = $type, fr.unit = $unit",
                id=ratio_id,
                name=data['official_name'],
                desc=data['description'],
                type=data['type'],
                unit=data.get('unit')
            )
            tx.run(
                "MATCH (fr:FinancialRatio {id: $fr_id}), (av:AnalysisViewpoint {id: $av_id}) MERGE (fr)-[:PART_OF_VIEWPOINT]->(av)",
                fr_id=ratio_id,
                av_id=data['viewpoint']
            )
            if data.get('components'):
                for acc_id in data['components']:
                    tx.run(
                        "MATCH (fr:FinancialRatio {id: $fr_id}), (a:Account {id: $acc_id}) MERGE (fr)-[:REQUIRES_ACCOUNT]->(a)",
                        fr_id=ratio_id,
                        acc_id=acc_id
                    )

    def _tx_process_main_row(self, tx, row_data, account_columns, file_name):
        """메인 재무제표 데이터 행을 처리합니다."""
        company_id = row_data.get('company_id')
        if not company_id:
            return
        is_cic_row = row_data.get('CIC') == 'Y'
        
        # 컨텍스트 파싱
        year, month = int(row_data['year']), int(row_data['month'])
        type_str = 'IS' if 'IS' in row_data['계정'] else 'BS'
        scope_str = 'CONSOLIDATED' if '연결' in row_data['계정'] else 'SEPARATE'
        class_str = 'ACTUAL' if row_data['항목'] == '실적' else 'PLAN'
        fs_id = f"{company_id}_{year}{month:02d}_{type_str}_{scope_str}_{class_str}"
        period_id = f"{year}{month:02d}"

        # FinancialStatement 및 차원 연결
        tx.run("""
            MATCH (dim_type:StatementType {id: $stmt_type})
            MATCH (dim_scope:StatementScope {id: $stmt_scope})
            MATCH (dim_class:DataClass {id: $stmt_class})
            MERGE (p:Period {id: $pid}) ON CREATE SET p.year = $year, p.month = $month
            MERGE (fs:FinancialStatement {id: $fsid})
            WITH fs, p, dim_type, dim_scope, dim_class, $cid AS cid
            MATCH (c) WHERE c.id = cid AND (c:Company OR c:CIC)
            MERGE (c)-[:HAS_STATEMENT]->(fs)
            MERGE (fs)-[:FOR_PERIOD]->(p)
            MERGE (fs)-[:HAS_TYPE]->(dim_type)
            MERGE (fs)-[:HAS_SCOPE]->(dim_scope)
            MERGE (fs)-[:HAS_CLASS]->(dim_class)
        """, cid=company_id, pid=period_id, year=year, month=month, fsid=fs_id,
             stmt_type=type_str, stmt_scope=scope_str, stmt_class=class_str)
        
        # 그룹 관계 연결
        if not is_cic_row:
            for group_id, data in self.config['business_rules']['company_groups'].items():
                if data.get('aliases') and len(data['aliases']) > 0:
                    if row_data.get(data['aliases'][0]) == 'Y':
                        tx.run(
                            "MATCH (c:Company {id: $cid}), (cg:CompanyGroup {id: $gid}) MERGE (c)-[:MEMBER_OF]->(cg)",
                            cid=company_id,
                            gid=group_id
                        )

        # Metric 및 ValueObservation 생성
        metrics_to_create = []
        for col_name in account_columns:
            value = self._parse_numeric(row_data.get(col_name))
            # [속도 개선] 0 값 필터링 (NULL로 간주)
            if value is not None and value != 0:
                metrics_to_create.append({"acc_id": col_name, "value": value})
        
        if metrics_to_create:
            tx.run("""
                MATCH (fs:FinancialStatement {id: $fsid})
                UNWIND $metrics AS m_data
                MATCH (a:Account {id: m_data.acc_id})
                MERGE (m:Metric {id: $fsid + '_' + m_data.acc_id})
                CREATE (v:ValueObservation {value: m_data.value, source_file: $fname, timestamp: datetime()})
                MERGE (fs)-[:CONTAINS]->(m)
                MERGE (m)-[:INSTANCE_OF_RULE]->(a)
                MERGE (m)-[:HAS_OBSERVATION]->(v)
            """, fsid=fs_id, metrics=metrics_to_create, fname=file_name)

        # 데이터 레벨 계산 관계 구축
        for parent_id, components in self.config['relationships']['account_hierarchy'].items():
            if not isinstance(components, list):
                continue
            tx.run("""
                WITH $fsid AS fsid, $parent_id AS parent_id, $components AS components
                OPTIONAL MATCH (parent_metric:Metric {id: fsid + '_' + parent_id})
                WITH parent_metric, fsid, components
                WHERE parent_metric IS NOT NULL
                UNWIND components AS comp
                OPTIONAL MATCH (child_metric:Metric {id: fsid + '_' + comp.account_id})
                WITH parent_metric, child_metric, comp
                WHERE child_metric IS NOT NULL
                MERGE (parent_metric)-[r:SUM_OF {operation: comp.operation}]->(child_metric)
            """, fsid=fs_id, parent_id=parent_id, components=components)

        # KPI 파생 관계 구축
        for ratio_id, data in self.config['financial_ratios']['ratios'].items():
            if data['type'] == 'STORED':
                tx.run("""
                    WITH $fsid AS fsid, $source_acc AS source_acc, $components AS components
                    OPTIONAL MATCH (kpi_metric:Metric {id: fsid + '_' + source_acc})
                    WITH kpi_metric, fsid, components
                    WHERE kpi_metric IS NOT NULL
                    UNWIND components AS comp_id
                    OPTIONAL MATCH (comp_metric:Metric {id: fsid + '_' + comp_id})
                    WITH kpi_metric, comp_metric
                    WHERE comp_metric IS NOT NULL
                    MERGE (kpi_metric)-[:DERIVED_FROM]->(comp_metric)
                """, fsid=fs_id, source_acc=data['source_account'], components=data.get('related_accounts_for_context', []))
    
    def _tx_process_segment_batch(self, tx, batch_data, file_name, format_type='DEFAULT', target_company_override=None):
        """사업별 손익 데이터 배치를 처리합니다 (속도 개선)"""
        if not batch_data:
            return
        
        # 배치 데이터 전처리
        processed_batch = []
        
        for row_data in batch_data:
            company_id = row_data['company_id']
            year, month = int(row_data['year']), int(row_data['month'])
            segment_name = row_data['segment_name']
            account_name = row_data['account_name']
            region = row_data['region']
            is_cumulative = row_data['is_cumulative']
            value = row_data['value']
            
            # 사업별 손익은 항상 별도(SEPARATE) 재무제표 기준이며, 손익계산서(IS)입니다.
            scope_str, type_str = 'SEPARATE', 'IS'
            class_str = 'ACTUAL' if row_data['항목'] == '실적' else 'PLAN'
            fs_id = f"{company_id}_{year}{month:02d}_{type_str}_{scope_str}_{class_str}"
            
            # CIC 매핑 로직
            target_company_id = company_id
            
            if format_type == 'CIC_DIRECT' and target_company_override:
                target_company_id = target_company_override
                fs_id = f"{target_company_id}_{year}{month:02d}_{type_str}_{scope_str}_{class_str}"
            elif company_id == "ELECTRIC" and format_type == 'ELECTRIC_CIC':
                inferred_cic = self._infer_cic_for_segment(company_id, segment_name)
                if inferred_cic:
                    target_company_id = inferred_cic
                    fs_id = f"{target_company_id}_{year}{month:02d}_{type_str}_{scope_str}_{class_str}"
            
            # Account ID 매핑
            account_id = self._get_account_id_for_segment(account_name)
            
            # BusinessSegment ID
            segment_id = f"{target_company_id}_{segment_name.replace(' ', '_')}"
            
            # Metric ID
            metric_id = f"{fs_id}_{segment_name}_{account_name}"
            
            # ValueObservation ID
            value_obs_id = f"{metric_id}_{region}"
            
            # Period ID
            period_id = f"{year}{month:02d}"
            
            processed_batch.append({
                'aid': account_id,
                'aname': account_name,
                'target_cid': target_company_id,
                'fsid': fs_id,
                'pid': period_id,
                'year': year,
                'month': month,
                'seg_id': segment_id,
                'seg_name': segment_name,
                'mid': metric_id,
                'vid': value_obs_id,
                'region': region,
                'is_cumulative': is_cumulative,
                'value': value,
                'fname': file_name
            })
        
        # Account 노드 먼저 생성 (segment_ 접두사인 것들)
        unique_accounts = {item['aid']: item['aname'] for item in processed_batch if item['aid'].startswith('segment_')}
        if unique_accounts:
            tx.run("""
                UNWIND $accounts AS acc
                MERGE (a:Account {id: acc.id})
                ON CREATE SET 
                    a.name = acc.name,
                    a.category = 'SEGMENT_IS',
                    a.aggregation = 'SUM',
                    a.official_name = acc.name,
                    a.description = '사업별 손익에서 자동 생성된 계정입니다.'
            """, accounts=[{'id': aid, 'name': aname} for aid, aname in unique_accounts.items()])
        
        # 배치 데이터 일괄 처리 (UNWIND 사용)
        tx.run("""
            UNWIND $batch AS item
            
            MATCH (a:Account {id: item.aid})
            MATCH (c) WHERE c.id = item.target_cid AND (c:Company OR c:CIC)
            
            MERGE (fs:FinancialStatement {id: item.fsid})
            MERGE (bs:BusinessSegment {id: item.seg_id})
            ON CREATE SET bs.name = item.seg_name, bs.company_id = item.target_cid
            
            MERGE (p:Period {id: item.pid})
            ON CREATE SET p.year = item.year, p.month = item.month
            
            MERGE (bs)-[:PART_OF]->(c)
            MERGE (m:Metric {id: item.mid})
            MERGE (v:ValueObservation {id: item.vid})
            ON CREATE SET 
                v.metric_id = item.mid,
                v.region = item.region,
                v.source_file = item.fname,
                v.timestamp = datetime()
            SET v += CASE WHEN item.is_cumulative THEN {cumulative_value: item.value} ELSE {value: item.value} END
            
            MERGE (fs)-[:CONTAINS]->(m)
            MERGE (fs)-[:FOR_PERIOD]->(p)
            MERGE (m)-[:INSTANCE_OF_RULE]->(a)
            MERGE (m)-[:HAS_OBSERVATION]->(v)
            MERGE (m)-[:FOR_SEGMENT]->(bs)
        """, batch=processed_batch)
    
    def _tx_process_segment_row(self, tx, row_data, file_name, format_type='DEFAULT', target_company_override=None):
        """사업별 손익 데이터 행을 처리합니다."""
        company_id = row_data['company_id']
        year, month = int(row_data['year']), int(row_data['month'])
        segment_name = row_data['segment_name']
        account_name = row_data['account_name']
        region = row_data['region']
        is_cumulative = row_data['is_cumulative']
        value = row_data['value']
        
        # 사업별 손익은 항상 별도(SEPARATE) 재무제표 기준이며, 손익계산서(IS)입니다.
        scope_str, type_str = 'SEPARATE', 'IS'
        class_str = 'ACTUAL' if row_data['항목'] == '실적' else 'PLAN'
        fs_id = f"{company_id}_{year}{month:02d}_{type_str}_{scope_str}_{class_str}"
        
        # CIC 매핑 로직
        target_company_id = company_id
        
        if format_type == 'CIC_DIRECT' and target_company_override:
            # CIC 전용 파일 (사업별손익_LS일렉트릭_전력CIC.csv 등)
            # 이 파일의 모든 사업 부문은 해당 CIC에 직접 귀속
            target_company_id = target_company_override
            fs_id = f"{target_company_id}_{year}{month:02d}_{type_str}_{scope_str}_{class_str}"
        elif company_id == "ELECTRIC" and format_type == 'ELECTRIC_CIC':
            # ELECTRIC 통합 파일 → 키워드로 CIC 추론
            inferred_cic = self._infer_cic_for_segment(company_id, segment_name)
            if inferred_cic:
                target_company_id = inferred_cic
                # CIC의 FinancialStatement ID로 변경
                fs_id = f"{target_company_id}_{year}{month:02d}_{type_str}_{scope_str}_{class_str}"
        
        # Account ID 매핑 (기존 Account 활용 또는 신규 생성)
        account_id = self._get_account_id_for_segment(account_name)
        
        # Account가 없으면 생성 (기존 Account에 없는 사업별 전용 계정)
        if account_id.startswith('segment_'):
            tx.run("""
                MERGE (a:Account {id: $aid})
                ON CREATE SET 
                    a.name = $aname,
                    a.category = 'SEGMENT_IS',
                    a.aggregation = 'SUM',
                    a.official_name = $aname,
                    a.description = '사업별 손익에서 자동 생성된 계정입니다.'
            """, aid=account_id, aname=account_name)
        
        # BusinessSegment ID: 회사별 고유성 확보
        segment_id = f"{target_company_id}_{segment_name.replace(' ', '_')}"
        
        # Metric ID: FS + Segment + Account
        metric_id = f"{fs_id}_{segment_name}_{account_name}"
        
        # ValueObservation ID: region만 포함 (하나의 노드에 value + cumulative_value 저장)
        value_obs_id = f"{metric_id}_{region}"
        
        # Period ID 생성
        period_id = f"{year}{month:02d}"
        
        # 그래프 구축
        tx.run("""
            MATCH (a:Account {id: $aid})
            MATCH (c) WHERE c.id = $target_cid AND (c:Company OR c:CIC)
            MERGE (fs:FinancialStatement {id: $fsid})
            MERGE (bs:BusinessSegment {id: $seg_id})
            ON CREATE SET bs.name = $seg_name, bs.company_id = $target_cid
            
            MERGE (p:Period {id: $pid})
            ON CREATE SET p.year = $year, p.month = $month
            
            MERGE (bs)-[:PART_OF]->(c)
            MERGE (m:Metric {id: $mid})
            MERGE (v:ValueObservation {id: $vid})
            ON CREATE SET 
                v.metric_id = $mid,
                v.region = $region,
                v.source_file = $fname,
                v.timestamp = datetime()
            SET v += CASE WHEN $is_cumulative THEN {cumulative_value: $value} ELSE {value: $value} END
            
            MERGE (fs)-[:CONTAINS]->(m)
            MERGE (fs)-[:FOR_PERIOD]->(p)
            MERGE (m)-[:INSTANCE_OF_RULE]->(a)
            MERGE (m)-[:HAS_OBSERVATION]->(v)
            MERGE (m)-[:FOR_SEGMENT]->(bs)
        """,
            aid=account_id,
            target_cid=target_company_id,
            fsid=fs_id,
            pid=period_id,
            year=year,
            month=month,
            seg_id=segment_id,
            seg_name=segment_name,
            mid=metric_id,
            vid=value_obs_id,
            region=region,
            is_cumulative=is_cumulative,
            value=value,
            fname=file_name
        )

    def _tx_build_segment_shortcuts(self, tx):
        """
        Company와 CIC가 모든 하위 BusinessSegment에 직접 접근할 수 있도록
        단축 관계(:HAS_ALL_SEGMENTS)를 생성합니다.
        
        예: ELECTRIC -[:HAS_ALL_SEGMENTS]-> "저압기기"
            전력CIC -[:HAS_ALL_SEGMENTS]-> "저압기기"
        """
        # Company의 HAS_ALL_SEGMENTS 관계
        tx.run("""
            MATCH (company:Company)
            
            // 본사 직속 사업 부문
            OPTIONAL MATCH (company)<-[:PART_OF]-(bs_direct:BusinessSegment)
            WHERE NOT (bs_direct)<-[:PART_OF]-(:CIC)
            
            // CIC 소속 사업 부문
            OPTIONAL MATCH (company)<-[:PART_OF]-(cic:CIC)<-[:PART_OF]-(bs_cic:BusinessSegment)
            
            WITH company, collect(DISTINCT bs_direct) + collect(DISTINCT bs_cic) AS all_segments
            UNWIND all_segments AS bs
            WITH company, bs
            WHERE bs IS NOT NULL
            
            MERGE (company)-[:HAS_ALL_SEGMENTS]->(bs)
        """)
        
        # CIC의 HAS_ALL_SEGMENTS 관계 추가
        tx.run("""
            MATCH (cic:CIC)<-[:PART_OF]-(bs:BusinessSegment)
            MERGE (cic)-[:HAS_ALL_SEGMENTS]->(bs)
        """)

    def _tx_build_post_relations(self, tx):
        """후처리 관계(시간 계층, 계획-실적 비교)를 구축합니다."""
        # 1. 시간 계층 생성
        tx.run("""
            MATCH (p:Period)
            WITH p, p.year AS year, toInteger((p.month - 1) / 3) + 1 AS quarter, toInteger((p.month - 1) / 6) + 1 AS half
            MERGE (y:Year {year: year})
            MERGE (h:HalfYear {id: toString(year) + '-H' + toString(half)})
            MERGE (q:Quarter {id: toString(year) + '-Q' + toString(quarter)})
            MERGE (h)-[:PART_OF]->(y)
            MERGE (q)-[:PART_OF]->(h)
            MERGE (p)-[:PART_OF]->(q)
        """)
        
        # 2. 순차 관계 생성 (:PREVIOUS)
        for label in ["Period", "Quarter", "HalfYear", "Year"]:
            id_prop = "id" if label != "Year" else "year"
            tx.run(f"""
                MATCH (n:{label})
                WITH n ORDER BY n.{id_prop}
                WITH collect(n) as nodes
                UNWIND range(1, size(nodes) - 1) as i
                WITH nodes[i] as current, nodes[i-1] as prev
                MERGE (current)-[:PREVIOUS]->(prev)
            """)

        # 3. 전년 동기 관계 생성 (:PRIOR_YEAR_EQUIV)
        tx.run("""
            MATCH (p1:Period), (p2:Period)
            WHERE p2.year = p1.year - 1 AND p2.month = p1.month
            MERGE (p1)-[:PRIOR_YEAR_EQUIV]->(p2)
        """)
        
        tx.run("""
            MATCH (q1:Quarter), (q2:Quarter)
            WITH q1, q2, toInteger(substring(q1.id, 0, 4)) AS year1, substring(q1.id, 5) AS q_id1,
                 toInteger(substring(q2.id, 0, 4)) AS year2, substring(q2.id, 5) AS q_id2
            WHERE year2 = year1 - 1 AND q_id2 = q_id1
            MERGE (q1)-[:PRIOR_YEAR_EQUIV]->(q2)
        """)
        
        tx.run("""
            MATCH (h1:HalfYear), (h2:HalfYear)
            WITH h1, h2, toInteger(substring(h1.id, 0, 4)) AS year1, substring(h1.id, 5) AS h_id1,
                 toInteger(substring(h2.id, 0, 4)) AS year2, substring(h2.id, 5) AS h_id2
            WHERE year2 = year1 - 1 AND h_id2 = h_id1
            MERGE (h1)-[:PRIOR_YEAR_EQUIV]->(h2)
        """)
        
        # 4. 계획-실적 관계 생성 (:COMPARISON_FOR)
        config = self.config['relationships']['contextual_relationships']['PLAN_VS_ACTUAL']
        tx.run(f"""
            MATCH (c) WHERE c:Company OR c:CIC
            MATCH (c)-[:HAS_STATEMENT]->(fs_from:FinancialStatement)-[:HAS_CLASS]->(:DataClass {{id: '{config['direction']['from_id']}'}})
            MATCH (c)-[:HAS_STATEMENT]->(fs_to:FinancialStatement)-[:HAS_CLASS]->(:DataClass {{id: '{config['direction']['to_id']}'}})
            MATCH (fs_from)-[:FOR_PERIOD]->(p:Period)
            MATCH (fs_to)-[:FOR_PERIOD]->(p)
            MERGE (fs_from)-[:{config['relationship_type']}]->(fs_to)
        """)

if __name__ == "__main__":
    etl = None
    try:
        print("\n" + "="*70)
        print("  GMIS Knowledge Graph ETL Pipeline v5 Final")
        print("  - Main Data (IS/BS 연결/별도)")
        print("  - Segment Data (사업별 손익)")
        print("="*70)
        
        print("\n--- 설정 파일 로드 ---")
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        print(f"   - 완료: {CONFIG_FILE} 파일을 성공적으로 로드했습니다.")
        
        etl = GMISKnowledgeGraphETL(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, config=config_data)
        etl.run_etl_pipeline(clear_db=True)
        
    except FileNotFoundError as e:
        print(f"[ERROR] 오류: 설정 파일 '{CONFIG_FILE}'을 찾을 수 없습니다.")
        print(f"        스크립트와 동일한 디렉토리에 있는지 확인하세요.")
    except Exception as e:
        print(f"\n[ERROR] 예상치 못한 오류 발생: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if etl is not None:
            etl.close()

