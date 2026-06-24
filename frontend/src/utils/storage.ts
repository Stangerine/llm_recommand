/**
 * localStorage 封装，带类型安全和过期支持
 */

const PREFIX = "rec_";

interface StorageItem<T> {
  value: T;
  expiry?: number;
}

/**
 * 获取存储项
 */
export function getStorage<T>(key: string, defaultValue: T): T {
  try {
    const item = localStorage.getItem(PREFIX + key);
    if (!item) return defaultValue;

    const parsed: StorageItem<T> = JSON.parse(item);

    // 检查是否过期
    if (parsed.expiry && Date.now() > parsed.expiry) {
      localStorage.removeItem(PREFIX + key);
      return defaultValue;
    }

    return parsed.value;
  } catch {
    return defaultValue;
  }
}

/**
 * 设置存储项
 */
export function setStorage<T>(
  key: string,
  value: T,
  ttlMs?: number
): void {
  try {
    const item: StorageItem<T> = {
      value,
      expiry: ttlMs ? Date.now() + ttlMs : undefined,
    };
    localStorage.setItem(PREFIX + key, JSON.stringify(item));
  } catch (error) {
    console.error("Failed to save to localStorage:", error);
  }
}

/**
 * 移除存储项
 */
export function removeStorage(key: string): void {
  localStorage.removeItem(PREFIX + key);
}

/**
 * 清除所有带前缀的存储项
 */
export function clearStorage(): void {
  const keys = Object.keys(localStorage);
  keys.forEach((key) => {
    if (key.startsWith(PREFIX)) {
      localStorage.removeItem(key);
    }
  });
}

/**
 * 获取用户 ID（持久化）
 */
export function getUserId(): string {
  const stored = getStorage<string | null>("user_id", null);
  if (stored) return stored;

  const newId = `user_${Math.random().toString(36).slice(2, 9)}`;
  setStorage("user_id", newId);
  return newId;
}
