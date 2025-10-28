"use client"

import { Sparkles } from "lucide-react"

export function ChatHeader() {
  return (
    <div className="flex-1 flex items-center justify-center p-8">
      <div className="max-w-2xl w-full">
        <div className="bg-card border border-border rounded-lg p-8 shadow-sm">
          <div className="flex items-center gap-3 mb-4">
            <div className="h-10 w-10 rounded-lg bg-blue-500/20 flex items-center justify-center">
              <Sparkles className="h-5 w-5 text-blue-600 dark:text-blue-400" />
            </div>
            {/* </CHANGE> */}
            <h2 className="text-xl font-semibold text-foreground">GMIS Agent가 할 수 있는 일</h2>
          </div>
          <div className="space-y-3 text-sm text-muted-foreground leading-relaxed">
            <p>
              복잡한 재무 데이터를 자연어로 질문하고 분석할 수 있습니다. 회사별 매출, 영업이익, 부채비율 등의 재무지표를
              조회하고, 여러 회사를 비교하며, 시각화된 차트와 표로 데이터를 확인할 수 있습니다.
            </p>
            <div className="grid grid-cols-2 gap-3 mt-4">
              <div className="bg-muted/50 rounded-md p-3">
                <p className="font-medium text-foreground text-xs mb-1">재무 데이터 조회</p>
                <p className="text-xs">회사별 재무제표 및 핵심지표 분석</p>
              </div>
              <div className="bg-muted/50 rounded-md p-3">
                <p className="font-medium text-foreground text-xs mb-1">비교 분석</p>
                <p className="text-xs">여러 회사의 실적을 비교하고 인사이트 도출</p>
              </div>
              <div className="bg-muted/50 rounded-md p-3">
                <p className="font-medium text-foreground text-xs mb-1">데이터 시각화</p>
                <p className="text-xs">차트와 표로 데이터를 직관적으로 표현</p>
              </div>
              <div className="bg-muted/50 rounded-md p-3">
                <p className="font-medium text-foreground text-xs mb-1">다운로드</p>
                <p className="text-xs">분석 결과를 CSV 및 PNG로 저장</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
