import { useState } from "react";
import { useBehaviorStore } from "@/store/behaviorStore";
import { useNavigate } from "react-router-dom";

const PRESET_SEQUENCES = [
  {
    label: "电子元器件",
    description: "电阻、电容、芯片等电子元件",
    asins: ["0176496920", "0692782109", "0781776848"],
    color: "from-blue-500 to-cyan-500",
  },
  {
    label: "工业工具",
    description: "扳手、测量仪、电动工具",
    asins: ["0840026080", "0894558358", "0971007004"],
    color: "from-amber-500 to-orange-500",
  },
  {
    label: "测试设备",
    description: "万用表、示波器、信号发生器",
    asins: ["1587790319", "1587792052", "1587791420"],
    color: "from-emerald-500 to-teal-500",
  },
];

export function SimulatorPage() {
  const [input, setInput] = useState("");
  const addRecord = useBehaviorStore((s) => s.addRecord);
  const navigate = useNavigate();

  const applyPreset = (asins: string[]) => {
    asins.forEach((asin, i) =>
      addRecord({
        asin,
        title: `模拟商品 ${asin}`,
        action: "view",
        timestamp: Date.now() - (asins.length - i) * 1000,
      })
    );
    navigate("/");
  };

  const applyManual = () => {
    const asins = input.split(/[\n,\s]+/).filter(Boolean);
    asins.forEach((asin) =>
      addRecord({
        asin,
        title: `手动输入 ${asin}`,
        action: "view",
        timestamp: Date.now(),
      })
    );
    navigate("/");
  };

  return (
    <div className="max-w-xl mx-auto px-6 py-10">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-800 mb-2">行为模拟器</h1>
        <p className="text-sm text-slate-500">
          模拟用户浏览行为，测试推荐效果
        </p>
      </div>

      {/* Preset scenarios */}
      <div className="mb-10">
        <h2 className="text-sm font-semibold text-slate-600 mb-4 flex items-center gap-2">
          <span className="w-1 h-4 bg-gradient-to-b from-brand-400 to-brand-600 rounded-full" />
          快速预置场景
        </h2>
        <div className="space-y-3">
          {PRESET_SEQUENCES.map((p) => (
            <button
              key={p.label}
              onClick={() => applyPreset(p.asins)}
              className="w-full text-left card-base p-4 hover:border-brand-200 hover:shadow-card-hover hover:-translate-y-0.5 transition-all duration-200 group"
            >
              <div className="flex items-center gap-3">
                <div
                  className={`w-10 h-10 rounded-lg bg-gradient-to-br ${p.color} flex items-center justify-center shadow-sm`}
                >
                  <span className="text-white text-sm font-bold">
                    {p.asins.length}
                  </span>
                </div>
                <div>
                  <p className="text-sm font-medium text-slate-700 group-hover:text-brand-700 transition-colors">
                    {p.label}
                  </p>
                  <p className="text-xs text-slate-400 mt-0.5">
                    {p.description}
                  </p>
                </div>
                <svg
                  className="w-4 h-4 text-slate-300 group-hover:text-brand-400 ml-auto transition-colors"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M9 5l7 7-7 7"
                  />
                </svg>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Manual input */}
      <div>
        <h2 className="text-sm font-semibold text-slate-600 mb-4 flex items-center gap-2">
          <span className="w-1 h-4 bg-gradient-to-b from-slate-400 to-slate-500 rounded-full" />
          手动输入 ASIN
        </h2>
        <div className="card-base p-5 space-y-4">
          <p className="text-xs text-slate-400">
            换行或逗号分隔多个 ASIN
          </p>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            rows={4}
            className="input-base font-mono text-xs resize-none"
            placeholder={"0176496920\n0692782109\n0781776848"}
          />
          <button
            onClick={applyManual}
            disabled={!input.trim()}
            className="btn-primary w-full disabled:opacity-40 disabled:cursor-not-allowed"
          >
            注入历史并查看推荐
          </button>
        </div>
      </div>
    </div>
  );
}
