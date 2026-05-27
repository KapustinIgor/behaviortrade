import { useCallback, useEffect, useRef, useState } from "react";
import { createWebSocket } from "@/api/client";

const MAX_DELAY = 30_000;

export function useWebSocket(path: string, onMessage: (data: unknown) => void) {
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const delayRef = useRef(1_000);
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  useEffect(() => {
    let stopped = false;

    function connect() {
      if (stopped) return;
      const ws = createWebSocket(path);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        delayRef.current = 1_000;
      };

      ws.onmessage = (e) => {
        try {
          onMessageRef.current(JSON.parse(e.data));
        } catch {
          onMessageRef.current(e.data);
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
        if (!stopped) {
          setTimeout(connect, delayRef.current);
          delayRef.current = Math.min(delayRef.current * 2, MAX_DELAY);
        }
      };

      ws.onerror = () => ws.close();
    }

    connect();
    return () => {
      stopped = true;
      wsRef.current?.close();
    };
  }, [path]);

  const send = useCallback((data: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  return { isConnected, send };
}
