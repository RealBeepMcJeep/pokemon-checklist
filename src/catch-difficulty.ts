import capture from "../data/capture.json";
import { isRegional, encounterRegionalForm } from "./regional";
import { encounterViewContext } from "./encounter-names";
import { formSlug } from "./domain";

/** App-specific intrinsic tiers, never a battle probability or encounter rarity. */
export type CatchTier = "F" | "D" | "C" | "B" | "A" | "S";
export const CATCH_SCALE: readonly { tier: CatchTier; min: number; max: number }[] = [
  { tier: "F", min: 200, max: 255 },
  { tier: "D", min: 120, max: 199 },
  { tier: "C", min: 75, max: 119 },
  { tier: "B", min: 45, max: 74 },
  { tier: "A", min: 16, max: 44 },
  { tier: "S", min: 1, max: 15 },
];
export interface CatchDifficulty {
  profile: "sm" | "usum" | null;
  sourceForm: number | null;
  sourceName?: string;
  rate: number | null;
  tier: CatchTier | null;
  reason: "unknown-profile" | "unknown-species" | "unsupported-form" | "missing-profile" | "invalid-rate" | "zero-rate" | null;
  stockFallback: boolean;
}
const records = new Map(capture.pokemon.map(row => [`${row.id}:${row.form}`, row]));

/** Exact native indices or source-labeled form slugs only; never a carousel filter. */
export function resolveCatchDifficulty(id: number, mode: string, form?: string | number): CatchDifficulty {
  const profile = mode === "sun" || mode === "moon" ? "sm"
    : mode === "ultra-sun" || mode === "ultra-moon" || mode === "photonic-prismatic" ? "usum" : null;
  const result: CatchDifficulty = { profile, sourceForm: null, rate: null, tier: null, reason: null, stockFallback: mode === "photonic-prismatic" };
  if (!profile) return { ...result, reason: "unknown-profile" };
  if (!Number.isInteger(id) || !records.has(`${id}:0`)) return { ...result, reason: "unknown-species" };
  let index: number | undefined;
  if (form === undefined) index = isRegional(id) ? 1 : 0;
  else if (form === "base" || (form === "kanto" && isRegional(id))) index = 0;
  else if (form === "alolan" && isRegional(id)) index = 1;
  else if (typeof form === "number" && Number.isInteger(form) && form >= 0) index = form;
  else if (typeof form === "string") {
    // The generator labels these identities explicitly; generic "Form N" labels
    // are NOT a semantic crosswalk for guessed encounter names or pooled forms.
    index = capture.pokemon.find(row => {
      const label = row.name.split(" — ")[1];
      return row.id === id && label && !/^Form \d+$/.test(label) && formSlug(label) === form;
    })?.form;
  }
  const row = index === undefined ? undefined : records.get(`${id}:${index}`);
  if (!row) return { ...result, reason: "unsupported-form" };
  result.sourceForm = row.form;
  result.sourceName = row.name;
  const native = row[profile];
  if (!native) return { ...result, reason: "missing-profile" };
  const tier = catchTier(native.catchRate);
  return { ...result, rate: tier || native.catchRate === 0 ? native.catchRate : null, tier, reason: tier ? null : native.catchRate === 0 ? "zero-rate" : "invalid-rate" };
}

/** Use the same source identity for guide, inline allies and Catch next. */
export function encounterCatchForm(row: Parameters<typeof encounterViewContext>[0], canonical: string): string {
  if (!row.speciesId) return "unsupported";
  const regional = encounterRegionalForm(row.speciesId, row.form ? formSlug(row.form) : undefined);
  if (regional) return regional;
  const context = encounterViewContext(row, canonical);
  return context ? context.detailKey?.slice(String(row.speciesId).length + 1) ?? "unsupported" : "base";
}

export function catchTier(rate: unknown): CatchTier | null {
  if (typeof rate !== "number" || !Number.isInteger(rate) || rate < 1 || rate > 255) return null;
  return CATCH_SCALE.find(band => rate >= band.min && rate <= band.max)?.tier ?? null;
}
