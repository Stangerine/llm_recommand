import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, beforeEach, vi } from "vitest";
import { BehaviorPanel } from "./BehaviorPanel";
import { useBehaviorStore } from "@/store/behaviorStore";

// Mock the store
vi.mock("@/store/behaviorStore", () => ({
  useBehaviorStore: vi.fn(),
}));

describe("BehaviorPanel", () => {
  const mockRecords = [
    { asin: "B001", title: "Product 1", action: "view" as const, timestamp: 1000 },
    { asin: "B002", title: "Product 2", action: "click" as const, timestamp: 2000 },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders empty state when no records", () => {
    (useBehaviorStore as any).mockReturnValue({
      records: [],
      removeRecord: vi.fn(),
      clearAll: vi.fn(),
    });

    render(<BehaviorPanel />);
    expect(screen.getByText(/点击商品卡片/)).toBeInTheDocument();
  });

  it("renders history records", () => {
    (useBehaviorStore as any).mockReturnValue({
      records: mockRecords,
      removeRecord: vi.fn(),
      clearAll: vi.fn(),
    });

    render(<BehaviorPanel />);
    expect(screen.getByText("Product 1")).toBeInTheDocument();
    expect(screen.getByText("Product 2")).toBeInTheDocument();
  });

  it("shows record count", () => {
    (useBehaviorStore as any).mockReturnValue({
      records: mockRecords,
      removeRecord: vi.fn(),
      clearAll: vi.fn(),
    });

    render(<BehaviorPanel />);
    expect(screen.getByText(/已保留最近 2\/50 条/)).toBeInTheDocument();
  });

  it("calls clearAll when clear button clicked", () => {
    const clearAll = vi.fn();
    (useBehaviorStore as any).mockReturnValue({
      records: mockRecords,
      removeRecord: vi.fn(),
      clearAll,
    });

    render(<BehaviorPanel />);
    fireEvent.click(screen.getByText("清空"));
    expect(clearAll).toHaveBeenCalled();
  });

  it("does not show clear button when empty", () => {
    (useBehaviorStore as any).mockReturnValue({
      records: [],
      removeRecord: vi.fn(),
      clearAll: vi.fn(),
    });

    render(<BehaviorPanel />);
    expect(screen.queryByText("清空")).not.toBeInTheDocument();
  });
});
