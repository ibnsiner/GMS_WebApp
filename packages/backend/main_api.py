# GMS_WebApp/packages/backend/main_api.py

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid
import json
from datetime import datetime
from neo4j import GraphDatabase

# 에이전트 코드를 import 합니다.
from agent import GmisAgentV4

# Neo4j 연결 설정
NEO4J_URI = "bolt://127.0.0.1:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "vlvmffoq1!"

app = FastAPI()

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

agents = {}

class ChatRequest(BaseModel):
    sessionId: str | None = None
    query: str

def get_segment_structure_from_neo4j():
    """Neo4j에서 동적으로 사업 구조를 조회합니다"""
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        session = driver.session()
        
        # 회사별 사업 구조 조회
        query = """
        // 1. 사업별 손익 데이터가 있는 최상위 회사만 조회 (CIC 제외)
        MATCH (company:Company)
        OPTIONAL MATCH (company)-[:HAS_ALL_SEGMENTS]->(bs:BusinessSegment)
        WITH company, collect(DISTINCT bs.name) as direct_segments
        WHERE size(direct_segments) > 0
        
        // 2. 하위 CIC 조회 (전력CIC, 자동화CIC 등)
        OPTIONAL MATCH (company)<-[:PART_OF]-(cic:CIC)-[:HAS_ALL_SEGMENTS]->(cic_bs:BusinessSegment)
        WITH company, direct_segments, 
             cic, collect(DISTINCT cic_bs.name) as cic_segments
        
        // 3. CIC별로 그룹화
        WITH company, direct_segments,
             collect(CASE 
                WHEN cic IS NOT NULL AND size(cic_segments) > 0 
                THEN {id: cic.id, name: cic.official_name, segments: cic_segments}
                ELSE null
             END) as all_cics
        
        // 4. null 제거
        WITH company, direct_segments,
             [cic IN all_cics WHERE cic IS NOT NULL] as filtered_cics
        
        RETURN 
            company.id as company_id,
            company.official_name as company_name,
            CASE 
                // ELECTRIC의 경우: CIC가 있으면 직접 사업 목록 숨김
                WHEN company.id = 'ELECTRIC' AND size(filtered_cics) > 0 THEN []
                // 다른 회사: 직접 사업 목록 표시
                ELSE direct_segments
            END as segments,
            filtered_cics as cics
        ORDER BY company.id
        """
        
        result = session.run(query)
        records = list(result)
        
        # 결과를 직접 변환
        company_structure = []
        
        for record in records:
            company_id = record['company_id']
            company_name = record['company_name']
            segments = record['segments']
            cics_raw = record['cics']
            
            # 표시명 정리 (별도, 연결 등 제거)
            display_name = company_name.replace('(별도)', '').replace('(연결)', '').strip()
            
            # CIC 필터링 (null 제외)
            cics_filtered = [
                {
                    "id": cic['id'],
                    "name": cic['name'],
                    "segments": cic['segments']
                }
                for cic in cics_raw 
                if cic['id'] is not None and len(cic['segments']) > 0
            ]
            
            company_structure.append({
                "id": company_id,
                "name": display_name,
                "type": "company",
                "cics": cics_filtered,
                "segments": segments
            })
        
        session.close()
        driver.close()
        
        # 순서 지정: LS전선, LS ELECTRIC, LS MnM, LS엠트론
        order = ['LSCNS_S', 'ELECTRIC', 'MnM', '엠트론']
        company_structure.sort(key=lambda x: order.index(x['id']) if x['id'] in order else 999)
        
        return company_structure
        
    except Exception as e:
        print(f"Neo4j 조회 오류: {e}")
        import traceback
        traceback.print_exc()
        return []

def parse_config_for_menu():
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # Company items
    companies = [
        {"id": cid, "name": cdata["official_name"]} 
        for cid, cdata in config["entities"]["companies"].items() if cdata.get("type") != "CIC"
    ]
    
    # Group financial accounts by category
    accounts_by_category = {}
    for aid, adata in config["entities"]["accounts"].items():
        category = adata.get("category", "기타")
        
        # 기타(ETC) 카테고리는 제외
        if category == "ETC":
            continue
            
        category_name_map = {
            "IS": "손익계산서 (IS)",
            "BS": "재무상태표 (BS)",
            "KPI": "관리지표",
            "EXTERNAL_FACTOR": "외부요인"
        }
        category_display = category_name_map.get(category, category)
        
        if category_display not in accounts_by_category:
            accounts_by_category[category_display] = []
        
        accounts_by_category[category_display].append({
            "id": aid,
            "name": adata["official_name"]
        })
    
    # Build financial accounts as sub-categories (순서 지정)
    category_order = ["손익계산서 (IS)", "재무상태표 (BS)", "관리지표", "외부요인"]
    financial_account_items = []
    
    for category_name in category_order:
        if category_name in accounts_by_category:
            financial_account_items.append({
                "name": category_name,
                "sub_items": accounts_by_category[category_name]
            })
    
    # Neo4j에서 사업 구조 조회
    segment_structure = get_segment_structure_from_neo4j()
    
    # Build menu structure matching frontend types
    menu = [
        {
            "category": "회사",
            "type": "company",
            "items": companies
        },
        {
            "category": "재무계정",
            "type": "account",
            "items": financial_account_items
        },
        {
            "category": "사업",
            "type": "segment",
            "items": segment_structure
        }
    ]

    return {"menu": menu}

@app.get("/api/knowledge-menu")
def get_knowledge_menu():
    return parse_config_for_menu()

@app.post("/api/chat")
async def handle_chat(request: ChatRequest):
    session_id = request.sessionId
    
    # 세션이 없거나 agents 딕셔너리에 없으면 새로 생성
    if not session_id or session_id not in agents:
        session_id = str(uuid.uuid4())
        agents[session_id] = GmisAgentV4(session_id=session_id)
        print(f"새로운 세션 시작: {session_id}")

    agent = agents[session_id]
    
    # Agent의 구조화된 출력 메서드 호출
    agent_response_content = agent.run_and_get_structured_output(request.query)

    # 프론트엔드 타입에 맞게 응답 반환
    return {
        "id": f"msg-agent-{uuid.uuid4()}",
        "author": "agent",  # 프론트엔드 타입과 일치
        "content": agent_response_content,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "sessionId": session_id  # 세션 ID를 프론트엔드에 전달
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

