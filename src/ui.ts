import { signal } from "@preact/signals";
import {
  activeEncounters,
  changeNotice,
  cycleSpecies,
  drawerOpen,
  exportState,
  focusedLocation,
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
import { firstIncompleteLocation, MODE_LABELS } from "./domain";
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
  link.download = "pokemon-checklist-state-v3.json";
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
    changeNotice("Backup restored.");
  } catch (error) {
    showNotice(
      `Restore failed: ${error instanceof Error ? error.message : "that file could not be read"}.`,
      "error",
    );
  }
}

export function reset(): void {
  if (
    !confirm(
      "Clear all caught and seen statuses, tracked forms, starred Pokémon, and settings?",
    )
  )
    return;
  resetState();
  focusedLocation.value = firstIncomplete()?.id || null;
  changeNotice("Checklist reset.");
}
