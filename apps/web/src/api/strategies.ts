import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost } from "./client";
import type { StrategyState } from "@/types";

export interface StrategySignalEvent {
  ts: number;
  price: number;
  action: "buy" | "sell";
}

export interface StrategyPerf {
  equity: number[];
  signals: StrategySignalEvent[];
  total_return: number;
  win_rate: number;
  trades: number;
  regime_score: number;
  display_name: string;
  // Backtest quality metrics
  max_drawdown?: number;
  sharpe_approx?: number;
  profit_factor?: number;
  benchmark_buy_hold_return?: number;
}

export interface StrategyPerformanceData {
  asset: string;
  timestamps: number[];
  prices: number[];
  strategies: Record<string, StrategyPerf>;
  combo: { equity: number[]; signals: StrategySignalEvent[]; total_return: number; win_rate: number; trades: number };
  gnn_regime: string;
  recommended: string[];
  error?: string;
}

export interface RegimeScores {
  regime: string;
  gnn_confidence: number;
  scores: Record<string, number>;
  recommended: string[];
  avoid: string[];
}

export function useStrategies() {
  return useQuery<StrategyState[]>({
    queryKey: ["strategies"],
    queryFn: () => apiGet<StrategyState[]>("/strategies"),
    refetchInterval: 15_000,
  });
}

export interface StrategySignalResponse {
  name: string;
  action: "buy" | "sell" | "hold";
  state: string;
  modifier: number;
  gnn_influence: number;
  timestamp: string;
}

export function useStrategySignal(name: string) {
  return useQuery<StrategySignalResponse>({
    queryKey: ["strategy_signal", name],
    queryFn: () => apiGet<StrategySignalResponse>(`/strategies/${name}/signal`),
    enabled: !!name,
    refetchInterval: 15_000,
  });
}

export function useActivateStrategy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => apiPost(`/strategies/${name}/activate`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["strategies"] }),
  });
}

export function useDeactivateStrategy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => apiPost(`/strategies/${name}/deactivate`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["strategies"] }),
  });
}

export function useToggleGNN() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => apiPost(`/strategies/${name}/toggle-gnn`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["strategies"] }),
  });
}

export function useStrategyPerformance(asset: string) {
  return useQuery<StrategyPerformanceData>({
    queryKey: ["strategy_performance", asset],
    queryFn: () => apiGet(`/strategies/performance/${asset}`),
    refetchInterval: 300_000,  // refresh every 5 min (same as Binance cache)
    staleTime:       300_000,
    enabled: !!asset,
  });
}

export function useStrategyRegimeScores() {
  return useQuery<RegimeScores>({
    queryKey: ["strategy_regime_scores"],
    queryFn: () => apiGet("/strategies/regime-scores"),
    refetchInterval: 30_000,
    staleTime: 15_000,
  });
}
