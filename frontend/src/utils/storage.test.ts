import { describe, it, expect, beforeEach, vi } from "vitest";
import { getStorage, setStorage, removeStorage, clearStorage, getUserId } from "./storage";

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] || null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value;
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      store = {};
    }),
    get length() {
      return Object.keys(store).length;
    },
    key: vi.fn((index: number) => Object.keys(store)[index] || null),
  };
})();

Object.defineProperty(window, "localStorage", { value: localStorageMock });

describe("storage utils", () => {
  beforeEach(() => {
    localStorageMock.clear();
    vi.clearAllMocks();
  });

  describe("getStorage", () => {
    it("returns default value when key not found", () => {
      const result = getStorage("nonexistent", "default");
      expect(result).toBe("default");
    });

    it("returns stored value", () => {
      localStorageMock.setItem("rec_test", JSON.stringify({ value: "stored" }));
      const result = getStorage("test", "default");
      expect(result).toBe("stored");
    });

    it("returns default when expired", () => {
      const expiredItem = {
        value: "expired",
        expiry: Date.now() - 1000,
      };
      localStorageMock.setItem("rec_expired", JSON.stringify(expiredItem));
      const result = getStorage("expired", "default");
      expect(result).toBe("default");
    });
  });

  describe("setStorage", () => {
    it("stores value", () => {
      setStorage("key", "value");
      expect(localStorageMock.setItem).toHaveBeenCalledWith(
        "rec_key",
        expect.any(String)
      );
    });

    it("stores value with expiry", () => {
      setStorage("key", "value", 60000);
      expect(localStorageMock.setItem).toHaveBeenCalled();
    });
  });

  describe("removeStorage", () => {
    it("removes stored item", () => {
      removeStorage("key");
      expect(localStorageMock.removeItem).toHaveBeenCalledWith("rec_key");
    });
  });

  describe("clearStorage", () => {
    it("removes all rec_ prefixed items", () => {
      localStorageMock.setItem("rec_key1", "value1");
      localStorageMock.setItem("rec_key2", "value2");
      localStorageMock.setItem("other_key", "value3");

      clearStorage();
      expect(localStorageMock.removeItem).toHaveBeenCalledWith("rec_key1");
      expect(localStorageMock.removeItem).toHaveBeenCalledWith("rec_key2");
    });
  });

  describe("getUserId", () => {
    it("returns stored user id", () => {
      localStorageMock.setItem("rec_user_id", JSON.stringify({ value: "user_123" }));
      const result = getUserId();
      expect(result).toBe("user_123");
    });

    it("creates new user id when not stored", () => {
      const result = getUserId();
      expect(result).toMatch(/^user_[a-z0-9]+$/);
    });
  });
});
