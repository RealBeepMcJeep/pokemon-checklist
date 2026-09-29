# Multi-device sync: current architecture and status

## Current shape

The project ships one tracked, self-contained `index.html`. It remains offline-first: localStorage is the source of truth, and a player who never signs in does not contact the network. The same artifact enables sync after Google sign-in.

The player save remains schema v3. It contains species, forms, stars, and settings and still accepts v1 and v2 saves through the existing migration path. Every write also refreshes a `<save key>:last-good` copy; a save that cannot be read is kept aside under `<save key>:unreadable` (then `:unreadable-2`, ...) and is never written over, and it never hides a readable one: the last-good copy loads instead. An older build's v1/v2 save is migrated only when there is no current save at all, never over a current save that merely failed to read.

Sync bookkeeping is separate, in the localStorage document `pokemon-checklist-sync-v1`:

- `deviceId`, `uid`, `email`;
- `base`: the records the server has **acknowledged**. A value this page wrote but the server has not acknowledged is never stored as confirmed, even though Firebase shows it to the page's own listeners at once;
- `intents`: this device's unsent edits, each with the estimated server time it was made (`Date.now()` plus `.info/serverTimeOffset`). An edit stays here until its write is acknowledged, so a tab killed mid-write re-sends it after a reload;
- `reset` and `op`: a pending Reset (`op` absent) or Restore (`op: "restore"`) before-image;
- `offset`: the last known server clock offset, for edits made offline after a reload.

Firebase Realtime Database stores one account namespace at `users/{uid}`:

- `state/records` is the merged per-record view; each record is `{s, at, by}` (the chat tooling rejects any other field).
- `log` holds per-record `op: "set"` entries (actor, device or channel, server time, key, `from`, `to`), one `op: "reset"` entry per Reset with its before-image in `cleared`, and one `op: "restore"` entry per Restore (including an Undo of a Reset or Restore) with its before-image in `before`.

## How an edit travels

1. A tap is saved locally first and recorded as an intent with the time it was made.
2. It is published only while the connection is up and after the server's current records have arrived. The record listener is detached while offline, so a reconnect starts from what the server holds then, not from a stale cache.
3. When a remote change arrives for a record with an unsent intent, **the edit made last wins**: the intent is dropped if the remote change is newer. Close calls within a 2 s clock slack go to the side that keeps data. The echo of this page's own write in flight is recognised by matching that write, and is cleared once acknowledged.
4. On acknowledgement the intent is forgotten and the value becomes confirmed. A refused write is reverted by Firebase before it rejects; the intent stays and is sent again. A `PERMISSION_DENIED` after a lost acknowledgement (the log entries already exist) is retried once with fresh log ids.
5. After a reload, edits are recovered as `diff(confirmed base, save)`, keeping each edit's recorded time where one exists; an edit with no known time loses any close call that would clear data. A recovered set that would clear every live record is discarded. If the sync store itself was lost, only records the server has never held, plus edits recorded with their time in this session, are sent.

A whole-account-clear guard judges every publish except the records a Reset or Restore replaces on purpose. Clears that would empty the account (two or more live records) are held back and reported while everything else is still sent.

## Tabs

One tab per account syncs: it holds the Web Lock `pokemon-checklist-sync:<uid>`. The other tabs show and save the account's checklist and show "Syncing in another tab". The syncing tab takes their writes, read from the storage event (or merged in when its own save finds a newer one), as its own edits. A Reset or Restore in another tab is handed over through the `pokemon-checklist-sync-replace:<uid>` key, so it is still sent as one logged replacement. When the syncing tab closes, another tab takes the lock and recovers any edit it had not sent yet from the save.

Where Web Locks are unavailable, every tab syncs for itself. Another tab's save is then shown with this tab's unsent edits laid back over it, and never taken as this tab's own edits. The shared sync store keeps other tabs' unsent intents and pending Reset instead of writing over them.

A tab opened before a sign-in elsewhere follows that sign-in through the session flag's storage event. It never clears that flag on Firebase's first "signed out" report.

## Undo

The notice after a status, form or star change, a Reset, or a Restore offers one-step Undo, which works offline too. It puts back only the records that change touched, and only where they still hold what the change left there. It expires when any of those records changes elsewhere or the account changes. It goes through the ordinary save path, so sync sends it as plain edits; an Undo of a Reset or Restore is sent as a logged Restore.

## Known limitations

- A record's `at` is the time the server **received** the write, not when the edit was made. An edit that sat offline therefore carries a late `at` once sent, and a third device comparing against it can misjudge which of two edits was made last. Fixing this needs an edit-time field on records, which `tools/pokemon_ops.py` would reject today (it allows only `s`, `at`, `by`).
- A write issued just before Firebase notices a dead connection is still sent later by the SDK, stamped when it arrives.
- Echoes are recognised by value while a write is in flight: another device writing the same value in that moment is taken as this page's echo, which is harmless.
- Without Web Locks, an unsent edit in another tab is only known to this tab through the save; its edit time is kept in the shared store as far as each tab's writes preserve it.

## Implemented

- Firebase Google authentication with a verified allowlisted email, and account-specific local save namespaces.
- The sync engine above, with realtime subscriptions, offline edits, adoption of an existing device save on first sign-in, and safe sign-out that reports unsent edits.
- Per-record `set` logs for ordinary app changes and chat changes; atomic Reset and Restore with before-images.
- Service-account chat tooling: `tools/pokemon_chat.py` parses intents, `tools/pokemon_ops.py` resolves and validates operations, and `tools/firebase-admin-rest.mjs` applies validated patches without putting credentials in the repository.

## Still outstanding

- Undo from the log (chat tooling): the Reset and Restore events hold the before-images it needs.
- Define and implement log retention or compaction.
- Test reset, reconnect, concurrent edits, multiple tabs, account switching, and retention on real Firebase accounts and multiple physical devices.

The offline save, export/import validation, v1/v2 migration, and cross-tab behavior remain independent of the sync document and must continue to work when sync is unused.
