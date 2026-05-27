import { Component, type ErrorInfo, type ReactNode } from "react";
import { Dashboard } from "@/pages/Dashboard";
import { CopilotChat } from "@/components/copilot/CopilotChat";
import { useLiveBehavior } from "@/hooks/useLiveBehavior";
import { useLivePrices } from "@/hooks/useLivePrices";

function LiveInit() {
  useLiveBehavior();
  useLivePrices();
  return null;
}

class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("BehaviorTrade error:", error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="min-h-screen bg-surface-900 flex items-center justify-center p-8">
          <div className="text-center space-y-4 max-w-md">
            <div className="text-4xl">⚠️</div>
            <h1 className="text-xl font-bold text-white">Something went wrong</h1>
            <p className="text-gray-400 text-sm">{(this.state.error as Error).message}</p>
            <button
              onClick={() => this.setState({ error: null })}
              className="px-4 py-2 bg-brand rounded-lg text-white text-sm hover:bg-brand-dark transition-colors"
            >
              Retry
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

export default function App() {
  return (
    <ErrorBoundary>
      <LiveInit />
      <Dashboard />
      <CopilotChat />
    </ErrorBoundary>
  );
}
