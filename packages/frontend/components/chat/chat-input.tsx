"use client"

import { useState, type KeyboardEvent } from "react"
import { Send, Moon, Sun } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { useTheme } from "next-themes"

interface ChatInputProps {
  onSend: (message: string) => void
  disabled?: boolean
}

export function ChatInput({ onSend, disabled = false }: ChatInputProps) {
  const [input, setInput] = useState("")
  const { theme, setTheme } = useTheme()

  const handleSend = () => {
    if (input.trim() && !disabled) {
      onSend(input.trim())
      setInput("")
    }
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const toggleTheme = () => {
    setTheme(theme === "dark" ? "light" : "dark")
  }
  // </CHANGE>

  return (
    <div className="border-t border-border bg-background">
      <div className="max-w-4xl mx-auto p-4">
        <div className="bg-card border border-border rounded-lg p-3 shadow-sm">
          <div className="flex gap-3 items-start">
            <Button
              variant="ghost"
              size="icon"
              onClick={toggleTheme}
              className="shrink-0 h-[60px] w-[60px]"
              aria-label="테마 전환"
            >
              {theme === "dark" ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
            </Button>
            {/* </CHANGE> */}
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="데이터에 대해 무엇이든 물어보세요..."
              disabled={disabled}
              className="min-h-[60px] max-h-[200px] resize-none border-0 focus-visible:ring-0 bg-transparent"
            />
            <Button
              onClick={handleSend}
              disabled={disabled || !input.trim()}
              size="icon"
              className="shrink-0 h-[60px] w-[60px] rounded-lg"
            >
              <Send className="h-5 w-5" />
            </Button>
          </div>
        </div>
        <p className="text-xs text-muted-foreground text-center mt-3">by Human Resource/Business Intelligence Team</p>
      </div>
    </div>
  )
}
