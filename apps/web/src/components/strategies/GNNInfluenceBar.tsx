interface GNNInfluenceBarProps {
  value: number;
}

export function GNNInfluenceBar({ value }: GNNInfluenceBarProps) {
  const pct = Math.min(100, Math.max(0, value));
  const color = pct > 70 ? "#f59e0b" : pct > 40 ? "#6366f1" : "#4b5563";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1 bg-surface-700 rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all duration-500" style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
      <span className="text-xs font-mono text-gray-400 w-8 text-right">{Math.round(pct)}%</span>
    </div>
  );
}
