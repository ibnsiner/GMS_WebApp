"use client"

import type { AgentContent } from "@/lib/types"
import { TextBlock } from "./text-block"
import { InteractiveTable } from "./interactive-table"
import { InteractiveChart } from "./interactive-chart"
import ReactMarkdown from "react-markdown"

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
      // Base64 이미지가 있으면 직접 표시
      if (content.content.image_base64) {
        return (
          <div className="rounded-lg overflow-hidden border border-border bg-background">
            <img 
              src={`data:image/png;base64,${content.content.image_base64}`}
              alt="Chart"
              className="w-full h-auto"
            />
          </div>
        )
      }
      // 기존 차트 데이터 형식
      return <InteractiveChart data={content.content} />

    case "text":
      return (
        <div className="text-sm text-foreground prose prose-sm dark:prose-invert max-w-none">
          <ReactMarkdown
            components={{
              h3: ({ children }) => <h3 className="text-base font-semibold mt-4 mb-2">{children}</h3>,
              h4: ({ children }) => <h4 className="text-sm font-semibold mt-3 mb-1">{children}</h4>,
              p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
              ul: ({ children }) => <ul className="list-disc list-inside mb-2 space-y-1">{children}</ul>,
              ol: ({ children }) => <ol className="list-decimal list-inside mb-2 space-y-1">{children}</ol>,
              li: ({ children }) => <li className="ml-2">{children}</li>,
              strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,
              code: ({ children }) => <code className="bg-muted px-1 py-0.5 rounded text-xs">{children}</code>,
              blockquote: ({ children }) => <blockquote className="border-l-4 border-primary pl-4 italic text-muted-foreground">{children}</blockquote>,
              table: ({ children }) => (
                <div className="overflow-x-auto my-4">
                  <table className="min-w-full text-sm border-collapse border border-border">
                    {children}
                  </table>
                </div>
              ),
              thead: ({ children }) => <thead className="bg-muted/30">{children}</thead>,
              tbody: ({ children }) => <tbody>{children}</tbody>,
              tr: ({ children }) => <tr className="border-t border-border">{children}</tr>,
              th: ({ children }) => <th className="px-4 py-2 text-left font-medium border border-border whitespace-nowrap">{children}</th>,
              td: ({ children }) => <td className="px-4 py-2 border border-border whitespace-nowrap">{children}</td>,
            }}
          >
            {content.content}
          </ReactMarkdown>
        </div>
      )

    default:
      return null
  }
}
