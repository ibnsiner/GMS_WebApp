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
    
    companies = [
        {"id": cid, "name": cdata["official_name"], "description": ""} 
        for cid, cdata in config["entities"]["companies"].items() if cdata.get("type") != "CIC"
    ]
    
    financial_accounts = [
        {"id": aid, "name": adata["aliases"][0] if adata.get("aliases") else adata["official_name"], "category": adata["category"], "description": adata.get("description", "")}
        for aid, adata in config["entities"]["accounts"].items()
    ]

    return {
        "companies": companies,
        "financialAccounts": financial_accounts,
        "businessSegments": []
    }

@app.get("/api/knowledge-menu")
def get_knowledge_menu():
    return parse_config_for_menu()

@app.post("/api/chat")
async def handle_chat(request: ChatRequest):
    # 이 부분은 추후 Agent 로직과 연동하여 완성합니다.
    session_id = request.sessionId or str(uuid.uuid4())
    
    # 임시 응답 (향후 실제 Agent 로직으로 교체)
    return {
        "id": f"msg-agent-{uuid.uuid4()}",
        "role": "assistant",
        "content": [{"type": "text", "content": f"Received query for session {session_id}: {request.query}"}],
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

