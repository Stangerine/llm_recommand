/**
 * 格式化价格
 */
export function formatPrice(price: number | null | undefined): string {
  if (price == null || price <= 0) return "";
  return `$${price.toFixed(2)}`;
}

/**
 * 格式化评分
 */
export function formatRating(rating: number | null | undefined): string {
  if (rating == null) return "";
  return rating.toFixed(1);
}

/**
 * 格式化评分数量
 */
export function formatRatingCount(count: number | null | undefined): string {
  if (count == null) return "";
  if (count >= 10000) {
    return `${(count / 10000).toFixed(1)}万`;
  }
  if (count >= 1000) {
    return `${(count / 1000).toFixed(1)}k`;
  }
  return count.toLocaleString();
}

/**
 * 格式化分类路径（取最后一级）
 */
export function formatCategory(category: string | null | undefined): string {
  if (!category) return "";
  const parts = category.split(" > ");
  return parts[parts.length - 1] || category;
}

/**
 * 格式化时间戳
 */
export function formatTimestamp(timestamp: number): string {
  const date = new Date(timestamp);
  const now = new Date();
  const diff = now.getTime() - date.getTime();

  if (diff < 60000) return "刚刚";
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`;

  return date.toLocaleDateString("zh-CN", {
    month: "numeric",
    day: "numeric",
    hour: "numeric",
    minute: "numeric",
  });
}

/**
 * 截断文本
 */
export function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength) + "...";
}
