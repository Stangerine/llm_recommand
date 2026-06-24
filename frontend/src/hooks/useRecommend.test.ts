import { describe, it, expect, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { useRecommend } from "./useRecommend";

// Mock the dependencies
vi.mock("@/api/recommend", () => ({
  fetchRecommendations: vi.fn(),
  reportBehavior: vi.fn(),
}));

vi.mock("@/store/behaviorStore", () => ({
  useBehaviorStore: vi.fn((selector: (state: Record<string, unknown>) => unknown) => {
    const state = {
      records: [],
      historyAsins: () => [],
    };
    return selector(state);
  }),
}));

vi.mock("@/store/userStore", () => ({
  useUserStore: vi.fn((selector: (state: Record<string, unknown>) => unknown) => {
    const state = { userId: "test_user" };
    return selector(state);
  }),
}));

vi.mock("@tanstack/react-query", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    useQuery: vi.fn(() => ({
      data: null,
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    })),
    useQueryClient: vi.fn(() => ({
      invalidateQueries: vi.fn(),
    })),
  };
});

describe("useRecommend", () => {
  it("returns query state", () => {
    const { result } = renderHook(() => useRecommend());
    expect(result.current).toBeDefined();
    expect(result.current.isLoading).toBe(false);
    expect(result.current.data).toBeNull();
  });
});
