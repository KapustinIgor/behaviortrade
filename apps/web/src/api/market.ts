import { useQuery } from "@tanstack/react-query";
import { apiGet } from "./client";
import type { MarketData, OHLCVResponse } from "@/types";

export function useOHLCV(asset: string, timeframe: string) {
  return useQuery<OHLCVResponse>({
    queryKey: ["ohlcv", asset, timeframe],
    queryFn: () => apiGet<OHLCVResponse>(`/prices/${asset}/ohlcv`, { timeframe }),
    staleTime: 30_000,
  });
}

export function useLatestPrice(asset: string) {
  return useQuery<MarketData>({
    queryKey: ["price", asset],
    queryFn: () => apiGet<MarketData>(`/prices/${asset}/latest`),
    refetchInterval: 5_000,
  });
}

export function useGlobalMetrics() {
  return useQuery<Record<string, unknown>>({
    queryKey: ["global_metrics"],
    queryFn: () => apiGet<Record<string, unknown>>("/prices/global"),
    staleTime: 60_000,
  });
}
