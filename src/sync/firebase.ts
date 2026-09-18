import { initializeApp, type FirebaseApp } from "firebase/app";
import {
  GoogleAuthProvider,
  getAuth,
  onAuthStateChanged,
  signInWithPopup,
  signInWithRedirect,
  signOut,
  type Auth,
  type User,
} from "firebase/auth";
import { getDatabase, type Database } from "firebase/database";
import { FIREBASE_CONFIG, isAllowedEmail } from "./config";

// Nothing in this module touches the network until a player signs in.
// `initializeApp`, `getAuth` and `getDatabase` construct local objects and read
// local persistence only, so an offline player never causes a request — which is
// what keeps the published artifact's "silent while signed out" promise testable.

let app: FirebaseApp | undefined;
let auth: Auth | undefined;
let db: Database | undefined;

export function initFirebase(): { auth: Auth; db: Database } {
  if (!app) {
    app = initializeApp(FIREBASE_CONFIG);
    auth = getAuth(app);
    db = getDatabase(app);
  }
  return { auth: auth!, db: db! };
}

export function watchAuth(
  onUser: (user: User | null, allowed: boolean) => void,
): () => void {
  const { auth: instance } = initFirebase();
  return onAuthStateChanged(instance, (user) => {
    onUser(user, isAllowedEmail(user?.email));
  });
}

/**
 * Popup first because it keeps the page alive. Callers must fall back to
 * `signInWithRedirect` when the popup is blocked, which is why the result is
 * returned rather than assumed.
 */
export async function signInWithGoogle(): Promise<User | null> {
  const { auth: instance } = initFirebase();
  const result = await signInWithPopup(instance, new GoogleAuthProvider());
  return result.user;
}

/**
 * The fallback for a browser that refuses the popup. Firebase leaves the page and
 * comes back, so the caller must not expect a user out of this one.
 */
export async function signInWithGoogleRedirect(): Promise<void> {
  const { auth: instance } = initFirebase();
  await signInWithRedirect(instance, new GoogleAuthProvider());
}

export async function signOutOfSync(): Promise<void> {
  const { auth: instance } = initFirebase();
  await signOut(instance);
}
