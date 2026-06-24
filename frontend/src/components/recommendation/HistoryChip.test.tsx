import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { HistoryChip } from "./HistoryChip";
import type { BehaviorRecord } from "@/types/product";

describe("HistoryChip", () => {
  const mockRecord: BehaviorRecord = {
    asin: "B001",
    title: "Test Industrial Product",
    action: "view",
    timestamp: Date.now(),
  };

  it("renders record title", () => {
    render(<HistoryChip record={mockRecord} onRemove={vi.fn()} />);
    expect(screen.getByText("Test Industrial Product")).toBeInTheDocument();
  });

  it("renders action label", () => {
    render(<HistoryChip record={mockRecord} onRemove={vi.fn()} />);
    expect(screen.getByText(/浏览/)).toBeInTheDocument();
  });

  it("renders click action label", () => {
    const clickRecord = { ...mockRecord, action: "click" as const };
    render(<HistoryChip record={clickRecord} onRemove={vi.fn()} />);
    expect(screen.getByText(/点击/)).toBeInTheDocument();
  });

  it("calls onRemove when remove button clicked", () => {
    const onRemove = vi.fn();
    render(<HistoryChip record={mockRecord} onRemove={onRemove} />);
    fireEvent.click(screen.getByText("✕"));
    expect(onRemove).toHaveBeenCalled();
  });

  it("renders timestamp", () => {
    render(<HistoryChip record={mockRecord} onRemove={vi.fn()} />);
    // Should render some time string
    expect(screen.getByText(/:/)).toBeInTheDocument();
  });
});
