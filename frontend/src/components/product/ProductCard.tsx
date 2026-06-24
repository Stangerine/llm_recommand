import type { Product } from "@/types/product";

interface Props {
  product: Product;
  rank?: number;
  onClick?: (product: Product) => void;
  onAddToHistory?: (product: Product) => void;
}

export function ProductCard({ product, rank, onClick, onAddToHistory }: Props) {
  const isTopRank = rank !== undefined && rank < 3;

  return (
    <div
      className="group relative cursor-pointer rounded-xl bg-white border border-slate-200/80 p-4 shadow-card hover:shadow-card-hover hover:border-brand-200/60 hover:-translate-y-0.5 transition-all duration-200 ease-out"
      onClick={() => onClick?.(product)}
    >
      {/* Rank badge */}
      {rank !== undefined && (
        <span
          className={`absolute top-3 left-3 z-10 text-xs font-bold px-2 py-0.5 rounded-full ${
            isTopRank
              ? "bg-gradient-to-r from-brand-500 to-brand-600 text-white shadow-sm"
              : "bg-slate-100 text-slate-500"
          }`}
        >
          #{rank + 1}
        </span>
      )}

      <div className="space-y-3">
        {/* Title */}
        <p className="text-sm font-medium leading-relaxed line-clamp-2 text-slate-800 min-h-[2.5rem]">
          {product.title}
        </p>

        {/* Brand + Category chips */}
        <div className="flex flex-wrap gap-1.5">
          {product.brand && (
            <span className="inline-flex items-center rounded-md bg-brand-50 px-2 py-0.5 text-xs font-medium text-brand-700 border border-brand-100">
              {product.brand}
            </span>
          )}
          {product.category && (
            <span className="inline-flex items-center rounded-md bg-slate-50 px-2 py-0.5 text-xs text-slate-500 max-w-[130px] truncate border border-slate-100">
              {product.category.split(" > ").pop()}
            </span>
          )}
        </div>

        {/* Rating + Price */}
        <div className="flex items-center justify-between pt-1">
          <div className="flex items-center gap-1 text-xs text-slate-500">
            {product.rating && (
              <>
                <span className="text-amber-400">★</span>
                <span className="font-medium">{product.rating.toFixed(1)}</span>
                {product.rating_count && (
                  <span className="text-slate-400">
                    ({product.rating_count.toLocaleString()})
                  </span>
                )}
              </>
            )}
          </div>
          {product.price != null && product.price > 0 && (
            <span className="text-sm font-bold text-brand-600">
              ${product.price.toFixed(2)}
            </span>
          )}
        </div>

        {/* Add to history button */}
        {onAddToHistory && (
          <button
            className="w-full mt-1 py-1.5 text-xs font-medium text-brand-600 bg-brand-50 border border-brand-200/60 rounded-lg hover:bg-brand-100 hover:border-brand-300 transition-all duration-150 opacity-0 group-hover:opacity-100 translate-y-1 group-hover:translate-y-0"
            onClick={(e) => {
              e.stopPropagation();
              onAddToHistory(product);
            }}
          >
            + 加入浏览历史
          </button>
        )}
      </div>
    </div>
  );
}
