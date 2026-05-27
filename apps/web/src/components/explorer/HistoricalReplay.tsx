import { X, Play, Pause, SkipBack, FastForward } from "lucide-react";
import { useState } from "react";
import { cn } from "@/components/ui/cn";

interface HistoricalReplayProps {
  onClose: () => void;
}

const KEY_EVENTS = [
  { date: "2022-11-08", label: "FTX Collapse", impact: "bear" },
  { date: "2023-01-12", label: "BTC Recovery", impact: "bull" },
  { date: "2024-01-10", label: "BTC ETF Approval", impact: "bull" },
  { date: "2024-04-20", label: "BTC Halving", impact: "bull" },
];

export function HistoricalReplay({ onClose }: HistoricalReplayProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [selectedDate, setSelectedDate] = useState("2024-01-10");
  const [speed, setSpeed] = useState(1);

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-surface-800 border border-surface-700 rounded-2xl w-full max-w-3xl flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-surface-700">
          <div>
            <h2 className="text-lg font-bold text-white">⏱ Time Machine — Historical Replay</h2>
            <p className="text-sm text-gray-500 mt-0.5">Phase 4 feature — animated behavioral replay coming soon</p>
          </div>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-surface-700 text-gray-400">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-6">
          {/* Date picker */}
          <div>
            <label className="text-xs text-gray-500 uppercase tracking-wide block mb-2">Select Date</label>
            <input
              type="date"
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
              min="2019-01-01"
              max={new Date().toISOString().split("T")[0]}
              className="bg-surface-700 border border-surface-600 text-gray-200 text-sm rounded-lg px-3 py-2 w-48"
            />
          </div>

          {/* Key events */}
          <div>
            <label className="text-xs text-gray-500 uppercase tracking-wide block mb-2">Jump to Key Event</label>
            <div className="flex flex-wrap gap-2">
              {KEY_EVENTS.map((ev) => (
                <button
                  key={ev.date}
                  onClick={() => setSelectedDate(ev.date)}
                  className={cn(
                    "text-xs px-3 py-1.5 rounded-lg border transition-colors",
                    selectedDate === ev.date
                      ? ev.impact === "bull" ? "border-bull/50 bg-bull/10 text-bull" : "border-bear/50 bg-bear/10 text-bear"
                      : "border-surface-600 text-gray-400 hover:border-surface-500"
                  )}
                >
                  {ev.label} <span className="text-gray-600 ml-1">{ev.date}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Playback controls */}
          <div className="flex items-center gap-4 bg-surface-700 rounded-xl p-4">
            <button className="text-gray-400 hover:text-gray-200">
              <SkipBack className="w-5 h-5" />
            </button>
            <button
              onClick={() => setIsPlaying((p) => !p)}
              className="w-10 h-10 rounded-full bg-brand flex items-center justify-center hover:bg-brand-dark transition-colors"
            >
              {isPlaying ? <Pause className="w-4 h-4 text-white" /> : <Play className="w-4 h-4 text-white ml-0.5" />}
            </button>
            <button className="text-gray-400 hover:text-gray-200">
              <FastForward className="w-5 h-5" />
            </button>
            <div className="flex items-center gap-2 ml-4">
              <span className="text-xs text-gray-500">Speed:</span>
              {[1, 2, 5, 10].map((s) => (
                <button
                  key={s}
                  onClick={() => setSpeed(s)}
                  className={cn("text-xs px-2 py-0.5 rounded", speed === s ? "bg-brand text-white" : "text-gray-400")}
                >
                  {s}x
                </button>
              ))}
            </div>
          </div>

          {/* Placeholder visualization */}
          <div className="h-40 bg-surface-700/50 rounded-xl flex items-center justify-center border border-surface-600 border-dashed">
            <div className="text-center">
              <p className="text-gray-400 text-sm font-medium">Behavioral Timeline Visualization</p>
              <p className="text-gray-600 text-xs mt-1">Phase 4: animated behavioral score replay with price overlay</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
