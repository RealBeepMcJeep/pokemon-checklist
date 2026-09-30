# Multi-device sync: current architecture and status

## Current shape

The project ships one tracked, self-contained `index.html`. It remains offline-first: localStorage is the source of truth, and a player who never signs in does not contact the network. The same artifact enables sync after Google sign-in.

The player save remains schema v3. It contains species, forms, stars, and settings and still accepts v1 and v2 saves through the existing migration path. Every write also refreshes a `<save key>:last-good` copy; a save that cannot be read is kept aside under `<save key>:unreadable` (then `:unreadable-2`, ...) and is never written over, and it never hides a readable one: the last-good copy loads instead. An older build's v1/v2 save is migrated only when there is no current save at all, never over a current save that merely failed to read.

Sync bookkeeping is separate, in the localStorage document `pokemon-checklist-sync-v1`:

- `deviceId`, `uid`, `email`;
- `base`: the records the server has **acknowledged**. A value this page wrote but the server has not acknowledged is never stored as confirmed, even though Firebase shows it to the page's own listeners at once;
- `intents`: this device's unsent edits, each with the estimated server time it was made (`Date.now()` plus `.info/serverTimeOffset`). An edit stays here until its write is acknowledged, so a tab killed mid-write re-sends it after a reload;
- `reset` and `op`: a pending Reset (`op` absent) or Restore (`op: "restore"`) before-image;
- `offset`: the last known server clock offset, for edits made offline after a reload;
- `held`: clears held back by the whole-account guard until the player decides.

Firebase Realtime Database stores one account namespace at `users/{uid}`:

- `state/records` is the merged per-record view; each record is `{s, at, by}` (the chat tooling rejects any other field).
- `log` holds per-record `op: "set"` entries (actor, device or channel, server time, key, `from`, `to`), one `op: "reset"` entry per Reset with its before-image in `cleared`, and one `op: "restore"` entry per Restore (including an Undo of a Reset or Restore) with its before-image in `before`.

## How an edit travels

1. A tap is saved locally first and recorded as an intent with the time it was made.
2. It is published only while the connection is up and after the server's current records have arrived. The record listener is detached while offline, so a reconnect starts from what the server holds then, not from a stale cache.
3. When a remote change arrives for a record with an unsent intent, **the edit made last wins**: the intent is dropped if the remote change is newer. Close calls within a 2 s clock slack go to the side that keeps data. The echo of this page's own write in flight is recognised by matching that write, and is cleared once acknowledged.
4. On acknowledgement the intent is forgotten and the value becomes confirmed. A refused write is reverted by Firebase before it rejects; the intent stays and is sent again. A `PERMISSION_DENIED` after a lost acknowledgement (the log entries already exist) is retried once with fresh log ids.
5. After a reload, edits are recovered as `diff(confirmed base, save)`, keeping each edit's recorded time where one exists; an edit with no known time loses any close call that would clear data. A recovered set that would clear every live record is discarded. If the sync store itself was lost, only records the server has never held, plus edits recorded with their time in this session, are sent.

A whole-account-clear guard judges every publish except the records a Reset or Restore replaces on purpose. Clears that would empty the account (two or more live records) are held back and reported while everything else is still sent. Held clears are kept in the sync store and stay held, across reloads and whatever the account gains meanwhile, until the player chooses. **Put back** (the first, default choice) returns those Pokémon as the account has them. **Send clears**, styled as destructive and confirmed with "Clear N Pokémon on every device? This can't be undone here.", sends them as one logged `reset` with its before-image. A view-only tab shows that clears are held, with the choices disabled.

After a reload, a recovered set that would empty the account is still treated as a stale copy, but only its clears are dropped (with a notice); what it adds is sent.

## Tabs

Exactly one tab edits a checklist: the one holding its Web Lock (`src/editing.ts`). Signed in, that is the account's lock `pokemon-checklist-sync:<uid>`, and the editing tab is also the only one that syncs. Signed out, it is the device's lock `pokemon-checklist-edit`. Web Locks are local, so claiming one never touches the network.

- Every other tab of that checklist is view-only. It follows the editor's saves through the storage event, and its status, form, star, mode, Reset, Restore and Undo controls are disabled and change nothing (`readOnly` in `state.ts` guards every change as well). A banner pinned to the bottom of the screen (above the phone drawer, so it is in sight wherever the player is) says "This checklist is being edited in another tab." and offers **Use this tab**; since disabled controls react to nothing, the banner is the explanation.
- **Use this tab** takes the lock with `navigator.locks.request(name, { steal: true }, ...)`. The tab it was taken from sees its held lock's request reject with `AbortError` and turns view-only at once: it stops syncing, stops writing the sync store, and shuts its database connection for good (`goOffline`), so writes still queued in its Firebase client can never land after the new editor's newer ones. Every unsent edit is already in the store's `intents` (written on each change), so the new editor reads and sends it. Nothing is handed over between tabs, and no tab keeps an id of its own, so a duplicated tab (which copies `sessionStorage`) is simply another view-only tab.
- A tab that starts editing first re-reads the save from storage (it may have been asleep and missed the last editor's final save), and starts with no memory of what it pushed or retried before.
- A tab whose database connection was shut this way takes editing back only as a fresh page: **Use this tab** there (or the lock coming back when the editing tab closes) sets a `sessionStorage` flag naming the lock and reloads, and the fresh page takes the lock (`steal: true`) as it arrives. Its unsent edits come back from the store.
- When the editing tab closes, its lock is released and a waiting tab starts editing.
- A tab waits for its own lock to be released before asking for one again (asking earlier is refused by the tab itself). Only a first claim that Web Locks refuse outright lets the tab edit without a lock; any later refusal leaves it view-only, never a second editor.
- Reset, Restore and **Send clears** ask for confirmation. The dialog blocks the tab, so news that another tab took editing meanwhile is queued behind it: after a yes the tab lets that news through first and goes on only if it still edits.
- The editor never takes another tab's save as edits; if one is written anyway (a sign-in in another tab, say), it only replaces it with its own view.

Where Web Locks are unavailable, or they refuse (a `SecurityError`, say), every tab edits and syncs for itself. Another tab's save is then shown with this tab's unsent edits laid back over it, and never taken as this tab's own edits. It is saved back only where the other tab left a record as the account has it, so two tabs holding different unsent edits of one record settle instead of writing over each other for ever. The shared sync store keeps other tabs' unsent intents and pending Reset instead of writing over them.

### Builds

Two builds must never edit one checklist at once. Each tab announces its build (`BUILD_LABEL`) under `pokemon-checklist-build` when it loads. A tab that hears a different build announced after it becomes view-only, shows "A newer version is open in another tab" with **Reload**, and gives up its lock so the newer tab can edit. Commits cannot be ordered, so the tab loaded last is taken as the newer build: pages are loaded after a deploy, so the last one runs what is deployed.

**Deploying:** a tab still running a build from before this guard (or before these editing rules) neither listens for newer builds nor gives up editing to a stolen lock the way this build does. After deploying, reload the app tab on every device before pressing **Use this tab** anywhere.

A tab opened before a sign-in elsewhere follows that sign-in through the session flag's storage event. It never clears that flag on Firebase's first "signed out" report.

## Undo

The notice after a status, form or star change, a Reset, or a Restore offers one-step Undo, which works offline too. It puts back only the records that change touched, and only where they still hold what the change left there. It expires when any of those records changes elsewhere or the account changes. It goes through the ordinary save path, so sync sends it as plain edits; an Undo of a Reset or Restore is sent as a logged Restore; undoing one still in flight logs the Restore with what that Reset left, not what it found. Another tab's update does not withdraw an Undo unless it touched what the Undo would put back.

## Known limitations

- A record's `at` is the time the server **received** the write, not when the edit was made. An edit that sat offline therefore carries a late `at` once sent, and a third device comparing against it can misjudge which of two edits was made last. Fixing this needs an edit-time field on records, which `tools/pokemon_ops.py` would reject today (it allows only `s`, `at`, `by`).
- A write issued just before Firebase notices a dead connection is still sent later by the SDK, stamped when it arrives.
- Echoes are recognised by value while a write is in flight: another device writing the same value in that moment is taken as this page's echo, which is harmless.
- Without Web Locks, an unsent edit in another tab is only known to this tab through the save; its edit time is kept in the shared store as far as each tab's writes preserve it. Two such tabs holding different edits of one record each show their own until the server settles it.
- A write the old editor had already sent when "Use this tab" moved editing may have reached the server just before its connection was shut; the new editor then finds that value on the server and does not send it again, or sends the same value once more if it looked first. Nothing queued after the shutdown is ever delivered.
- Held clears are counted as Pokémon (species and forms) and favourites (stars). **Send clears** is refused, with a notice, while a Reset or Restore is still being sent, so its before-image is never lost.
- A sync store written by a build before these changes may hold, in `base`, a value that was shown locally but never acknowledged; such a value is not re-sent after upgrading. This could only have happened with a tab killed mid-write on that build.

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
