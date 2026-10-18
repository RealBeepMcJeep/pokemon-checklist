import { signal } from "@preact/signals";
import {
  activeEncounters,
  activeSaveKey,
  activeUnlocks,
  changeNotice,
  cycleSpecies,
  drawerOpen,
  exportState,
  focusedLocation,
  mode,
  parseState,
  resetState,
  restoreState,
  savedNotice,
  selectedDex,
  setMode,
  showNotice,
  sidebarHidden,
  speciesStatus,
} from "./state";
import { firstIncompleteLocation, MODE_LABELS, safeId } from "./domain";
import { readLastLocation, writeLastLocation } from "./location-memory";
import { stillEditingAfterDialog } from "./editing";
import type { GameMode, Location } from "./types";

export const DRAWER_BREAKPOINT = 1000;
let previousFocus: HTMLElement | null = null;
// Set once and updated only by the media query below, so a resize or rotation
// across the breakpoint is never missed by a render that reads window.innerWidth
// once and never again. Pokedex.tsx and Header.tsx derive mobile/hidden state
// from this instead of reading the viewport directly.
const mobileQuery = window.matchMedia(`(max-width: ${DRAWER_BREAKPOINT - 1}px)`);
export const isMobile = signal(mobileQuery.matches);
mobileQuery.addEventListener("change", (event) => {
  isMobile.value = event.matches;
  // The phone drawer is a modal; left open into the desktop layout it would keep the
  // page scroll-locked and everything behind it inert.
  if (!event.matches) drawerOpen.value = false;
});
// The drawer is a modal on a phone: lock the page behind it so a swipe on the
// backdrop can't scroll the location list underneath.
let bodyOverflowLock: (() => void) | null = null;
drawerOpen.subscribe((open) => {
  if (open && !bodyOverflowLock) {
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    bodyOverflowLock = () => {
      document.body.style.overflow = previous;
    };
  } else if (!open && bodyOverflowLock) {
    bodyOverflowLock();
    bodyOverflowLock = null;
  }
});
/** Set right before opening the drawer so its focus lands on the selection panel
 * (opened for a specific Pokémon) rather than the search box (opened generically). */
let focusSelectionOnOpen = false;

export function firstIncomplete(): Location | null {
  return firstIncompleteLocation(activeEncounters.value, speciesStatus, activeUnlocks.value);
}

let memoryWarningShown = false;
export function rememberLocation(id: string, expectedMode = mode.peek(), expectedNamespace = activeSaveKey()): void {
  // A delayed toggle from an unmounted mode/account must not write into the new one.
  if (mode.peek() !== expectedMode || activeSaveKey() !== expectedNamespace) return;
  if (!activeEncounters.peek().islands.some(island => island.locations.some(location => location.id === id))) return;
  if (!writeLastLocation(expectedMode, expectedNamespace, id) && !memoryWarningShown) {
    memoryWarningShown = true;
    showNotice("Last area could not be remembered on this device. Browsing still works.", "error");
  }
}

/** Called only on startup or a mode/account change, never on tab visibility. */
export function restoreLocation(hash = ""): void {
  const locations = activeEncounters.peek().islands.flatMap(island => island.locations);
  const linked = locations.find(location =>
    hash === `#location-${safeId(location.id)}` || location.groups.some(group =>
      group.encounters.some(row => hash === `#encounter-${safeId(row.id)}`)));
  const id = linked?.id || readLastLocation(mode.peek(), activeSaveKey(), locations.map(location => location.id)) || firstIncomplete()?.id || null;
  if (linked && hash.startsWith("#encounter-")) jumpTo(hash, linked.id);
  else focusedLocation.value = id;
}

export function changeMode(nextMode: GameMode): void {
  setMode(nextMode);
  changeNotice(`Switched to ${MODE_LABELS[nextMode]}.`);
}

export function changeSpecies(id: number): void {
  const before = firstIncomplete()?.id || null;
  cycleSpecies(id);
  const after = firstIncomplete()?.id || null;
  savedNotice("Status");
  if (before !== after) focusedLocation.value = after;
}

function focusEncounterRow(hash: string): boolean {
  const target = document.getElementById(hash.slice(1));
  if (!target) return false;
  const locationId = target.closest<HTMLDetailsElement>("details.location")?.dataset.locationId;
  if (locationId) rememberLocation(locationId);
  let parent = target.parentElement;
  while (parent) {
    if (parent instanceof HTMLDetailsElement) parent.open = true;
    parent = parent.parentElement;
  }
  history.replaceState(null, "", hash);
  target.scrollIntoView({ block: "center" });
  target.focus({ preventScroll: true });
  closeDrawer();
  return true;
}

// Set right before focusing a new location so its own open effect (which would
// otherwise focus the location's <summary>) yields to the more specific row jumpTo
// is about to focus. Locations.tsx consumes this once per location change.
let pendingRowFocus: string | null = null;

/** Consumed by Locations.tsx's own scroll/focus effect: true means jumpTo is about
 * to focus a specific row in this location, so the effect must not also focus the
 * location's summary out from under it. */
export function consumeRowFocusIntent(locationId: string): boolean {
  if (pendingRowFocus !== locationId) return false;
  pendingRowFocus = null;
  return true;
}

/**
 * Scroll to and focus an encounter row, opening its owning location first when
 * that location has never been opened (so the row hasn't mounted yet). `locationId`
 * is the id of the location the row lives in; omit it for a hash known to already
 * be on the page (e.g. one the caller just opened itself).
 */
export function jumpTo(hash: string, locationId?: string): void {
  if (focusEncounterRow(hash)) return;
  if (!locationId) return;
  pendingRowFocus = locationId;
  focusedLocation.value = locationId;
  // The location's body mounts the first time it opens (Locations.tsx), which
  // happens on the next render plus its own mount effect; retry across a few
  // frames rather than guessing exactly how many renders that takes.
  let attempts = 10;
  const retry = () => {
    if (focusEncounterRow(hash) || --attempts <= 0) return;
    requestAnimationFrame(retry);
  };
  requestAnimationFrame(retry);
}

export function openPokemon(id: number): void {
  selectedDex.value = id;
  if (isMobile.value) {
    if (!drawerOpen.value)
      previousFocus = document.activeElement as HTMLElement | null;
    focusSelectionOnOpen = true;
    drawerOpen.value = true;
  } else {
    sidebarHidden.value = false;
  }
  requestAnimationFrame(() => {
    document.querySelector<HTMLElement>("#dex-selection")?.focus({
      preventScroll: true,
    });
  });
}

/** Consumed by Pokedex.tsx's open effect: true means openPokemon already queued
 * focus for the selection panel, so the effect must not steal it back to search. */
export function consumeSelectionFocusIntent(): boolean {
  const value = focusSelectionOnOpen;
  focusSelectionOnOpen = false;
  return value;
}

export function closeDrawer(): void {
  drawerOpen.value = false;
  if (isMobile.value) previousFocus?.focus();
}

export function toggleSidebar(): void {
  if (isMobile.value) {
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
  link.download = "pokemon-checklist-state-v4.json";
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
    if (!(await stillEditingAfterDialog())) return;
    restoreState(imported);
    focusedLocation.value = firstIncomplete()?.id || null;
    changeNotice("Backup restored.");
  } catch (error) {
    showNotice(
      `Restore failed: ${error instanceof Error ? error.message : "that file could not be read"}.`,
      "error",
    );
  }
}

export async function reset(): Promise<void> {
  if (
    !confirm(
      "Clear all caught and seen statuses, tracked forms, starred Pokémon, encounter unlocks, and settings?",
    )
  )
    return;
  if (!(await stillEditingAfterDialog())) return;
  resetState();
  focusedLocation.value = firstIncomplete()?.id || null;
  changeNotice("Checklist reset.");
}
