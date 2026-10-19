import { expect, it } from "vitest";
import { resolveFormEdit, isCurrentFormEdit, type FormEditContext, type FormEditRequest } from "./form-edit";
const context = (): FormEditContext => ({ namespace: "synthetic-offline", generation: 0, mode: "photonic-prismatic", tracking: true,
  readOnly: false, id: 52, species: "caught", statuses: { alolan: "caught", kanto: "caught" }, favorites: { alolan: false, kanto: false }, legacyFavorite: false });
const request = (): FormEditRequest => ({ before: context(), action: { kind: "status", next: "seen" } });
it("resolves an explicitly identified form directly", () => {
  expect(resolveFormEdit({ ...request(), explicit: "kanto" })).toEqual({ kind: "apply", form: "kanto" });
});
it("asks for an unspecified incoming catch with tracking on even with a sole owned form", () => {
  const before = context(); before.statuses.kanto = "none";
  expect(resolveFormEdit({ before, action: { kind: "status", next: "caught" } })).toEqual({ kind: "choose", forms: ["alolan", "kanto"] });
});
it("defaults an unspecified incoming catch to Alolan only with tracking off", () => {
  const before = context(); before.tracking = false;
  expect(resolveFormEdit({ before, action: { kind: "status", next: "caught" } })).toEqual({ kind: "apply", form: "alolan" });
});
it("infers a sole owned outgoing form without choosing the Alolan artwork default", () => {
  const before = context(); before.statuses.alolan = "seen";
  expect(resolveFormEdit({ before, action: { kind: "status", next: "seen" } })).toEqual({ kind: "apply", form: "kanto" });
});
it("leaves unidentified outgoing legacy ownership unresolved", () => {
  const before = context(); before.statuses = { alolan: "seen", kanto: "none" };
  expect(resolveFormEdit({ before, action: { kind: "status", next: "seen" } })).toEqual({ kind: "unresolved" });
});
it("uses favorite candidates independently of currently owned candidates", () => {
  const before = context(); before.statuses.kanto = "none"; before.favorites.kanto = true;
  expect(resolveFormEdit({ before, action: { kind: "favorite", next: false } })).toEqual({ kind: "apply", form: "kanto" });
});
it("does not mutate a request while resolving it", () => {
  const value = request(), before = structuredClone(value); resolveFormEdit(value); expect(value).toEqual(before);
});
for (const field of ["namespace", "generation", "mode", "tracking", "readOnly", "species", "statuses", "favorites", "legacyFavorite"] as const)
  it(`rejects changed ${field} before confirmation`, () => {
    const value = request(); const now = context();
    const changes = { namespace: "another", generation: 1, mode: "sun", tracking: false, readOnly: true,
      species: "seen", statuses: { alolan: "caught", kanto: "seen" }, favorites: { alolan: false, kanto: true }, legacyFavorite: true };
    Object.assign(now, { [field]: changes[field] });
    expect(isCurrentFormEdit(value, now)).toBe(false);
  });
it("accepts an unchanged context", () => { expect(isCurrentFormEdit(request(), context())).toBe(true); });
