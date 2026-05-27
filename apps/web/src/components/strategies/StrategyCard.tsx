import { Badge } from "@/components/ui/Badge";
import { GNNInfluenceBar } from "./GNNInfluenceBar";
import { cn } from "@/components/ui/cn";
import { useActivateStrategy, useDeactivateStrategy, useToggleGNN } from "@/api/strategies";
import type { StrategyState } from "@/types";

interface StrategyCardProps {
  strategy: StrategyState;
  isRecommended?: boolean;
}

export function StrategyCard({ strategy, isRecommended }: StrategyCardProps) {
  const activate   = useActivateStrategy();
  const deactivate = useDeactivateStrategy();
  const toggleGNN  = useToggleGNN();

  const stateVariant =
    strategy.signal_state === "active"  ? "active"  :
    strategy.signal_state === "blocked" ? "blocked" : "standby";

  const regimeScore   = (strategy as StrategyState & { regime_score?: number }).regime_score ?? 0;
  const regimeColor   = regimeScore >= 75 ? "#22c55e" : regimeScore >= 50 ? "#f59e0b" : "#ef4444";
  const regimeLabel   = regimeScore >= 75 ? "Good fit" : regimeScore >= 50 ? "Moderate" : "Poor fit";

  return (
    <div className={cn(
      "panel-sm p-4 flex flex-col gap-3 transition-colors",
      strategy.is_active && "border-brand/40",
      isRecommended && "border-brand/60 bg-brand/5",
    )}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            {isRecommended && <span className="text-brand-light text-xs">★</span>}
            <h4 className="font-semibold text-gray-200 text-sm truncate">{strategy.display_name}</h4>
          </div>
          <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">{strategy.description}</p>
        </div>
        <Badge variant={stateVariant} className="flex-shrink-0">{strategy.signal_state}</Badge>
      </div>

      {/* GNN Regime Fit */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs text-gray-500">Regime Fit</span>
          <span className="text-xs font-semibold" style={{ color: regimeColor }}>{regimeLabel}</span>
        </div>
        <div className="h-1 bg-surface-700 rounded-full overflow-hidden">
          <div className="h-full rounded-full transition-all" style={{ width: `${regimeScore}%`, backgroundColor: regimeColor }} />
        </div>
      </div>

      {/* GNN influence */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs text-gray-500">GNN Influence</span>
          <button
            onClick={() => toggleGNN.mutate(strategy.name)}
            className={cn(
              "text-xs px-2 py-0.5 rounded-full border transition-colors",
              strategy.gnn_enabled ? "border-brand/50 text-brand-light" : "border-surface-600 text-gray-500"
            )}
          >
            {strategy.gnn_enabled ? "ON" : "OFF"}
          </button>
        </div>
        <GNNInfluenceBar value={strategy.gnn_influence} />
      </div>

      {/* Modifier + P&L */}
      <div className="flex items-center justify-between text-xs">
        <div className="text-gray-500">
          Modifier:{" "}
          <span className={cn("font-mono font-semibold", strategy.modifier !== 1.0 ? "text-warn" : "text-gray-400")}>
            {strategy.modifier?.toFixed(2) ?? "1.00"}x
          </span>
        </div>
        <div className={cn("font-mono font-semibold", strategy.pnl_30d >= 0 ? "text-bull" : "text-bear")}>
          {strategy.pnl_30d >= 0 ? "+" : ""}{strategy.pnl_30d.toFixed(1)}% 30d
        </div>
      </div>

      {/* Action */}
      <button
        onClick={() => strategy.is_active ? deactivate.mutate(strategy.name) : activate.mutate(strategy.name)}
        className={cn(
          "w-full py-1.5 rounded-lg text-xs font-semibold transition-colors",
          strategy.is_active
            ? "bg-bear/20 text-bear hover:bg-bear/30"
            : "bg-brand/20 text-brand-light hover:bg-brand/30"
        )}
      >
        {strategy.is_active ? "Deactivate" : "Activate"}
      </button>
    </div>
  );
}
