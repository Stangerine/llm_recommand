export interface Product {
  asin: string;
  title: string;
  description?: string;
  category?: string;
  brand?: string;
  price?: number;
  rating?: number;
  rating_count?: number;
}

export interface RecommendRequest {
  user_id: string;
  history_asins: string[];
  top_k?: number;
}

export interface RecommendResponse {
  user_id: string;
  recommendations: Product[];
  total: number;
  model_version: string;
}

export interface SearchResponse {
  results: Product[];
  total: number;
}

export type BehaviorAction = "view" | "click" | "purchase";

export interface BehaviorRecord {
  asin: string;
  title: string;
  action: BehaviorAction;
  timestamp: number;
}
