import type { Product } from "@/types/product";
import { ProductCard } from "./ProductCard";

interface Props {
  products: Product[];
  rankOffset?: number;
  onProductClick?: (product: Product) => void;
  onAddToHistory?: (product: Product) => void;
}

export function ProductGrid({
  products,
  rankOffset = 0,
  onProductClick,
  onAddToHistory,
}: Props) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4 animate-fade-in">
      {products.map((product, idx) => (
        <ProductCard
          key={product.asin}
          product={product}
          rank={rankOffset + idx}
          onClick={onProductClick}
          onAddToHistory={onAddToHistory}
        />
      ))}
    </div>
  );
}
