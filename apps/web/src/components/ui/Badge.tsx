import { cn } from "./cn";

type BadgeVariant =
  | "bull" | "bear" | "sideways" | "transition"
  | "active" | "standby" | "blocked"
  | "positive" | "negative" | "neutral"
  | "default";

const VARIANTS: Record<BadgeVariant, string> = {
  bull:       "bg-bull/20 text-bull border border-bull/30",
  bear:       "bg-bear/20 text-bear border border-bear/30",
  sideways:   "bg-gray-500/20 text-gray-400 border border-gray-500/30",
  transition: "bg-warn/20 text-warn border border-warn/30",
  active:     "bg-bull/20 text-bull border border-bull/30",
  standby:    "bg-warn/20 text-warn border border-warn/30",
  blocked:    "bg-bear/20 text-bear border border-bear/30",
  positive:   "bg-bull/20 text-bull border border-bull/30",
  negative:   "bg-bear/20 text-bear border border-bear/30",
  neutral:    "bg-gray-500/20 text-gray-400 border border-gray-500/30",
  default:    "bg-surface-700 text-gray-300 border border-surface-600",
};

interface BadgeProps {
  variant?: BadgeVariant;
  children: React.ReactNode;
  className?: string;
}

export function Badge({ variant = "default", children, className }: BadgeProps) {
  return (
    <span className={cn("inline-flex items-center px-2 py-0.5 rounded-md text-xs font-semibold uppercase tracking-wide", VARIANTS[variant], className)}>
      {children}
    </span>
  );
}
