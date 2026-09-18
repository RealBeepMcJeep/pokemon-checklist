// The Firebase web configuration is public by design. It identifies the project;
// it does not authorise anything. Access is decided by `firebase/database.rules.json`,
// which checks the signed-in account against an allowlist, so this object is safe to
// commit and ships inside the published artifact regardless.
export const FIREBASE_CONFIG = {
  apiKey: "AIzaSyBXUU2diLRtFlntb_kUcNRnHXOOFTQnbYg",
  authDomain: "pokemon-checklist-8c75f.firebaseapp.com",
  databaseURL: "https://pokemon-checklist-8c75f-default-rtdb.firebaseio.com",
  projectId: "pokemon-checklist-8c75f",
  storageBucket: "pokemon-checklist-8c75f.firebasestorage.app",
  messagingSenderId: "397847973162",
  appId: "1:397847973162:web:9c558f41df4944c96be253",
} as const;

// Mirrored in the database rules, which are what actually enforce it. Keeping the
// list here as well lets the UI say "this account is not on the list" instead of
// showing a permission error, and lets the tests assert the two agree.
export const ALLOWED_EMAILS = ["realbeepmcjeep@gmail.com"] as const;

export function isAllowedEmail(email: string | null | undefined): boolean {
  if (!email) return false;
  return (ALLOWED_EMAILS as readonly string[]).includes(email.toLowerCase());
}
