import {
  activeEncounters,
  cycleSpecies,
  drawerOpen,
  exportState,
  focusedLocation,
  parseState,
  resetState,
  restoreState,
  savedNotice,
  setMode,
  showNotice,
  sidebarHidden,
  speciesStatus,
} from "./state";
import { firstIncompleteLocation, MODE_LABELS } from "./domain";
import type { GameMode, Location } from "./types";

export const DRAWER_BREAKPOINT = 1000;
let previousFocus: HTMLElement | null = null;

export function currentOpenLocations(): string[] {
  return [
    ...document.querySelectorAll<HTMLDetailsElement>("details.location[open]"),
  ]
    .map((item) => item.dataset.locationId)
    .filter((id): id is string => Boolean(id));
}

export function firstIncomplete(): Location | null {
  return firstIncompleteLocation(activeEncounters.value, speciesStatus);
}

export function changeMode(nextMode: GameMode): void {
  const open = currentOpenLocations();
  setMode(nextMode);
  const available = new Set(
    activeEncounters.value.islands.flatMap((island) =>
      island.locations.map(({ id }) => id),
    ),
  );
  focusedLocation.value =
    open.find((id) => available.has(id)) || firstIncomplete()?.id || null;
  showNotice(`Switched to ${MODE_LABELS[nextMode]}.`, "good");
}

export function changeSpecies(id: number): void {
  const before = firstIncomplete()?.id || null;
  cycleSpecies(id);
  const after = firstIncomplete()?.id || null;
  savedNotice("Status");
  if (before !== after) focusedLocation.value = after;
}

export function jumpTo(hash: string): void {
  const target = document.getElementById(hash.slice(1));
  if (!target) return;
  let parent = target.parentElement;
  while (parent) {
    if (parent instanceof HTMLDetailsElement) parent.open = true;
    parent = parent.parentElement;
  }
  history.replaceState(null, "", hash);
  target.scrollIntoView({ block: "center" });
  target.focus({ preventScroll: true });
  closeDrawer();
}

export function closeDrawer(): void {
  drawerOpen.value = false;
  if (window.innerWidth < DRAWER_BREAKPOINT) previousFocus?.focus();
}

export function toggleSidebar(): void {
  if (window.innerWidth < DRAWER_BREAKPOINT) {
    if (!drawerOpen.value)
      previousFocus = document.activeElement as HTMLElement | null;
    drawerOpen.value = !drawerOpen.value;
  } else {
    sidebarHidden.value = !sidebarHidden.value;
  }
}

export function exportJSON(): void {
  const blob = new Blob([`${JSON.stringify(exportState(), null, 2)}\n`], {
    type: "application/json",
  });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "pokemon-checklist-state-v2.json";
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(link.href), 0);
  showNotice("Backup downloaded.", "good");
}

export async function importFile(event: Event): Promise<void> {
  const input = event.currentTarget as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (!file) return;
  try {
    const imported = parseState(await file.text());
    if (!confirm("Replace your current checklist with this backup?")) return;
    restoreState(imported);
    focusedLocation.value = firstIncomplete()?.id || null;
    showNotice("Backup restored.", "good");
  } catch (error) {
    showNotice(
      `Restore failed: ${error instanceof Error ? error.message : "that file could not be read"}.`,
      "error",
    );
  }
}

export function reset(): void {
  if (
    !confirm("Clear all caught and seen statuses, tracked forms, and settings?")
  )
    return;
  resetState();
  focusedLocation.value = firstIncomplete()?.id || null;
  showNotice("Checklist reset.", "good");
}
