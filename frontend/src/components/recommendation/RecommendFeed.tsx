import { useRecommend, useBehaviorReport } from "@/hooks/useRecommend";
import { useBehaviorStore } from "@/store/behaviorStore";
import { ProductGrid } from "@/components/product/ProductGrid";
import { ProductDetailModal } from "@/components/product/ProductDetailModal";
import { RefreshButton } from "./RefreshButton";
import { EmptyState } from "@/components/common/EmptyState";
import { LoadingSpinner } from "@/components/common/LoadingSpinner";
import { useState } from "react";
import type { Product } from "@/types/product";

export function RecommendFeed() {
  const { data, isLoading, isError, error, refresh } = useRecommend();
  const { mutate: reportBehavior } = useBehaviorReport();
  const addRecord = useBehaviorStore((s) => s.addRecord);
  const [selected, setSelected] = useState<Product | null>(null);

  const handleProductClick = (product: Product) => {
    setSelected(product);
    reportBehavior({ asin: product.asin, action: "click" });
    addRecord({
      asin: product.asin,
      title: product.title,
      action: "click",
      timestamp: Date.now(),
    });
  };

  const handleAddToHistory = (product: Product) => {
    addRecord({
      asin: product.asin,
      title: product.title,
      action: "view",
      timestamp: Date.now(),
    });
    reportBehavior({ asin: product.asin, action: "view" });
  };

  if (isLoading) return <LoadingSpinner size="lg" />;

  if (isError)
    return (
      <EmptyState
        title="加载失败"
        description={(error as Error).message}
        action={{ label: "重试", onClick: refresh }}
      />
    );

  if (!data?.recommendations.length)
    return (
      <EmptyState
        title="暂无推荐"
        description="点击右侧商品卡片的「加入浏览历史」触发个性化推荐"
      />
    );

  return (
    <section>
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className="text-lg font-semibold text-slate-800 flex items-center gap-2">
            <span className="w-1 h-5 bg-gradient-to-b from-brand-400 to-brand-600 rounded-full" />
            为你推荐
          </h2>
          <p className="text-xs text-slate-400 mt-1 ml-3">
            基于浏览历史的个性化推荐 · 共 {data.total} 件
          </p>
        </div>
        <RefreshButton onRefresh={refresh} />
      </div>

      <ProductGrid
        products={data.recommendations}
        onProductClick={handleProductClick}
        onAddToHistory={handleAddToHistory}
      />

      {selected && (
        <ProductDetailModal
          product={selected}
          onClose={() => setSelected(null)}
        />
      )}
    </section>
  );
}
