import apiClient from "./client";
import type { Product, SearchResponse } from "@/types/product";

export async function fetchProductDetail(asin: string): Promise<Product> {
  const { data } = await apiClient.get<Product>(`/products/${asin}`);
  return data;
}

export async function searchProducts(
  query: string,
  category?: string,
  size = 20
): Promise<SearchResponse> {
  const { data } = await apiClient.get<SearchResponse>("/products/search", {
    params: { q: query, category, size },
  });
  return data;
}
