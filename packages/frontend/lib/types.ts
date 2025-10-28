// Core data structures for GMIS Agent

export interface MenuItem {
  id: string
  name: string
}

export interface SubCategory {
  name: string
  sub_items: MenuItem[]
}

export interface Category {
  category: string
  type: "company" | "account" | "segment"
  items: (MenuItem | SubCategory)[]
}

export interface KnowledgeMenuData {
  menu: Category[]
}

export interface ChatSession {
  id: string
  title: string
  last_updated: string
}

export type AgentContent = {
  type: "summary" | "insight" | "notice" | "table" | "chart" | "text"
  content: any
}

export interface ChatMessage {
  id: string
  author: "user" | "agent"
  content: AgentContent[]
  timestamp: string
}

export interface TableData {
  columns: string[]
  rows: (string | number)[][]
}

export interface ChartData {
  type: "line" | "bar" | "pie"
  labels: string[]
  datasets: {
    label: string
    data: number[]
    backgroundColor?: string | string[]
    borderColor?: string
  }[]
}
