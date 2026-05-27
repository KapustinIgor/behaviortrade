import { useState, useMemo } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from "recharts";
import { useStrategyPerformance } from "@/api/strategies";
import { useMarketStore } from "@/store/useMarketStore";
import { cn } from "@/components/ui/cn";

const STRATEGY_COLORS: Record<string, string> = {
  TREND_FOLLOWING: "#3b82f6",
  SWING:           "#8b5cf6",
  SCALPING:        "#f59e0b",
  RANGE:           "#06b6d4",
  DCA:             "#22c55e",
  HODL:            "#6b7280",
  DAY_TRADING:     "#ec4899",
  ALGO_BOT:        "#f97316",
  NEWS_SENTIMENT:  "#84cc16",
  FUTURES:         "#ef4444",
  ARBITRAGE:       "#14b8a6",
  DEFI_YIELD:      "#a78bfa",
};

const COMBO_COLOR = "#ffffff";

const DISPLAY_NAMES: Record<string, string> = {
  TREND_FOLLOWING: "Trend",
  SWING:           "Swing",
  SCALPING:        "Scalping",
  RANGE:           "Range",
  DCA:             "DCA",
  HODL:            "HODL",
  DAY_TRADING:     "Day",
  ALGO_BOT:        "Algo",
  NEWS_SENTIMENT:  "News",
  FUTURES:         "Futures",
  ARBITRAGE:       "Arb",
  DEFI_YIELD:      "DeFi",
};

const REGIME_COLORS: Record<string, string> = {
  bull:       "text-bull",
  bear:       "text-bear",
  sideways:   "text-warn",
  transition: "text-gray-400",
};

interface StrategyPerformanceChartProps {
  height?: number;
}

export function StrategyPerformanceChart({ height = 220 }: StrategyPerformanceChartProps) {
  const selectedAsset = useMarketStore((s) => s.selectedAsset);
  const asset = selectedAsset?.toUpperCase() ?? "BTC";

  const { data, isLoading } = useStrategyPerformance(asset);

  // Which strategies are toggled on
  const [visible, setVisible] = useState<Set<string>>(
    new Set(["TREND_FOLLOWING", "SWING", "DCA", "ALGO_BOT"])
  );
  const [showCombo, setShowCombo] = useState(true);

  const toggle = (name: string) =>
    setVisible((prev) => {
      const next = new Set(prev);
      next.has(name) ? next.delete(name) : next.add(name);
      return next;
    });

  // Build chart data: one row per timestamp
  const chartData = useMemo(() => {
    if (!data?.timestamps || !data.strategies) return [];
    return data.timestamps.map((ts: number, i: number) => {
      const row: Record<string, number | string> = {
        time: new Date(ts * 1000).toLocaleDateString("en-US", { month: "short", day: "numeric" }),
      };
      for (const [name, strat] of Object.entries(data.strategies as Record<string, { equity: number[] }>)) {
        row[name] = strat.equity[i] ?? 0;
      }
      if (data.combo?.equity) {
        row["COMBO"] = data.combo.equity[i] ?? 0;
      }
      return row;
    });
  }, [data]);

  // Subsample to ~60 points for performance
  const sampledData = useMemo(() => {
    if (!chartData.length) return [];
    const step = Math.max(1, Math.floor(chartData.length / 60));
    return chartData.filter((_, i) => i % step === 0 || i === chartData.length - 1);
  }, [chartData]);

  const recommended = (data?.recommended ?? []) as string[];
  const regime      = (data?.gnn_regime  ?? "sideways") as string;

  if (isLoading) {
    return (
      <div className="h-56 flex items-center justify-center">
        <div className="text-xs text-gray-600 animate-pulse">Computing strategy signals…</div>
      </div>
    );
  }

  if (!data || data.error) {
    return (
      <div className="h-32 flex items-center justify-center text-xs text-gray-600">
        {data?.error ?? "No data"}
      </div>
    );
  }

  const strategies = data.strategies as Record<string, {
    equity: number[];
    total_return: number;
    win_rate: number;
    trades: number;
    regime_score: number;
    display_name: string;
  }>;

  return (
    <div className="border-t border-surface-700 bg-surface-800/30">
      {/* Header row */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-surface-700">
        <div className="flex items-center gap-3">
          <span className="text-xs font-semibold text-gray-300">Strategy Performance</span>
          <span className="text-xs text-gray-500">{asset} · last 200h</span>
          <span className={cn("text-xs font-mono font-semibold capitalize", REGIME_COLORS[regime])}>
            {regime} regime
          </span>
        </div>
        {/* Combo toggle */}
        <button
          onClick={() => setShowCombo((v) => !v)}
          className={cn(
            "text-xs px-2 py-0.5 rounded border transition-colors",
            showCombo ? "border-white/40 text-white" : "border-surface-600 text-gray-500"
          )}
        >
          Combo
        </button>
      </div>

      {/* Strategy chip selector */}
      <div className="flex flex-wrap gap-1.5 px-4 py-2 border-b border-surface-700">
        {Object.keys(STRATEGY_COLORS).map((name) => {
          const s = strategies[name];
          const isRec = recommended.includes(name);
          const ret = s?.total_return ?? 0;
          return (
            <button
              key={name}
              onClick={() => toggle(name)}
              style={visible.has(name) ? { borderColor: STRATEGY_COLORS[name], color: STRATEGY_COLORS[name] } : undefined}
              className={cn(
                "flex items-center gap-1 px-2 py-0.5 rounded border text-xs transition-colors",
                visible.has(name) ? "bg-opacity-10" : "border-surface-600 text-gray-600 hover:text-gray-400",
                isRec && !visible.has(name) && "border-brand/30 text-gray-400"
              )}
            >
              {isRec && <span className="text-brand-light">★</span>}
              {DISPLAY_NAMES[name]}
              <span className={cn("font-mono text-[10px]", ret >= 0 ? "text-bull" : "text-bear")}>
                {ret >= 0 ? "+" : ""}{ret.toFixed(1)}%
              </span>
            </button>
          );
        })}
      </div>

      {/* Chart */}
      <div style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={sampledData} margin={{ top: 8, right: 12, bottom: 0, left: -10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
            <XAxis
              dataKey="time"
              tick={{ fontSize: 9, fill: "#6b7280" }}
              interval="preserveStartEnd"
            />
            <YAxis
              tick={{ fontSize: 9, fill: "#6b7280" }}
              tickFormatter={(v) => `${v > 0 ? "+" : ""}${v.toFixed(0)}%`}
              width={42}
            />
            <Tooltip
              contentStyle={{ background: "#1f2937", border: "1px solid #374151", fontSize: 11 }}
              formatter={(value: number, name: string) => [
                `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`,
                name === "COMBO" ? "Combo" : (DISPLAY_NAMES[name] ?? name),
              ]}
            />
            <ReferenceLine y={0} stroke="#374151" strokeDasharray="4 4" />

            {/* Strategy lines */}
            {Object.keys(STRATEGY_COLORS).map((name) =>
              visible.has(name) ? (
                <Line
                  key={name}
                  type="monotone"
                  dataKey={name}
                  stroke={STRATEGY_COLORS[name]}
                  strokeWidth={1.5}
                  dot={false}
                  isAnimationActive={false}
                />
              ) : null
            )}

            {/* Combo line */}
            {showCombo && (
              <Line
                key="COMBO"
                type="monotone"
                dataKey="COMBO"
                stroke={COMBO_COLOR}
                strokeWidth={2.5}
                dot={false}
                isAnimationActive={false}
                strokeDasharray="6 2"
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Stats strip */}
      <div className="flex gap-4 overflow-x-auto px-4 py-2 border-t border-surface-700">
        {[...visible].map((name) => {
          const s = strategies[name];
          if (!s) return null;
          return (
            <div key={name} className="flex-shrink-0 text-xs space-y-0.5">
              <div className="font-medium" style={{ color: STRATEGY_COLORS[name] }}>
                {DISPLAY_NAMES[name]}
              </div>
              <div className={cn("font-mono", s.total_return >= 0 ? "text-bull" : "text-bear")}>
                {s.total_return >= 0 ? "+" : ""}{s.total_return.toFixed(1)}%
              </div>
              <div className="text-gray-600">{s.trades}T · {s.win_rate.toFixed(0)}%W</div>
            </div>
          );
        })}
        {showCombo && data.combo && (
          <div className="flex-shrink-0 text-xs space-y-0.5 border-l border-surface-700 pl-4">
            <div className="font-medium text-white">Combo</div>
            <div className={cn("font-mono", data.combo.total_return >= 0 ? "text-bull" : "text-bear")}>
              {data.combo.total_return >= 0 ? "+" : ""}{data.combo.total_return.toFixed(1)}%
            </div>
            <div className="text-gray-600">{data.combo.trades}T · {data.combo.win_rate.toFixed(0)}%W</div>
          </div>
        )}
      </div>
    </div>
  );
}
