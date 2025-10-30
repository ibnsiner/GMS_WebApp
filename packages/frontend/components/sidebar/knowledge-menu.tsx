"use client"

import { useState } from "react"
import { ChevronDown, ChevronRight, Building2, FileText, BarChart3, Network } from "lucide-react"
import type { KnowledgeMenuData, SubCategory, MenuItem, SegmentCompany, SegmentCIC } from "@/lib/types"

interface KnowledgeMenuProps {
  menuData: KnowledgeMenuData | null
}

export function KnowledgeMenu({ menuData }: KnowledgeMenuProps) {
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set())
  const [expandedSubCategories, setExpandedSubCategories] = useState<Set<string>>(new Set())
  const [expandedCompanies, setExpandedCompanies] = useState<Set<string>>(new Set())
  const [expandedCICs, setExpandedCICs] = useState<Set<string>>(new Set())

  if (!menuData) {
    return <div className="p-4 text-sm text-muted-foreground">지식 베이스를 불러오는 중...</div>
  }

  const toggleCategory = (categoryName: string) => {
    setExpandedCategories((prev) => {
      const next = new Set(prev)
      if (next.has(categoryName)) {
        next.delete(categoryName)
      } else {
        next.add(categoryName)
      }
      return next
    })
  }

  const toggleSubCategory = (subCategoryName: string) => {
    setExpandedSubCategories((prev) => {
      const next = new Set(prev)
      if (next.has(subCategoryName)) {
        next.delete(subCategoryName)
      } else {
        next.add(subCategoryName)
      }
      return next
    })
  }

  const toggleCompany = (companyId: string) => {
    setExpandedCompanies((prev) => {
      const next = new Set(prev)
      if (next.has(companyId)) {
        next.delete(companyId)
      } else {
        next.add(companyId)
      }
      return next
    })
  }

  const toggleCIC = (cicId: string) => {
    setExpandedCICs((prev) => {
      const next = new Set(prev)
      if (next.has(cicId)) {
        next.delete(cicId)
      } else {
        next.add(cicId)
      }
      return next
    })
  }

  const isSubCategory = (item: MenuItem | SubCategory | SegmentCompany): item is SubCategory => {
    return "sub_items" in item
  }

  const isSegmentCompany = (item: MenuItem | SubCategory | SegmentCompany): item is SegmentCompany => {
    return "type" in item && item.type === "company" && "segments" in item
  }

  const getCategoryIcon = (type: string) => {
    switch (type) {
      case "company":
        return <Building2 className="h-4 w-4" />
      case "account":
        return <FileText className="h-4 w-4" />
      case "segment":
        return <BarChart3 className="h-4 w-4" />
      default:
        return null
    }
  }

  return (
    <div className="p-4">
      <div className="space-y-1">
        {menuData.menu.map((category) => (
          <div key={category.category}>
            <button
              onClick={() => toggleCategory(category.category)}
              className="flex items-center w-full px-3 py-2 text-sm text-foreground hover:bg-accent rounded-lg transition-colors group"
            >
              {expandedCategories.has(category.category) ? (
                <ChevronDown className="h-4 w-4 mr-2 shrink-0 text-muted-foreground" />
              ) : (
                <ChevronRight className="h-4 w-4 mr-2 shrink-0 text-muted-foreground" />
              )}
              <span className="mr-2 text-muted-foreground">{getCategoryIcon(category.type)}</span>
              <span className="font-medium">{category.category}</span>
            </button>

            {expandedCategories.has(category.category) && (
              <div className="ml-6 mt-1 space-y-1">
                {category.items.map((item, idx) => {
                  // 사업 카테고리의 특별 처리
                  if (isSegmentCompany(item)) {
                    const companyKey = `segment-${item.id}`
                    return (
                      <div key={companyKey}>
                        <button
                          onClick={() => toggleCompany(companyKey)}
                          className="flex items-center w-full px-3 py-1.5 text-sm text-foreground hover:bg-accent rounded-md transition-colors"
                        >
                          {expandedCompanies.has(companyKey) ? (
                            <ChevronDown className="h-3 w-3 mr-2 shrink-0 text-muted-foreground" />
                          ) : (
                            <ChevronRight className="h-3 w-3 mr-2 shrink-0 text-muted-foreground" />
                          )}
                          <Building2 className="h-3 w-3 mr-2 shrink-0 text-muted-foreground" />
                          <span className="text-muted-foreground font-medium">{item.name}</span>
                        </button>

                        {expandedCompanies.has(companyKey) && (
                          <div className="ml-5 mt-1 space-y-1">
                            {/* CIC 레벨 (ELECTRIC만) */}
                            {item.cics && item.cics.length > 0 && item.cics.map((cic) => {
                              const cicKey = `${companyKey}-${cic.id}`
                              return (
                                <div key={cicKey}>
                                  <button
                                    onClick={() => toggleCIC(cicKey)}
                                    className="flex items-center w-full px-3 py-1.5 text-xs text-foreground hover:bg-accent rounded-md transition-colors"
                                  >
                                    {expandedCICs.has(cicKey) ? (
                                      <ChevronDown className="h-3 w-3 mr-2 shrink-0 text-muted-foreground" />
                                    ) : (
                                      <ChevronRight className="h-3 w-3 mr-2 shrink-0 text-muted-foreground" />
                                    )}
                                    <Network className="h-3 w-3 mr-2 shrink-0 text-muted-foreground" />
                                    <span className="text-muted-foreground">{cic.name}</span>
                                    <span className="ml-auto text-[10px] text-muted-foreground/60">
                                      {cic.segments.length}개
                                    </span>
                                  </button>

                                  {expandedCICs.has(cicKey) && (
                                    <div className="ml-5 mt-1 space-y-0.5">
                                      {cic.segments.map((segment) => (
                                        <button
                                          key={`${cicKey}-${segment}`}
                                          className="block w-full px-3 py-1 text-[11px] text-left text-muted-foreground hover:text-foreground hover:bg-accent/50 rounded-md transition-colors"
                                        >
                                          {segment}
                                        </button>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              )
                            })}

                            {/* 직접 사업 목록 (CIC 없는 회사) */}
                            {item.segments && item.segments.length > 0 && item.segments.map((segment) => (
                              <button
                                key={`${companyKey}-${segment}`}
                                className="block w-full px-3 py-1 text-xs text-left text-muted-foreground hover:text-foreground hover:bg-accent/50 rounded-md transition-colors"
                              >
                                {segment}
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    )
                  }
                  // 재무계정 카테고리의 SubCategory 처리
                  else if (isSubCategory(item)) {
                    const subKey = `${category.category}-${item.name}`
                    return (
                      <div key={subKey}>
                        <button
                          onClick={() => toggleSubCategory(subKey)}
                          className="flex items-center w-full px-3 py-1.5 text-sm text-foreground hover:bg-accent rounded-md transition-colors"
                        >
                          {expandedSubCategories.has(subKey) ? (
                            <ChevronDown className="h-3 w-3 mr-2 shrink-0 text-muted-foreground" />
                          ) : (
                            <ChevronRight className="h-3 w-3 mr-2 shrink-0 text-muted-foreground" />
                          )}
                          <span className="text-muted-foreground">{item.name}</span>
                        </button>

                        {expandedSubCategories.has(subKey) && (
                          <div className="ml-5 mt-1 space-y-0.5">
                            {item.sub_items.map((subItem) => (
                              <button
                                key={subItem.id}
                                className="block w-full px-3 py-1.5 text-xs text-left text-muted-foreground hover:text-foreground hover:bg-accent/50 rounded-md transition-colors"
                              >
                                {subItem.name}
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    )
                  }
                  // 일반 MenuItem (회사 카테고리)
                  else {
                    return (
                      <button
                        key={item.id}
                        className="block w-full px-3 py-1.5 text-sm text-left text-muted-foreground hover:text-foreground hover:bg-accent/50 rounded-md transition-colors"
                      >
                        {item.name}
                      </button>
                    )
                  }
                })}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
