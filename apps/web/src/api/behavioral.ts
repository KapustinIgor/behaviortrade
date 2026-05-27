import { useQuery } from "@tanstack/react-query";
import { apiGet } from "./client";
import type { BehavioralScores } from "@/types";

export function useBehavioralScores() {
  return useQuery<BehavioralScores>({
    queryKey: ["behavioral_scores"],
    queryFn: () => apiGet<BehavioralScores>("/behavioral/scores"),
    refetchInterval: 10_000,
  });
}

export function useFearGreed() {
  return useQuery<{ value: number; value_classification: string; last_30_days: { value: number; classification: string; timestamp: string }[] }>({
    queryKey: ["fear_greed"],
    queryFn: () => apiGet("/behavioral/fear-greed"),
    refetchInterval: 300_000,
    staleTime: 60_000,
  });
}

export function useBehavioralHistory(asset: string, from: string, to: string) {
  return useQuery<{ asset: string; data: BehavioralScores[] }>({
    queryKey: ["behavioral_history", asset, from, to],
    queryFn: () => apiGet(`/behavioral/history`, { asset, from, to }),
    enabled: !!asset,
  });
}
