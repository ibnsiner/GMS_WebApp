"use client"

import { Plus } from "lucide-react"
import { Button } from "@/components/ui/button"

interface SidebarHeaderProps {
  onNewChat: () => void
}

export function SidebarHeader({ onNewChat }: SidebarHeaderProps) {
  return (
    <div className="flex items-center justify-between p-4 border-b border-border min-h-[120px]">
      <h1 className="text-2xl font-semibold text-foreground">GMIS Agent</h1>
      {/* </CHANGE> */}
      <Button variant="ghost" size="icon" onClick={onNewChat} className="shrink-0" aria-label="새 채팅">
        <Plus className="h-5 w-5" />
      </Button>
    </div>
  )
}
