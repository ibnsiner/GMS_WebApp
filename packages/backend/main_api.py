# GMS_WebApp/packages/backend/main_api.py

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid
import json
from datetime import datetime

# 에이전트 코드를 import 합니다.
from agent import GmisAgentV4

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
        category_name_map = {
            "IS": "손익계산서 (IS)",
            "BS": "재무상태표 (BS)",
            "KPI": "관리지표",
            "EXTERNAL_FACTOR": "외부요인",
            "ETC": "기타"
        }
        category_display = category_name_map.get(category, category)
        
        if category_display not in accounts_by_category:
            accounts_by_category[category_display] = []
        
        accounts_by_category[category_display].append({
            "id": aid,
            "name": adata["aliases"][0] if adata.get("aliases") else adata["official_name"]
        })
    
    # Build financial accounts as sub-categories
    financial_account_items = [
        {
            "name": category_name,
            "sub_items": items
        }
        for category_name, items in accounts_by_category.items()
    ]
    
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
            "items": []
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

