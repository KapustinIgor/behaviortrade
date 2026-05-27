import { useQuery } from "@tanstack/react-query";
import { apiGet } from "./client";

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
