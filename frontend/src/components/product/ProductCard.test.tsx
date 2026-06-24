import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { ProductCard } from "./ProductCard";
import type { Product } from "@/types/product";

const mockProduct: Product = {
  asin: "B001TEST",
  title: "Test Industrial Product",
  brand: "TestBrand",
  category: "Industrial & Scientific > Safety",
  price: 29.99,
  rating: 4.3,
  rating_count: 512,
};

describe("ProductCard", () => {
  it("renders product title", () => {
    render(<ProductCard product={mockProduct} />);
    expect(screen.getByText("Test Industrial Product")).toBeInTheDocument();
  });

  it("renders price correctly", () => {
    render(<ProductCard product={mockProduct} />);
    expect(screen.getByText("$29.99")).toBeInTheDocument();
  });

  it("shows rank badge when rank provided", () => {
    render(<ProductCard product={mockProduct} rank={0} />);
    expect(screen.getByText("#1")).toBeInTheDocument();
  });

  it("renders brand badge", () => {
    render(<ProductCard product={mockProduct} />);
    expect(screen.getByText("TestBrand")).toBeInTheDocument();
  });

  it("renders rating", () => {
    render(<ProductCard product={mockProduct} />);
    expect(screen.getByText("4.3")).toBeInTheDocument();
  });

  it("calls onClick when clicked", () => {
    const handleClick = vi.fn();
    render(<ProductCard product={mockProduct} onClick={handleClick} />);
    screen.getByText("Test Industrial Product").click();
    expect(handleClick).toHaveBeenCalledWith(mockProduct);
  });

  it("calls onAddToHistory when button clicked", () => {
    const handleAdd = vi.fn();
    render(<ProductCard product={mockProduct} onAddToHistory={handleAdd} />);
    screen.getByText("+ 加入浏览历史").click();
    expect(handleAdd).toHaveBeenCalledWith(mockProduct);
  });
});
