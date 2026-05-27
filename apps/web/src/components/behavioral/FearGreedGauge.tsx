import { useFearGreed } from "@/api/behavioral";
import { Sparkline } from "@/components/ui/Sparkline";

const ZONES = [
  { max: 25, label: "Extreme Fear", color: "#ef4444" },
  { max: 45, label: "Fear",         color: "#f97316" },
  { max: 55, label: "Neutral",      color: "#eab308" },
  { max: 75, label: "Greed",        color: "#84cc16" },
  { max: 100, label: "Extreme Greed", color: "#22c55e" },
];

function getZone(value: number) {
  return ZONES.find((z) => value <= z.max) ?? ZONES[ZONES.length - 1];
}

export function FearGreedGauge() {
  const { data } = useFearGreed();
  const value = data?.value ?? 50;
  const zone = getZone(value);

  const history = (data?.last_30_days ?? []).map((d) => d.value).reverse();

  const angle = -135 + (value / 100) * 270;
  const cx = 60, cy = 60, r = 44;
  const rad = (deg: number) => (deg * Math.PI) / 180;
  const needleX = cx + r * 0.7 * Math.cos(rad(angle - 90));
  const needleY = cy + r * 0.7 * Math.sin(rad(angle - 90));

  return (
    <div className="flex flex-col items-center py-2">
      <svg width="120" height="80" viewBox="0 0 120 80">
        {[
          { start: -135, end: -81, color: "#ef4444" },
          { start: -81,  end: -27, color: "#f97316" },
          { start: -27,  end:  27, color: "#eab308" },
          { start:  27,  end:  81, color: "#84cc16" },
          { start:  81,  end: 135, color: "#22c55e" },
        ].map((seg, i) => {
          const toRad = (d: number) => ((d - 90) * Math.PI) / 180;
          const x1 = cx + r * Math.cos(toRad(seg.start));
          const y1 = cy + r * Math.sin(toRad(seg.start));
          const x2 = cx + r * Math.cos(toRad(seg.end));
          const y2 = cy + r * Math.sin(toRad(seg.end));
          const large = Math.abs(seg.end - seg.start) > 180 ? 1 : 0;
          return (
            <path
              key={i}
              d={`M ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2}`}
              fill="none"
              stroke={seg.color}
              strokeWidth="8"
              strokeLinecap="round"
              opacity="0.7"
            />
          );
        })}
        <line x1={cx} y1={cy} x2={needleX} y2={needleY} stroke="white" strokeWidth="2" strokeLinecap="round" />
        <circle cx={cx} cy={cy} r="3" fill="white" />
      </svg>

      <div className="text-center -mt-1">
        <div className="text-2xl font-bold font-mono" style={{ color: zone.color }}>{value}</div>
        <div className="text-xs font-semibold" style={{ color: zone.color }}>{zone.label}</div>
      </div>

      {history.length > 1 && (
        <div className="mt-2 w-full px-2">
          <Sparkline data={history} color={zone.color} width={140} height={24} />
          <div className="text-center text-xs text-gray-600 mt-0.5">30-day trend</div>
        </div>
      )}
    </div>
  );
}
