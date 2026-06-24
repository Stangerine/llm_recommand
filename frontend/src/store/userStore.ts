import { create } from "zustand";
import { persist } from "zustand/middleware";

interface UserState {
  userId: string;
  setUserId: (id: string) => void;
}

export const useUserStore = create<UserState>()(
  persist(
    (set) => ({
      userId: `user_${Math.random().toString(36).slice(2, 9)}`,
      setUserId: (id) => set({ userId: id }),
    }),
    { name: "user-store" }
  )
);
