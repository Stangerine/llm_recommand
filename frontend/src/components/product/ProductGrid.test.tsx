import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { ProductGrid } from "./ProductGrid";
import type { Product } from "@/types/product";

const mockProducts: Product[] = [
  {
    asin: "B001",
    title: "Product 1",
    brand: "Brand A",
    price: 10.99,
    rating: 4.5,
  },
  {
    asin: "B002",
    title: "Product 2",
    brand: "Brand B",
    price: 20.99,
    rating: 4.0,
  },
  {
    asin: "B003",
    title: "Product 3",
    brand: "Brand C",
    price: 30.99,
    rating: 3.5,
  },
];

describe("ProductGrid", () => {
  it("renders all products", () => {
    render(<ProductGrid products={mockProducts} />);
    expect(screen.getByText("Product 1")).toBeInTheDocument();
    expect(screen.getByText("Product 2")).toBeInTheDocument();
    expect(screen.getByText("Product 3")).toBeInTheDocument();
  });

  it("renders rank badges when rankOffset provided", () => {
    render(<ProductGrid products={mockProducts} rankOffset={3} />);
    expect(screen.getByText("#4")).toBeInTheDocument();
    expect(screen.getByText("#5")).toBeInTheDocument();
    expect(screen.getByText("#6")).toBeInTheDocument();
  });

  it("calls onProductClick when product clicked", () => {
    const handleClick = vi.fn();
    render(<ProductGrid products={mockProducts} onProductClick={handleClick} />);
    fireEvent.click(screen.getByText("Product 1"));
    expect(handleClick).toHaveBeenCalledWith(mockProducts[0]);
  });

  it("calls onAddToHistory when add button clicked", () => {
    const handleAdd = vi.fn();
    render(<ProductGrid products={mockProducts} onAddToHistory={handleAdd} />);
    const addButtons = screen.getAllByText("+ 加入浏览历史");
    fireEvent.click(addButtons[0]);
    expect(handleAdd).toHaveBeenCalledWith(mockProducts[0]);
  });

  it("renders empty grid for empty products", () => {
    const { container } = render(<ProductGrid products={[]} />);
    expect(container.querySelector(".grid")).toBeInTheDocument();
    expect(screen.queryByText("Product")).not.toBeInTheDocument();
  });
});
