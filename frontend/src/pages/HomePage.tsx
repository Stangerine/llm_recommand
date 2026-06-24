import { RecommendFeed } from "@/components/recommendation/RecommendFeed";
import { BehaviorPanel } from "@/components/recommendation/BehaviorPanel";

export function HomePage() {
  return (
    <div className="min-h-screen bg-slate-50">
      <div className="max-w-screen-xl mx-auto px-6 py-8 flex gap-6">
        <main className="flex-1 min-w-0">
          <RecommendFeed />
        </main>
        <BehaviorPanel />
      </div>
    </div>
  );
}
