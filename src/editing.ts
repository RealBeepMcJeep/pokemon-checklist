import { effect } from "@preact/signals";
import { readOnly, setEditable, showReadOnly } from "./state";

/**
 * One tab edits a checklist at a time: the one holding its Web Lock. Every other
 * tab is view-only and follows that tab's saves; "Use this tab" steals the lock,
 * and the tab it was taken from turns view-only at once and waits to edit again.
 *
 * Signed out, the lock is the device's (`pokemon-checklist-edit`); signed in, the
 * account's (`pokemon-checklist-sync:<uid>`), which also decides the one tab that
 * syncs. Web Locks are local, so claiming one never touches the network. Without
 * Web Locks, or if they refuse the first claim (a SecurityError, say), every tab
 * edits.
 */

export type EditMode = "lock" | "alone";

export interface EditHandlers {
  /** Another tab edits: this one is view-only until it gets the lock. */
  waiting?: () => void;
  /** This tab edits now, holding the lock or (without Web Locks) alone. */
  edit?: (mode: EditMode) => void;
  /** The lock was taken from this tab; it is view-only again. */
  lost?: () => void;
}

interface Claim {
  name: string;
  takeOver: () => void;
  release: (() => void) | null;
}

export const DEVICE_LOCK = "pokemon-checklist-edit";
/** Set by "Use this tab" just before a reload: the lock the fresh page takes. */
const TAKE_OVER_KEY = "pokemon-checklist-take-over";

let current: Claim | null = null;
/** Settles once the lock this tab last held has been released. */
let released: Promise<unknown> = Promise.resolve();
/**
 * Locks this page gave up after syncing under them: its database connection was
 * then shut, and must stay shut (writes still queued in it would land late). Taking
 * such a lock back, by "Use this tab" or when the editing tab closes, needs a fresh
 * page, which takes the lock as it arrives.
 */
const reloadToTakeOver = new Set<string>();
let stealOnArrival = ((): string | null => {
  try {
    const name = sessionStorage.getItem(TAKE_OVER_KEY);
    if (name !== null) sessionStorage.removeItem(TAKE_OVER_KEY);
    return name;
  } catch {
    return null;
  }
})();

export function claimEditing(name: string, on: EditHandlers = {}): void {
  const previous = releaseEditing();
  if (readOnly.value === "outdated") return;
  const locks = (globalThis as { navigator?: Navigator }).navigator?.locks;
  const alone = () => {
    setEditable(true);
    on.edit?.("alone");
  };
  if (!locks) return alone();
  const mine: Claim = { name, takeOver: () => request({ steal: true }), release: null };
  current = mine;
  /** The request that holds the lock, while this tab holds it. */
  let holder: object | null = null;
  const settledBy = new Map<object, Promise<unknown>>();
  const hold = (lock: Lock | null, token: object): Promise<void> | void => {
    // A claim given up, or a request overtaken by "Use this tab": let it go.
    if (current !== mine || holder) return;
    if (!lock) {
      setEditable(false);
      on.waiting?.();
      request({});
      return;
    }
    if (reloadToTakeOver.has(name)) {
      // Returning at once releases the lock for the fresh page to take.
      reloadAndTake(name);
      return;
    }
    holder = token;
    const settled = settledBy.get(token);
    if (settled) released = settled;
    setEditable(true);
    on.edit?.("lock");
    return new Promise<void>((release) => (mine.release = release));
  };
  const failed = (error: unknown, token: object, first: boolean) => {
    if (current !== mine) return;
    if (token === holder) {
      // Stolen: another tab pressed "Use this tab". Wait to edit again.
      if ((error as { name?: string })?.name !== "AbortError") return;
      holder = null;
      mine.release = null;
      setEditable(false);
      on.lost?.();
      request({});
      return;
    }
    // Only a first claim refused outright (Web Locks unusable here) lets every tab
    // edit. A later refusal leaves this tab waiting: never a second editor.
    if (first) alone();
  };
  const request = (options: LockOptions, first = false) => {
    const token = {};
    try {
      const settled = locks
        .request(name, options, (lock) => hold(lock, token))
        .catch((error: unknown) => failed(error, token, first));
      settledBy.set(token, settled);
      if (holder === token) released = settled;
    } catch (error) {
      failed(error, token, first);
    }
  };
  const steal = stealOnArrival === name;
  if (steal) stealOnArrival = null;
  // Ask only once this tab's last lock is released: asking earlier is refused by
  // the tab itself, which then flashed view-only (and lost its Undo).
  void previous.then(() => {
    if (current === mine) request(steal ? { steal: true } : { ifAvailable: true }, true);
  });
}

/** "Use this tab": take editing over from the tab that has it. */
export function useThisTab(): void {
  const claim = current;
  if (readOnly.value !== "elsewhere" || !claim) return;
  if (reloadToTakeOver.has(claim.name)) reloadAndTake(claim.name);
  else claim.takeOver();
}

function reloadAndTake(name: string): void {
  try {
    sessionStorage.setItem(TAKE_OVER_KEY, name);
  } catch {
    return;
  }
  location.reload();
}

/** This page's database connection for this lock has been shut for good. */
export function takeOverNeedsReload(name: string): void {
  reloadToTakeOver.add(name);
}

/** Give up this tab's claim; settles once its lock is actually released. */
export function releaseEditing(): Promise<unknown> {
  const claim = current;
  current = null;
  claim?.release?.();
  return released;
}

/** Signed out: claim the device's own checklist. */
export function claimDeviceEditing(): void {
  claimEditing(DEVICE_LOCK);
}

/**
 * Call when a confirm() dialog has just said yes. The dialog blocked this tab, so
 * news that another tab took editing meanwhile is still queued behind it: let it
 * through first, and go on only if this tab still edits.
 */
export async function stillEditingAfterDialog(): Promise<boolean> {
  await new Promise((resolve) => setTimeout(resolve, 0));
  if (!readOnly.value) return true;
  showReadOnly();
  return false;
}

// A newer build open in another tab: stop editing here for good, so it can.
effect(() => {
  if (readOnly.value === "outdated") void releaseEditing();
});
