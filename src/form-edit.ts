import type { RegionalForm } from "./regional";
import type { Status } from "./types";

export const REGIONS: readonly RegionalForm[] = ["alolan", "kanto"];
export interface FormEditContext {
  namespace: string;
  generation: number;
  mode: string;
  tracking: boolean;
  readOnly: boolean;
  id: number;
  species: Status;
  statuses: Record<RegionalForm, Status>;
  favorites: Record<RegionalForm, boolean>;
  legacyFavorite: boolean;
}
export type FormEditAction = { kind: "status"; next: Status } | { kind: "favorite"; next: boolean };
export interface FormEditRequest { before: FormEditContext; action: FormEditAction; explicit?: RegionalForm }
export type FormEditDecision = { kind: "apply"; form: RegionalForm } | { kind: "choose"; forms: readonly RegionalForm[] } | { kind: "unresolved" };

/** Decide identity only; never read globals or mutate player records. */
export function resolveFormEdit(request: FormEditRequest): FormEditDecision {
  if (request.explicit) return { kind: "apply", form: request.explicit };
  const { before, action } = request;
  if (action.kind === "favorite") {
    const favorites = REGIONS.filter(form => before.favorites[form]);
    const owned = REGIONS.filter(form => before.statuses[form] === "caught");
    const candidates = action.next ? owned : favorites.length ? favorites : before.legacyFavorite ? owned : [];
    return candidates.length === 1 ? { kind: "apply", form: candidates[0] }
      : { kind: "choose", forms: candidates.length ? candidates : REGIONS };
  }
  if (action.next === "caught") return before.tracking
    ? { kind: "choose", forms: REGIONS } : { kind: "apply", form: "alolan" };
  const candidates = REGIONS.filter(form => before.statuses[form] === before.species && before.species !== "none");
  return candidates.length === 1 ? { kind: "apply", form: candidates[0] }
    : candidates.length ? { kind: "choose", forms: candidates } : { kind: "unresolved" };
}

/** Guard only this species and its action context, not unrelated collection edits. */
export function isCurrentFormEdit(request: FormEditRequest, now: FormEditContext): boolean {
  const before = request.before;
  return !now.readOnly && before.generation === now.generation && before.namespace === now.namespace && before.mode === now.mode
    && before.tracking === now.tracking && before.id === now.id && before.species === now.species
    && before.legacyFavorite === now.legacyFavorite && REGIONS.every(form =>
      before.statuses[form] === now.statuses[form] && before.favorites[form] === now.favorites[form]);
}
