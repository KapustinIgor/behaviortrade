import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost } from "./client";
import type { Prediction } from "@/types";

export function usePredictions(asset: string) {
  return useQuery<{ asset: string; predictions: Record<string, unknown> }>({
    queryKey: ["predictions", asset],
    queryFn: () => apiGet(`/predictions/${asset}`),
    refetchInterval: 30_000,
  });
}

export function useLatestPredictions(limit = 5) {
  return useQuery<Prediction[]>({
    queryKey: ["predictions_latest", limit],
    queryFn: () => apiGet<Prediction[]>("/predictions/latest", { limit: String(limit) }),
    refetchInterval: 30_000,
  });
}

export function usePredictionAccuracy() {
  return useQuery<{ overall: number; "1h": number; "4h": number; "24h": number; sample_size: number }>({
    queryKey: ["prediction_accuracy"],
    queryFn: () => apiGet("/predictions/accuracy"),
    staleTime: 60_000,
  });
}

export function useVotePrediction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, agree }: { id: string; agree: boolean }) =>
      apiPost(`/predictions/${id}/vote`, { agree }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["predictions_latest"] }),
  });
}

export interface PastPoint  { time: number; price: number; }
export interface FuturePoint { time: number; price: number; upper: number; lower: number; }

export interface PriceForecastData {
  asset: string;
  regime: string;
  gnn_confidence: number;
  direction: "up" | "down";
  prob_24h: number;
  past_line: PastPoint[];
  future_line: FuturePoint[];
  now_ts: number;
  generated_at: number;
  error?: string;
}

export function usePriceForecast(asset: string, enabled = true) {
  return useQuery<PriceForecastData>({
    queryKey: ["price_forecast", asset],
    queryFn: () => apiGet<PriceForecastData>(`/predictions/forecast/${asset}`),
    enabled: enabled && !!asset,
    refetchInterval: 300_000,
    staleTime: 300_000,
  });
}
