"use client"

import { useEffect, useRef } from "react"
import { Download } from "lucide-react"
import { Button } from "@/components/ui/button"
import type { ChartData } from "@/lib/types"
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
} from "chart.js"

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, BarElement, ArcElement, Title, Tooltip, Legend)

interface InteractiveChartProps {
  data: ChartData
}

export function InteractiveChart({ data }: InteractiveChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const chartRef = useRef<ChartJS | null>(null)

  useEffect(() => {
    if (!canvasRef.current) return

    const ctx = canvasRef.current.getContext("2d")
    if (!ctx) return

    // Destroy existing chart
    if (chartRef.current) {
      chartRef.current.destroy()
    }

    // Create new chart
    chartRef.current = new ChartJS(ctx, {
      type: data.type,
      data: {
        labels: data.labels,
        datasets: data.datasets,
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
          legend: {
            position: "top",
            onClick: (e, legendItem, legend) => {
              const index = legendItem.datasetIndex
              const chart = legend.chart
              const meta = chart.getDatasetMeta(index!)
              meta.hidden = !meta.hidden
              chart.update()
            },
          },
          tooltip: {
            enabled: true,
          },
        },
      },
    })

    return () => {
      if (chartRef.current) {
        chartRef.current.destroy()
      }
    }
  }, [data])

  const downloadPNG = () => {
    if (!canvasRef.current) return

    const url = canvasRef.current.toDataURL("image/png")
    const a = document.createElement("a")
    a.href = url
    a.download = "chart.png"
    a.click()
  }

  return (
    <div className="border border-border rounded-lg overflow-hidden p-4">
      <div className="flex items-center justify-between mb-4">
        <span className="text-xs font-medium text-muted-foreground">Chart Visualization</span>
        <Button variant="ghost" size="sm" onClick={downloadPNG} className="h-7 text-xs">
          <Download className="h-3 w-3 mr-1" />
          Download PNG
        </Button>
      </div>

      <div className="relative">
        <canvas ref={canvasRef} />
      </div>
    </div>
  )
}
