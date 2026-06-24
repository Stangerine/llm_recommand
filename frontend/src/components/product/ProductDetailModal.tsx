import type { Product } from "@/types/product";

interface Props {
  product: Product;
  onClose: () => void;
}

export function ProductDetailModal({ product, onClose }: Props) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm animate-fade-in"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-lg mx-4 rounded-2xl bg-white shadow-2xl border border-slate-200/60 animate-slide-up overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header accent */}
        <div className="h-1 bg-gradient-to-r from-brand-400 via-brand-500 to-brand-600" />

        <div className="p-6">
          {/* Close button */}
          <button
            onClick={onClose}
            className="absolute top-4 right-4 w-8 h-8 flex items-center justify-center rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-all duration-150"
          >
            ✕
          </button>

          {/* Title */}
          <h2 className="text-lg font-semibold text-slate-800 pr-10 leading-relaxed">
            {product.title}
          </h2>

          {/* Details */}
          <div className="mt-5 space-y-4">
            {product.brand && (
              <div className="flex items-start gap-3">
                <span className="text-xs font-medium text-slate-400 uppercase tracking-wider w-10 pt-0.5">
                  品牌
                </span>
                <span className="text-sm text-slate-700 font-medium">
                  {product.brand}
                </span>
              </div>
            )}

            {product.category && (
              <div className="flex items-start gap-3">
                <span className="text-xs font-medium text-slate-400 uppercase tracking-wider w-10 pt-0.5">
                  分类
                </span>
                <span className="text-sm text-slate-600">
                  {product.category}
                </span>
              </div>
            )}

            {product.price != null && product.price > 0 && (
              <div className="flex items-start gap-3">
                <span className="text-xs font-medium text-slate-400 uppercase tracking-wider w-10 pt-0.5">
                  价格
                </span>
                <span className="text-lg font-bold text-brand-600">
                  ${product.price.toFixed(2)}
                </span>
              </div>
            )}

            {product.rating && (
              <div className="flex items-start gap-3">
                <span className="text-xs font-medium text-slate-400 uppercase tracking-wider w-10 pt-0.5">
                  评分
                </span>
                <div className="flex items-center gap-2">
                  <span className="text-amber-400 text-lg">★</span>
                  <span className="text-sm font-semibold text-slate-700">
                    {product.rating.toFixed(1)}
                  </span>
                  {product.rating_count && (
                    <span className="text-xs text-slate-400">
                      ({product.rating_count.toLocaleString()} 条评价)
                    </span>
                  )}
                </div>
              </div>
            )}

            {product.description && (
              <div className="pt-4 border-t border-slate-100">
                <p className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">
                  商品描述
                </p>
                <p className="text-sm text-slate-600 leading-relaxed max-h-40 overflow-y-auto">
                  {product.description}
                </p>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="mt-6 flex justify-end">
            <button onClick={onClose} className="btn-ghost">
              关闭
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
