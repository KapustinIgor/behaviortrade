const BASE_URL = import.meta.env.VITE_API_URL ?? "/api";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface CopilotContext {
  asset?: string;
  scores?: Record<string, number | string>;
  forecast?: {
    direction: string;
    prob_24h: number;
    gnn_confidence: number;
  };
  strategies?: Array<{ name: string; pnl_30d: number }>;
}

export async function streamCopilotChat(
  message: string,
  history: ChatMessage[],
  context: CopilotContext,
  onChunk: (text: string) => void,
  onDone: () => void,
  onError: (err: string) => void,
): Promise<void> {
  try {
    const res = await fetch(`${BASE_URL}/copilot/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, history, context }),
    });

    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: res.statusText }));
      onError(body.detail ?? `Error ${res.status}`);
      return;
    }

    const reader = res.body?.getReader();
    if (!reader) { onError("No response body"); return; }

    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const payload = line.slice(6).trim();
        if (payload === "[DONE]") { onDone(); return; }
        try {
          const parsed = JSON.parse(payload);
          if (parsed.text) onChunk(parsed.text);
        } catch { /* skip malformed */ }
      }
    }
    onDone();
  } catch (err) {
    onError(err instanceof Error ? err.message : "Unknown error");
  }
}
