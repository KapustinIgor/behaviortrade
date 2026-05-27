import type { CorrelationResult } from "@/types";

interface CorrelationChartProps {
  data: CorrelationResult[];
  selectedLag?: number;
}

export function CorrelationChart({ data, selectedLag }: CorrelationChartProps) {
  if (!data.length) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-500 text-sm">
        No correlation data. Run computation first.
      </div>
    );
  }

  // TODO: Phase 3 — implement D3 scatter plot with trend line
  // Steps:
  //   1. d3.scaleLinear() for x (price change %) and y (signal value)
  //   2. Plot each historical data point as a circle
  //   3. d3.line() for regression trend line
  //   4. Annotate with R² and p-value

  const best = data.reduce((a, b) => (Math.abs(a.pearson_r) > Math.abs(b.pearson_r) ? a : b));
  return (
    <div className="h-64 bg-surface-700/50 rounded-lg flex flex-col items-center justify-center gap-3 text-center p-4">
      <p className="text-gray-400 text-sm">D3 scatter plot — Phase 3</p>
      <div className="text-xs text-gray-500 space-y-1">
        <div>Best correlation: <span className="text-brand-light font-mono">{best.signal_source}</span></div>
        <div>Pearson R: <span className="font-mono text-warn">{best.pearson_r.toFixed(3)}</span></div>
        <div>Lag: <span className="font-mono">{selectedLag ?? best.lag_hours}h</span></div>
      </div>
    </div>
  );
}
