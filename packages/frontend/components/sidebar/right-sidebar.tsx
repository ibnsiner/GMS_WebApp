"use client"

import { useState, useEffect } from "react"
import { KnowledgeMenu } from "./knowledge-menu"
import type { KnowledgeMenuData } from "@/lib/types"
import { Database, Info } from "lucide-react"

export function RightSidebar() {
  const [menuData, setMenuData] = useState<KnowledgeMenuData | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    async function fetchMenuData() {
      setIsLoading(true)
      try {
        const response = await fetch('http://localhost:8000/api/knowledge-menu')
        const data = await response.json()
        setMenuData(data)
      } catch (error) {
        console.error("Failed to fetch knowledge menu:", error)
      } finally {
        setIsLoading(false)
      }
    }
    fetchMenuData()
  }, [])
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
