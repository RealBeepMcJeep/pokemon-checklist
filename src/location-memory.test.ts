import { beforeEach, describe, expect, it, vi } from "vitest";
import { locationMemoryKey, readLastLocation, writeLastLocation } from "./location-memory";
import { LEGACY_STORAGE_KEYS, STORAGE_KEY } from "./domain";

let data: Map<string, string>;
beforeEach(() => {
  data = new Map();
  vi.stubGlobal("localStorage", {
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => { data.set(key, value); },
  });
});
describe("device-local last-area preference", () => {
  it.each(["", ":account-a"])("migrates only the matching legacy namespace and mode (%s)", suffix => {
    const previous = `${LEGACY_STORAGE_KEYS[0]}${suffix}`;
    const current = `${STORAGE_KEY}${suffix}`;
    data.set(locationMemoryKey("sun", previous), "route-b");
    data.set(locationMemoryKey("moon", previous), "route-other-mode");
    data.set(locationMemoryKey("sun", `${LEGACY_STORAGE_KEYS[0]}:other-account`), "route-other-account");
    data.set(previous, "unchanged player save");
    expect(readLastLocation("sun", current, ["route-b", "route-other-mode", "route-other-account"])).toBe("route-b");
    expect(data.get(locationMemoryKey("sun", current))).toBe("route-b");
    expect(data.get(locationMemoryKey("sun", previous))).toBe("route-b");
    expect(data.get(previous)).toBe("unchanged player save");
    expect(data.has(locationMemoryKey("moon", current))).toBe(false);
  });
  it("never replaces a present current preference with older memory", () => {
    const previous = locationMemoryKey("sun", LEGACY_STORAGE_KEYS[0]);
    const current = locationMemoryKey("sun", STORAGE_KEY);
    data.set(previous, "route-old");
    data.set(current, "route-new");
    expect(readLastLocation("sun", STORAGE_KEY, ["route-old", "route-new"])).toBe("route-new");
    data.set(current, "removed-current-route");
    expect(readLastLocation("sun", STORAGE_KEY, ["route-old", "route-new"])).toBeNull();
    expect(data.get(current)).toBe("removed-current-route");
  });
  it("does not borrow another account or mode when legacy memory is missing", () => {
    data.set(locationMemoryKey("sun", LEGACY_STORAGE_KEYS[0]), "offline-only");
    data.set(locationMemoryKey("moon", `${LEGACY_STORAGE_KEYS[0]}:account-a`), "moon-only");
    expect(readLastLocation("sun", `${STORAGE_KEY}:account-a`, ["offline-only", "moon-only"])).toBeNull();
    expect(readLastLocation("sun", "unrelated-namespace", ["offline-only"])).toBeNull();
  });
  it("uses readable legacy memory even if its optional copy cannot persist", () => {
    data.set(locationMemoryKey("sun", LEGACY_STORAGE_KEYS[0]), "route-old");
    vi.stubGlobal("localStorage", { getItem: (key: string) => data.get(key) ?? null, setItem: () => { throw Error("quota"); } });
    expect(readLastLocation("sun", STORAGE_KEY, ["route-old"])).toBe("route-old");
    expect(data.has(locationMemoryKey("sun", STORAGE_KEY))).toBe(false);
  });
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
