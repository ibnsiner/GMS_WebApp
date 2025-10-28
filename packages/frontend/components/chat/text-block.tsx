"use client"

import ReactMarkdown from "react-markdown"

interface TextBlockProps {
  content: string
  type: "summary" | "insight" | "notice"
}

export function TextBlock({ content, type }: TextBlockProps) {
  const getStyles = () => {
    switch (type) {
      case "insight":
        return "bg-blue-50 dark:bg-blue-950/30 border-l-4 border-blue-500 pl-4 py-3"
      case "notice":
        return "bg-amber-50 dark:bg-amber-950/30 border-l-4 border-amber-500 pl-4 py-3"
      default:
        return ""
    }
  }

  return (
    <div className={`text-sm text-foreground ${getStyles()}`}>
      <ReactMarkdown
        components={{
          p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
          strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
