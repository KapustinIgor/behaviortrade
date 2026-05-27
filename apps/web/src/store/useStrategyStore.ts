import { create } from "zustand";
import type { StrategyState } from "@/types";

interface StrategyStore {
  strategies: StrategyState[];
  capitalWeights: Record<string, number>;
  setStrategies: (s: StrategyState[]) => void;
  setWeight: (name: string, weight: number) => void;
}

export const useStrategyStore = create<StrategyStore>((set) => ({
  strategies: [],
  capitalWeights: {},
  setStrategies: (strategies) => set({ strategies }),
  setWeight: (name, weight) =>
    set((s) => ({ capitalWeights: { ...s.capitalWeights, [name]: weight } })),
}));
