import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { searchProducts } from "@/api/products";
import { ProductGrid } from "@/components/product/ProductGrid";
import { useBehaviorStore } from "@/store/behaviorStore";
import { LoadingSpinner } from "@/components/common/LoadingSpinner";
import { EmptyState } from "@/components/common/EmptyState";

export function SearchPage() {
  const [query, setQuery] = useState("");
  const addRecord = useBehaviorStore((s) => s.addRecord);

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["search", query],
    queryFn: () => searchProducts(query),
    enabled: query.trim().length >= 2,
    staleTime: 30_000,
  });

  return (
    <div className="max-w-screen-xl mx-auto px-6 py-8">
      {/* Search header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-800 mb-2">搜索商品</h1>
        <p className="text-sm text-slate-500">在工业科学用品目录中搜索</p>
      </div>

      {/* Search input */}
      <div className="mb-8 max-w-2xl">
        <div className="relative">
          <svg
            className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="输入关键词搜索..."
            className="input-base pl-11 pr-4 py-3"
          />
        </div>
      </div>

      {/* Results */}
      {isLoading || isFetching ? (
        <LoadingSpinner />
      ) : data ? (
        <>
          <p className="text-xs text-slate-400 mb-5">
            找到{" "}
            <span className="font-medium text-slate-600">{data.total}</span>{" "}
            个结果
          </p>
          <ProductGrid
            products={data.results}
            onAddToHistory={(product) =>
              addRecord({
                asin: product.asin,
                title: product.title,
                action: "view",
                timestamp: Date.now(),
              })
            }
          />
        </>
      ) : query.trim().length >= 2 ? (
        <EmptyState title="暂无结果" description="尝试更换搜索关键词" />
      ) : (
        <EmptyState
          title="开始搜索"
          description="输入至少 2 个字符开始搜索"
        />
      )}
    </div>
  );
}
