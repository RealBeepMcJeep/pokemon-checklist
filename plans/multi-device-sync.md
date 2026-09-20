# Multi-device sync: current architecture and status

## Current shape

The project ships one tracked, self-contained `index.html`. It remains offline-first: localStorage is the source of truth, and a player who never signs in does not contact the network. The same artifact enables sync after Google sign-in.

The player save remains schema v3. It contains species, forms, stars, and settings and still accepts v1 and v2 saves through the existing migration path. Sync bookkeeping is separate in the localStorage document `pokemon-checklist-sync-v1`; it stores the device identity, account namespace, and last Firebase-confirmed document (`base`).

Firebase Realtime Database stores one account namespace at `users/{uid}`:

- `state/records` is the merged per-record view.
- `log` contains the current per-record `op: "set"` entries with actor, device or channel, server time, key, `from`, and `to`.

Records use server-assigned timestamps and deterministic UID tie-breaking. A device layers local edits over its confirmed base. Pending work is derived as `diff(base, current save)`, not stored as an operation queue; retries are idempotent and the server echo empties the diff.

## Implemented

- Firebase Google authentication, allowed-email handling, and account-specific local save namespaces.
- Firebase sync engine with realtime subscriptions, server-ordered per-record merging, offline local edits, adoption of an existing device save on first sign-in, and safe sign-out.
- Per-record `set` logs for ordinary app changes and chat changes. A signed-in Reset currently remains local: `resetState()` produces a derived whole-account-clear diff, and the sync guard rejects publishing it, so Reset is not propagated and does not currently produce and publish ordinary per-record logs.
- A whole-account-clear guard that refuses any substantial whole-account clear before it can tombstone the account.
- Service-account chat tooling: `tools/pokemon_chat.py` parses intents, `tools/pokemon_ops.py` resolves and validates operations, and `tools/firebase-admin-rest.mjs` applies validated patches without putting credentials in the repository.

## Still outstanding

- Define and implement a safe synced-reset path, plus any undo design; neither exists today.
- Define and implement log retention or compaction.
- Test reset, reconnect, concurrent edits, account switching, and retention on real Firebase accounts and multiple physical devices.

The offline save, export/import validation, v1/v2 migration, and cross-tab behavior remain independent of the sync document and must continue to work when sync is unused.
