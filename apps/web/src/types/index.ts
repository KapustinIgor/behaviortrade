export interface PriceCandle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface BehavioralScores {
  panic_score: number;
  greed_score: number;
  accumulation_score: number;
  distribution_score: number;
  regime: Regime;
  confidence: number;
  news_shock_score: number;
  direction_1h: number;
  direction_4h: number;
  direction_24h: number;
  updated_at?: string;
  [key: string]: number | string | undefined;
}

export type Regime = "bull" | "bear" | "sideways" | "transition";

export interface ContributingSignal {
  name: string;
  weight: number;
  value: number;
}

export interface Prediction {
  id: string;
  asset: string;
  direction: "up" | "down" | "sideways";
  probability: number;
  confidence: number;
  timeframe: "1h" | "4h" | "24h";
  contributing_signals: ContributingSignal[];
  created_at: string;
  outcome?: string;
  accuracy_flag?: boolean;
  community_agree?: number;
  community_disagree?: number;
}

export interface NewsItem {
  id: string | number;
  source: string;
  headline: string;
  url: string;
  sentiment_score: number;
  sentiment_label: "positive" | "negative" | "neutral";
  published_at: string;
  currencies: string[];
  votes: { positive: number; negative: number };
}

export interface StrategyState {
  name: string;
  display_name: string;
  description: string;
  signal_state: "active" | "standby" | "blocked";
  gnn_enabled: boolean;
  gnn_influence: number;
  position_size_modifier: number;
  action: string;
  modifier: number;
  pnl_30d: number;
  is_active: boolean;
  regime_score?: number;
}

export interface MarketData {
  asset: string;
  price: number;
  change_24h: number;
  volume_24h: number;
  market_cap?: number;
}

export interface CorrelationResult {
  signal_type: string;
  signal_source: string;
  asset: string;
  lag_hours: number;
  pearson_r: number;
  p_value: number;
  r_squared: number;
  sample_size: number;
  // Enriched fields
  strength?: "strong" | "moderate" | "weak" | "negligible";
  direction?: "positive" | "negative";
  is_actionable?: boolean;
  effective_sample_size?: number;
  data_quality?: "real" | "proxy" | "mixed";
  source_type?: "direct" | "derived" | "composite";
  warning?: string | null;
  lag_interpretation?: string;
}

export interface WhaleFlow {
  from: string;
  to: string;
  amount_usd: number;
  asset: string;
  timestamp: string;
  direction: "in" | "out";
}

export interface OHLCVResponse {
  asset: string;
  timeframe: string;
  data: Array<{ timestamp: number; open: number; high: number; low: number; close: number }>;
}
