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
- Per-record `set` logging for app changes and chat changes. Reset uses the normal local save path: clearing the checklist produces ordinary per-record changes and logs, not a separate reset operation.
- A whole-account-clear guard that refuses a suspicious derived diff before it can tombstone a substantial account.
- Service-account chat tooling: `tools/pokemon_chat.py` resolves deterministic player commands, and `tools/firebase-admin-rest.mjs` validates and applies record patches without putting credentials in the repository.

## Still outstanding

- Decide and implement reset undo, if it is wanted; no reset-specific undo log format is shipped.
- Define and implement log retention or compaction.
- Test reset, reconnect, concurrent edits, account switching, and retention on real Firebase accounts and multiple physical devices.

The offline save, export/import validation, v1/v2 migration, and cross-tab behavior remain independent of the sync document and must continue to work when sync is unused.
