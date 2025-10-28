"use client"

import { useState } from "react"
import { Download, ArrowUpDown } from "lucide-react"
import { Button } from "@/components/ui/button"
import type { TableData } from "@/lib/types"

interface InteractiveTableProps {
  data: TableData
}

export function InteractiveTable({ data }: InteractiveTableProps) {
  const [sortColumn, setSortColumn] = useState<number | null>(null)
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc")
  const [sortedRows, setSortedRows] = useState(data.rows)

  const handleSort = (columnIndex: number) => {
    const newDirection = sortColumn === columnIndex && sortDirection === "asc" ? "desc" : "asc"

    const sorted = [...data.rows].sort((a, b) => {
      const aVal = a[columnIndex]
      const bVal = b[columnIndex]

      if (typeof aVal === "number" && typeof bVal === "number") {
        return newDirection === "asc" ? aVal - bVal : bVal - aVal
      }

      const aStr = String(aVal)
      const bStr = String(bVal)
      return newDirection === "asc" ? aStr.localeCompare(bStr) : bStr.localeCompare(aStr)
    })

    setSortedRows(sorted)
    setSortColumn(columnIndex)
    setSortDirection(newDirection)
  }

  const downloadCSV = () => {
    const csv = [data.columns.join(","), ...sortedRows.map((row) => row.join(","))].join("\n")

    const blob = new Blob([csv], { type: "text/csv" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = "data.csv"
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <div className="flex items-center justify-between p-2 bg-muted/50 border-b border-border">
        <span className="text-xs font-medium text-muted-foreground">Data Table</span>
        <Button variant="ghost" size="sm" onClick={downloadCSV} className="h-7 text-xs">
          <Download className="h-3 w-3 mr-1" />
          Download CSV
        </Button>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-muted/30">
            <tr>
              {data.columns.map((column, idx) => (
                <th
                  key={idx}
                  className="px-4 py-3 text-left font-medium text-foreground cursor-pointer hover:bg-muted/50 transition-colors"
                  onClick={() => handleSort(idx)}
                >
                  <div className="flex items-center gap-2">
                    {column}
                    <ArrowUpDown className="h-3 w-3 text-muted-foreground" />
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sortedRows.map((row, rowIdx) => (
              <tr key={rowIdx} className="border-t border-border hover:bg-muted/20 transition-colors even:bg-muted/10">
                {row.map((cell, cellIdx) => (
                  <td key={cellIdx} className="px-4 py-3 text-foreground">
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
