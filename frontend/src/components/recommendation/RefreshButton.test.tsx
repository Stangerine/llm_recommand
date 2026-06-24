import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { RefreshButton } from "./RefreshButton";

describe("RefreshButton", () => {
  it("renders refresh text", () => {
    render(<RefreshButton onRefresh={vi.fn()} />);
    expect(screen.getByText("刷新")).toBeInTheDocument();
  });

  it("calls onRefresh when clicked", () => {
    const onRefresh = vi.fn();
    render(<RefreshButton onRefresh={onRefresh} />);
    fireEvent.click(screen.getByText("刷新"));
    expect(onRefresh).toHaveBeenCalled();
  });

  it("shows spinning animation on click", () => {
    render(<RefreshButton onRefresh={vi.fn()} />);
    const button = screen.getByText("刷新");
    fireEvent.click(button);
    const svg = button.querySelector("svg");
    expect(svg?.className).toContain("animate-spin");
  });
});
