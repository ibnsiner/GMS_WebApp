# GMIS Agent - 프로젝트 구조 요약

## 프로젝트 개요

**GMIS Agent**는 HR/Business Intelligence 팀을 위한 AI 기반 데이터 분석 챗봇 UI입니다. 사용자가 자연어로 복잡한 데이터를 질의하고, 대화형 인터페이스를 통해 테이블과 차트로 시각화된 결과를 받을 수 있습니다.

### 핵심 기능
- 3단 컬럼 레이아웃 (채팅 히스토리 | 채팅 영역 | Knowledge Base)
- 접을 수 있는 왼쪽 사이드바
- 대화형 데이터 테이블 (정렬, CSV 다운로드)
- 인터랙티브 차트 (PNG 다운로드)
- Knowledge Base 탐색 (회사, 재무계정, 사업 정보)
- 다크/라이트 모드 지원
- 마크다운 렌더링

---

## 기술 스택

- **프레임워크**: Next.js 16 (App Router)
- **언어**: TypeScript
- **스타일링**: Tailwind CSS v4
- **UI 컴포넌트**: shadcn/ui
- **차트**: Recharts
- **폰트**: Noto Sans KR (Google Fonts)
- **아이콘**: lucide-react

---

## 프로젝트 구조

\`\`\`
gmis-agent/
├── app/
│   ├── layout.tsx              # 루트 레이아웃, 폰트 설정
│   ├── page.tsx                # 메인 페이지, 상태 관리
│   ├── globals.css             # 전역 스타일, 디자인 토큰
│   └── providers.tsx           # 테마 프로바이더
│
├── components/
│   ├── chat/                   # 채팅 관련 컴포넌트
│   │   ├── chat-area.tsx       # 채팅 영역 컨테이너
│   │   ├── chat-header.tsx     # 채팅 헤더 (GMIS Agent 설명)
│   │   ├── chat-input.tsx      # 메시지 입력 폼
│   │   ├── message-stream.tsx  # 메시지 스트림 렌더러
│   │   ├── text-block.tsx      # 텍스트 메시지 블록
│   │   ├── interactive-table.tsx  # 정렬/다운로드 가능한 테이블
│   │   ├── interactive-chart.tsx  # 다운로드 가능한 차트
│   │   ├── agent-response-renderer.tsx  # AI 응답 렌더러
│   │   └── welcome-screen.tsx  # 웰컴 화면 (미사용)
│   │
│   ├── sidebar/                # 사이드바 관련 컴포넌트
│   │   ├── left-sidebar.tsx    # 왼쪽 사이드바 (채팅 히스토리)
│   │   ├── right-sidebar.tsx   # 오른쪽 사이드바 (Knowledge Base)
│   │   ├── sidebar-header.tsx  # 사이드바 헤더
│   │   ├── chat-history-list.tsx  # 채팅 히스토리 목록
│   │   ├── knowledge-menu.tsx  # Knowledge Base 아코디언 메뉴
│   │   └── sidebar-footer.tsx  # 사이드바 푸터 (미사용)
│   │
│   ├── ui/                     # shadcn/ui 컴포넌트
│   │   ├── button.tsx
│   │   ├── card.tsx
│   │   ├── accordion.tsx
│   │   ├── input.tsx
│   │   └── ... (기타 UI 컴포넌트)
│   │
│   └── theme-provider.tsx      # 다크/라이트 모드 프로바이더
│
├── lib/
│   ├── types.ts                # TypeScript 타입 정의
│   ├── mock-data.ts            # 목 데이터 (채팅 히스토리, Knowledge Base)
│   └── utils.ts                # 유틸리티 함수 (cn)
│
└── public/                     # 정적 파일
\`\`\`

---

## 주요 컴포넌트 설명

### 1. **app/page.tsx**
- 애플리케이션의 메인 페이지
- 전역 상태 관리 (메시지, 테마, 사이드바 접기 상태)
- 3단 컬럼 레이아웃 구성
- 메시지 전송 핸들러

### 2. **components/sidebar/left-sidebar.tsx**
- 왼쪽 사이드바 컴포넌트
- 채팅 히스토리 목록 표시
- 접기/펼치기 기능 (ChevronLeft/ChevronRight 아이콘)
- 새 채팅 시작 버튼

### 3. **components/sidebar/right-sidebar.tsx**
- 오른쪽 사이드바 컴포넌트
- Knowledge Base 설명 및 메뉴 표시
- 회사, 재무계정, 사업 정보 아코디언

### 4. **components/chat/chat-area.tsx**
- 중앙 채팅 영역 컨테이너
- 채팅 헤더, 메시지 스트림, 입력 폼 포함
- 메시지가 없을 때 GMIS Agent 설명 표시

### 5. **components/chat/message-stream.tsx**
- 메시지 목록 렌더링
- 사용자/AI 메시지 구분
- 텍스트, 테이블, 차트 블록 렌더링

### 6. **components/chat/interactive-table.tsx**
- 정렬 가능한 데이터 테이블
- CSV 다운로드 기능
- 컬럼 헤더 클릭으로 정렬

### 7. **components/chat/interactive-chart.tsx**
- Recharts 기반 차트 컴포넌트
- PNG 다운로드 기능
- 반응형 디자인

### 8. **components/sidebar/knowledge-menu.tsx**
- 아코디언 기반 Knowledge Base 메뉴
- 회사, 재무계정, 사업 카테고리
- 각 항목 클릭 시 상세 정보 표시

---

## 데이터 구조

### ChatMessage (lib/types.ts)
\`\`\`typescript
interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: MessageBlock[]
  timestamp: Date
}

interface MessageBlock {
  type: 'text' | 'table' | 'chart'
  content: string | TableData | ChartData
}
\`\`\`

### KnowledgeMenu (lib/types.ts)
\`\`\`typescript
interface KnowledgeMenu {
  companies: Company[]
  financialAccounts: FinancialAccount[]
  businessSegments: BusinessSegment[]
}

interface Company {
  id: string
  name: string
  description: string
}

interface FinancialAccount {
  id: string
  name: string
  category: string
  description: string
}

interface BusinessSegment {
  id: string
  name: string
  description: string
}
\`\`\`

---

## 디자인 시스템

### 색상 (app/globals.css)
- **Primary**: Blue 계열 (#3b82f6)
- **Background**: White (라이트 모드) / Dark Gray (다크 모드)
- **Foreground**: Black (라이트 모드) / White (다크 모드)
- **Muted**: Gray 계열
- **Accent**: Blue 계열

### 타이포그래피
- **폰트**: Noto Sans KR (Google Fonts)
- **헤딩**: font-sans, font-semibold/font-bold
- **본문**: font-sans, text-sm/text-base

### 레이아웃
- **3단 컬럼**: 왼쪽 사이드바 (256px) | 중앙 채팅 (flex-1) | 오른쪽 사이드바 (320px)
- **접힌 왼쪽 사이드바**: 0px (완전히 숨김)
- **반응형**: 모바일에서는 단일 컬럼

### 간격
- **컨테이너 패딩**: p-4, p-6
- **요소 간격**: gap-2, gap-4, gap-6
- **섹션 간격**: mb-4, mb-6

---

## 주요 기능 구현

### 1. 사이드바 접기/펼치기
- `isLeftSidebarCollapsed` 상태로 관리
- 버튼은 사이드바 외부에 절대 위치 (항상 표시)
- Tailwind의 `transition-all duration-300`으로 부드러운 애니메이션

### 2. 다크/라이트 모드
- `next-themes` 라이브러리 사용
- `theme-provider.tsx`로 전역 테마 관리
- 채팅 입력창 왼쪽에 토글 버튼 배치

### 3. 메시지 렌더링
- `message-stream.tsx`에서 메시지 타입별 렌더링
- 텍스트: `text-block.tsx` (마크다운 지원)
- 테이블: `interactive-table.tsx` (정렬, CSV 다운로드)
- 차트: `interactive-chart.tsx` (PNG 다운로드)

### 4. Knowledge Base 탐색
- 아코디언 UI로 카테고리별 정보 표시
- 회사, 재무계정, 사업 3개 카테고리
- 각 항목에 아이콘 표시 (Building2, FileText, BarChart3)

---

## 상태 관리

### 전역 상태 (app/page.tsx)
\`\`\`typescript
const [messages, setMessages] = useState<ChatMessage[]>([])
const [isLeftSidebarCollapsed, setIsLeftSidebarCollapsed] = useState(false)
const [theme, setTheme] = useTheme()
\`\`\`

### Props 전달
- `page.tsx` → `left-sidebar.tsx`: `isCollapsed`, `onToggleCollapse`
- `page.tsx` → `chat-area.tsx`: `messages`, `onSendMessage`
- `page.tsx` → `right-sidebar.tsx`: `menuData`

---

## 스타일링 패턴

### Tailwind 클래스 사용
- **레이아웃**: `flex`, `grid`, `gap-*`
- **간격**: `p-*`, `m-*`, `space-*`
- **색상**: `bg-background`, `text-foreground`, `border-border`
- **반응형**: `md:*`, `lg:*`
- **애니메이션**: `transition-*`, `duration-*`

### 디자인 토큰
- `--background`, `--foreground`
- `--primary`, `--primary-foreground`
- `--muted`, `--muted-foreground`
- `--border`, `--input`
- `--radius` (border-radius)

---

## 개발 가이드

### 새 메시지 타입 추가
1. `lib/types.ts`에 새 `MessageBlock` 타입 추가
2. `components/chat/message-stream.tsx`에 렌더링 로직 추가
3. 새 컴포넌트 생성 (예: `new-block.tsx`)

### 새 Knowledge Base 카테고리 추가
1. `lib/types.ts`에 새 인터페이스 추가
2. `lib/mock-data.ts`에 목 데이터 추가
3. `components/sidebar/knowledge-menu.tsx`에 아코디언 아이템 추가

### 스타일 커스터마이징
1. `app/globals.css`에서 디자인 토큰 수정
2. Tailwind 클래스로 개별 컴포넌트 스타일 조정

---

## 배포 및 설치

### 로컬 개발
\`\`\`bash
npm install
npm run dev
\`\`\`

### 빌드
\`\`\`bash
npm run build
npm start
\`\`\`

### Vercel 배포
- v0에서 "Publish" 버튼 클릭
- 또는 GitHub 연동 후 Vercel에서 자동 배포

---

## 향후 개선 사항

- [ ] 실제 AI API 연동 (현재는 목 데이터)
- [ ] 메시지 스트리밍 구현
- [ ] 채팅 히스토리 저장 (로컬 스토리지 또는 DB)
- [ ] Knowledge Base 검색 기능
- [ ] 더 많은 차트 타입 지원
- [ ] 모바일 반응형 개선
- [ ] 접근성 (a11y) 개선

---

## 문의 및 지원

이 프로젝트는 v0.dev에서 생성되었습니다.
- v0 문서: https://v0.dev/docs
- Next.js 문서: https://nextjs.org/docs
- shadcn/ui 문서: https://ui.shadcn.com
