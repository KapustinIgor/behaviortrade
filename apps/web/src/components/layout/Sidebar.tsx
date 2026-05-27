import { TrendingUp, TrendingDown, Minus, Activity } from "lucide-react";
import { cn } from "@/components/ui/cn";
import { Badge } from "@/components/ui/Badge";
import { useMarketStore } from "@/store/useMarketStore";
import { useBehaviorStore } from "@/store/useBehaviorStore";
import { useStrategies } from "@/api/strategies";
import type { Regime } from "@/types";

const ASSETS = ["BTC", "ETH", "SOL", "BNB", "XRP"];

function RegimeIcon({ regime }: { regime: Regime }) {
  if (regime === "bull") return <TrendingUp className="w-3 h-3" />;
  if (regime === "bear") return <TrendingDown className="w-3 h-3" />;
  if (regime === "transition") return <Activity className="w-3 h-3" />;
  return <Minus className="w-3 h-3" />;
}

export function Sidebar() {
  const { selectedAsset, setSelectedAsset, livePrice } = useMarketStore();
  const { scores, isConnected } = useBehaviorStore();
  const { data: strategies } = useStrategies();

  const activeStrategies = strategies?.filter((s) => s.is_active) ?? [];
  const regime = (scores?.regime ?? "sideways") as Regime;

  return (
    <aside className="w-[260px] flex-shrink-0 flex flex-col bg-surface-800 border-r border-surface-700 h-full">
      {/* Brand */}
      <div className="px-4 py-4 border-b border-surface-700">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-brand flex items-center justify-center">
            <Activity className="w-4 h-4 text-white" />
          </div>
          <span className="font-bold text-white text-lg tracking-tight">BehaviorTrade</span>
        </div>
        <div className="flex items-center gap-1.5 mt-2">
          <div className={cn("w-1.5 h-1.5 rounded-full", isConnected ? "bg-bull animate-pulse" : "bg-bear")} />
          <span className="text-xs text-gray-500">{isConnected ? "Live" : "Reconnecting..."}</span>
        </div>
      </div>

      {/* Regime */}
      {scores && (
        <div className="px-4 py-3 border-b border-surface-700">
          <div className="text-xs text-gray-500 mb-1.5">Market Regime</div>
          <div className="flex items-center justify-between">
            <Badge variant={regime}>
              <RegimeIcon regime={regime} />
              <span className="ml-1">{regime}</span>
            </Badge>
            <span className="text-xs text-gray-400">{scores.confidence}% confidence</span>
          </div>
        </div>
      )}

      {/* Asset selector */}
      <div className="px-4 py-3 border-b border-surface-700">
        <div className="text-xs text-gray-500 mb-2 uppercase tracking-wide">Assets</div>
        <div className="space-y-1">
          {ASSETS.map((asset) => {
            const price = livePrice[asset];
            const isSelected = selectedAsset === asset;
            return (
              <button
                key={asset}
                onClick={() => setSelectedAsset(asset)}
                className={cn(
                  "w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-colors",
                  isSelected
                    ? "bg-brand/20 text-brand-light border border-brand/30"
                    : "text-gray-400 hover:bg-surface-700 hover:text-gray-200"
                )}
              >
                <span className="font-semibold">{asset}</span>
                {price && (
                  <div className="text-right">
                    <div className="text-xs text-gray-300">${price.price.toLocaleString()}</div>
                    <div className={cn("text-xs", price.change_24h >= 0 ? "text-bull" : "text-bear")}>
                      {price.change_24h >= 0 ? "+" : ""}{price.change_24h.toFixed(2)}%
                    </div>
                  </div>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Active strategies */}
      <div className="px-4 py-3 flex-1 overflow-y-auto">
        <div className="text-xs text-gray-500 mb-2 uppercase tracking-wide">
          Active Strategies ({activeStrategies.length})
        </div>
        {activeStrategies.length === 0 ? (
          <p className="text-xs text-gray-600">No active strategies. Enable strategies from the marketplace.</p>
        ) : (
          <div className="space-y-1.5">
            {activeStrategies.map((s) => (
              <div key={s.name} className="flex items-center gap-2 text-xs">
                <div className={cn("w-1.5 h-1.5 rounded-full flex-shrink-0", s.signal_state === "active" ? "bg-bull" : s.signal_state === "blocked" ? "bg-bear" : "bg-warn")} />
                <span className="text-gray-300 truncate">{s.display_name}</span>
                <span className="ml-auto text-gray-500 flex-shrink-0">{s.modifier?.toFixed(1)}x</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Disclaimer */}
      <div className="px-4 py-3 border-t border-surface-700">
        <p className="text-[10px] text-gray-600 leading-relaxed">
          Research & analysis only. Not financial advice. All signals are probabilistic and carry risk.
        </p>
      </div>
    </aside>
  );
}
