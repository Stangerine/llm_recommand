import { useQuery } from "@tanstack/react-query";
import { searchProducts } from "@/api/products";

export function useProductSearch(query: string, category?: string) {
  return useQuery({
    queryKey: ["search", query, category],
    queryFn: () => searchProducts(query, category),
    enabled: query.trim().length >= 2,
    staleTime: 30_000,
  });
}
