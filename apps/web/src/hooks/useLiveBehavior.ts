import { useEffect } from "react";
import { useBehaviorStore } from "@/store/useBehaviorStore";
import { useWebSocket } from "./useWebSocket";
import type { BehavioralScores } from "@/types";

export function useLiveBehavior() {
  const { updateScores, setConnected } = useBehaviorStore();

  const { isConnected } = useWebSocket("/ws/behavioral", (data) => {
    if (data && typeof data === "object" && "panic_score" in (data as object)) {
      updateScores(data as BehavioralScores);
    }
  });

  useEffect(() => {
    setConnected(isConnected);
  }, [isConnected, setConnected]);

  return { isConnected };
}
