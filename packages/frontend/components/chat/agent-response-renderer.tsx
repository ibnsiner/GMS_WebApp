"use client"

import type { AgentContent } from "@/lib/types"
import { TextBlock } from "./text-block"
import { InteractiveTable } from "./interactive-table"
import { InteractiveChart } from "./interactive-chart"

interface AgentResponseRendererProps {
  content: AgentContent
}

export function AgentResponseRenderer({ content }: AgentResponseRendererProps) {
  switch (content.type) {
    case "summary":
    case "insight":
    case "notice":
      return <TextBlock content={content.content} type={content.type} />

    case "table":
      return <InteractiveTable data={content.content} />

    case "chart":
      return <InteractiveChart data={content.content} />

    case "text":
      return <div className="text-sm text-foreground">{content.content}</div>

    default:
      return null
  }
}
