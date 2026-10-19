import { beforeEach, afterEach, expect, it, vi } from "vitest";
vi.stubGlobal("window", { matchMedia: () => ({ matches: false, addEventListener() {} }), addEventListener() {} });
const ui = await import("./ui");
const state = await import("./state");
beforeEach(() => {
  const values = new Map<string, string>();
  vi.stubGlobal("localStorage", { getItem: (k: string) => values.get(k) ?? null,
    setItem: (k: string, v: string) => { values.set(k, v); }, removeItem: (k: string) => { values.delete(k); } });
  state.readOnly.value = null;
  state.setSyncAccount(null);
  state.applyState({ ...state.defaultState(), species: { "52": "caught" }, forms: { "52:alolan": "caught", "52:kanto": "caught" } });
  ui.cancelFormEdit();
});
afterEach(() => { ui.cancelFormEdit(); state.setSyncAccount(null); });

it("preserves unrelated edits when confirming one form", () => {
  ui.changeSpecies(52); const request = ui.pendingFormEdit.value!;
  state.cycleSpecies(25);
  ui.applyFormEdit(request, "kanto");
  expect(state.exportState()).toMatchObject({ species: { "25": "caught", "52": "caught" }, forms: { "52:alolan": "caught", "52:kanto": "seen" } });
});
it("does not apply a captured confirmation after Cancel", () => {
  ui.changeSpecies(52);
  const request = ui.pendingFormEdit.value!;
  expect(request).not.toBeNull();
  const before = state.exportState();
  ui.cancelFormEdit();
  ui.applyFormEdit(request, "kanto");
  expect(state.exportState()).toEqual(before);
});
it("invalidates a pending action across an account round trip", () => {
  ui.changeSpecies(52);
  const request = ui.pendingFormEdit.value!;
  state.setSyncAccount("synthetic-form-choice-account");
  state.setSyncAccount(null);
  const before = state.exportState();
  ui.applyFormEdit(request, "kanto");
  expect(state.exportState()).toEqual(before);
});
it("invalidates a pending action after an equal-valued whole-save restore", () => {
  ui.changeSpecies(52);
  const request = ui.pendingFormEdit.value!;
  state.restoreState(state.exportState());
  const before = state.exportState();
  ui.applyFormEdit(request, "kanto");
  expect(state.exportState()).toEqual(before);
});
