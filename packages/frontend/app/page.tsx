"use client"

import { useState } from "react"
import { LeftSidebar } from "@/components/sidebar/left-sidebar"
import { RightSidebar } from "@/components/sidebar/right-sidebar"
import { ChatArea } from "@/components/chat/chat-area"
import { mockKnowledgeMenu, mockChatHistory, mockMessages } from "@/lib/mock-data"
import type { ChatMessage } from "@/lib/types"

export default function Home() {
  const [activeSessionId, setActiveSessionId] = useState<string | null>("session-1")
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isLeftSidebarCollapsed, setIsLeftSidebarCollapsed] = useState(false)
  // </CHANGE>

  const handleNewChat = () => {
    setActiveSessionId(null)
    setMessages([])
  }

  const handleSelectSession = (sessionId: string) => {
    setActiveSessionId(sessionId)
    // In a real app, load messages for this session
    setMessages(mockMessages)
  }

  const handleSendMessage = (content: string) => {
    const newMessage: ChatMessage = {
      id: `msg-${Date.now()}`,
      author: "user",
      content: [{ type: "text", content }],
      timestamp: new Date().toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      }),
    }

    setMessages((prev) => [...prev, newMessage])
    setIsLoading(true)

    // Simulate API response
    setTimeout(() => {
      const agentResponse: ChatMessage = {
        id: `msg-${Date.now()}`,
        author: "agent",
        content: [
          {
            type: "summary",
            content: "쿼리를 분석했습니다. 사용 가능한 데이터를 기반으로 찾은 내용은 다음과 같습니다.",
          },
        ],
        timestamp: new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        }),
      }

      setMessages((prev) => [...prev, agentResponse])
      setIsLoading(false)
    }, 1500)
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <LeftSidebar
        sessions={mockChatHistory}
        activeSessionId={activeSessionId}
        onNewChat={handleNewChat}
        onSelectSession={handleSelectSession}
        isCollapsed={isLeftSidebarCollapsed}
        onToggleCollapse={() => setIsLeftSidebarCollapsed(!isLeftSidebarCollapsed)}
      />
      {/* </CHANGE> */}
      <ChatArea messages={messages} onSendMessage={handleSendMessage} isLoading={isLoading} />
      <RightSidebar menuData={mockKnowledgeMenu} />
    </div>
  )
}
