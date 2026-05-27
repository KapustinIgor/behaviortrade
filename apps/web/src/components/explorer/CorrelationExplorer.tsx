import { useState } from "react";
import { X, RefreshCw } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/api/client";
import { CorrelationChart } from "@/components/charts/CorrelationChart";
import { cn } from "@/components/ui/cn";
import type { CorrelationResult } from "@/types";

const SIGNALS = [
  { value: "fear_greed",       label: "Fear & Greed Index" },
  { value: "reddit_sentiment", label: "Reddit Sentiment" },
  { value: "twitter_volume",   label: "Twitter Volume" },
  { value: "whale_inflow",     label: "Whale Exchange Inflows" },
  { value: "google_trends",    label: "Google Trends (BTC)" },
  { value: "news_sentiment",   label: "News Sentiment" },
];

const ASSETS = ["BTC", "ETH", "SOL", "BNB", "XRP"];

interface CorrelationExplorerProps {
  onClose: () => void;
}

export function CorrelationExplorer({ onClose }: CorrelationExplorerProps) {
  const [signal, setSignal] = useState("fear_greed");
  const [asset,  setAsset]  = useState("BTC");
  const [lag,    setLag]    = useState(0);

  // Top correlations (best lag per signal) for the summary cards
  const { data: topData, isLoading: topLoading } = useQuery<{
    asset: string;
    top_correlations: CorrelationResult[];
    multiple_testing_warning?: string | null;
  }>({
    queryKey: ["correlations_top", asset],
    queryFn:  () => apiGet("/correlations/top", { asset }),
    staleTime: 300_000,
  });

  // Lag-sweep for the selected signal — all lags at once for the chart
  const { data: sweepData, isLoading: sweepLoading } = useQuery<{
    asset: string;
    correlations: CorrelationResult[];
  }>({
    queryKey: ["correlations_sweep", asset, signal],
    queryFn:  () => apiGet("/correlations", { asset, signal_type: signal }),
    staleTime: 300_000,
  });

  // Single-lag detail for the stat cards
  const { data: detailData } = useQuery<{
    asset: string;
    correlations: CorrelationResult[];
  }>({
    queryKey: ["correlations_detail", asset, signal, lag],
    queryFn:  () => apiGet("/correlations", { asset, signal_type: signal, lag_hours: String(lag) }),
    staleTime: 60_000,
    enabled: lag !== 0,
  });

  const topCorrelations         = topData?.top_correlations ?? [];
  const sweepCorrelations       = sweepData?.correlations    ?? [];
  const multipleTestingWarning  = topData?.multiple_testing_warning ?? null;
  // For the selected signal at the chosen lag — fall back to sweep data
  const lagPoint = detailData?.correlations?.[0]
    ?? sweepCorrelations.find((c) => c.lag_hours === lag);

  const isLoading = topLoading || sweepLoading;

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-surface-800 border border-surface-700 rounded-2xl w-full max-w-4xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-surface-700">
          <div>
            <h2 className="text-lg font-bold text-white">Behavior ↔ Price Correlation Explorer</h2>
            <p className="text-sm text-gray-500 mt-0.5">
              Which behavioral signals historically led price movements for {asset}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {isLoading && <RefreshCw className="w-4 h-4 text-gray-500 animate-spin" />}
            <button onClick={onClose} className="p-2 rounded-lg hover:bg-surface-700 text-gray-400">
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        <div className="flex gap-6 p-6 flex-1 overflow-y-auto min-h-0">
          {/* Controls */}
          <div className="w-52 flex-shrink-0 space-y-5">
            {/* Signal selector */}
            <div>
              <label className="text-xs text-gray-500 uppercase tracking-wide block mb-2">Signal</label>
              <div className="space-y-0.5">
                {SIGNALS.map((s) => (
                  <button
                    key={s.value}
                    onClick={() => setSignal(s.value)}
                    className={cn(
                      "w-full text-left text-xs px-3 py-2 rounded-lg transition-colors",
                      signal === s.value
                        ? "bg-brand/20 text-brand-light border border-brand/30"
                        : "text-gray-400 hover:bg-surface-700 border border-transparent"
                    )}
                  >
                    {s.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Asset selector */}
            <div>
              <label className="text-xs text-gray-500 uppercase tracking-wide block mb-2">Asset</label>
              <div className="flex flex-wrap gap-1">
                {ASSETS.map((a) => (
                  <button
                    key={a}
                    onClick={() => setAsset(a)}
                    className={cn(
                      "px-2 py-1 rounded text-xs font-medium transition-colors",
                      asset === a ? "bg-brand text-white" : "bg-surface-700 text-gray-400 hover:text-gray-200"
                    )}
                  >
                    {a}
                  </button>
                ))}
              </div>
            </div>

            {/* Lag slider */}
            <div>
              <label className="text-xs text-gray-500 uppercase tracking-wide block mb-2">
                Lag:{" "}
                <span className="text-gray-300 font-mono">
                  {lag > 0 ? `+${lag}h` : lag < 0 ? `${lag}h` : "0 (same time)"}
                </span>
              </label>
              <input
                type="range"
                min={-168}
                max={168}
                step={4}
                value={lag}
                onChange={(e) => setLag(Number(e.target.value))}
                className="w-full accent-brand"
              />
              <div className="flex justify-between text-xs text-gray-600 mt-1">
                <span>-7d</span><span>0</span><span>+7d</span>
              </div>
              <p className="text-[10px] text-gray-600 mt-2">
                Negative = signal lagged behind price<br />
                Positive = signal led price
              </p>
            </div>

            {/* Selected signal at chosen lag */}
            {lagPoint && (
              <div className="bg-surface-700 rounded-xl p-3 space-y-2 text-xs border border-surface-600">
                <p className="text-gray-400 font-semibold">
                  {SIGNALS.find(s => s.value === signal)?.label}
                </p>
                <div className="flex justify-between">
                  <span className="text-gray-500">Lag</span>
                  <span className="font-mono text-gray-300">{lagPoint.lag_hours}h</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Pearson R</span>
                  <span className={cn("font-mono font-bold", lagPoint.pearson_r > 0 ? "text-bull" : lagPoint.pearson_r < 0 ? "text-bear" : "text-gray-400")}>
                    {lagPoint.pearson_r.toFixed(3)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">p-value</span>
                  <span className="font-mono">{lagPoint.p_value.toFixed(4)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">R²</span>
                  <span className="font-mono">{lagPoint.r_squared.toFixed(3)}</span>
                </div>
                {lagPoint.p_value < 0.05 && (
                  <p className="text-[10px] text-brand-light">Statistically significant (p &lt; 0.05)</p>
                )}
              </div>
            )}
          </div>

          {/* Right: chart + top correlations */}
          <div className="flex-1 space-y-4 min-w-0">
            {/* Lag-sweep chart for selected signal */}
            {sweepCorrelations.length > 0 && (
              <div className="bg-surface-700 rounded-xl p-4">
                <p className="text-xs text-gray-500 mb-3">
                  Pearson R across lag window —{" "}
                  <span className="text-gray-300">{SIGNALS.find(s => s.value === signal)?.label}</span>
                </p>
                <CorrelationChart data={sweepCorrelations} selectedLag={lag} />
              </div>
            )}

            {/* Top signal summary cards */}
            {topCorrelations.length > 0 && (
              <div>
                <p className="text-xs text-gray-500 mb-2">Best correlations — {asset}</p>

                {/* Multiple testing warning banner */}
                {multipleTestingWarning && (
                  <div className="mb-2 px-3 py-2 rounded-lg bg-yellow-500/10 border border-yellow-500/30 text-[10px] text-yellow-400 leading-relaxed">
                    {multipleTestingWarning}
                  </div>
                )}

                <div className="grid grid-cols-2 gap-2">
                  {topCorrelations.slice(0, 4).map((c, i) => (
                    <button
                      key={i}
                      onClick={() => {
                        const match = SIGNALS.find(s => s.value === c.signal_type);
                        if (match) setSignal(match.value);
                        setLag(c.lag_hours);
                      }}
                      className={cn(
                        "rounded-lg p-3 text-xs space-y-1 text-left transition-colors border hover:border-brand/30",
                        c.data_quality !== "real"
                          ? "bg-surface-700/50 hover:bg-surface-600/50 border-surface-700/50 opacity-70"
                          : "bg-surface-700 hover:bg-surface-600 border-transparent"
                      )}
                    >
                      <div className="flex items-center gap-1.5">
                        <span className={cn(
                          "font-semibold truncate flex-1",
                          c.data_quality !== "real" ? "text-gray-500" : "text-gray-300"
                        )}>{c.signal_source}</span>
                        {c.data_quality && (
                          <span className={cn(
                            "px-1 py-0.5 rounded text-[9px] font-medium flex-shrink-0",
                            c.data_quality === "real"         ? "bg-green-500/20 text-green-400" :
                            c.data_quality === "proxy"        ? "bg-yellow-500/20 text-yellow-400" :
                            c.data_quality === "insufficient" ? "bg-red-500/20 text-red-400" :
                                                                "bg-gray-500/20 text-gray-400"
                          )}>
                            {c.data_quality.toUpperCase()}
                          </span>
                        )}
                      </div>
                      <div className="flex justify-between text-gray-500">
                        <span>Pearson R</span>
                        <span className={cn("font-mono font-semibold", c.pearson_r > 0 ? "text-bull" : "text-bear")}>
                          {c.pearson_r.toFixed(3)}
                        </span>
                      </div>
                      {c.spearman_r != null && (
                        <div className="flex justify-between text-gray-500">
                          <span>Spearman R</span>
                          <span className={cn("font-mono", c.spearman_r > 0 ? "text-bull/80" : "text-bear/80")}>
                            {c.spearman_r.toFixed(3)}
                          </span>
                        </div>
                      )}
                      <div className="flex justify-between text-gray-500">
                        <span>Best lag</span>
                        <span className="font-mono">{c.lag_hours}h</span>
                      </div>
                      <div className="flex justify-between text-gray-500">
                        <span>Strength</span>
                        <span className={cn("font-mono capitalize", {
                          "text-green-400":  c.strength === "strong",
                          "text-yellow-400": c.strength === "moderate",
                          "text-gray-400":   c.strength === "weak" || c.strength === "negligible",
                        })}>{c.strength ?? "—"}</span>
                      </div>
                      {c.p_value_method && (
                        <p className="text-[9px] text-gray-600 font-mono">
                          method: {c.p_value_method}
                        </p>
                      )}
                      {c.actionability_reason && (
                        <p className="text-[9px] text-gray-500 italic leading-tight mt-0.5">
                          {c.actionability_reason}
                        </p>
                      )}
                      {c.warning && (
                        <p className="text-[9px] text-yellow-400/70 leading-tight mt-0.5">{c.warning}</p>
                      )}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {!isLoading && sweepCorrelations.length === 0 && topCorrelations.length === 0 && (
              <div className="flex items-center justify-center h-40 text-gray-600 text-sm">
                Price history unavailable — correlations require live price data
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
