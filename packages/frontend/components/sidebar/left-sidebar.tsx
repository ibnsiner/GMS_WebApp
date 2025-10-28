"use client"

import { SidebarHeader } from "./sidebar-header"
import { ChatHistoryList } from "./chat-history-list"
import type { ChatSession } from "@/lib/types"
import { ChevronLeft, ChevronRight } from "lucide-react"
import { Button } from "@/components/ui/button"

interface LeftSidebarProps {
  sessions: ChatSession[]
  activeSessionId: string | null
  onNewChat: () => void
  onSelectSession: (sessionId: string) => void
  isCollapsed: boolean
  onToggleCollapse: () => void
}

export function LeftSidebar({
  sessions,
  activeSessionId,
  onNewChat,
  onSelectSession,
  isCollapsed,
  onToggleCollapse,
}: LeftSidebarProps) {
  return (
    <>
      <div
        className={`absolute top-1/2 -translate-y-1/2 z-20 transition-all duration-300 ${isCollapsed ? "left-2" : "left-[312px]"}`}
      >
        <Button
          variant="outline"
          size="icon"
          className="h-8 w-8 rounded-full bg-background shadow-md hover:bg-accent border-border"
          onClick={onToggleCollapse}
        >
          {isCollapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </Button>
      </div>

      <aside
        className={`relative border-r border-border bg-sidebar flex flex-col h-screen transition-all duration-300 ${
          isCollapsed ? "w-0 overflow-hidden" : "w-80"
        }`}
      >
        <SidebarHeader onNewChat={onNewChat} />
        <ChatHistoryList sessions={sessions} activeSessionId={activeSessionId} onSelectSession={onSelectSession} />
      </aside>
    </>
  )
}
