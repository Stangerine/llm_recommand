import apiClient from "./client";
import type { RecommendRequest, RecommendResponse } from "@/types/product";

export async function fetchRecommendations(
  req: RecommendRequest
): Promise<RecommendResponse> {
  const { data } = await apiClient.post<RecommendResponse>("/recommend", req);
  return data;
}

export async function reportBehavior(
  userId: string,
  asin: string,
  action: string
): Promise<void> {
  await apiClient.post("/behavior", {
    user_id: userId,
    asin,
    action_type: action,
  });
}
