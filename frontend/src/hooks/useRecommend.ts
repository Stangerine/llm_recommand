import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchRecommendations, reportBehavior } from "@/api/recommend";
import { useBehaviorStore } from "@/store/behaviorStore";
import { useUserStore } from "@/store/userStore";

export function useRecommend() {
  const queryClient = useQueryClient();
  const userId = useUserStore((s) => s.userId);
  const history = useBehaviorStore((s) => s.historyAsins());

  const query = useQuery({
    queryKey: ["recommend", userId, history],
    queryFn: () =>
      fetchRecommendations({
        user_id: userId,
        history_asins: history,
        top_k: 10,
      }),
    enabled: history.length > 0,
    staleTime: 1000 * 60 * 5, // 5 分钟内不重新请求
    retry: 1,
  });

  const refresh = () =>
    queryClient.invalidateQueries({ queryKey: ["recommend", userId] });

  return { ...query, refresh };
}

export function useBehaviorReport() {
  const userId = useUserStore((s) => s.userId);
  return useMutation({
    mutationFn: ({ asin, action }: { asin: string; action: string }) =>
      reportBehavior(userId, asin, action),
  });
}
