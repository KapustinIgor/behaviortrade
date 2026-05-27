import { cn } from "@/components/ui/cn";

interface PanelHeaderProps {
  title: string;
  badge?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
}

export function PanelHeader({ title, badge, actions, className }: PanelHeaderProps) {
  return (
    <div className={cn("flex items-center justify-between px-4 py-3 border-b border-surface-700", className)}>
      <div className="flex items-center gap-2">
        <h3 className="text-sm font-semibold text-gray-200 tracking-wide uppercase">{title}</h3>
        {badge}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}
