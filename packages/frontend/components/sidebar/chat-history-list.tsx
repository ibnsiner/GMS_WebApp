"use client"

import { MessageSquare } from "lucide-react"
import type { ChatSession } from "@/lib/types"
import { cn } from "@/lib/utils"

interface ChatHistoryListProps {
  sessions: ChatSession[]
  activeSessionId: string | null
  onSelectSession: (sessionId: string) => void
}

export function ChatHistoryList({ sessions, activeSessionId, onSelectSession }: ChatHistoryListProps) {
  // Group sessions by date
  const today: ChatSession[] = []
  const yesterday: ChatSession[] = []
  const previous: ChatSession[] = []

  sessions.forEach((session) => {
    if (session.last_updated.includes("PM") || session.last_updated.includes("AM")) {
      today.push(session)
    } else if (session.last_updated === "Yesterday") {
      yesterday.push(session)
    } else {
      previous.push(session)
    }
  })

  const renderGroup = (title: string, items: ChatSession[]) => {
    if (items.length === 0) return null

    return (
      <div className="mb-4">
        <h3 className="px-4 py-2 text-xs font-medium text-muted-foreground uppercase">{title}</h3>
        <div className="space-y-1 px-2">
          {items.map((session) => (
            <button
              key={session.id}
              onClick={() => onSelectSession(session.id)}
              className={cn(
                "w-full px-3 py-2.5 text-left text-sm transition-colors hover:bg-sidebar-accent rounded-lg group",
                activeSessionId === session.id && "bg-sidebar-accent",
              )}
            >
              <div className="flex items-start gap-2">
                <MessageSquare className="h-4 w-4 mt-0.5 shrink-0 text-muted-foreground" />
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-sidebar-foreground truncate">{session.title}</div>
                  <div className="text-xs text-muted-foreground mt-0.5">{session.last_updated}</div>
                </div>
              </div>
            </button>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto">
      {renderGroup("오늘", today)}
      {renderGroup("어제", yesterday)}
      {renderGroup("지난 7일", previous)}
    </div>
  )
}
