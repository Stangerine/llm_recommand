import { describe, it, expect, beforeEach } from "vitest";
import { useBehaviorStore } from "./behaviorStore";

describe("behaviorStore", () => {
  beforeEach(() => {
    useBehaviorStore.setState({ records: [] });
  });

  it("starts with empty records", () => {
    const { records } = useBehaviorStore.getState();
    expect(records).toEqual([]);
  });

  it("adds a record", () => {
    const { addRecord } = useBehaviorStore.getState();
    addRecord({
      asin: "B001",
      title: "Test Product",
      action: "view",
      timestamp: Date.now(),
    });

    const { records } = useBehaviorStore.getState();
    expect(records).toHaveLength(1);
    expect(records[0].asin).toBe("B001");
  });

  it("deduplicates records by asin", () => {
    const { addRecord } = useBehaviorStore.getState();
    const now = Date.now();

    addRecord({ asin: "B001", title: "Product 1", action: "view", timestamp: now });
    addRecord({ asin: "B001", title: "Product 1 Updated", action: "click", timestamp: now + 1000 });

    const { records } = useBehaviorStore.getState();
    expect(records).toHaveLength(1);
    expect(records[0].action).toBe("click");
  });

  it("limits records to 50", () => {
    const { addRecord } = useBehaviorStore.getState();

    for (let i = 0; i < 60; i++) {
      addRecord({
        asin: `B${i.toString().padStart(3, "0")}`,
        title: `Product ${i}`,
        action: "view",
        timestamp: Date.now() + i,
      });
    }

    const { records } = useBehaviorStore.getState();
    expect(records).toHaveLength(50);
  });

  it("removes a record", () => {
    const { addRecord, removeRecord } = useBehaviorStore.getState();

    addRecord({ asin: "B001", title: "Product 1", action: "view", timestamp: Date.now() });
    addRecord({ asin: "B002", title: "Product 2", action: "view", timestamp: Date.now() });
    removeRecord("B001");

    const { records } = useBehaviorStore.getState();
    expect(records).toHaveLength(1);
    expect(records[0].asin).toBe("B002");
  });

  it("clears all records", () => {
    const { addRecord, clearAll } = useBehaviorStore.getState();

    addRecord({ asin: "B001", title: "Product 1", action: "view", timestamp: Date.now() });
    addRecord({ asin: "B002", title: "Product 2", action: "view", timestamp: Date.now() });
    clearAll();

    const { records } = useBehaviorStore.getState();
    expect(records).toHaveLength(0);
  });

  it("returns history asins sorted by timestamp", () => {
    const { addRecord, historyAsins } = useBehaviorStore.getState();

    addRecord({ asin: "B002", title: "Product 2", action: "view", timestamp: 2000 });
    addRecord({ asin: "B001", title: "Product 1", action: "view", timestamp: 1000 });
    addRecord({ asin: "B003", title: "Product 3", action: "view", timestamp: 3000 });

    const asins = historyAsins();
    expect(asins).toEqual(["B001", "B002", "B003"]);
  });
});
