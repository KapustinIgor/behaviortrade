import { useState } from "react";
import { ChevronDown, ChevronUp, ThumbsUp, ThumbsDown } from "lucide-react";
import { cn } from "@/components/ui/cn";
import { useVotePrediction } from "@/api/predictions";
import type { Prediction } from "@/types";

interface PredictionCardProps {
  prediction: Prediction;
}

export function PredictionCard({ prediction: p }: PredictionCardProps) {
  const [expanded, setExpanded] = useState(false);
  const vote = useVotePrediction();
  const isUp = p.direction === "up";

  return (
    <div className={cn("panel-sm overflow-hidden", isUp ? "border-bull/20" : "border-bear/20")}>
      <div className="p-3">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className={cn("text-2xl font-bold font-mono", isUp ? "text-bull" : "text-bear")}>
              {isUp ? "▲" : "▼"} {Math.round(p.probability)}%
            </span>
            <div>
              <div className="text-xs font-semibold text-gray-300">{p.asset}</div>
              <div className="text-xs text-gray-500">{p.timeframe} outlook</div>
            </div>
          </div>
          <div className="text-right">
            <div className="text-xs text-gray-500">confidence</div>
            <div className="text-sm font-mono text-info">{Math.round(p.confidence)}%</div>
          </div>
        </div>

        <button
          onClick={() => setExpanded((e) => !e)}
          className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-300 mt-2 transition-colors"
        >
          {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          Signals
        </button>

        {expanded && (
          <div className="mt-2 space-y-1.5">
            {p.contributing_signals.map((s, i) => (
              <div key={i} className="flex items-center gap-2 text-xs">
                <span className="text-gray-400 flex-1 truncate">{s.name}</span>
                <div className="flex-1 h-1 bg-surface-700 rounded-full">
                  <div
                    className="h-full bg-brand rounded-full"
                    style={{ width: `${Math.abs(s.value)}%` }}
                  />
                </div>
                <span className="font-mono text-gray-300 w-6 text-right">{Math.round(s.weight * 100)}%</span>
              </div>
            ))}
          </div>
        )}

        <div className="flex items-center gap-3 mt-2 pt-2 border-t border-surface-700">
          <button
            onClick={() => vote.mutate({ id: p.id, agree: true })}
            className="flex items-center gap-1 text-xs text-gray-500 hover:text-bull transition-colors"
          >
            <ThumbsUp className="w-3 h-3" />
            {p.community_agree ?? 0}
          </button>
          <button
            onClick={() => vote.mutate({ id: p.id, agree: false })}
            className="flex items-center gap-1 text-xs text-gray-500 hover:text-bear transition-colors"
          >
            <ThumbsDown className="w-3 h-3" />
            {p.community_disagree ?? 0}
          </button>
          {p.accuracy_flag !== undefined && (
            <span className={cn("ml-auto text-xs", p.accuracy_flag ? "text-bull" : "text-bear")}>
              {p.accuracy_flag ? "✓ Correct" : "✗ Wrong"}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
