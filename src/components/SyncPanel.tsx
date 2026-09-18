import { useState } from "preact/hooks";
import {
  syncAccount,
  syncMessage,
  syncPending,
  syncPhase,
  watchSyncAccount,
} from "../sync/engine";
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
        ? "1 change to send"
        : `${syncPending.value} changes to send`;
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
      return "The sign-in window was blocked; trying a full-page sign-in.";
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
    // Registering the handler before signing in means the account is picked up the
    // moment the provider hands one back.
    watchSyncAccount();
    try {
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
      if (code === "auth/popup-blocked" || code === "auth/cancelled-popup-request") {
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
        {account
          ? `${account.email || "Signed in"}${statusText() ? ` · ${statusText()}` : ""}`
          : statusText()}
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
          onClick={signIn}
        >
          {busy ? "Signing in…" : "Sign in to sync"}
        </button>
      )}
    </span>
  );
}
