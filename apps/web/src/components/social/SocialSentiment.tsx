import { formatDistanceToNow } from "date-fns";
import { useRedditPosts, useRedditSentiment } from "@/api/social";
import { PanelHeader } from "@/components/layout/PanelHeader";
import { cn } from "@/components/ui/cn";

function SentimentBar({ value, label }: { value: number; label: string }) {
  // value is -1..1, shift to 0..100 for display
  const pct = Math.round((value + 1) / 2 * 100);
  const color = value > 0.05 ? "bg-bull" : value < -0.05 ? "bg-bear" : "bg-warn";
  return (
    <div className="space-y-0.5">
      <div className="flex justify-between text-xs text-gray-400">
        <span className="truncate max-w-[110px]">{label}</span>
        <span className={cn("font-mono font-semibold", value > 0.05 ? "text-bull" : value < -0.05 ? "text-bear" : "text-warn")}>
          {value >= 0 ? "+" : ""}{(value * 100).toFixed(1)}
        </span>
      </div>
      <div className="h-1.5 bg-surface-700 rounded-full overflow-hidden">
        <div className={cn("h-full rounded-full transition-all", color)} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function PostCard({ post }: { post: import("@/api/social").RedditPost }) {
  const timeAgo = post.scored_at ? formatDistanceToNow(new Date(post.scored_at), { addSuffix: true }) : null;
  const sentColor = post.sentiment === "positive" ? "text-bull" : post.sentiment === "negative" ? "text-bear" : "text-gray-500";

  return (
    <a
      href={post.url}
      target="_blank"
      rel="noopener noreferrer"
      className="block px-4 py-2.5 border-b border-surface-700 last:border-0 hover:bg-surface-700/30 transition-colors"
    >
      <div className="flex items-start gap-2">
        <span className={cn("text-xs font-bold flex-shrink-0 w-10 text-right font-mono mt-0.5", sentColor)}>
          {post.sentiment_score >= 0 ? "+" : ""}{(post.sentiment_score * 100).toFixed(0)}
        </span>
        <div className="flex-1 min-w-0">
          <p className="text-xs text-gray-300 line-clamp-2 leading-relaxed">{post.title || post.text}</p>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="text-xs text-gray-600">${post.subreddit}</span>
            {post.asset_mentions.length > 0 && (
              <div className="flex gap-1">
                {post.asset_mentions.slice(0, 2).map((a) => (
                  <span key={a} className="text-[10px] bg-surface-700 text-gray-500 px-1 rounded">{a}</span>
                ))}
              </div>
            )}
            {timeAgo && <span className="text-xs text-gray-600">{timeAgo}</span>}
            <span className="text-xs text-gray-600 ml-auto flex-shrink-0">▲{post.score}</span>
          </div>
        </div>
      </div>
    </a>
  );
}

export function SocialSentiment() {
  const { data: agg } = useRedditSentiment();
  const { data: postsData, isLoading } = useRedditPosts(15);

  const subreddits = Object.entries(agg?.subreddits ?? {});
  const posts = postsData?.posts ?? [];
  const overall = agg?.overall_sentiment ?? null;
  const configured = agg && agg.total_posts > 0;

  return (
    <div className="flex flex-col">
      <PanelHeader
        title="Social Sentiment"
        badge={
          configured
            ? <span className="text-xs text-gray-500">{agg!.total_posts} messages</span>
            : <span className="text-xs text-gray-500">loading…</span>
        }
        actions={
          overall !== null && configured ? (
            <span className={cn(
              "text-xs font-mono font-semibold",
              overall > 0.05 ? "text-bull" : overall < -0.05 ? "text-bear" : "text-warn"
            )}>
              {overall >= 0 ? "+" : ""}{(overall * 100).toFixed(1)} overall
            </span>
          ) : null
        }
      />

      {!configured ? (
        <div className="px-4 py-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="py-2.5 border-b border-surface-700">
              <div className="h-7 bg-surface-700 rounded animate-pulse" />
            </div>
          ))}
        </div>
      ) : (
        <>
          {/* Per-subreddit bars */}
          {subreddits.length > 0 && (
            <div className="px-4 py-3 space-y-2.5 border-b border-surface-700">
              {subreddits.map(([sr, stats]) => (
                <SentimentBar key={sr} value={stats.mean_sentiment} label={`$${sr}`} />
              ))}
            </div>
          )}

          {/* Live post feed */}
          <div className="flex-1 overflow-y-auto">
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="px-4 py-2.5 border-b border-surface-700">
                  <div className="h-8 bg-surface-700 rounded animate-pulse" />
                </div>
              ))
            ) : posts.length > 0 ? (
              posts.map((post) => <PostCard key={post.id} post={post} />)
            ) : (
              <p className="px-4 py-4 text-xs text-gray-600">No posts yet — fetching…</p>
            )}
          </div>
        </>
      )}
    </div>
  );
}
