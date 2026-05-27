import { useQuery } from "@tanstack/react-query";
import { apiGet } from "./client";

export interface SubredditSentiment {
  mean_sentiment: number;
  post_count: number;
  bullish_pct: number;
  bearish_pct: number;
}

export interface RedditSentiment {
  overall_sentiment: number;
  total_posts: number;
  subreddits: Record<string, SubredditSentiment>;
  updated_at: string | null;
  note?: string;
}

export interface RedditPost {
  id: string;
  title: string;
  text: string;
  subreddit: string;
  score: number;
  upvote_ratio: number;
  num_comments: number;
  url: string;
  sentiment: "positive" | "negative" | "neutral";
  sentiment_score: number;
  positive: number;
  negative: number;
  asset_mentions: string[];
  scored_at: string;
  created_utc: number;
}

export function useRedditSentiment() {
  return useQuery<RedditSentiment>({
    queryKey: ["reddit_sentiment"],
    queryFn: () => apiGet("/social/reddit/sentiment"),
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
}

export function useRedditPosts(limit = 20) {
  return useQuery<{ posts: RedditPost[]; count: number }>({
    queryKey: ["reddit_posts", limit],
    queryFn: () => apiGet("/social/reddit/posts", { limit: String(limit) }),
    refetchInterval: 30_000,
  });
}
