import { useState } from "react";
import { X } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/api/client";
import { CorrelationChart } from "@/components/charts/CorrelationChart";
import { cn } from "@/components/ui/cn";
import type { CorrelationResult } from "@/types";

const SIGNALS = [
  { value: "fear_greed", label: "Fear & Greed Index" },
  { value: "reddit_sentiment", label: "Reddit Sentiment" },
  { value: "twitter_volume", label: "Twitter Volume" },
  { value: "whale_inflow", label: "Whale Exchange Inflows" },
  { value: "google_trends", label: "Google Trends (BTC)" },
  { value: "news_sentiment", label: "News Sentiment" },
];

const ASSETS = ["BTC", "ETH", "SOL", "BNB", "XRP"];

interface CorrelationExplorerProps {
  onClose: () => void;
}

export function CorrelationExplorer({ onClose }: CorrelationExplorerProps) {
  const [signal, setSignal] = useState("fear_greed");
  const [asset, setAsset] = useState("BTC");
  const [lag, setLag] = useState(0);

  const { data } = useQuery<{ asset: string; top_correlations: CorrelationResult[] }>({
    queryKey: ["correlations_top", asset],
    queryFn: () => apiGet("/correlations/top", { asset }),
  });

  const correlations = data?.top_correlations ?? [];

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-surface-800 border border-surface-700 rounded-2xl w-full max-w-4xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-surface-700">
          <div>
            <h2 className="text-lg font-bold text-white">Behavior ↔ Price Correlation Explorer</h2>
            <p className="text-sm text-gray-500 mt-0.5">Discover which behavioral signals historically led price movements</p>
          </div>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-surface-700 text-gray-400">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex gap-6 p-6 flex-1 overflow-y-auto">
          {/* Controls */}
          <div className="w-56 flex-shrink-0 space-y-4">
            <div>
              <label className="text-xs text-gray-500 uppercase tracking-wide block mb-2">Signal</label>
              <div className="space-y-1">
                {SIGNALS.map((s) => (
                  <button
                    key={s.value}
                    onClick={() => setSignal(s.value)}
                    className={cn("w-full text-left text-xs px-3 py-2 rounded-lg transition-colors", signal === s.value ? "bg-brand/20 text-brand-light" : "text-gray-400 hover:bg-surface-700")}
                  >
                    {s.label}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="text-xs text-gray-500 uppercase tracking-wide block mb-2">Asset</label>
              <div className="flex flex-wrap gap-1">
                {ASSETS.map((a) => (
                  <button key={a} onClick={() => setAsset(a)} className={cn("px-2 py-1 rounded text-xs font-medium transition-colors", asset === a ? "bg-brand text-white" : "bg-surface-700 text-gray-400 hover:text-gray-200")}>
                    {a}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="text-xs text-gray-500 uppercase tracking-wide block mb-2">
                Lag: {lag > 0 ? `+${lag}h` : lag < 0 ? `${lag}h` : "0 (same time)"}
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
                <span>-7d</span>
                <span>0</span>
                <span>+7d</span>
              </div>
            </div>
          </div>

          {/* Chart + Stats */}
          <div className="flex-1 space-y-4">
            <CorrelationChart data={correlations} selectedLag={lag} />

            {correlations.length > 0 && (
              <div className="grid grid-cols-2 gap-3">
                {correlations.slice(0, 4).map((c, i) => (
                  <div key={i} className="bg-surface-700 rounded-lg p-3 text-xs space-y-1">
                    <div className="font-semibold text-gray-300">{c.signal_source}</div>
                    <div className="flex justify-between text-gray-500">
                      <span>Pearson R</span>
                      <span className={cn("font-mono font-semibold", c.pearson_r > 0 ? "text-bull" : "text-bear")}>{c.pearson_r.toFixed(3)}</span>
                    </div>
                    <div className="flex justify-between text-gray-500">
                      <span>p-value</span>
                      <span className="font-mono">{c.p_value.toFixed(4)}</span>
                    </div>
                    <div className="flex justify-between text-gray-500">
                      <span>R²</span>
                      <span className="font-mono">{c.r_squared.toFixed(3)}</span>
                    </div>
                    <div className="flex justify-between text-gray-500">
                      <span>Lag</span>
                      <span className="font-mono">{c.lag_hours}h</span>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <p className="text-xs text-gray-600">
              Full correlation computation with real data arrives in Phase 3. Shown above is sample data demonstrating the interface.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
