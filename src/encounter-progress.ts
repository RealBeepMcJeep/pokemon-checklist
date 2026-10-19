import { catchNowRows, encounterStatus, locationProgress, formKey } from "./domain";
import { isRegional } from "./regional";
import type { Location, Status } from "./types";

/** One target scope for eligible, locked and backtrack summaries. Source callers
 * and duplicate occurrences never become a third generic regional target. */
export function locationSummary(location: Location, statusOf: (id: number) => Status,
  unlocks: readonly string[] = [], formStatusOf?: (key: string) => Status) {
  const tracking = !!formStatusOf;
  const progress = locationProgress(location, statusOf, unlocks, formStatusOf);
  const native = catchNowRows(location, [], tracking);
  const known = new Set<string>();
  for (const group of location.groups) for (const row of group.encounters) {
    for (const target of [row, ...row.allies, ...(row.conditionalAllies || [])]) {
      if (!target.speciesId) continue;
      // Match encounterStatus/eligibleRows exactly: absent defaults to Alolan,
      // but an explicit unsupported token must not silently become Alolan.
      known.add(tracking && isRegional(target.speciesId)
        ? formKey(target.speciesId, "form", target.form || "alolan") : String(target.speciesId));
    }
  }
  return { progress, locked: known.size - progress.total,
    backtrack: unlocks.length > 0 && native.length > 0
      && native.every(row => encounterStatus(row, statusOf, formStatusOf) === "caught")
      && progress.caught < progress.total,
    complete: progress.total > 0 && progress.caught === progress.total };
}
