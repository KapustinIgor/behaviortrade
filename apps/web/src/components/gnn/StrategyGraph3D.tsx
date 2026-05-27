import { useCallback, useEffect, useRef, useState } from "react";
import { X, RotateCcw, Layers, TrendingUp, Activity, Zap, Eye, EyeOff } from "lucide-react";
import ForceGraph3D from "react-force-graph-3d";
import * as THREE from "three";
import { useStrategyGraph, type StrategyGraphNode } from "@/api/gnn";
import { useMarketStore } from "@/store/useMarketStore";
import { cn } from "@/components/ui/cn";

// ── Layer toggle config ───────────────────────────────────────────────────────

const LAYERS = [
  { key: "strategy",   label: "Strategies",   icon: TrendingUp, color: "#22c55e" },
  { key: "combo",      label: "Combos",        icon: Layers,     color: "#818cf8" },
  { key: "regime",     label: "Regimes",       icon: Activity,   color: "#f59e0b" },
  { key: "behavioral", label: "Behavioral",    icon: Zap,        color: "#f472b6" },
] as const;

type LayerKey = typeof LAYERS[number]["key"];

// ── Detail panel ──────────────────────────────────────────────────────────────

function NodeDetailPanel({ node, onClose }: { node: StrategyGraphNode; onClose: () => void }) {
  const typeLabels: Record<string, string> = {
    strategy: "Strategy",
    combo: "Combo Strategy",
    regime: "Market Regime",
    behavioral: "Behavioral Signal",
  };

  return (
    <div className="absolute top-4 right-4 w-64 bg-surface-800/95 backdrop-blur border border-surface-600 rounded-2xl p-4 space-y-3 z-10">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[10px] text-gray-500 uppercase tracking-wide">{typeLabels[node.type]}</p>
          <h3 className="text-sm font-bold text-white leading-tight mt-0.5">{node.name}</h3>
        </div>
        <button onClick={onClose} className="p-1 rounded text-gray-500 hover:text-gray-300 flex-shrink-0">
          <X className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Color indicator */}
      <div className="flex items-center gap-2">
        <div className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: node.color }} />
        {node.is_active && (
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-brand/20 text-brand-light border border-brand/30">
            Active
          </span>
        )}
        {node.current && (
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-warn/20 text-warn border border-warn/30">
            Current Regime
          </span>
        )}
      </div>

      {/* Stats */}
      <div className="space-y-1.5 text-xs">
        {node.pnl_30d !== undefined && (
          <div className="flex justify-between">
            <span className="text-gray-500">30d PnL</span>
            <span className={cn("font-mono font-semibold", node.pnl_30d >= 0 ? "text-bull" : "text-bear")}>
              {node.pnl_30d >= 0 ? "+" : ""}{node.pnl_30d.toFixed(2)}%
            </span>
          </div>
        )}
        {node.win_rate !== undefined && node.win_rate > 0 && (
          <div className="flex justify-between">
            <span className="text-gray-500">Win Rate</span>
            <span className="font-mono text-gray-300">{node.win_rate.toFixed(1)}%</span>
          </div>
        )}
        {node.regime_score !== undefined && (
          <div className="flex justify-between">
            <span className="text-gray-500">Regime Fit</span>
            <span className={cn("font-mono font-semibold",
              node.regime_score >= 75 ? "text-bull" : node.regime_score >= 50 ? "text-warn" : "text-bear"
            )}>
              {node.regime_score.toFixed(0)}%
            </span>
          </div>
        )}
        {node.synergy !== undefined && (
          <div className="flex justify-between">
            <span className="text-gray-500">Synergy Score</span>
            <span className="font-mono text-brand-light">{node.synergy.toFixed(3)}</span>
          </div>
        )}
        {node.correlation !== undefined && (
          <div className="flex justify-between">
            <span className="text-gray-500">Correlation</span>
            <span className={cn("font-mono", Math.abs(node.correlation) < 0.3 ? "text-bull" : "text-warn")}>
              {node.correlation.toFixed(3)}
            </span>
          </div>
        )}
        {node.score !== undefined && (
          <div className="flex justify-between">
            <span className="text-gray-500">Signal Strength</span>
            <span className="font-mono text-gray-300">{node.score.toFixed(1)}</span>
          </div>
        )}
        {node.members && (
          <div>
            <span className="text-gray-500">Strategies</span>
            <div className="mt-1 flex flex-wrap gap-1">
              {node.members.map((m) => (
                <span key={m} className="text-[10px] px-1.5 py-0.5 rounded bg-surface-700 text-gray-300">{m}</span>
              ))}
            </div>
          </div>
        )}
      </div>

      {node.description && (
        <p className="text-[10px] text-gray-600 border-t border-surface-700 pt-2 leading-relaxed">
          {node.description}
        </p>
      )}
    </div>
  );
}

// ── Legend ────────────────────────────────────────────────────────────────────

function Legend({ regime, confidence }: { regime: string; confidence: number }) {
  return (
    <div className="absolute bottom-4 left-4 space-y-2 pointer-events-none">
      <div className="bg-surface-800/80 backdrop-blur rounded-xl px-3 py-2 space-y-1.5">
        <p className="text-[10px] text-gray-500 uppercase tracking-wide">Node Size</p>
        <p className="text-[10px] text-gray-400">Larger = better 30d performance</p>
      </div>
      <div className="bg-surface-800/80 backdrop-blur rounded-xl px-3 py-2 space-y-1.5">
        <p className="text-[10px] text-gray-500 uppercase tracking-wide">Node Color</p>
        <div className="flex flex-col gap-0.5">
          {[
            { color: "#22c55e", label: "Strong regime fit / Active" },
            { color: "#f59e0b", label: "Moderate fit" },
            { color: "#ef4444", label: "Poor fit" },
            { color: "#818cf8", label: "Combo strategy" },
          ].map(({ color, label }) => (
            <div key={label} className="flex items-center gap-1.5">
              <div className="w-2 h-2 rounded-full" style={{ backgroundColor: color }} />
              <span className="text-[10px] text-gray-400">{label}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="bg-surface-800/80 backdrop-blur rounded-xl px-3 py-2">
        <p className="text-[10px] text-gray-500 uppercase tracking-wide mb-1">Regime</p>
        <p className="text-xs font-semibold capitalize text-warn">{regime}</p>
        <p className="text-[10px] text-gray-500">{confidence.toFixed(0)}% confidence</p>
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

interface StrategyGraph3DProps {
  onClose: () => void;
}

export function StrategyGraph3D({ onClose }: StrategyGraph3DProps) {
  const { selectedAsset } = useMarketStore();
  const { data, isLoading } = useStrategyGraph(selectedAsset);
  const fgRef = useRef<any>(null);
  const [selected, setSelected] = useState<StrategyGraphNode | null>(null);
  const [visibleLayers, setVisibleLayers] = useState<Set<LayerKey>>(
    new Set(["strategy", "combo", "regime", "behavioral"])
  );
  const [highlightNodes, setHighlightNodes] = useState<Set<string>>(new Set());
  const [highlightLinks, setHighlightLinks] = useState<Set<unknown>>(new Set());

  // Initial camera position
  useEffect(() => {
    if (fgRef.current) {
      fgRef.current.cameraPosition({ x: 0, y: 60, z: 320 });
    }
  }, [data]);

  const toggleLayer = (key: LayerKey) => {
    setVisibleLayers((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  };

  const resetCamera = useCallback(() => {
    fgRef.current?.cameraPosition({ x: 0, y: 60, z: 320 }, undefined, 800);
  }, []);

  // Filter by visible layers
  const filteredNodes = (data?.nodes ?? []).filter((n) =>
    visibleLayers.has(n.type as LayerKey)
  );
  const filteredNodeIds = new Set(filteredNodes.map((n) => n.id));
  const filteredLinks = (data?.links ?? []).filter((l) => {
    const src = typeof l.source === "string" ? l.source : (l.source as StrategyGraphNode).id;
    const tgt = typeof l.target === "string" ? l.target : (l.target as StrategyGraphNode).id;
    return filteredNodeIds.has(src) && filteredNodeIds.has(tgt);
  });

  // Hover highlight
  const handleNodeHover = useCallback((node: StrategyGraphNode | null) => {
    if (!node) { setHighlightNodes(new Set()); setHighlightLinks(new Set()); return; }
    const hn = new Set<string>([node.id]);
    const hl = new Set<unknown>();
    filteredLinks.forEach((l) => {
      const src = typeof l.source === "string" ? l.source : (l.source as StrategyGraphNode).id;
      const tgt = typeof l.target === "string" ? l.target : (l.target as StrategyGraphNode).id;
      if (src === node.id || tgt === node.id) {
        hl.add(l);
        hn.add(src);
        hn.add(tgt);
      }
    });
    setHighlightNodes(hn);
    setHighlightLinks(hl);
  }, [filteredLinks]);

  // Custom node renderer
  const nodeThreeObject = useCallback((node: StrategyGraphNode) => {
    const isHighlighted = highlightNodes.size === 0 || highlightNodes.has(node.id);
    const isSelected    = selected?.id === node.id;
    const radius = node.val ?? 5;

    // Geometry differs by type
    let geometry: THREE.BufferGeometry;
    if (node.type === "combo") {
      geometry = new THREE.OctahedronGeometry(radius * 1.1);
    } else if (node.type === "regime") {
      geometry = new THREE.DodecahedronGeometry(radius);
    } else if (node.type === "behavioral") {
      geometry = new THREE.TetrahedronGeometry(radius * 1.2);
    } else {
      geometry = new THREE.SphereGeometry(radius, 16, 16);
    }

    const opacity = isHighlighted ? 1.0 : 0.18;
    const material = new THREE.MeshPhongMaterial({
      color:       new THREE.Color(node.color),
      emissive:    new THREE.Color(node.color),
      emissiveIntensity: isSelected ? 0.8 : isHighlighted ? 0.35 : 0.05,
      transparent: true,
      opacity,
      shininess: 80,
    });

    const mesh = new THREE.Mesh(geometry, material);

    // Outer ring for selected
    if (isSelected) {
      const ring = new THREE.Mesh(
        new THREE.TorusGeometry(radius * 1.6, radius * 0.15, 8, 32),
        new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.7 })
      );
      ring.rotation.x = Math.PI / 2;
      mesh.add(ring);
    }

    // Glow sphere for active strategies
    if (node.is_active) {
      const glow = new THREE.Mesh(
        new THREE.SphereGeometry(radius * 1.8, 16, 16),
        new THREE.MeshBasicMaterial({
          color: new THREE.Color("#818cf8"),
          transparent: true,
          opacity: 0.08,
          side: THREE.BackSide,
        })
      );
      mesh.add(glow);
    }

    return mesh;
  }, [highlightNodes, selected]);

  const meta = data?.meta;

  return (
    <div className="fixed inset-0 bg-surface-900 z-50 flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-surface-700 flex-shrink-0 bg-surface-800/80 backdrop-blur">
        <div className="flex items-center gap-4">
          <div>
            <h2 className="text-base font-bold text-white">Strategy GNN Graph — 3D</h2>
            {meta && (
              <p className="text-xs text-gray-500 mt-0.5">
                {selectedAsset} · {meta.node_count} nodes · {meta.link_count} links ·{" "}
                <span className="capitalize text-warn">{meta.regime}</span>{" "}
                regime · {meta.gnn_confidence.toFixed(0)}% confidence
              </p>
            )}
          </div>

          {/* Layer toggles */}
          <div className="flex items-center gap-1 ml-4">
            {LAYERS.map((layer) => {
              const Icon = layer.icon;
              const active = visibleLayers.has(layer.key);
              return (
                <button
                  key={layer.key}
                  onClick={() => toggleLayer(layer.key)}
                  className={cn(
                    "flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all",
                    active
                      ? "border text-white"
                      : "border border-surface-600 text-gray-600 hover:text-gray-400"
                  )}
                  style={active ? { borderColor: layer.color + "60", backgroundColor: layer.color + "15", color: layer.color } : {}}
                >
                  {active ? <Eye className="w-3 h-3" /> : <EyeOff className="w-3 h-3" />}
                  <Icon className="w-3 h-3" />
                  {layer.label}
                </button>
              );
            })}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={resetCamera}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs text-gray-400 hover:text-gray-200 hover:bg-surface-700 transition-colors"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            Reset view
          </button>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-surface-700 text-gray-400 hover:text-white transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Graph canvas */}
      <div className="flex-1 relative overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center space-y-3">
              <div className="w-12 h-12 rounded-full border-2 border-brand border-t-transparent animate-spin mx-auto" />
              <p className="text-sm text-gray-400">Building strategy graph…</p>
              <p className="text-xs text-gray-600">Computing equity correlations & synergy scores</p>
            </div>
          </div>
        ) : (
          <ForceGraph3D
            ref={fgRef}
            graphData={{ nodes: filteredNodes, links: filteredLinks }}
            backgroundColor="#0f1117"
            nodeLabel={(node: object) => (node as StrategyGraphNode).name}
            nodeVal={(node: object) => (node as StrategyGraphNode).val ?? 5}
            nodeColor={(node: object) => (node as StrategyGraphNode).color}
            nodeThreeObject={nodeThreeObject as (node: object) => THREE.Object3D}
            nodeThreeObjectExtend={false}
            linkColor={(link: object) => {
              const l = link as StrategyGraphLink;
              return highlightLinks.size === 0 || highlightLinks.has(link)
                ? (l as any).color ?? "#374151"
                : "#1f2937";
            }}
            linkWidth={(link: object) => {
              const l = link as any;
              const base = Math.max(0.3, (l.value ?? 1) * 0.5);
              return highlightLinks.has(link) ? base * 2.5 : base;
            }}
            linkDirectionalParticles={(link: object) => {
              const l = link as any;
              if (l.type === "combo_member") return 3;
              if (l.type === "regime_fit")  return 2;
              if (l.type === "beh_influence") return 4;
              return 0;
            }}
            linkDirectionalParticleWidth={(link: object) =>
              highlightLinks.has(link) ? 3 : 1.5
            }
            linkDirectionalParticleColor={(link: object) => (link as any).color ?? "#818cf8"}
            linkDirectionalParticleSpeed={0.004}
            linkOpacity={0.5}
            onNodeClick={(node: object) => {
              const n = node as StrategyGraphNode;
              setSelected((prev) => prev?.id === n.id ? null : n);
            }}
            onNodeHover={(node: object | null) => handleNodeHover(node as StrategyGraphNode | null)}
            enableNodeDrag
            enableNavigationControls
            showNavInfo={false}
            d3AlphaDecay={0.02}
            d3VelocityDecay={0.35}
            warmupTicks={80}
            cooldownTicks={200}
          />
        )}

        {/* Selected node panel */}
        {selected && (
          <NodeDetailPanel node={selected} onClose={() => setSelected(null)} />
        )}

        {/* Legend */}
        {meta && !isLoading && (
          <Legend regime={meta.regime} confidence={meta.gnn_confidence} />
        )}

        {/* Bottom hint */}
        {!isLoading && (
          <div className="absolute bottom-4 right-4 text-[10px] text-gray-700 text-right pointer-events-none">
            Scroll to zoom · Drag to rotate · Click node for details
          </div>
        )}
      </div>
    </div>
  );
}

// Type alias needed by link color callback
type StrategyGraphLink = { source: string | StrategyGraphNode; target: string | StrategyGraphNode; value: number; type: string; color: string; };
