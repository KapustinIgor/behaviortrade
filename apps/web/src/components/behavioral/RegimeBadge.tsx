import { TrendingUp, TrendingDown, Minus, Activity } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import type { Regime } from "@/types";

interface RegimeBadgeProps {
  regime: Regime;
}

export function RegimeBadge({ regime }: RegimeBadgeProps) {
  const icon = {
    bull: <TrendingUp className="w-3 h-3" />,
    bear: <TrendingDown className="w-3 h-3" />,
    sideways: <Minus className="w-3 h-3" />,
    transition: <Activity className="w-3 h-3 animate-spin-slow" />,
  }[regime];

  return (
    <Badge variant={regime} className="gap-1">
      {icon}
      {regime}
    </Badge>
  );
}
