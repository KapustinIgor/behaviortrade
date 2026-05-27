import { create } from "zustand";
import type { MarketData } from "@/types";

interface MarketStore {
  selectedAsset: string;
  selectedTimeframe: string;
  watchlist: string[];
  livePrice: Record<string, MarketData>;
  setSelectedAsset: (asset: string) => void;
  setSelectedTimeframe: (tf: string) => void;
  addToWatchlist: (asset: string) => void;
  updateLivePrice: (data: MarketData) => void;
}

export const useMarketStore = create<MarketStore>((set) => ({
  selectedAsset: "BTC",
  selectedTimeframe: "1D",
  watchlist: ["BTC", "ETH", "SOL", "BNB", "XRP"],
  livePrice: {},
  setSelectedAsset: (asset) => set({ selectedAsset: asset }),
  setSelectedTimeframe: (tf) => set({ selectedTimeframe: tf }),
  addToWatchlist: (asset) =>
    set((s) => ({ watchlist: s.watchlist.includes(asset) ? s.watchlist : [...s.watchlist, asset] })),
  updateLivePrice: (data) =>
    set((s) => ({ livePrice: { ...s.livePrice, [data.asset]: data } })),
}));
