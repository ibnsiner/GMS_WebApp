"use client"

import { KnowledgeMenu } from "./knowledge-menu"
import type { KnowledgeMenuData } from "@/lib/types"
import { Database, Info } from "lucide-react"

interface RightSidebarProps {
  menuData: KnowledgeMenuData | null
}

export function RightSidebar({ menuData }: RightSidebarProps) {
  return (
    <aside className="w-80 border-l border-border bg-sidebar flex flex-col h-screen overflow-y-auto">
      <div className="p-4 border-b border-border min-h-[120px] flex flex-col justify-center">
        <div className="flex items-center gap-2 mb-3">
          <Database className="h-5 w-5 text-primary" />
          <h2 className="text-lg font-semibold">Knowledge Base</h2>
        </div>
        <div className="bg-muted/50 rounded-lg p-3 border border-border">
          <div className="flex items-start gap-2">
            <Info className="h-4 w-4 text-primary mt-0.5 flex-shrink-0" />
            <p className="text-xs text-muted-foreground leading-relaxed">
              저는 아래 메뉴들에 포함된 내용에 대해 답할 수 있습니다. 제가 보유한 지식을 참조해주세요.
            </p>
          </div>
        </div>
      </div>
      {/* </CHANGE> */}
      <KnowledgeMenu menuData={menuData} />
    </aside>
  )
}
