import type { BehaviorRecord } from "@/types/product";

interface Props {
  record: BehaviorRecord;
  onRemove: () => void;
}

const actionConfig = {
  view: { label: "浏览", color: "bg-blue-50 text-blue-600" },
  click: { label: "点击", color: "bg-emerald-50 text-emerald-600" },
  purchase: { label: "购买", color: "bg-amber-50 text-amber-600" },
};

export function HistoryChip({ record, onRemove }: Props) {
  const action = actionConfig[record.action];

  return (
    <li className="group flex items-center justify-between gap-2 p-2.5 rounded-lg hover:bg-slate-50 transition-colors duration-150">
      <div className="flex-1 min-w-0">
        <p className="text-xs font-medium text-slate-700 truncate leading-relaxed">
          {record.title}
        </p>
        <div className="flex items-center gap-2 mt-1">
          <span
            className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium ${action.color}`}
          >
            {action.label}
          </span>
          <span className="text-[10px] text-slate-400">
            {new Date(record.timestamp).toLocaleTimeString()}
          </span>
        </div>
      </div>
      <button
        onClick={onRemove}
        className="shrink-0 w-6 h-6 flex items-center justify-center rounded text-slate-300 hover:text-red-500 hover:bg-red-50 transition-all duration-150 opacity-0 group-hover:opacity-100"
      >
        ✕
      </button>
    </li>
  );
}
