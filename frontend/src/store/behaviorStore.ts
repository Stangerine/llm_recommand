import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { BehaviorRecord } from "@/types/product";

interface BehaviorState {
  records: BehaviorRecord[];
  addRecord: (record: BehaviorRecord) => void;
  removeRecord: (asin: string) => void;
  clearAll: () => void;
  historyAsins: () => string[];
}

export const useBehaviorStore = create<BehaviorState>()(
  persist(
    (set, get) => ({
      records: [],

      addRecord: (record) =>
        set((state) => {
          const filtered = state.records.filter((r) => r.asin !== record.asin);
          return { records: [record, ...filtered].slice(0, 50) }; // 最多保留 50 条
        }),

      removeRecord: (asin) =>
        set((state) => ({
          records: state.records.filter((r) => r.asin !== asin),
        })),

      clearAll: () => set({ records: [] }),

      historyAsins: () =>
        get()
          .records.sort((a, b) => a.timestamp - b.timestamp)
          .map((r) => r.asin),
    }),
    { name: "behavior-history" } // 持久化至 localStorage
  )
);
