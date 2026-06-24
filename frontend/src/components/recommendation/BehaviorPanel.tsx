import { useBehaviorStore } from "@/store/behaviorStore";
import { HistoryChip } from "./HistoryChip";

export function BehaviorPanel() {
  const { records, removeRecord, clearAll } = useBehaviorStore();

  return (
    <aside className="w-72 shrink-0">
      <div className="card-base p-5 sticky top-20">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-slate-700 flex items-center gap-2">
            <span className="w-1 h-4 bg-gradient-to-b from-amber-400 to-amber-500 rounded-full" />
            浏览历史
          </h3>
          {records.length > 0 && (
            <button
              onClick={clearAll}
              className="text-xs text-slate-400 hover:text-red-500 transition-colors duration-150"
            >
              清空
            </button>
          )}
        </div>

        {records.length === 0 ? (
          <div className="text-center py-10">
            <div className="w-12 h-12 mx-auto mb-3 rounded-full bg-slate-100 flex items-center justify-center">
              <span className="text-xl opacity-40">📋</span>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              点击商品卡片的
              <br />
              <span className="font-medium text-slate-500">
                「加入浏览历史」
              </span>
              <br />
              即可触发个性化推荐
            </p>
          </div>
        ) : (
          <ul className="space-y-1.5 max-h-[60vh] overflow-y-auto pr-1">
            {records.map((r) => (
              <HistoryChip
                key={r.asin}
                record={r}
                onRemove={() => removeRecord(r.asin)}
              />
            ))}
          </ul>
        )}

        {/* Footer */}
        <div className="mt-4 pt-3 border-t border-slate-100">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400">
              {records.length}/50 条记录
            </span>
            <div className="w-16 h-1 bg-slate-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-brand-400 to-brand-500 rounded-full transition-all duration-300"
                style={{ width: `${(records.length / 50) * 100}%` }}
              />
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}
