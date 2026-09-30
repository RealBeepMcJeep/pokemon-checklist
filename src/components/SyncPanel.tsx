import { useState } from "preact/hooks";
import {
  beginSignIn,
  cancelSignIn,
  resolveHeldClears,
  syncAccount,
  syncHeldKeys,
  syncMessage,
  syncOnline,
  syncPending,
  syncPhase,
} from "../sync/engine";
import { stillEditingAfterDialog, useThisTab } from "../editing";
import { heldSummary } from "../sync/outbox";
import { isAllowedAccount } from "../sync/config";
import {
  prepareSignIn,
  signInWithGoogle,
  signOutOfSync,
} from "../sync/firebase";
import { readOnly, showNotice } from "../state";

/**
 * The only control that can make the app touch the network, and it never fires on
 * its own: nothing happens until a player presses it. A player who never presses it
 * is running the offline-only app, and the browser test that records every request
 * proves it stays silent.
 */

function statusText(): string {
  switch (syncPhase.value) {
    case "off":
      return syncAccount.value ? "Signed in" : "";
    case "connecting":
      return "Syncing…";
    case "pending": {
      const count =
        syncPending.value === 1 ? "1 to send" : `${syncPending.value} to send`;
      return syncOnline.value ? count : `Offline · ${count}`;
    }
    case "ready":
      // "Synced" while offline would claim the other devices have caught up.
      return syncOnline.value ? "Synced" : "Offline";
    case "error":
      return syncMessage.value || "Sync is not working";
    case "elsewhere":
      // One tab per account edits and syncs; this one follows it.
      return "Editing in another tab";
    case "outdated":
      return "A newer version is open";
  }
}

function errorCode(error: unknown): string {
  return typeof error === "object" && error !== null && "code" in error
    ? String((error as { code: unknown }).code)
    : "";
}

function describeSignIn(error: unknown): string {
  switch (errorCode(error)) {
    case "auth/unauthorized-domain":
      return "This site is not authorized for sign-in in the Firebase console yet.";
    case "auth/popup-closed-by-user":
    case "auth/cancelled-popup-request":
      return "The sign-in window was closed before signing in finished. Your checklist here is untouched.";
    case "auth/network-request-failed":
      return "No connection right now. Keep playing — your progress is saved here.";
    case "auth/operation-not-allowed":
      return "Google sign-in is not enabled for this project yet.";
    default:
      return "Sign-in did not complete. Your checklist here is untouched.";
  }
}

// Google's sign-in helper, once loaded, stays loaded for the page's lifetime.
let prepared = false;

export function SyncPanel() {
  const account = syncAccount.value;
  const phase = syncPhase.value;
  const [busy, setBusy] = useState(false);
  // The browser blocked the popup; the next press opens it straight from the click.
  const [blocked, setBlocked] = useState(false);

  async function signIn(): Promise<void> {
    setBusy(true);
    // Before anything else, so the session is looked for if the page reloads.
    beginSignIn();
    try {
      // Only the first press waits here. After it, the popup below opens within the
      // click itself, which is what Safari requires.
      if (!prepared) {
        await prepareSignIn();
        prepared = true;
      }
      const user = await signInWithGoogle();
      setBlocked(false);
      // A disallowed account gets its own notice from the auth watcher; this one would
      // overwrite it with a false promise.
      if (isAllowedAccount(user)) {
        showNotice(
          "Signed in. This checklist now syncs across your devices.",
          "good",
        );
      }
    } catch (error) {
      if (errorCode(error) === "auth/popup-blocked") {
        setBlocked(true);
        showNotice(
          "Your browser blocked Google's sign-in window. Press “Continue with Google” to open it.",
          "",
        );
      } else {
        cancelSignIn();
        setBlocked(false);
        showNotice(describeSignIn(error), "error");
      }
    } finally {
      setBusy(false);
    }
  }

  async function signOut(): Promise<void> {
    // Read before signing out, which resets it.
    const unsent = syncPending.value;
    try {
      await signOutOfSync();
      showNotice(
        unsent > 0
          ? `Signed out. ${unsent === 1 ? "1 change" : `${unsent} changes`} had not reached your other devices yet; they are kept here and sent the next time you sign in on this device.`
          : "Signed out. This device keeps its own checklist; nothing was deleted.",
        "good",
      );
    } catch {
      showNotice("Could not sign out.", "error");
    }
  }

  return (
    <span class="sync-panel" id="sync-panel">
      <span
        class="sync-status"
        id="sync-status"
        data-phase={phase === "off" ? undefined : phase}
        data-online={account ? String(syncOnline.value) : undefined}
        role="status"
        aria-live="polite"
      >
        {/*
          Split in two so a phone can drop the long part. The account is detail
          (kept in the title for a long press); the status word is the signal.
        */}
        {account && (
          <span class="sync-account" title={account.email || "Signed in"}>
            {account.email || "Signed in"}
          </span>
        )}
        <span class="sync-phase" title={statusText()}>
          {statusText()}
        </span>
      </span>
      {account ? (
        <button
          class="action-button"
          id="sync-signout"
          type="button"
          onClick={signOut}
        >
          Sign out
        </button>
      ) : (
        <button
          class="action-button"
          id="sync-signin"
          type="button"
          disabled={busy || phase === "connecting"}
          onClick={() => void signIn()}
        >
          {busy
            ? "Signing in…"
            : blocked
              ? "Continue with Google"
              : "Sign in to sync"}
        </button>
      )}
    </span>
  );
}

/**
 * Shown while this tab may not edit: another tab of the account is the editor (and
 * this one can take over), or a newer build of the app is open (reload).
 */
export function ViewOnlyBanner() {
  const reason = readOnly.value;
  if (!reason) return null;
  return (
    <div class="view-only" id="view-only" role="status">
      <span>
        {reason === "outdated"
          ? "A newer version is open in another tab, so this one can no longer change anything."
          : "This checklist is being edited in another tab."}
      </span>
      {reason === "outdated" ? (
        <button class="action-button" type="button" onClick={() => location.reload()}>
          Reload
        </button>
      ) : (
        <button
          class="action-button"
          id="use-this-tab"
          type="button"
          onClick={useThisTab}
        >
          Use this tab
        </button>
      )}
    </div>
  );
}

/**
 * Clears held back because together they would empty the account. Putting them
 * back is the first, safe choice; sending them is spelled out before it happens.
 */
export function HeldClears() {
  const keys = syncHeldKeys.value;
  if (!syncAccount.value || keys.length === 0) return null;
  const locked = readOnly.value !== null;
  return (
    <div class="held-clears" id="held-clears" role="alert">
      <span>
        Clearing {heldSummary(keys)} would empty the checklist on every device, so{" "}
        {keys.length === 1 ? "it was" : "they were"} not sent.
      </span>
      <span class="held-actions">
        <button
          class="action-button"
          id="held-put-back"
          type="button"
          disabled={locked}
          onClick={() => resolveHeldClears(false)}
        >
          Put back
        </button>
        <button
          class="action-button danger"
          id="held-send"
          type="button"
          disabled={locked}
          onClick={async () => {
            if (!confirm(heldConfirmText(keys))) return;
            if (await stillEditingAfterDialog()) resolveHeldClears(true);
          }}
        >
          Send clears
        </button>
      </span>
    </div>
  );
}

export function heldConfirmText(keys: readonly string[]): string {
  return `Clear ${heldSummary(keys)} on every device? This can't be undone here.`;
}
