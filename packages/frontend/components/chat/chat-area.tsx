"use client"

import type { ChatMessage } from "@/lib/types"
import { MessageStream } from "./message-stream"
import { ChatInput } from "./chat-input"
import { ChatHeader } from "./chat-header"

interface ChatAreaProps {
  messages: ChatMessage[]
  onSendMessage: (message: string) => void
  isLoading?: boolean
}

export function ChatArea({ messages, onSendMessage, isLoading = false }: ChatAreaProps) {
  const showHeader = messages.length === 0

  return (
    <div className="flex-1 flex flex-col h-screen bg-muted/30">
      {showHeader && <ChatHeader />}
      <MessageStream messages={messages} />
      <ChatInput onSend={onSendMessage} disabled={isLoading} />
    </div>
  )
}
