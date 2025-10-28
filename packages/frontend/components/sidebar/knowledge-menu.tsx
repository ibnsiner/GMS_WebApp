"use client"

import { useState } from "react"
import { ChevronDown, ChevronRight, Building2, FileText, BarChart3 } from "lucide-react"
import type { KnowledgeMenuData, SubCategory, MenuItem } from "@/lib/types"

interface KnowledgeMenuProps {
  menuData: KnowledgeMenuData | null
}

export function KnowledgeMenu({ menuData }: KnowledgeMenuProps) {
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set())
  const [expandedSubCategories, setExpandedSubCategories] = useState<Set<string>>(new Set())

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

  const isSubCategory = (item: MenuItem | SubCategory): item is SubCategory => {
    return "sub_items" in item
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
                  if (isSubCategory(item)) {
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
                  } else {
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
