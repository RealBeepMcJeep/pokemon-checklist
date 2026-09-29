import { initializeApp, type FirebaseApp } from "firebase/app";
import {
  GoogleAuthProvider,
  getAuth,
  getRedirectResult,
  onAuthStateChanged,
  signInWithPopup,
  signOut,
  type Auth,
  type User,
} from "firebase/auth";
import { getDatabase, type Database } from "firebase/database";
import { FIREBASE_CONFIG, isAllowedAccount } from "./config";

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
    onUser(user, isAllowedAccount(user));
  });
}

/**
 * Load Google's sign-in helper ahead of the popup.
 *
 * `signInWithPopup` fetches that helper before it opens its window, which takes
 * seconds on a first sign-in. Safari only lets a click open a window straight away,
 * so it blocks a popup that late. Once this has run, the popup opens at once.
 * (`getRedirectResult` is the public call that initialises the helper.)
 */
export async function prepareSignIn(): Promise<void> {
  const { auth: instance } = initFirebase();
  await getRedirectResult(instance);
}

/**
 * The only sign-in path. A full-page redirect cannot work here: the app is on
 * github.io and Firebase's sign-in page on firebaseapp.com, and Safari, Firefox's
 * strict mode and Chrome without third-party cookies keep the two sites' storage
 * apart, so a redirect comes back signed out.
 */
export async function signInWithGoogle(): Promise<User | null> {
  const { auth: instance } = initFirebase();
  const result = await signInWithPopup(instance, new GoogleAuthProvider());
  return result.user;
}

export async function signOutOfSync(): Promise<void> {
  const { auth: instance } = initFirebase();
  await signOut(instance);
}
