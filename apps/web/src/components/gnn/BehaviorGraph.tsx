import { useRef, useEffect, useState, useCallback } from "react";
import * as d3 from "d3";
import { X, RefreshCw } from "lucide-react";
import { useGNNGraph, type GraphNode } from "@/api/gnn";

// D3 simulation augments nodes with x/y/vx/vy/fx/fy
interface SimNode extends GraphNode {
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
  fx?: number | null;
  fy?: number | null;
  index?: number;
}

// D3 force link augments edge source/target to SimNode objects at runtime
interface SimEdge {
  source: SimNode | string;
  target: SimNode | string;
  type: string;
  weight: number;
  color: string;
}

interface BehaviorGraphProps {
  onClose: () => void;
}

// Soft-pull cluster offsets per node type (unscaled, relative to center)
const TYPE_OFFSETS: Record<string, [number, number]> = {
  exchange:          [0,     0   ],
  whale_wallet:      [-200, -50  ],
  dex_pool:          [-150,  150 ],
  retail_cluster:    [0,     200 ],
  news_source:       [200,  -50  ],
  social_account:    [150,  -150 ],
  on_chain_contract: [-50,  -200 ],
};

const NODE_TYPE_LABELS: Record<string, string> = {
  exchange:          "Exchange",
  whale_wallet:      "Whale Wallet",
  dex_pool:          "DEX Pool",
  retail_cluster:    "Retail Cluster",
  news_source:       "News Source",
  social_account:    "Social Account",
  on_chain_contract: "On-Chain Contract",
};

// Lighten a hex color for the node border
function lightenHex(hex: string, amount = 40): string {
  const n = parseInt(hex.replace("#", ""), 16);
  const r = Math.min(255, (n >> 16) + amount);
  const g = Math.min(255, ((n >> 8) & 0xff) + amount);
  const b = Math.min(255, (n & 0xff) + amount);
  return `#${((r << 16) | (g << 8) | b).toString(16).padStart(6, "0")}`;
}

function nodeRadius(size: number): number {
  return size * 20 + 6;
}

export function BehaviorGraph({ onClose }: BehaviorGraphProps) {
  const { data, isFetching, refetch } = useGNNGraph();

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const simRef = useRef<d3.Simulation<SimNode, SimEdge> | null>(null);
  const rafRef = useRef<number>(0);
  const nodesRef = useRef<SimNode[]>([]);
  const edgesRef = useRef<SimEdge[]>([]);
  const transformRef = useRef<d3.ZoomTransform>(d3.zoomIdentity);
  const hoveredRef = useRef<SimNode | null>(null);
  const pinnedRef = useRef<Set<string>>(new Set());

  const [tooltip, setTooltip] = useState<{
    x: number;
    y: number;
    node: SimNode;
  } | null>(null);

  // Build unique node types present in the data for the legend
  const legendTypes = data
    ? Array.from(new Set(data.nodes.map((n) => n.type))).map((type) => ({
        type,
        color: data.nodes.find((n) => n.type === type)!.color,
        label: NODE_TYPE_LABELS[type] ?? type,
      }))
    : [];

  // ─── render loop ──────────────────────────────────────────────────────────
  const drawFrame = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const { width, height } = canvas;
    const t = transformRef.current;

    ctx.save();
    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = "#0d1117";
    ctx.fillRect(0, 0, width, height);

    ctx.translate(t.x, t.y);
    ctx.scale(t.k, t.k);

    const hovered = hoveredRef.current;

    // Draw edges
    for (const edge of edgesRef.current) {
      const src = edge.source as SimNode;
      const tgt = edge.target as SimNode;
      if (src.x == null || src.y == null || tgt.x == null || tgt.y == null) continue;

      const isHoverEdge =
        hovered != null && (src.id === hovered.id || tgt.id === hovered.id);

      ctx.beginPath();
      ctx.moveTo(src.x, src.y);
      ctx.lineTo(tgt.x, tgt.y);
      ctx.lineWidth = edge.weight * 2;
      ctx.strokeStyle = edge.color;
      ctx.globalAlpha = isHoverEdge ? 0.7 : 0.3;
      ctx.stroke();
      ctx.globalAlpha = 1;
    }

    // Draw nodes
    for (const node of nodesRef.current) {
      if (node.x == null || node.y == null) continue;

      const r = nodeRadius(node.size);
      const isHovered = hovered?.id === node.id;
      const isPinned = pinnedRef.current.has(node.id);
      const drawR = isHovered ? r * 1.35 : r;

      // Fill
      ctx.beginPath();
      ctx.arc(node.x, node.y, drawR, 0, Math.PI * 2);
      ctx.fillStyle = isHovered ? lightenHex(node.color, 40) : node.color;
      ctx.fill();

      // Stroke
      ctx.lineWidth = isPinned ? 2.5 : 2;
      ctx.strokeStyle = lightenHex(node.color, 60);
      ctx.stroke();

      // Pin indicator
      if (isPinned) {
        ctx.beginPath();
        ctx.arc(node.x, node.y, 3, 0, Math.PI * 2);
        ctx.fillStyle = "#fff";
        ctx.fill();
      }

      // Label
      if (node.size > 0.5 || isHovered) {
        ctx.font = "10px Inter, sans-serif";
        ctx.fillStyle = "#ffffff";
        ctx.textAlign = "center";
        ctx.fillText(node.label, node.x, node.y + drawR + 13);
      }
    }

    ctx.restore();

    rafRef.current = requestAnimationFrame(drawFrame);
  }, []);

  // ─── mouse helpers ────────────────────────────────────────────────────────
  const canvasToSim = useCallback(
    (cx: number, cy: number): [number, number] => {
      const t = transformRef.current;
      return [(cx - t.x) / t.k, (cy - t.y) / t.k];
    },
    []
  );

  const nodeAtPoint = useCallback((sx: number, sy: number): SimNode | null => {
    for (let i = nodesRef.current.length - 1; i >= 0; i--) {
      const n = nodesRef.current[i];
      if (n.x == null || n.y == null) continue;
      const dx = n.x - sx;
      const dy = n.y - sy;
      if (dx * dx + dy * dy <= (nodeRadius(n.size) * 1.35) ** 2) return n;
    }
    return null;
  }, []);

  // ─── simulation init ──────────────────────────────────────────────────────
  useEffect(() => {
    if (!data || !canvasRef.current) return;

    const canvas = canvasRef.current;
    const width = canvas.width;
    const height = canvas.height;
    const scale = width / 800;

    // Clone data so D3 can mutate freely
    const simNodes: SimNode[] = data.nodes.map((n) => ({ ...n }));
    const simEdges: SimEdge[] = data.edges.map((e) => ({ ...e }));

    nodesRef.current = simNodes;
    edgesRef.current = simEdges;

    // Stop previous simulation
    simRef.current?.stop();

    const sim = d3
      .forceSimulation<SimNode>(simNodes)
      .force(
        "link",
        d3
          .forceLink<SimNode, SimEdge>(simEdges)
          .id((d) => d.id)
          .distance(80)
          .strength(0.3)
      )
      .force("charge", d3.forceManyBody<SimNode>().strength(-200))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force(
        "collision",
        d3.forceCollide<SimNode>((d) => d.size * 20 + 10)
      )
      .force(
        "x",
        d3
          .forceX<SimNode>((d) => {
            const off = TYPE_OFFSETS[d.type]?.[0] ?? 0;
            return width / 2 + off * scale;
          })
          .strength(0.05)
      )
      .force(
        "y",
        d3
          .forceY<SimNode>((d) => {
            const off = TYPE_OFFSETS[d.type]?.[1] ?? 0;
            return height / 2 + off * scale;
          })
          .strength(0.05)
      );

    simRef.current = sim;

    return () => {
      sim.stop();
    };
  }, [data]);

  // ─── canvas setup + render loop ───────────────────────────────────────────
  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const resize = () => {
      const { width, height } = container.getBoundingClientRect();
      canvas.width = width;
      canvas.height = height;
      simRef.current
        ?.force("center", d3.forceCenter(width / 2, height / 2))
        .alpha(0.3)
        .restart();
    };

    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(container);

    rafRef.current = requestAnimationFrame(drawFrame);

    return () => {
      ro.disconnect();
      cancelAnimationFrame(rafRef.current);
    };
  }, [drawFrame]);

  // ─── D3 drag + zoom ───────────────────────────────────────────────────────
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    // Zoom
    const zoom = d3
      .zoom<HTMLCanvasElement, unknown>()
      .scaleExtent([0.2, 4])
      .on("zoom", (event: d3.D3ZoomEvent<HTMLCanvasElement, unknown>) => {
        transformRef.current = event.transform;
      });

    d3.select(canvas).call(zoom);

    // Drag
    let dragging: SimNode | null = null;

    const drag = d3
      .drag<HTMLCanvasElement, unknown>()
      .subject((_event: d3.D3DragEvent<HTMLCanvasElement, unknown, unknown>) => {
        // subject is called with the raw event
        const e = _event.sourceEvent as MouseEvent;
        const rect = canvas.getBoundingClientRect();
        const [sx, sy] = canvasToSim(e.clientX - rect.left, e.clientY - rect.top);
        return nodeAtPoint(sx, sy) as unknown as d3.SubjectPosition;
      })
      .on("start", (event: d3.D3DragEvent<HTMLCanvasElement, unknown, unknown>) => {
        dragging = event.subject as unknown as SimNode;
        if (!event.active) simRef.current?.alphaTarget(0.3).restart();
        dragging.fx = dragging.x;
        dragging.fy = dragging.y;
      })
      .on("drag", (event: d3.D3DragEvent<HTMLCanvasElement, unknown, unknown>) => {
        if (!dragging) return;
        const t = transformRef.current;
        dragging.fx = (event.x - t.x) / t.k;
        dragging.fy = (event.y - t.y) / t.k;
      })
      .on("end", (event: d3.D3DragEvent<HTMLCanvasElement, unknown, unknown>) => {
        if (!event.active) simRef.current?.alphaTarget(0);
        if (dragging && !pinnedRef.current.has(dragging.id)) {
          dragging.fx = null;
          dragging.fy = null;
        }
        dragging = null;
      });

    // We need drag to win over zoom on node hits — apply drag first
    d3.select(canvas).call(drag as unknown as (sel: d3.Selection<HTMLCanvasElement, unknown, null, undefined>) => void);

    return () => {
      d3.select(canvas).on(".zoom", null).on(".drag", null);
    };
  }, [canvasToSim, nodeAtPoint]);

  // ─── mousemove for hover + tooltip ────────────────────────────────────────
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const onMove = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      const [sx, sy] = canvasToSim(e.clientX - rect.left, e.clientY - rect.top);
      const hit = nodeAtPoint(sx, sy);
      hoveredRef.current = hit;
      if (hit) {
        setTooltip({ x: e.clientX, y: e.clientY, node: hit });
        canvas.style.cursor = "pointer";
      } else {
        setTooltip(null);
        canvas.style.cursor = "";
      }
    };

    const onLeave = () => {
      hoveredRef.current = null;
      setTooltip(null);
    };

    canvas.addEventListener("mousemove", onMove);
    canvas.addEventListener("mouseleave", onLeave);
    return () => {
      canvas.removeEventListener("mousemove", onMove);
      canvas.removeEventListener("mouseleave", onLeave);
    };
  }, [canvasToSim, nodeAtPoint]);

  // ─── click to pin/unpin ───────────────────────────────────────────────────
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const onClick = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      const [sx, sy] = canvasToSim(e.clientX - rect.left, e.clientY - rect.top);
      const hit = nodeAtPoint(sx, sy);
      if (!hit) return;

      if (pinnedRef.current.has(hit.id)) {
        pinnedRef.current.delete(hit.id);
        hit.fx = null;
        hit.fy = null;
      } else {
        pinnedRef.current.add(hit.id);
        hit.fx = hit.x;
        hit.fy = hit.y;
      }
    };

    canvas.addEventListener("click", onClick);
    return () => canvas.removeEventListener("click", onClick);
  }, [canvasToSim, nodeAtPoint]);

  const meta = data?.meta;
  const regimeColor =
    meta?.regime === "bull"
      ? "text-green-400 bg-green-400/10"
      : meta?.regime === "bear"
      ? "text-red-400 bg-red-400/10"
      : "text-yellow-400 bg-yellow-400/10";

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-[#0d1117]">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-white/10 shrink-0">
        <span className="text-white font-semibold text-sm tracking-wide">
          Behavioral Graph
        </span>

        {meta && (
          <>
            <span
              className={`px-2 py-0.5 rounded text-xs font-medium capitalize ${regimeColor}`}
            >
              {meta.regime}
            </span>
            <span className="text-gray-500 text-xs">
              GNN confidence: {meta.gnn_confidence.toFixed(1)}%
            </span>
            <span
              className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                meta.model_mode === "trained"
                  ? "bg-green-500/20 text-green-400"
                  : "bg-yellow-500/20 text-yellow-400"
              }`}
              title={meta.model_mode === "trained" ? "Running on trained GNN checkpoint" : "Using heuristic mock scores — no trained checkpoint loaded"}
            >
              {meta.model_mode === "trained" ? "TRAINED" : "MOCK"}
            </span>
            <span className="text-gray-600 text-xs">
              {meta.node_count} nodes · {meta.edge_count} edges
            </span>
            {meta.model_mode === "mock" && (
              <span className="text-yellow-400/80 text-xs italic ml-2">
                Research mode: heuristic scores, not trained GNN inference.
              </span>
            )}
          </>
        )}

        <div className="ml-auto flex items-center gap-2">
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs text-gray-400 hover:text-gray-200 hover:bg-white/10 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? "animate-spin" : ""}`} />
            Refresh
          </button>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Canvas area */}
      <div ref={containerRef} className="relative flex-1 overflow-hidden">
        <canvas ref={canvasRef} className="absolute inset-0 w-full h-full" />

        {/* Legend */}
        {legendTypes.length > 0 && (
          <div className="absolute bottom-4 left-4 bg-black/60 backdrop-blur-sm rounded-lg px-3 py-2.5 flex flex-col gap-1.5">
            {legendTypes.map(({ type, color, label }) => (
              <div key={type} className="flex items-center gap-2">
                <span
                  className="w-2.5 h-2.5 rounded-full shrink-0"
                  style={{ backgroundColor: color }}
                />
                <span className="text-gray-300 text-xs">{label}</span>
              </div>
            ))}
          </div>
        )}

        {/* Empty / loading state */}
        {!data && !isFetching && (
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-gray-500 text-sm">No graph data available</span>
          </div>
        )}
        {isFetching && !data && (
          <div className="absolute inset-0 flex items-center justify-center">
            <RefreshCw className="w-6 h-6 text-gray-400 animate-spin" />
          </div>
        )}
      </div>

      {/* Tooltip */}
      {tooltip && (
        <div
          className="fixed z-[60] pointer-events-none bg-[#161b22] border border-white/10 rounded-lg px-3 py-2 shadow-xl text-xs"
          style={{
            left: tooltip.x + 14,
            top: tooltip.y - 8,
            transform: "translateY(-50%)",
          }}
        >
          <div className="text-white font-medium mb-1">{tooltip.node.label}</div>
          <div className="text-gray-400 space-y-0.5">
            <div>
              Type:{" "}
              <span className="text-gray-200">
                {NODE_TYPE_LABELS[tooltip.node.type] ?? tooltip.node.type}
              </span>
            </div>
            <div>
              Volume rank:{" "}
              <span className="text-gray-200">
                {(tooltip.node.metrics.volume_rank * 100).toFixed(0)}%
              </span>
            </div>
            <div>
              24h change:{" "}
              <span
                className={
                  tooltip.node.metrics.change_24h >= 0
                    ? "text-green-400"
                    : "text-red-400"
                }
              >
                {tooltip.node.metrics.change_24h >= 0 ? "+" : ""}
                {(tooltip.node.metrics.change_24h * 100).toFixed(1)}%
              </span>
            </div>
            <div>
              Sentiment:{" "}
              <span className="text-gray-200">
                {(tooltip.node.metrics.sentiment * 100).toFixed(0)}%
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
