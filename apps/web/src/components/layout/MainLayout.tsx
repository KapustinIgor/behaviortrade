import { Sidebar } from "./Sidebar";
import { cn } from "@/components/ui/cn";

interface MainLayoutProps {
  center: React.ReactNode;
  rightPanel: React.ReactNode;
  bottomPanel: React.ReactNode;
}

export function MainLayout({ center, rightPanel, bottomPanel }: MainLayoutProps) {
  return (
    <div className="flex h-screen overflow-hidden bg-surface-900">
      {/* Left sidebar */}
      <Sidebar />

      {/* Main content area */}
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        {/* Top section: center + right panel */}
        <div className="flex flex-1 min-h-0">
          {/* Center: chart + tabs */}
          <main className={cn("flex-1 min-w-0 overflow-y-auto p-3 space-y-3")}>
            {center}
          </main>

          {/* Right panel: behavioral scores + predictions */}
          <aside className="w-[300px] flex-shrink-0 border-l border-surface-700 overflow-y-auto flex flex-col">
            {rightPanel}
          </aside>
        </div>

        {/* Bottom panel: news feed */}
        <div className="h-[200px] flex-shrink-0 border-t border-surface-700 overflow-hidden">
          {bottomPanel}
        </div>
      </div>
    </div>
  );
}
