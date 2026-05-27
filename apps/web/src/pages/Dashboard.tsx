import { useState } from "react";
import { LayoutGrid, Clock, BarChart2, Network, Box } from "lucide-react";
import { MainLayout } from "@/components/layout/MainLayout";
import { PriceChart } from "@/components/charts/PriceChart";
import { BehaviorOverlay } from "@/components/charts/BehaviorOverlay";
import { BehaviorScores } from "@/components/behavioral/BehaviorScores";
import { WhaleTracker } from "@/components/behavioral/WhaleTracker";
import { PredictionFeed } from "@/components/predictions/PredictionFeed";
import { NewsFeed } from "@/components/news/NewsFeed";
import { StrategyMarketplace } from "@/components/strategies/StrategyMarketplace";
import { CorrelationExplorer } from "@/components/explorer/CorrelationExplorer";
import { HistoricalReplay } from "@/components/explorer/HistoricalReplay";
import { BehaviorGraph } from "@/components/gnn/BehaviorGraph";
import { StrategyGraph3D } from "@/components/gnn/StrategyGraph3D";
import { SocialSentiment } from "@/components/social/SocialSentiment";
import { StrategyPerformanceChart } from "@/components/charts/StrategyPerformanceChart";
import { cn } from "@/components/ui/cn";

type ActiveTab = "chart" | "strategies" | "correlations";

export function Dashboard() {
  const [tab, setTab] = useState<ActiveTab>("chart");
  const [showMarketplace,   setShowMarketplace]   = useState(false);
  const [showCorrelations,  setShowCorrelations]  = useState(false);
  const [showReplay,        setShowReplay]        = useState(false);
  const [showGraph,         setShowGraph]         = useState(false);
  const [showStrategyGraph, setShowStrategyGraph] = useState(false);

  const TABS = [
    { key: "chart" as const,       label: "Chart",        icon: BarChart2 },
    { key: "strategies" as const,  label: "Strategies",   icon: LayoutGrid },
    { key: "correlations" as const, label: "Correlations", icon: BarChart2 },
  ];

  const center = (
    <div className="space-y-3">
      {/* Tab bar */}
      <div className="flex items-center gap-1 border-b border-surface-700 pb-2 flex-wrap">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => {
              if (t.key === "strategies")  { setShowMarketplace(true);  return; }
              if (t.key === "correlations") { setShowCorrelations(true); return; }
              setTab(t.key);
            }}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors",
              tab === t.key ? "bg-brand/20 text-brand-light" : "text-gray-400 hover:text-gray-200"
            )}
          >
            <t.icon className="w-3.5 h-3.5" />
            {t.label}
          </button>
        ))}

        <div className="ml-auto flex items-center gap-1">
          {/* Time Machine */}
          <button
            onClick={() => setShowReplay(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm text-gray-400 hover:text-gray-200 hover:bg-surface-700 transition-colors"
          >
            <Clock className="w-3.5 h-3.5" />
            Time Machine
          </button>

          {/* Behavioral GNN graph (2D) */}
          <button
            onClick={() => setShowGraph(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm text-gray-400 hover:text-gray-200 hover:bg-surface-700 transition-colors"
          >
            <Network className="w-3.5 h-3.5" />
            Graph
          </button>

          {/* Strategy 3-D graph */}
          <button
            onClick={() => setShowStrategyGraph(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors border border-brand/40 text-brand-light hover:bg-brand/10"
          >
            <Box className="w-3.5 h-3.5" />
            3D Strategy
          </button>
        </div>
      </div>

      {/* Main chart area */}
      <PriceChart height={340} />
      <BehaviorOverlay />
      <StrategyPerformanceChart height={200} />
    </div>
  );

  const rightPanel = (
    <div className="flex flex-col gap-0 divide-y divide-surface-700">
      <BehaviorScores />
      <PredictionFeed />
      <WhaleTracker />
      <SocialSentiment />
    </div>
  );

  const bottomPanel = <NewsFeed />;

  return (
    <>
      <MainLayout center={center} rightPanel={rightPanel} bottomPanel={bottomPanel} />
      {showMarketplace   && <StrategyMarketplace onClose={() => setShowMarketplace(false)} />}
      {showCorrelations  && <CorrelationExplorer  onClose={() => setShowCorrelations(false)} />}
      {showReplay        && <HistoricalReplay      onClose={() => setShowReplay(false)} />}
      {showGraph         && <BehaviorGraph         onClose={() => setShowGraph(false)} />}
      {showStrategyGraph && <StrategyGraph3D       onClose={() => setShowStrategyGraph(false)} />}
    </>
  );
}
