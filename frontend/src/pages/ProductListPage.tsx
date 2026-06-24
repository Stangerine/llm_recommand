import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import apiClient from "@/api/client";
import { ProductCard } from "@/components/product/ProductCard";
import { LoadingSpinner } from "@/components/common/LoadingSpinner";
import { EmptyState } from "@/components/common/EmptyState";
import { useBehaviorStore } from "@/store/behaviorStore";
import type { Product } from "@/types/product";

interface ProductListResponse {
  products: Product[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export function ProductListPage() {
  const [page, setPage] = useState(1);
  const addRecord = useBehaviorStore((s) => s.addRecord);

  const { data, isLoading, error } = useQuery<ProductListResponse>({
    queryKey: ["products", page],
    queryFn: async () => {
      const params = new URLSearchParams({
        page: String(page),
        page_size: "20",
      });
      const { data } = await apiClient.get(`/products?${params}`);
      return data;
    },
  });

  const handleAddToHistory = (product: Product) => {
    addRecord({
      asin: product.asin,
      title: product.title,
      action: "view",
      timestamp: Date.now(),
    });
  };

  if (isLoading) return <LoadingSpinner size="lg" />;

  if (error) {
    return (
      <EmptyState
        title="加载失败"
        description="请刷新重试"
        action={{ label: "刷新", onClick: () => window.location.reload() }}
      />
    );
  }

  return (
    <div className="max-w-screen-xl mx-auto px-6 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">商品列表</h1>
          <p className="text-sm text-slate-500 mt-1">
            共 {data?.total || 0} 个商品
          </p>
        </div>
      </div>

      {/* Product grid */}
      {data?.products.length ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4 animate-fade-in">
          {data.products.map((product) => (
            <ProductCard
              key={product.asin}
              product={product}
              onAddToHistory={handleAddToHistory}
            />
          ))}
        </div>
      ) : (
        <EmptyState title="暂无商品" />
      )}

      {/* Pagination */}
      {data && data.total_pages > 1 && (
        <div className="flex items-center justify-center gap-3 mt-10">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="btn-ghost disabled:opacity-30 disabled:cursor-not-allowed"
          >
            上一页
          </button>
          <div className="flex items-center gap-1">
            {Array.from(
              { length: Math.min(data.total_pages, 7) },
              (_, i) => {
                const pageNum = i + 1;
                return (
                  <button
                    key={pageNum}
                    onClick={() => setPage(pageNum)}
                    className={`w-8 h-8 rounded-lg text-xs font-medium transition-all duration-150 ${
                      page === pageNum
                        ? "bg-brand-500 text-white shadow-sm"
                        : "text-slate-500 hover:bg-slate-100"
                    }`}
                  >
                    {pageNum}
                  </button>
                );
              }
            )}
            {data.total_pages > 7 && (
              <span className="text-slate-400 px-1">...</span>
            )}
          </div>
          <button
            onClick={() =>
              setPage((p) => Math.min(data.total_pages, p + 1))
            }
            disabled={page === data.total_pages}
            className="btn-ghost disabled:opacity-30 disabled:cursor-not-allowed"
          >
            下一页
          </button>
        </div>
      )}
    </div>
  );
}
