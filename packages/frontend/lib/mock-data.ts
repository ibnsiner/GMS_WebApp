import type { KnowledgeMenuData, ChatSession, ChatMessage } from "./types"

export const mockKnowledgeMenu: KnowledgeMenuData = {
  menu: [
    {
      category: "회사",
      type: "company",
      items: [
        { id: "LSCNS_C", name: "LS전선 (연결)" },
        { id: "LSCNS_S", name: "LS전선 (별도)" },
        { id: "ELECTRIC", name: "LS일렉트릭" },
        { id: "MnM", name: "LS엠앤엠" },
        { id: "엠트론", name: "LS엠트론" },
        { id: "E1", name: "E1" },
        { id: "가온", name: "가온전선" },
        { id: "I&D", name: "LS아이앤디" },
        { id: "글로벌", name: "LS글로벌" },
      ],
    },
    {
      category: "재무계정",
      type: "account",
      items: [
        {
          name: "손익계산서 (IS)",
          sub_items: [
            { id: "매출액_합계", name: "매출액" },
            { id: "매출총이익", name: "매출총이익" },
            { id: "판매관리비", name: "판매관리비" },
            { id: "영업이익", name: "영업이익" },
            { id: "조정영업이익", name: "조정영업이익" },
            { id: "기타영업손익_합계", name: "기타영업손익" },
            { id: "영업외손익_합계", name: "영업외손익" },
            { id: "세전이익", name: "세전이익" },
            { id: "법인세", name: "법인세" },
            { id: "당기순이익", name: "당기순이익" },
            { id: "당기순이익_지배주주손익", name: "당기순이익 (지배주주)" },
            { id: "EBITDA", name: "EBITDA" },
          ],
        },
        {
          name: "재무상태표 (BS)",
          sub_items: [
            { id: "자산_합계", name: "자산총계" },
            { id: "유동자산_합계", name: "유동자산" },
            { id: "유동자산_현/예금", name: "현금및현금성자산" },
            { id: "유동자산_재고자산", name: "재고자산" },
            { id: "유동자산_매출채권", name: "매출채권" },
            { id: "비유동자산_합계", name: "비유동자산" },
            { id: "비유동자산_유형자산", name: "유형자산" },
            { id: "비유동자산_무형자산", name: "무형자산" },
            { id: "부채_합계", name: "부채총계" },
            { id: "부채_매입채무", name: "매입채무" },
            { id: "부채_차입금", name: "차입금" },
            { id: "자기자본_합계", name: "자본총계" },
            { id: "자기자본_이익잉여금", name: "이익잉여금" },
            { id: "자기자본_비지배주주지분", name: "비지배주주지분" },
          ],
        },
        {
          name: "관리지표",
          sub_items: [
            { id: "영업이익률", name: "영업이익률" },
            { id: "세전이익률", name: "세전이익률" },
            { id: "영업이익_이자보상배율", name: "이자보상배율" },
            { id: "관리지표_부채비율(%)", name: "부채비율" },
            { id: "관리지표_차입금비율(%)", name: "차입금비율" },
            { id: "관리지표_재고회전일", name: "재고회전일" },
            { id: "관리지표_채권회전일", name: "채권회전일" },
            { id: "ROE", name: "자기자본이익률 (ROE)" },
          ],
        },
      ],
    },
    {
      category: "사업",
      type: "segment",
      items: [],
    },
  ],
}

export const mockChatHistory: ChatSession[] = [
  {
    id: "session-1",
    title: "LS전선 2023년 실적 분석",
    last_updated: "2:30 PM",
  },
  {
    id: "session-2",
    title: "4분기 매출 비교",
    last_updated: "Yesterday",
  },
  {
    id: "session-3",
    title: "부채비율 분석",
    last_updated: "2 days ago",
  },
]

export const mockMessages: ChatMessage[] = [
  {
    id: "msg-1",
    author: "user",
    content: [
      {
        type: "text",
        content: "LS전선과 엠앤엠의 작년 매출을 비교해줘",
      },
    ],
    timestamp: "2:30 PM",
  },
  {
    id: "msg-2",
    author: "agent",
    content: [
      {
        type: "summary",
        content: "LS전선과 LS엠앤엠의 전년도 매출 데이터를 분석했습니다. 다음은 분석 결과입니다:",
      },
      {
        type: "table",
        content: {
          columns: ["회사", "2023 매출 (원)", "2022 매출 (원)", "전년대비 성장률"],
          rows: [
            ["LS전선", "5.2조", "4.8조", "+8.3%"],
            ["LS엠앤엠", "2.1조", "1.9조", "+10.5%"],
          ],
        },
      },
      {
        type: "insight",
        content:
          "두 회사 모두 강한 성장세를 보였으며, LS엠앤엠이 절대 매출액은 낮지만 성장률 측면에서 LS전선을 앞섰습니다.",
      },
    ],
    timestamp: "2:31 PM",
  },
]
