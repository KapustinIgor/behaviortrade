import { useCallback, useEffect, useRef, useState } from "react";
import { Bot, ChevronDown, Send, X, Sparkles, AlertCircle } from "lucide-react";
import { streamCopilotChat, type ChatMessage, type CopilotContext } from "@/api/copilot";
import { useMarketStore } from "@/store/useMarketStore";
import { useBehavioralScores } from "@/api/behavioral";
import { usePriceForecast } from "@/api/predictions";
import { useStrategies } from "@/api/strategies";
import { cn } from "@/components/ui/cn";

// ── Simple inline markdown renderer ──────────────────────────────────────────

function renderText(text: string): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  const lines = text.split("\n");

  lines.forEach((line, i) => {
    if (line.startsWith("### ")) {
      nodes.push(<p key={i} className="font-semibold text-white mt-2">{line.slice(4)}</p>);
    } else if (line.startsWith("## ")) {
      nodes.push(<p key={i} className="font-bold text-white mt-3">{line.slice(3)}</p>);
    } else if (line.startsWith("- ") || line.startsWith("• ")) {
      nodes.push(
        <div key={i} className="flex gap-1.5 ml-1">
          <span className="text-brand-light mt-0.5 flex-shrink-0">•</span>
          <span>{inlineMd(line.slice(2))}</span>
        </div>
      );
    } else if (line.trim() === "") {
      nodes.push(<div key={i} className="h-2" />);
    } else {
      nodes.push(<p key={i}>{inlineMd(line)}</p>);
    }
  });
  return nodes;
}

function inlineMd(text: string): React.ReactNode {
  // Bold **text**
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((p, i) =>
    p.startsWith("**") && p.endsWith("**")
      ? <strong key={i} className="font-semibold text-white">{p.slice(2, -2)}</strong>
      : <span key={i}>{p}</span>
  );
}

// ── Message bubble ────────────────────────────────────────────────────────────

function MessageBubble({ msg, streaming }: { msg: ChatMessage; streaming?: boolean }) {
  const isUser = msg.role === "user";
  return (
    <div className={cn("flex gap-2", isUser ? "justify-end" : "justify-start")}>
      {!isUser && (
        <div className="w-6 h-6 rounded-full bg-brand/20 border border-brand/30 flex items-center justify-center flex-shrink-0 mt-0.5">
          <Bot className="w-3 h-3 text-brand-light" />
        </div>
      )}
      <div
        className={cn(
          "max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed",
          isUser
            ? "bg-brand/20 border border-brand/30 text-gray-100 rounded-tr-sm"
            : "bg-surface-700 border border-surface-600 text-gray-300 rounded-tl-sm"
        )}
      >
        {isUser
          ? <p>{msg.content}</p>
          : <div className="space-y-0.5">{renderText(msg.content)}</div>
        }
        {streaming && (
          <span className="inline-block w-1.5 h-3.5 bg-brand-light ml-0.5 animate-pulse rounded-sm" />
        )}
      </div>
    </div>
  );
}

// ── Suggestion chips ──────────────────────────────────────────────────────────

const SUGGESTIONS = [
  "What does the current regime mean for me?",
  "Explain the GNN forecast confidence",
  "Which strategies fit this market?",
  "What are whales doing right now?",
  "Summarize the behavioral scores",
];

// ── Main component ────────────────────────────────────────────────────────────

export function CopilotChat() {
  const [open, setOpen]     = useState(false);
  const [input, setInput]   = useState("");
  const [history, setHistory] = useState<ChatMessage[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [error, setError]   = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef  = useRef<HTMLTextAreaElement>(null);
  const { selectedAsset } = useMarketStore();
  const { data: scores }  = useBehavioralScores();
  const { data: forecast } = usePriceForecast(selectedAsset, true);
  const { data: strategies } = useStrategies();

  const buildContext = useCallback((): CopilotContext => ({
    asset: selectedAsset,
    scores: scores as Record<string, number | string> | undefined,
    forecast: forecast && !forecast.error ? {
      direction: forecast.direction,
      prob_24h: forecast.prob_24h,
      gnn_confidence: forecast.gnn_confidence,
    } : undefined,
    strategies: strategies?.map((s) => ({ name: s.name, pnl_30d: s.pnl_30d })),
  }), [selectedAsset, scores, forecast, strategies]);

  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [open]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [history, streaming]);

  const send = useCallback(async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || streaming) return;

    setError(null);
    const userMsg: ChatMessage = { role: "user", content: trimmed };
    const assistantMsg: ChatMessage = { role: "assistant", content: "" };

    setHistory((h) => [...h, userMsg, assistantMsg]);
    setInput("");
    setStreaming(true);

    const ctx = buildContext();
    const historyToSend = history.slice(-10);

    await streamCopilotChat(
      trimmed,
      historyToSend,
      ctx,
      (chunk) => {
        setHistory((h) => {
          const copy = [...h];
          const last = copy[copy.length - 1];
          if (last?.role === "assistant") {
            copy[copy.length - 1] = { ...last, content: last.content + chunk };
          }
          return copy;
        });
      },
      () => setStreaming(false),
      (err) => {
        setStreaming(false);
        setError(err);
        setHistory((h) => h.slice(0, -1)); // remove empty assistant message
      },
    );
  }, [streaming, history, buildContext]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  };

  const clearHistory = () => {
    setHistory([]);
    setError(null);
  };

  return (
    <>
      {/* Floating trigger button */}
      <button
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "fixed bottom-5 right-5 z-50 w-12 h-12 rounded-full shadow-lg",
          "flex items-center justify-center transition-all duration-200",
          open
            ? "bg-surface-700 border border-surface-600 text-gray-400 hover:text-gray-200"
            : "bg-brand hover:bg-brand-dark text-white"
        )}
        title="BehaviorTrade Copilot"
      >
        {open ? <ChevronDown className="w-5 h-5" /> : <Sparkles className="w-5 h-5" />}
      </button>

      {/* Chat panel */}
      {open && (
        <div
          className={cn(
            "fixed bottom-20 right-5 z-50 w-[380px] h-[560px] flex flex-col",
            "bg-surface-800 border border-surface-600 rounded-2xl shadow-2xl",
            "overflow-hidden"
          )}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-surface-700 flex-shrink-0">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-full bg-brand/20 border border-brand/40 flex items-center justify-center">
                <Bot className="w-3.5 h-3.5 text-brand-light" />
              </div>
              <div>
                <p className="text-sm font-semibold text-white">BT Copilot</p>
                <p className="text-[10px] text-gray-500">Research & analysis only</p>
              </div>
            </div>
            <div className="flex items-center gap-1">
              {history.length > 0 && (
                <button
                  onClick={clearHistory}
                  className="px-2 py-1 text-xs text-gray-500 hover:text-gray-300 transition-colors"
                >
                  Clear
                </button>
              )}
              <button
                onClick={() => setOpen(false)}
                className="p-1 text-gray-500 hover:text-gray-300 transition-colors rounded"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-3 space-y-3 min-h-0">
            {history.length === 0 && (
              <div className="space-y-3">
                <div className="text-center pt-4">
                  <div className="w-10 h-10 rounded-full bg-brand/10 border border-brand/20 flex items-center justify-center mx-auto mb-2">
                    <Sparkles className="w-5 h-5 text-brand-light" />
                  </div>
                  <p className="text-sm font-medium text-gray-300">Ask me about what you see</p>
                  <p className="text-xs text-gray-600 mt-1">
                    I read live market data, regime, GNN forecasts, and strategy performance.
                  </p>
                </div>
                <div className="space-y-1.5 pt-2">
                  {SUGGESTIONS.map((s) => (
                    <button
                      key={s}
                      onClick={() => send(s)}
                      className={cn(
                        "w-full text-left px-3 py-2 rounded-xl text-xs text-gray-400",
                        "border border-surface-600 hover:border-brand/40 hover:text-gray-200",
                        "hover:bg-brand/5 transition-colors"
                      )}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {history.map((msg, i) => (
              <MessageBubble
                key={i}
                msg={msg}
                streaming={streaming && i === history.length - 1 && msg.role === "assistant"}
              />
            ))}

            {error && (
              <div className="flex items-start gap-2 px-3 py-2.5 rounded-xl bg-red-950/30 border border-red-900/40">
                <AlertCircle className="w-3.5 h-3.5 text-red-400 flex-shrink-0 mt-0.5" />
                <p className="text-xs text-red-400">{error}</p>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div className="border-t border-surface-700 p-3 flex-shrink-0">
            <div className="flex items-end gap-2">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask about regime, signals, strategies…"
                rows={1}
                className={cn(
                  "flex-1 bg-surface-700 border border-surface-600 rounded-xl",
                  "px-3 py-2 text-sm text-gray-200 placeholder-gray-600",
                  "resize-none focus:outline-none focus:border-brand/50",
                  "max-h-24 overflow-y-auto leading-relaxed"
                )}
                style={{ height: "auto", minHeight: "36px" }}
                onInput={(e) => {
                  const el = e.currentTarget;
                  el.style.height = "auto";
                  el.style.height = `${Math.min(el.scrollHeight, 96)}px`;
                }}
                disabled={streaming}
              />
              <button
                onClick={() => send(input)}
                disabled={!input.trim() || streaming}
                className={cn(
                  "w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0",
                  "transition-colors",
                  input.trim() && !streaming
                    ? "bg-brand hover:bg-brand-dark text-white"
                    : "bg-surface-700 text-gray-600 cursor-not-allowed"
                )}
              >
                <Send className="w-4 h-4" />
              </button>
            </div>
            <p className="text-[10px] text-gray-700 mt-1.5 text-center">
              Research & analysis only · Not financial advice
            </p>
          </div>
        </div>
      )}
    </>
  );
}
