"use client"

import { useState } from "react"
import { LeftSidebar } from "@/components/sidebar/left-sidebar"
import { RightSidebar } from "@/components/sidebar/right-sidebar"
import { ChatArea } from "@/components/chat/chat-area"
import type { ChatMessage, ChatSession } from "@/lib/types"

export default function Home() {
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isLeftSidebarCollapsed, setIsLeftSidebarCollapsed] = useState(false)

  const handleNewChat = () => {
    setActiveSessionId(null)
    setMessages([])
  }

  const handleSelectSession = (sessionId: string) => {
    setActiveSessionId(sessionId)
    // TODO: 향후 세션별 메시지 로드 기능 추가
    setMessages([])
  }

  const handleSendMessage = async (content: string) => {
    if (!content.trim() || isLoading) return

    // 사용자 메시지 추가
    const userMessage: ChatMessage = {
      id: `msg-user-${Date.now()}`,
      author: "user",
      content: [{ type: "text", content }],
      timestamp: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, userMessage])
    setIsLoading(true)

    try {
      const response = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          sessionId: activeSessionId, 
          query: content 
        }),
      })

      if (!response.ok) {
        throw new Error('API request failed')
      }

      const agentResponse = await response.json()
      
      // 응답에서 sessionId 추출하여 상태 업데이트
      if (agentResponse.sessionId) {
        const newSessionId = agentResponse.sessionId
        setActiveSessionId(newSessionId)
        
        // 새 세션이면 세션 목록에 추가
        if (!activeSessionId) {
          const newSession: ChatSession = {
            id: newSessionId,
            title: content.slice(0, 30) + (content.length > 30 ? '...' : ''),
            last_updated: new Date().toLocaleTimeString('ko-KR', {
              hour: '2-digit',
              minute: '2-digit',
            })
          }
          setSessions((prev) => [newSession, ...prev])
        }
      }

      // 화면에 에이전트 메시지 추가
      setMessages((prev) => [...prev, agentResponse])

    } catch (error) {
      console.error('Error:', error)
      
      // 오류 메시지 표시
      const errorMessage: ChatMessage = {
        id: `msg-error-${Date.now()}`,
        author: "agent",
        content: [{ 
          type: "text", 
          content: "죄송합니다, 오류가 발생했습니다. 다시 시도해주세요." 
        }],
        timestamp: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <LeftSidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        onNewChat={handleNewChat}
        onSelectSession={handleSelectSession}
        isCollapsed={isLeftSidebarCollapsed}
        onToggleCollapse={() => setIsLeftSidebarCollapsed(!isLeftSidebarCollapsed)}
      />
      <ChatArea messages={messages} onSendMessage={handleSendMessage} isLoading={isLoading} />
      <RightSidebar />
    </div>
  )
}
