"use client"

import { SidebarHeader } from "./sidebar-header"
import { ChatHistoryList } from "./chat-history-list"
import { KnowledgeMenu } from "./knowledge-menu"
import { SidebarFooter } from "./sidebar-footer"
import type { ChatSession, KnowledgeMenuData } from "@/lib/types"

interface SidebarProps {
  sessions: ChatSession[]
  activeSessionId: string | null
  menuData: KnowledgeMenuData | null
  onNewChat: () => void
  onSelectSession: (sessionId: string) => void
}

export function Sidebar({ sessions, activeSessionId, menuData, onNewChat, onSelectSession }: SidebarProps) {
  return (
    <aside className="w-80 border-r border-border bg-background flex flex-col h-screen">
      <SidebarHeader onNewChat={onNewChat} />
      <ChatHistoryList sessions={sessions} activeSessionId={activeSessionId} onSelectSession={onSelectSession} />
      <KnowledgeMenu menuData={menuData} />
      <SidebarFooter />
    </aside>
  )
}
