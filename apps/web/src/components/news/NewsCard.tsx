import { Badge } from "@/components/ui/Badge";
import { formatDistanceToNow } from "date-fns";
import type { NewsItem } from "@/types";

interface NewsCardProps {
  item: NewsItem;
}

export function NewsCard({ item }: NewsCardProps) {
  const sentimentVariant = item.sentiment_label === "positive" ? "positive" : item.sentiment_label === "negative" ? "negative" : "neutral";
  const timeAgo = item.published_at
    ? formatDistanceToNow(new Date(item.published_at), { addSuffix: true })
    : "";

  return (
    <a
      href={item.url}
      target="_blank"
      rel="noopener noreferrer"
      className="flex-shrink-0 w-72 panel-sm p-3 flex flex-col gap-2 hover:border-brand/40 transition-colors cursor-pointer"
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs text-gray-500">{item.source}</span>
        <Badge variant={sentimentVariant}>{item.sentiment_label}</Badge>
      </div>
      <p className="text-xs text-gray-300 line-clamp-2 leading-relaxed">{item.headline}</p>
      <div className="flex items-center justify-between">
        <span className="text-xs text-gray-600">{timeAgo}</span>
        {item.currencies?.length > 0 && (
          <div className="flex gap-1">
            {item.currencies.slice(0, 3).map((c) => (
              <span key={c} className="text-xs bg-surface-700 text-gray-400 px-1.5 py-0.5 rounded">{c}</span>
            ))}
          </div>
        )}
      </div>
    </a>
  );
}
