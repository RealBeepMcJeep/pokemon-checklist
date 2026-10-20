import { beforeEach, describe, expect, it } from "vitest";
import { LEGACY_STORAGE_KEYS, STORAGE_KEY, validateState } from "./domain";
import { exportState, formFavoritesFromLegacy, reloadSave, resetState, setSyncAccount, storageAvailable, validForms, validPokemon } from "./state";

let store: Map<string, string>;
const legacy = JSON.stringify({ schemaVersion: 4, species: { "52": "caught", "25": "seen" }, forms: { "52:alolan": "caught", "52:kanto": "caught" }, starred: [52, 25], settings: { forms: true, mode: "moon", unlocks: ["sos"] } });
const oldKey = `${LEGACY_STORAGE_KEYS[0]}:fixture-a`;
const key = `${STORAGE_KEY}:fixture-a`;

beforeEach(() => {
  store = new Map();
  globalThis.localStorage = {
    getItem: name => store.get(name) ?? null,
    setItem: (name, value) => { store.set(name, value); },
    removeItem: name => { store.delete(name); },
  } as Storage;
  setSyncAccount(null);
  formFavoritesFromLegacy.value = false;
  resetState();
});

describe("legacy favorite source-capability persistence", () => {
  it("keeps capability account-local and outside the strict exported player schema", () => {
    store.set(oldKey, legacy);
    setSyncAccount("fixture-a");
    expect(formFavoritesFromLegacy.value).toBe(true);
    expect(store.get(`${key}:legacy-form-favorites`)).toBe("1");
    const exported = exportState();
    expect(validateState(exported, validPokemon, validForms)).toEqual(exported);
    expect(Object.keys(exported).sort()).toEqual(["forms", "schemaVersion", "settings", "species", "starred", "starredForms"]);
    setSyncAccount("fixture-b", { adopt: false });
    expect(formFavoritesFromLegacy.value).toBe(false);
    expect(store.has(`${STORAGE_KEY}:fixture-b:legacy-form-favorites`)).toBe(false);
    setSyncAccount(null);
    expect(formFavoritesFromLegacy.value).toBe(false);
    setSyncAccount("fixture-a");
    expect(formFavoritesFromLegacy.value).toBe(true);
    expect(exportState()).toEqual(exported);
    expect(store.get(oldKey)).toBe(legacy);
  });

  it("retains capability and the full state when recovering a corrupt current primary", () => {
    store.set(oldKey, legacy);
    setSyncAccount("fixture-a");
    const before = exportState();
    store.set(key, "{broken");
    reloadSave();
    expect(formFavoritesFromLegacy.value).toBe(true);
    expect(exportState()).toEqual(before);
    expect(store.get(`${key}:unreadable`)).toBe("{broken");
    expect(store.get(oldKey)).toBe(legacy);
  });

  it("does not write a v5 image when source-capability persistence fails", () => {
    store.set(oldKey, legacy);
    const setItem = localStorage.setItem;
    localStorage.setItem = (name, value) => {
      if (name.endsWith(":legacy-form-favorites")) throw new Error("quota");
      setItem(name, value);
    };
    setSyncAccount("fixture-a");
    expect(storageAvailable.value).toBe(false);
    expect(store.has(key)).toBe(false);
    expect(store.get(oldKey)).toBe(legacy);
    expect(exportState()).toMatchObject({ schemaVersion: 5, species: { "25": "seen", "52": "caught" }, starred: [25, 52], starredForms: [] });
  });
});
