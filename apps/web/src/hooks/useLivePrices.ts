import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/api/client";
import { useMarketStore } from "@/store/useMarketStore";
import type { MarketData } from "@/types";

const ASSETS = ["BTC", "ETH", "SOL", "BNB", "XRP"];

export function useLivePrices() {
  const updateLivePrice = useMarketStore((s) => s.updateLivePrice);

  const { data } = useQuery<MarketData[]>({
    queryKey: ["prices_all"],
    queryFn: () =>
      Promise.all(ASSETS.map((a) => apiGet<MarketData>(`/prices/${a}/latest`))),
    refetchInterval: 30_000,
    staleTime: 25_000,
  });

  useEffect(() => {
    if (!data) return;
    data.forEach((price, i) => {
      updateLivePrice({ ...price, asset: ASSETS[i] });
    });
  }, [data, updateLivePrice]);
}
