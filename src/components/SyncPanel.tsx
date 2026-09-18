import { useState } from "preact/hooks";
import {
  beginSignIn,
  syncAccount,
  syncMessage,
  syncPending,
  syncPhase,
} from "../sync/engine";

/**
 * Popup failures worth retrying as a full page. A script blocker is the common
 * cause and cannot be detected, so these are the codes that mean "the window did
 * not work" rather than "the player said no".
 */
const RETRY_FULL_PAGE = new Set([
  "auth/popup-blocked",
  "auth/cancelled-popup-request",
  "auth/operation-not-supported-in-this-environment",
  "auth/internal-error",
  "auth/web-storage-unsupported",
]);
import {
  signInWithGoogle,
  signInWithGoogleRedirect,
  signOutOfSync,
} from "../sync/firebase";
import { showNotice } from "../state";

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
    case "pending":
      return syncPending.value === 1
        ? "1 to send"
        : `${syncPending.value} to send`;
    case "ready":
      return "Synced";
    case "error":
      return syncMessage.value || "Sync is not working";
  }
}

function describeSignIn(error: unknown): string {
  const code =
    typeof error === "object" && error !== null && "code" in error
      ? String((error as { code: unknown }).code)
      : "";
  switch (code) {
    case "auth/unauthorized-domain":
      return "This site is not authorized for sign-in in the Firebase console yet.";
    case "auth/popup-blocked":
    case "auth/popup-closed-by-user":
    case "auth/cancelled-popup-request":
      return "The sign-in window was blocked, so it is being tried as a full page instead.";
    case "auth/network-request-failed":
      return "No connection right now. Keep playing — your progress is saved here.";
    case "auth/operation-not-allowed":
      return "Google sign-in is not enabled for this project yet.";
    default:
      return "Sign-in did not complete. Your checklist here is untouched — try “Full-page sign-in”, which does not need a popup.";
  }
}

export function SyncPanel() {
  const account = syncAccount.value;
  const phase = syncPhase.value;
  const [busy, setBusy] = useState(false);

  async function signIn(fullPage = false): Promise<void> {
    setBusy(true);
    // Before anything else: a full-page round trip reloads the page, and the flag
    // telling it to look for a session has to be in place by then.
    beginSignIn();
    try {
      if (fullPage) {
        await signInWithGoogleRedirect();
        return;
      }
      await signInWithGoogle();
      showNotice(
        "Signed in. This checklist now syncs across your devices.",
        "good",
      );
    } catch (error) {
      showNotice(describeSignIn(error), "error");
      const code =
        typeof error === "object" && error !== null && "code" in error
          ? String((error as { code: unknown }).code)
          : "";
      if (RETRY_FULL_PAGE.has(code)) {
        await signInWithGoogleRedirect().catch(() => undefined);
      }
    } finally {
      setBusy(false);
    }
  }

  async function signOut(): Promise<void> {
    try {
      await signOutOfSync();
      showNotice(
        "Signed out. This device keeps its own checklist; nothing was deleted.",
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
        <span class="sync-phase">{statusText()}</span>
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
        <>
          <button
            class="action-button"
            id="sync-signin"
            type="button"
            disabled={busy || phase === "connecting"}
            onClick={() => void signIn()}
          >
            {busy ? "Signing in…" : "Sign in to sync"}
          </button>
          {/* The popup needs scripts in a window the player cannot fix; a full-page
              sign-in is an ordinary navigation, so script blockers can allow it. */}
          <button
            class="sync-fallback"
            id="sync-signin-full"
            type="button"
            disabled={busy || phase === "connecting"}
            title="Sign in on a normal page instead of a popup. Use this if a script blocker stops the window."
            onClick={() => void signIn(true)}
          >
            Full-page sign-in
          </button>
        </>
      )}
    </span>
  );
}
