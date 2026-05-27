import { useQuery } from "@tanstack/react-query";
import { apiGet } from "./client";

// ── Behavioral GNN graph (existing) ──────────────────────────────────────────

export interface GraphNode {
  id: string;
  type: string;
  label: string;
  group: number;
  size: number;
  color: string;
  metrics: {
    volume_rank: number;
    change_24h: number;
    sentiment: number;
    fg_signal: number;
  };
  features: number[];
}

export interface GraphEdge {
  source: string;
  target: string;
  type: string;
  weight: number;
  color: string;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  meta: {
    regime: string;
    gnn_confidence: number;
    node_count: number;
    edge_count: number;
    generated_at: number;
  };
}

export function useGNNGraph() {
  return useQuery<GraphData>({
    queryKey: ["gnn_graph"],
    queryFn: () => apiGet<GraphData>("/gnn/graph"),
    refetchInterval: 30_000,
    staleTime: 15_000,
  });
}

// ── Strategy 3-D graph ────────────────────────────────────────────────────────

export interface StrategyGraphNode {
  id: string;
  name: string;
  type: "strategy" | "combo" | "regime" | "behavioral";
  group: number;
  val: number;
  color: string;
  pnl_30d?: number;
  win_rate?: number;
  regime_score?: number;
  is_active?: boolean;
  description?: string;
  synergy?: number;
  correlation?: number;
  members?: string[];
  score?: number;
  current?: boolean;
  // force-graph positions
  fx?: number;
  fy?: number;
  fz?: number;
  // runtime (set by force-graph)
  x?: number;
  y?: number;
  z?: number;
}

export interface StrategyGraphLink {
  source: string | StrategyGraphNode;
  target: string | StrategyGraphNode;
  value: number;
  type: "synergy" | "combo_member" | "regime_fit" | "beh_influence";
  color: string;
  label?: string;
}

export interface StrategyGraphData {
  nodes: StrategyGraphNode[];
  links: StrategyGraphLink[];
  meta: {
    asset: string;
    regime: string;
    gnn_confidence: number;
    node_count: number;
    link_count: number;
    generated_at: number;
  };
}

export function useStrategyGraph(asset = "BTC") {
  return useQuery<StrategyGraphData>({
    queryKey: ["strategy_graph", asset],
    queryFn:  () => apiGet<StrategyGraphData>("/gnn/strategy-graph", { asset }),
    staleTime: 60_000,
    refetchInterval: 60_000,
  });
}
