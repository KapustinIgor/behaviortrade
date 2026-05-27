import { useState } from "react";
import { X, Zap } from "lucide-react";
import { useStrategies, useStrategyRegimeScores, useStrategyPerformance } from "@/api/strategies";
import { StrategyCard } from "./StrategyCard";
import { cn } from "@/components/ui/cn";
import type { StrategyState } from "@/types";

type FilterState = "all" | "active" | "standby" | "blocked" | "gnn_picks";

interface StrategyMarketplaceProps {
  onClose: () => void;
}

const REGIME_COLORS: Record<string, string> = {
  bull: "text-bull", bear: "text-bear", sideways: "text-warn", transition: "text-gray-400",
};

export function StrategyMarketplace({ onClose }: StrategyMarketplaceProps) {
  const [filter, setFilter]         = useState<FilterState>("all");
  const [comboNames, setComboNames] = useState<Set<string>>(new Set());
  const [comboAsset, setComboAsset] = useState("BTC");

  const { data: strategies, isLoading }            = useStrategies();
  const { data: regimeScores }                     = useStrategyRegimeScores();
  const { data: perfData, isLoading: perfLoading } = useStrategyPerformance(comboAsset);

  const recommended = regimeScores?.recommended ?? [];
  const regime      = regimeScores?.regime ?? "sideways";

  const filtered = (strategies ?? []).filter((s: StrategyState) => {
    if (filter === "all")       return true;
    if (filter === "active")    return s.is_active;
    if (filter === "gnn_picks") return recommended.includes(s.name);
    return s.signal_state === filter;
  });

  const FILTERS: { key: FilterState; label: string }[] = [
    { key: "all",       label: "All" },
    { key: "active",    label: "Active" },
    { key: "standby",   label: "Standby" },
    { key: "blocked",   label: "Blocked" },
    { key: "gnn_picks", label: "★ GNN Picks" },
  ];

  const toggleCombo = (name: string) =>
    setComboNames((prev) => {
      const next = new Set(prev);
      next.has(name) ? next.delete(name) : next.add(name);
      return next;
    });

  const selectedPerfs = [...comboNames].map((n) => perfData?.strategies?.[n]).filter(Boolean);
  const avgReturn = selectedPerfs.length
    ? selectedPerfs.reduce((acc, s) => acc + (s?.total_return ?? 0), 0) / selectedPerfs.length
    : null;
  const comboPerf = perfData?.combo;

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-surface-800 border border-surface-700 rounded-2xl w-full max-w-5xl max-h-[90vh] flex flex-col">

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-surface-700">
          <div>
            <h2 className="text-lg font-bold text-white">Strategy Marketplace</h2>
            <p className="text-sm text-gray-500 mt-0.5">
              12 strategies · GNN regime:{" "}
              <span className={cn("font-semibold capitalize", REGIME_COLORS[regime])}>{regime}</span>
              {regimeScores && (
                <span className="text-gray-600 ml-2">· {Math.round(regimeScores.gnn_confidence * 100)}% confidence</span>
              )}
            </p>
          </div>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-surface-700 text-gray-400">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-2 px-6 py-3 border-b border-surface-700">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              className={cn(
                "flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium transition-colors",
                filter === f.key ? "bg-brand text-white" : "text-gray-400 hover:text-gray-200 bg-surface-700"
              )}
            >
              {f.key === "gnn_picks" && <Zap className="w-3 h-3" />}
              {f.label}
            </button>
          ))}
          <span className="ml-auto text-xs text-gray-500">{filtered.length} strategies</span>
        </div>

        <div className="flex flex-1 overflow-hidden">
          {/* Strategy grid */}
          <div className="overflow-y-auto flex-1 p-6">
            {isLoading ? (
              <div className="grid grid-cols-3 gap-4">
                {Array.from({ length: 12 }).map((_, i) => (
                  <div key={i} className="h-52 bg-surface-700 rounded-lg animate-pulse" />
                ))}
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {filtered.map((s: StrategyState) => (
                  <StrategyCard key={s.name} strategy={s} isRecommended={recommended.includes(s.name)} />
                ))}
              </div>
            )}
          </div>

          {/* Combo builder panel */}
          <div className="w-64 flex-shrink-0 border-l border-surface-700 flex flex-col">
            <div className="px-4 py-3 border-b border-surface-700">
              <h3 className="text-sm font-semibold text-gray-200">Combo Builder</h3>
              <p className="text-xs text-gray-500 mt-0.5">Select to see combined P&L</p>
            </div>

            <div className="flex gap-1 px-4 py-2 border-b border-surface-700">
              {["BTC", "ETH", "SOL"].map((a) => (
                <button key={a} onClick={() => setComboAsset(a)}
                  className={cn("px-2 py-0.5 rounded text-xs font-medium transition-colors",
                    comboAsset === a ? "bg-brand text-white" : "bg-surface-700 text-gray-400")}
                >{a}</button>
              ))}
            </div>

            <div className="overflow-y-auto flex-1 px-4 py-2 space-y-1">
              {(strategies ?? []).map((s: StrategyState) => {
                const ret = perfData?.strategies?.[s.name]?.total_return ?? 0;
                return (
                  <label key={s.name} className="flex items-center gap-2 cursor-pointer group py-1">
                    <input type="checkbox" checked={comboNames.has(s.name)}
                      onChange={() => toggleCombo(s.name)} className="accent-brand w-3 h-3" />
                    <span className="text-xs text-gray-300 flex-1 truncate group-hover:text-white transition-colors">
                      {s.display_name}
                    </span>
                    <span className={cn("text-xs font-mono flex-shrink-0", ret >= 0 ? "text-bull" : "text-bear")}>
                      {ret >= 0 ? "+" : ""}{ret.toFixed(1)}%
                    </span>
                  </label>
                );
              })}
            </div>

            <div className="border-t border-surface-700 px-4 py-3 space-y-2">
              {comboNames.size === 0 ? (
                <p className="text-xs text-gray-600">Check strategies above to combine.</p>
              ) : (
                <>
                  <div className="text-xs">
                    <span className="text-gray-500">Selected: </span>
                    <span className="text-gray-200 font-semibold">{comboNames.size}</span>
                  </div>
                  {avgReturn !== null && (
                    <div className="text-xs">
                      <span className="text-gray-500">Avg return: </span>
                      <span className={cn("font-mono font-semibold", avgReturn >= 0 ? "text-bull" : "text-bear")}>
                        {avgReturn >= 0 ? "+" : ""}{avgReturn.toFixed(1)}%
                      </span>
                    </div>
                  )}
                  {comboPerf && (
                    <div className="bg-surface-700 rounded-lg p-2 space-y-1 text-xs">
                      <div className="font-semibold text-gray-300">All-12 Combo</div>
                      <div className="flex justify-between text-gray-500">
                        <span>Return</span>
                        <span className={cn("font-mono font-semibold", comboPerf.total_return >= 0 ? "text-bull" : "text-bear")}>
                          {comboPerf.total_return >= 0 ? "+" : ""}{comboPerf.total_return.toFixed(1)}%
                        </span>
                      </div>
                      <div className="flex justify-between text-gray-500">
                        <span>Win rate</span><span className="font-mono">{comboPerf.win_rate.toFixed(0)}%</span>
                      </div>
                      <div className="flex justify-between text-gray-500">
                        <span>Trades</span><span className="font-mono">{comboPerf.trades}</span>
                      </div>
                    </div>
                  )}
                  {perfLoading && <div className="text-xs text-gray-600 animate-pulse">Computing…</div>}
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
