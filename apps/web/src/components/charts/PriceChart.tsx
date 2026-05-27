import { useEffect, useRef, useState } from "react";
import {
  createChart, type IChartApi, type ISeriesApi,
  ColorType, LineStyle,
} from "lightweight-charts";
import { useOHLCV } from "@/api/market";
import { usePriceForecast } from "@/api/predictions";
import { useMarketStore } from "@/store/useMarketStore";
import { ChartSkeleton } from "@/components/ui/LoadingSkeleton";
import { cn } from "@/components/ui/cn";

const TIMEFRAMES = ["1D", "4H", "1H", "15M"] as const;
type Timeframe = (typeof TIMEFRAMES)[number];

const TF_TO_API: Record<Timeframe, string> = {
  "1D": "30d", "4H": "7d", "1H": "7d", "15M": "1d",
};

type LP = { time: number; value: number };

interface PriceChartProps {
  height?: number;
}

export function PriceChart({ height = 380 }: PriceChartProps) {
  const { selectedAsset, selectedTimeframe, setSelectedTimeframe } = useMarketStore();
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef          = useRef<IChartApi | null>(null);
  const candleSeriesRef   = useRef<ISeriesApi<"Candlestick"> | null>(null);
  // GNN line: two segments (past + future) rendered as one visual line
  const pastLineRef       = useRef<ISeriesApi<"Line"> | null>(null);
  const futureLineRef     = useRef<ISeriesApi<"Line"> | null>(null);
  const upperBandRef      = useRef<ISeriesApi<"Line"> | null>(null);
  const lowerBandRef      = useRef<ISeriesApi<"Line"> | null>(null);

  const [showForecast, setShowForecast] = useState(true);

  const tf = (selectedTimeframe as Timeframe) ?? "1D";
  const { data, isLoading } = useOHLCV(selectedAsset, TF_TO_API[tf]);
  const { data: forecast }  = usePriceForecast(selectedAsset, showForecast);

  // Create chart + series once
  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "#161b22" },
        textColor: "#9ca3af",
      },
      grid: { vertLines: { color: "#1f2937" }, horzLines: { color: "#1f2937" } },
      crosshair: { mode: 1 },
      timeScale: { borderColor: "#374151", timeVisible: true },
      rightPriceScale: { borderColor: "#374151" },
      width: chartContainerRef.current.clientWidth,
      height,
    });

    const candleSeries = chart.addCandlestickSeries({
      upColor: "#22c55e", downColor: "#ef4444",
      borderUpColor: "#22c55e", borderDownColor: "#ef4444",
      wickUpColor: "#22c55e", wickDownColor: "#ef4444",
    });

    // Past portion — solid muted violet
    const pastLine = chart.addLineSeries({
      color: "rgba(167,139,250,0.55)",
      lineWidth: 2,
      lineStyle: LineStyle.Solid,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });

    // Confidence band (future only) — dotted, very faint
    const upper = chart.addLineSeries({
      color: "rgba(139,92,246,0.25)", lineWidth: 1,
      lineStyle: LineStyle.Dotted,
      priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
    });
    const lower = chart.addLineSeries({
      color: "rgba(139,92,246,0.25)", lineWidth: 1,
      lineStyle: LineStyle.Dotted,
      priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
    });

    // Future portion — dashed bright violet, labeled
    const futureLine = chart.addLineSeries({
      color: "#a78bfa",
      lineWidth: 2,
      lineStyle: LineStyle.Dashed,
      priceLineVisible: false,
      lastValueVisible: true,
      title: "GNN",
      crosshairMarkerVisible: true,
    });

    chartRef.current        = chart;
    candleSeriesRef.current = candleSeries;
    pastLineRef.current     = pastLine;
    futureLineRef.current   = futureLine;
    upperBandRef.current    = upper;
    lowerBandRef.current    = lower;

    const ro = new ResizeObserver(() => {
      if (chartContainerRef.current)
        chart.applyOptions({ width: chartContainerRef.current.clientWidth });
    });
    ro.observe(chartContainerRef.current);

    return () => { ro.disconnect(); chart.remove(); };
  }, [height]);

  // Update candle data
  useEffect(() => {
    if (!candleSeriesRef.current || !data?.data?.length) return;
    const formatted = data.data.map((c) => ({
      time: Math.floor(c.timestamp / 1000) as number,
      open: c.open, high: c.high, low: c.low, close: c.close,
    }));
    candleSeriesRef.current.setData(
      formatted as Parameters<typeof candleSeriesRef.current.setData>[0]
    );
    chartRef.current?.timeScale().fitContent();
  }, [data]);

  // Update GNN forecast lines
  useEffect(() => {
    const clear = () => {
      pastLineRef.current?.setData([]);
      futureLineRef.current?.setData([]);
      upperBandRef.current?.setData([]);
      lowerBandRef.current?.setData([]);
    };

    if (!showForecast || !forecast || forecast.error) { clear(); return; }
    if (!pastLineRef.current || !futureLineRef.current) return;

    if (forecast.past_line?.length) {
      const pts: LP[] = forecast.past_line.map((p) => ({ time: p.time, value: p.price }));
      pastLineRef.current.setData(pts as Parameters<typeof pastLineRef.current.setData>[0]);
    }

    if (forecast.future_line?.length) {
      const centre: LP[] = forecast.future_line.map((p) => ({ time: p.time, value: p.price }));
      const upper:  LP[] = forecast.future_line.map((p) => ({ time: p.time, value: p.upper }));
      const lower:  LP[] = forecast.future_line.map((p) => ({ time: p.time, value: p.lower }));
      futureLineRef.current.setData(centre as Parameters<typeof futureLineRef.current.setData>[0]);
      upperBandRef.current?.setData(upper  as Parameters<typeof upperBandRef.current.setData>[0]);
      lowerBandRef.current?.setData(lower  as Parameters<typeof lowerBandRef.current.setData>[0]);
    }

    chartRef.current?.timeScale().fitContent();
  }, [forecast, showForecast]);

  const direction  = forecast?.direction ?? "up";
  const prob       = forecast?.prob_24h ?? 50;
  const confidence = forecast?.gnn_confidence ?? 0;
  const regime     = forecast?.regime ?? "";
  const dirColor   = direction === "up" ? "#22c55e" : "#ef4444";
  const dirLabel   = direction === "up" ? "▲ Bullish" : "▼ Bearish";

  return (
    <div className="panel overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-surface-700">
        <div className="flex items-center gap-3 flex-wrap">
          <span className="font-bold text-white text-lg">{selectedAsset}/USDT</span>

          <button
            onClick={() => setShowForecast((v) => !v)}
            className={cn(
              "flex items-center gap-1.5 px-2.5 py-1 rounded border text-xs font-medium transition-colors",
              showForecast
                ? "border-violet-500/60 text-violet-300 bg-violet-500/10"
                : "border-surface-600 text-gray-500 hover:text-gray-300"
            )}
          >
            <span className="w-2 h-2 rounded-full"
              style={{ backgroundColor: showForecast ? "#a78bfa" : "#4b5563" }} />
            GNN Forecast
          </button>

          {showForecast && forecast && !forecast.error && (
            <div className="flex items-center gap-2 text-xs">
              <span className="font-semibold" style={{ color: dirColor }}>{dirLabel}</span>
              <span className="text-gray-500">
                {prob.toFixed(1)}% · {confidence.toFixed(0)}% conf
              </span>
              {regime && <span className="text-gray-600 capitalize">{regime}</span>}
            </div>
          )}
        </div>

        <div className="flex gap-1">
          {TIMEFRAMES.map((t) => (
            <button
              key={t}
              onClick={() => setSelectedTimeframe(t)}
              className={cn(
                "px-2.5 py-1 rounded text-xs font-medium transition-colors",
                tf === t
                  ? "bg-brand text-white"
                  : "text-gray-400 hover:text-gray-200 hover:bg-surface-700"
              )}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      <div className="relative">
        {isLoading && (
          <div className="absolute inset-0 z-10">
            <ChartSkeleton height={height} />
          </div>
        )}
        <div ref={chartContainerRef} />
      </div>
    </div>
  );
}
