import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/api/client";
import { NewsCard } from "./NewsCard";
import { cn } from "@/components/ui/cn";
import type { NewsItem } from "@/types";

type FilterType = "all" | "positive" | "negative";

export function NewsFeed() {
  const [filter, setFilter] = useState<FilterType>("all");

  const { data, isLoading } = useQuery<{ items: NewsItem[]; page: number }>({
    queryKey: ["news_feed", filter],
    queryFn: () => apiGet("/news/feed", { filter: "hot" }),
    refetchInterval: 60_000,
  });

  const items = (data?.items ?? []).filter((item) => {
    if (filter === "all") return true;
    return item.sentiment_label === filter;
  });

  const FILTERS: { key: FilterType; label: string }[] = [
    { key: "all", label: "All" },
    { key: "positive", label: "Positive" },
    { key: "negative", label: "Negative" },
  ];

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-2 border-b border-surface-700 flex-shrink-0">
        <span className="text-xs font-semibold text-gray-400 uppercase tracking-wide">News Feed</span>
        <div className="flex gap-1">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              className={cn(
                "px-2 py-0.5 rounded-full text-xs font-medium transition-colors",
                filter === f.key ? "bg-brand/20 text-brand-light" : "text-gray-500 hover:text-gray-300"
              )}
            >
              {f.label}
            </button>
          ))}
        </div>
        <span className="ml-auto text-xs text-gray-600">{items.length} articles</span>
      </div>

      {/* Scrollable horizontal feed */}
      <div className="flex-1 overflow-x-auto overflow-y-hidden">
        {isLoading ? (
          <div className="flex gap-3 p-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex-shrink-0 w-72 h-28 bg-surface-700 rounded-lg animate-pulse" />
            ))}
          </div>
        ) : (
          <div className="flex gap-3 p-3 h-full">
            {items.map((item) => (
              <NewsCard key={item.id} item={item} />
            ))}
            {items.length === 0 && (
              <div className="flex items-center justify-center w-full text-xs text-gray-600">
                No news items available.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
