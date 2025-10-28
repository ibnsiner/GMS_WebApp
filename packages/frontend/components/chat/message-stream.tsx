"use client"

import type { ChatMessage } from "@/lib/types"
import { AgentResponseRenderer } from "./agent-response-renderer"
import { cn } from "@/lib/utils"

interface MessageStreamProps {
  messages: ChatMessage[]
}

export function MessageStream({ messages }: MessageStreamProps) {
  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
      {messages.length === 0 ? (
        <div className="h-full" />
      ) : (
        messages.map((message) => (
          <div key={message.id} className={cn("flex", message.author === "user" ? "justify-end" : "justify-start")}>
            <div className={cn("max-w-3xl w-full space-y-3", message.author === "user" && "flex justify-end")}>
              {message.author === "user" ? (
                <div className="bg-primary text-primary-foreground rounded-lg px-4 py-3 inline-block max-w-2xl">
                  <p className="text-sm">{message.content[0].content}</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {message.content.map((content, idx) => (
                    <AgentResponseRenderer key={idx} content={content} />
                  ))}
                </div>
              )}
              <div className={cn("text-xs text-muted-foreground", message.author === "user" && "text-right")}>
                {message.timestamp}
              </div>
            </div>
          </div>
        ))
      )}
    </div>
  )
}
