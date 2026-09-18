import { useState } from "preact/hooks";
import {
  beginSignIn,
  syncAccount,
  syncMessage,
  syncPending,
  syncPhase,
} from "../sync/engine";

/**
 * Failures a full-page round trip cannot fix: the player's own choice, a network
 * that is down, or a project configured wrong. Anything else means the sign-in
 * WINDOW failed — a script blocker is the usual cause and cannot be detected — and
 * the full page is the path that works there, so it is taken without asking.
 */
const NO_FULL_PAGE_RETRY = new Set([
  "auth/popup-closed-by-user",
  "auth/network-request-failed",
  "auth/unauthorized-domain",
  "auth/operation-not-allowed",
  "auth/user-disabled",
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
      return "The sign-in window did not work here, so this page is handing over to Google instead.";
    case "auth/network-request-failed":
      return "No connection right now. Keep playing — your progress is saved here.";
    case "auth/operation-not-allowed":
      return "Google sign-in is not enabled for this project yet.";
    default:
      return "Sign-in did not complete. Your checklist here is untouched.";
  }
}

export function SyncPanel() {
  const account = syncAccount.value;
  const phase = syncPhase.value;
  const [busy, setBusy] = useState(false);

  async function signIn(): Promise<void> {
    setBusy(true);
    // Before anything else: a full-page round trip reloads the page, and the flag
    // telling it to look for a session has to be in place by then.
    beginSignIn();
    try {
      await signInWithGoogle();
      showNotice(
        "Signed in. This checklist now syncs across your devices.",
        "good",
      );
    } catch (error) {
      const code =
        typeof error === "object" && error !== null && "code" in error
          ? String((error as { code: unknown }).code)
          : "";
      if (NO_FULL_PAGE_RETRY.has(code)) {
        showNotice(describeSignIn(error), "error");
      } else {
        // Hand the whole page to Google rather than leaving the player with a window
        // that cannot sign in and no way to fix it from inside.
        showNotice(describeSignIn(error), "");
        await signInWithGoogleRedirect().catch(() =>
          showNotice("Sign-in could not be completed.", "error"),
        );
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
        <button
          class="action-button"
          id="sync-signin"
          type="button"
          disabled={busy || phase === "connecting"}
          onClick={() => void signIn()}
        >
          {busy ? "Signing in…" : "Sign in to sync"}
        </button>
      )}
    </span>
  );
}
