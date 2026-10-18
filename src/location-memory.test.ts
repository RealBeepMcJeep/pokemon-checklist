import { beforeEach, describe, expect, it, vi } from "vitest";
import { locationMemoryKey, readLastLocation, writeLastLocation } from "./location-memory";

let data: Map<string, string>;
beforeEach(() => {
  data = new Map();
  vi.stubGlobal("localStorage", {
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => { data.set(key, value); },
  });
});
describe("device-local last-area preference", () => {
  it("keeps each mode and account separate without touching player save bytes", () => {
    data.set("pokemon-checklist-state-v4", "unchanged player save");
    writeLastLocation("sun", "offline", "route-a");
    writeLastLocation("moon", "offline", "route-b");
    writeLastLocation("sun", "account-b", "route-c");
    expect(readLastLocation("sun", "offline", ["route-a", "route-b"])).toBe("route-a");
    expect(readLastLocation("moon", "offline", ["route-a", "route-b"])).toBe("route-b");
    expect(readLastLocation("sun", "account-b", ["route-c"])).toBe("route-c");
    expect(data.get("pokemon-checklist-state-v4")).toBe("unchanged player save");
  });
  it("ignores missing, corrupt, or removed area IDs", () => {
    expect(readLastLocation("sun", "offline", ["route-a"])).toBeNull();
    for (const corrupt of ["{broken", "null", "removed-route", "<script>"]) {
      data.set(locationMemoryKey("sun", "offline"), corrupt);
      expect(readLastLocation("sun", "offline", ["route-a"])).toBeNull();
    }
  });
  it("reports blocked storage without throwing", () => {
    vi.stubGlobal("localStorage", { getItem: () => { throw Error("blocked"); }, setItem: () => { throw Error("quota"); } });
    expect(readLastLocation("sun", "offline", ["route-a"])).toBeNull();
    expect(writeLastLocation("sun", "offline", "route-a")).toBe(false);
  });
});
