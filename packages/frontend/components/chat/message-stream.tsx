"use client"

import type { ChatMessage } from "@/lib/types"
import { AgentResponseRenderer } from "./agent-response-renderer"
import { cn } from "@/lib/utils"
import { Loader2 } from "lucide-react"

interface MessageStreamProps {
  messages: ChatMessage[]
  isLoading?: boolean
}

export function MessageStream({ messages, isLoading = false }: MessageStreamProps) {
  return (
    <div className="flex-1 overflow-y-auto p-6 pt-8 space-y-6">
      {messages.length === 0 ? (
        <div className="h-full" />
      ) : (
        <>
          {messages.map((message) => (
          <div key={message.id} className={cn("flex", message.author === "user" ? "justify-end" : "justify-start")}>
            <div className={cn("max-w-3xl w-full", message.author === "user" && "flex justify-end")}>
              {message.author === "user" ? (
                <div className="inline-block max-w-2xl">
                  <div className="bg-primary text-primary-foreground rounded-lg px-4 py-3">
                    <p className="text-sm">{message.content[0].content}</p>
                  </div>
                  <div className="text-xs text-muted-foreground text-right mt-1 pr-2">
                    {message.timestamp}
                  </div>
                </div>
              ) : (
                <div className="w-full space-y-4">
                  <div className="pl-4 space-y-4">
                    {message.content.map((content, idx) => (
                      <AgentResponseRenderer key={idx} content={content} />
                    ))}
                  </div>
                  <div className="text-xs text-muted-foreground pl-4 mt-2">
                    {message.timestamp}
                  </div>
                </div>
              )}
            </div>
          </div>
          ))}
          
          {isLoading && (
            <div className="flex justify-start">
              <div className="max-w-3xl w-full pl-4">
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span className="animate-pulse">AI가 생각하고 있습니다...</span>
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
