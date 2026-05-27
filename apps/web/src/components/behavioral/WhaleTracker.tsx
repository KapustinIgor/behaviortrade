import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/api/client";
import { PanelHeader } from "@/components/layout/PanelHeader";

interface WhaleFlow {
  hash: string;
  btc: number;
  fee_sat: number;
  timestamp: string;
  recipients: string[];
}

function shortHash(h: string) {
  return h ? `${h.slice(0, 8)}…${h.slice(-6)}` : "—";
}

function timeAgo(iso: string) {
  if (!iso) return "";
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}

export function WhaleTracker() {
  const { data, isLoading } = useQuery<{ flows: WhaleFlow[] }>({
    queryKey: ["whale_flows"],
    queryFn: () => apiGet("/behavioral/whale-flows", { min_btc: "10" }),
    refetchInterval: 60_000,
  });

  const flows = data?.flows ?? [];

  return (
    <div>
      <PanelHeader
        title="Whale Flow Monitor"
        badge={<span className="text-xs text-gray-500 font-mono">Live · BTC ≥10</span>}
      />
      <div className="px-4 py-3 space-y-1.5">
        {isLoading ? (
          Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-8 bg-surface-700 rounded animate-pulse" />
          ))
        ) : flows.length === 0 ? (
          <p className="text-xs text-gray-600">No large transactions in mempool right now.</p>
        ) : (
          flows.slice(0, 6).map((flow) => (
            <a
              key={flow.hash}
              href={`https://blockchain.info/tx/${flow.hash}`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 text-xs py-1.5 border-b border-surface-700 last:border-0 hover:bg-surface-700/30 -mx-2 px-2 rounded transition-colors"
            >
              <div className="w-2 h-2 rounded-full flex-shrink-0 bg-amber-500" />
              <span className="text-gray-500 font-mono truncate">{shortHash(flow.hash)}</span>
              <span className="ml-auto text-amber-400 font-mono font-semibold flex-shrink-0">
                {flow.btc.toLocaleString(undefined, { maximumFractionDigits: 1 })} BTC
              </span>
              <span className="text-gray-600 flex-shrink-0 w-14 text-right">{timeAgo(flow.timestamp)}</span>
            </a>
          ))
        )}
      </div>
    </div>
  );
}
