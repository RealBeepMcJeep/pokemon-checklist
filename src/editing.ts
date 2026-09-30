import { effect } from "@preact/signals";
import { readOnly, setEditable } from "./state";

/**
 * One tab edits a checklist at a time: the one holding its Web Lock. Every other
 * tab is view-only and follows that tab's saves; "Use this tab" steals the lock,
 * and the tab it was taken from turns view-only at once and waits to edit again.
 *
 * Signed out, the lock is the device's (`pokemon-checklist-edit`); signed in, the
 * account's (`pokemon-checklist-sync:<uid>`), which also decides the one tab that
 * syncs. Web Locks are local, so claiming one never touches the network. Without
 * Web Locks, or if they refuse (a SecurityError, say), every tab edits.
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
  takeOver: () => void;
  release: (() => void) | null;
}

export const DEVICE_LOCK = "pokemon-checklist-edit";

let current: Claim | null = null;

export function claimEditing(name: string, on: EditHandlers = {}): void {
  releaseEditing();
  if (readOnly.value === "outdated") return;
  const locks = (globalThis as { navigator?: Navigator }).navigator?.locks;
  const alone = () => {
    setEditable(true);
    on.edit?.("alone");
  };
  if (!locks) return alone();
  const mine: Claim = { takeOver: () => request({ steal: true }), release: null };
  current = mine;
  let held = false;
  const hold = (lock: Lock | null): Promise<void> | void => {
    // A claim given up, or a request overtaken by "Use this tab": let it go.
    if (current !== mine || held) return;
    if (!lock) {
      setEditable(false);
      on.waiting?.();
      request({});
      return;
    }
    held = true;
    setEditable(true);
    on.edit?.("lock");
    return new Promise<void>((release) => (mine.release = release));
  };
  const failed = (error: unknown) => {
    if (current !== mine) return;
    if (held) {
      // Stolen: another tab pressed "Use this tab". Wait to edit again.
      if ((error as { name?: string })?.name !== "AbortError") return;
      held = false;
      mine.release = null;
      setEditable(false);
      on.lost?.();
      request({});
      return;
    }
    alone();
  };
  const request = (options: LockOptions) => {
    try {
      locks.request(name, options, hold).catch(failed);
    } catch (error) {
      failed(error);
    }
  };
  request({ ifAvailable: true });
}

/** "Use this tab": take editing over from the tab that has it. */
export function useThisTab(): void {
  if (readOnly.value === "elsewhere") current?.takeOver();
}

export function releaseEditing(): void {
  const claim = current;
  current = null;
  claim?.release?.();
}

/** Signed out: claim the device's own checklist. */
export function claimDeviceEditing(): void {
  claimEditing(DEVICE_LOCK);
}

// A newer build open in another tab: stop editing here for good, so it can.
effect(() => {
  if (readOnly.value === "outdated") releaseEditing();
});
