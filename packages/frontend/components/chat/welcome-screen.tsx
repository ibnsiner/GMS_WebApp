"use client"

import { Button } from "@/components/ui/button"

interface WelcomeScreenProps {
  onPromptClick: (prompt: string) => void
}

const examplePrompts = [
  "Compare last year's revenue for LS Cable and MnM",
  "What is a Debt Ratio?",
  "Show me the list of business items for LS ELECTRIC",
  "Draw a chart of operating profit for the top 4 manufacturing companies",
]

export function WelcomeScreen({ onPromptClick }: WelcomeScreenProps) {
  return (
    <div className="flex flex-col items-center justify-center h-full p-8">
      <div className="text-center mb-8">
        <h1 className="text-3xl font-semibold text-foreground mb-2">GMIS Agent</h1>
        <p className="text-lg text-muted-foreground">How can I help you?</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-w-2xl w-full">
        {examplePrompts.map((prompt, idx) => (
          <Button
            key={idx}
            variant="outline"
            className="h-auto py-4 px-6 text-left justify-start whitespace-normal bg-transparent"
            onClick={() => onPromptClick(prompt)}
          >
            {prompt}
          </Button>
        ))}
      </div>
    </div>
  )
}
