import { PanelHeader } from "@/components/layout/PanelHeader";
import { PredictionCard } from "./PredictionCard";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";
import { useLatestPredictions, usePredictionAccuracy } from "@/api/predictions";

export function PredictionFeed() {
  const { data: predictions, isLoading } = useLatestPredictions(6);
  const { data: accuracy } = usePredictionAccuracy();

  const accuracyBadge = accuracy && (
    <span className="text-xs text-gray-500 bg-surface-700 px-2 py-0.5 rounded-full">
      {accuracy.overall}% accurate
    </span>
  );

  return (
    <div className="flex flex-col">
      <PanelHeader title="GNN Predictions" badge={accuracyBadge} />
      <div className="px-3 py-3 space-y-2 overflow-y-auto flex-1">
        {isLoading ? (
          <LoadingSkeleton lines={3} />
        ) : predictions?.length ? (
          predictions.map((p) => <PredictionCard key={p.id} prediction={p} />)
        ) : (
          <p className="text-xs text-gray-600 text-center py-4">No predictions yet. Start the API to generate signals.</p>
        )}
      </div>
    </div>
  );
}
