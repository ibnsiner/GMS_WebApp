# GMS WebApp - 경영정보 분석 시스템

GMIS(Group Management Information System) 웹 애플리케이션 모노레포입니다.

## 📁 프로젝트 구조

```
GMS_WebApp/
├── packages/           # 애플리케이션 패키지
│   ├── frontend/      # Next.js 프론트엔드
│   └── backend/       # FastAPI 백엔드
├── scripts/           # 개발 및 운영 스크립트
│   ├── etl.py        # ETL 파이프라인
│   └── test_*.py     # 테스트 스크립트
├── data/              # 데이터 파일
├── docs/              # 문서
│   └── segment_descriptions/  # 사업별 설명
└── .gitignore         # Git 제외 파일 설정
```

## 🚀 시작하기

### Backend 설정

```bash
cd packages/backend
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
python main_api.py
```

### Frontend 설정

```bash
cd packages/frontend
pnpm install
pnpm dev
```

## 📚 문서

상세 문서는 `docs/` 폴더를 참고하세요.

- [README.md](docs/README.md) - 전체 프로젝트 개요
- [TECHNICAL_DOCUMENTATION.md](docs/TECHNICAL_DOCUMENTATION.md) - 기술 문서
- [CHANGELOG.md](docs/CHANGELOG.md) - 변경 이력

## 🛠️ 주요 기능

- **지식 그래프 기반 재무 분석**: Neo4j 기반 지식 그래프
- **LLM 에이전트**: Google Gemini를 활용한 자연어 쿼리
- **대화형 인터페이스**: Next.js 기반 채팅 UI
- **시각화**: 차트 및 테이블 기반 데이터 시각화

