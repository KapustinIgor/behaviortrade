import { create } from "zustand";
import type { BehavioralScores } from "@/types";

const MAX_HISTORY = 60;

interface BehaviorStore {
  scores: BehavioralScores | null;
  scoreHistory: BehavioralScores[];
  isConnected: boolean;
  updateScores: (scores: BehavioralScores) => void;
  setConnected: (v: boolean) => void;
}

export const useBehaviorStore = create<BehaviorStore>((set) => ({
  scores: null,
  scoreHistory: [],
  isConnected: false,
  updateScores: (scores) =>
    set((s) => ({
      scores,
      scoreHistory: [...s.scoreHistory.slice(-(MAX_HISTORY - 1)), scores],
    })),
  setConnected: (isConnected) => set({ isConnected }),
}));
