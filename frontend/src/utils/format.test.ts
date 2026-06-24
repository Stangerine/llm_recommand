import { describe, it, expect } from "vitest";
import {
  formatPrice,
  formatRating,
  formatRatingCount,
  formatCategory,
  truncateText,
} from "./format";

describe("format utils", () => {
  describe("formatPrice", () => {
    it("formats price with dollar sign", () => {
      expect(formatPrice(29.99)).toBe("$29.99");
    });

    it("returns empty for null", () => {
      expect(formatPrice(null)).toBe("");
    });

    it("returns empty for zero", () => {
      expect(formatPrice(0)).toBe("");
    });

    it("returns empty for negative", () => {
      expect(formatPrice(-5)).toBe("");
    });
  });

  describe("formatRating", () => {
    it("formats rating to one decimal", () => {
      expect(formatRating(4.567)).toBe("4.6");
    });

    it("returns empty for null", () => {
      expect(formatRating(null)).toBe("");
    });
  });

  describe("formatRatingCount", () => {
    it("formats thousands with k suffix", () => {
      expect(formatRatingCount(1500)).toBe("1.5k");
    });

    it("formats ten thousands with 万 suffix", () => {
      expect(formatRatingCount(25000)).toBe("2.5万");
    });

    it("formats small numbers with locale", () => {
      expect(formatRatingCount(512)).toBe("512");
    });

    it("returns empty for null", () => {
      expect(formatRatingCount(null)).toBe("");
    });
  });

  describe("formatCategory", () => {
    it("returns last part of category path", () => {
      expect(formatCategory("Industrial & Scientific > Safety > Gloves")).toBe("Gloves");
    });

    it("returns full string if no separator", () => {
      expect(formatCategory("Safety")).toBe("Safety");
    });

    it("returns empty for null", () => {
      expect(formatCategory(null)).toBe("");
    });
  });

  describe("truncateText", () => {
    it("truncates long text", () => {
      expect(truncateText("Hello World", 5)).toBe("Hello...");
    });

    it("returns original text if short enough", () => {
      expect(truncateText("Hi", 5)).toBe("Hi");
    });
  });
});
