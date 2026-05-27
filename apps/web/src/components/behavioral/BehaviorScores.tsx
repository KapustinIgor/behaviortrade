import { useBehaviorStore } from "@/store/useBehaviorStore";
import { useBehavioralScores } from "@/api/behavioral";
import { PanelHeader } from "@/components/layout/PanelHeader";
import { ScoreBar } from "@/components/ui/ScoreBar";
import { Sparkline } from "@/components/ui/Sparkline";
import { FearGreedGauge } from "./FearGreedGauge";
import { RegimeBadge } from "./RegimeBadge";

const SCORE_CONFIGS = [
  { key: "panic_score",        label: "Panic",        color: "bg-bear",  sparkColor: "#ef4444" },
  { key: "greed_score",        label: "Greed",        color: "bg-warn",  sparkColor: "#f59e0b" },
  { key: "accumulation_score", label: "Accumulation", color: "bg-bull",  sparkColor: "#22c55e" },
  { key: "distribution_score", label: "Distribution", color: "bg-orange-500", sparkColor: "#f97316" },
  { key: "confidence",         label: "Confidence",   color: "bg-info",  sparkColor: "#3b82f6" },
  { key: "news_shock_score",   label: "News Shock",   color: "bg-purple-500", sparkColor: "#a855f7" },
] as const;

export function BehaviorScores() {
  const { scores, scoreHistory, isConnected } = useBehaviorStore();
  const { data: fetchedScores } = useBehavioralScores();
  const display = scores ?? fetchedScores ?? null;

  const liveIndicator = (
    <div className="flex items-center gap-1.5">
      <div className={`w-1.5 h-1.5 rounded-full ${isConnected ? "bg-bull animate-pulse" : "bg-surface-600"}`} />
      <span className="text-xs text-gray-500">{isConnected ? "Live" : "Polling"}</span>
    </div>
  );

  return (
    <div className="flex flex-col">
      <PanelHeader
        title="Behavioral Scores"
        badge={display && <RegimeBadge regime={display.regime} />}
        actions={liveIndicator}
      />

      <div className="px-4 py-3 border-b border-surface-700">
        <FearGreedGauge />
      </div>

      <div className="px-4 py-3 space-y-3">
        {SCORE_CONFIGS.map(({ key, label, color, sparkColor }) => {
          const value = display ? (display as Record<string, number>)[key] ?? 0 : 0;
          const history = scoreHistory.map((s) => (s as Record<string, number>)[key] ?? 0);
          return (
            <div key={key} className="flex items-center gap-3">
              <div className="flex-1">
                <ScoreBar value={value} color={color} label={label} />
              </div>
              <Sparkline data={history.slice(-20)} color={sparkColor} width={48} height={20} />
            </div>
          );
        })}
      </div>

      {display && (
        <div className="px-4 pb-3 grid grid-cols-3 gap-2 text-center">
          {(["direction_1h", "direction_4h", "direction_24h"] as const).map((k) => {
            const val = (display as Record<string, number>)[k] ?? 50;
            const up = val >= 50;
            return (
              <div key={k} className="bg-surface-700 rounded-lg p-2">
                <div className="text-xs text-gray-500">{k.replace("direction_", "")}</div>
                <div className={`text-sm font-bold font-mono ${up ? "text-bull" : "text-bear"}`}>
                  {up ? "▲" : "▼"} {Math.round(up ? val : 100 - val)}%
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
