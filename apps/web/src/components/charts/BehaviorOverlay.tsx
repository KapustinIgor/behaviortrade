import { useState } from "react";
import { cn } from "@/components/ui/cn";
import { useBehaviorStore } from "@/store/useBehaviorStore";

const OVERLAYS = [
  { key: "panic_score", label: "Panic", color: "#ef4444" },
  { key: "greed_score", label: "Greed", color: "#f59e0b" },
  { key: "accumulation_score", label: "Accumulation", color: "#22c55e" },
  { key: "distribution_score", label: "Distribution", color: "#f97316" },
] as const;

export function BehaviorOverlay() {
  const [active, setActive] = useState<Set<string>>(new Set());
  const { scores } = useBehaviorStore();

  const toggle = (key: string) =>
    setActive((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });

  return (
    <div className="flex items-center gap-2 px-4 py-2 border-b border-surface-700 bg-surface-800/50">
      <span className="text-xs text-gray-500 mr-1">Overlays:</span>
      {OVERLAYS.map((o) => {
        const isOn = active.has(o.key);
        const val = scores ? (scores as Record<string, number>)[o.key] ?? 0 : 0;
        return (
          <button
            key={o.key}
            onClick={() => toggle(o.key)}
            style={{ borderColor: isOn ? o.color : undefined, color: isOn ? o.color : undefined }}
            className={cn(
              "flex items-center gap-1.5 px-2.5 py-1 rounded border text-xs font-medium transition-colors",
              isOn ? "bg-opacity-10" : "border-surface-600 text-gray-500 hover:text-gray-300"
            )}
          >
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: isOn ? o.color : "#4b5563" }} />
            {o.label}
            {isOn && <span className="font-mono ml-1">{Math.round(val)}</span>}
          </button>
        );
      })}
    </div>
  );
}
