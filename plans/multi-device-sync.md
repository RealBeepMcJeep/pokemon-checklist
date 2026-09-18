# Multi-device sync and control from chat

Proposal, not a schedule. Nothing here is committed to a release until the open decisions
below are answered; the grilling rounds that resolve them are recorded at the bottom.

## Goal

1. The checklist is the same on the phone, the tablet and the PC, and a change on one shows up on
   the others without an export/import dance.
2. The player can change the checklist from Telegram instead of opening the app: mark a species
   caught, mark it seen again after a trade, and star or unstar team members.
3. Signing in does not mean running an account system: Google is the identity provider, and the
   owner's Google account is the only account.

## Non-goals

- Multiple users, sharing, or a public leaderboard. One account, several devices.
- Rewriting the offline app. The network-free `index.html` stays as it is unless a decision below
  says otherwise.
- Server-side rendering, a build system beyond the current one, or a bespoke API for reads.

## Constraints the design has to respect

- **The published artifact is network-free on purpose.** `tools/publish.mjs` rejects external
  scripts and stylesheets, images from outside the file, runtime fetch, source maps and unresolved
  build tokens, and the app must work with every network request blocked (there is a test for it).
  Sync therefore either rides in a second, opt-in build or the publisher's rule has to change.
- **The save format is validated and closed.** `references/state-schema.md` applies: the validator
  rejects unknown keys, so any sync metadata is a schema version bump (`v4`) with a lossless
  migration from `v1`-`v3`, not an extra field bolted onto the current shape.
- **A commit cannot contain its own hash**, and `index.html` is a committed build artifact that the
  site serves, so any second artifact has to go through the same build and `build:check` discipline.
- **Anything the player accumulates is migration-sensitive**: statuses, form progress, stars and the
  selected mode all round-trip through export/import today, and must keep doing so.

## Decisions taken (2026-09-18)

Owner's answers to the first grilling round, recorded as settled:

- **One artifact, not two.** A single build ships. It stays offline-first with localStorage as the
  source of truth exactly as today, and sync happens only after the player signs in. A player who
  never signs in must never touch the network — so the publisher's rule gets restated (below) rather
  than the app getting a second file.
- **Merge by record, ordered by the server.** Per-record timestamps merged field by field, with the
  provider's own server-side ordering as the tie-break, so device clock skew cannot silently pick a
  winner.
- **The chat channel is the agent, not a bot.** No second bot and no webhook: the owner talks to
  Hermes in the existing session and a skill performs the change. That removes the public endpoint
  requirement, and with it the whole "which free tier can host a webhook" question — the backend only
  has to do auth, storage and sync.
- **`trade` is sugar for seen.** It puts the species back to Seen and does nothing else. No fourth
  status, no schema change beyond sync metadata.
- **Family use is in scope, not a single account.** A seven-year-old son will use it on his own tablet
  with his own Google account, so the design is multi-account from the start and the merge model has
  to survive two people editing at once.

The event-log question the owner raised (append-only operations ordered by the database, converging
like a CRDT, without bloating storage) is being answered with numbers rather than opinion. The
relevant constraint is not storage size — an event at ~80 bytes a few times a day is under a
megabyte a year — but **per-document read billing**: a design that reads a long log on every device
open spends reads linearly, which Firestore charges for and Postgres-style backends do not.

## Recommended architecture

A static SPA plus a managed backend-as-a-service, with one small serverless function for the chat
channel. Nothing runs on a server we maintain.

```
 phone / tablet / PC
   └─ the app (static, offline-capable, localStorage first)
        └─ auth: Google sign-in via the provider's client SDK   (no account system of ours)
        └─ data: one document per account, holding the whole save
             └─ realtime subscription pushes changes to the other devices

 Telegram
   └─ dedicated bot -> webhook (serverless function, holds the service credentials)
        └─ maps Telegram user id -> account (linked once, by code)
        └─ applies the same state transition the app applies, writes the document
```

Shape of the data, and why this shape:

- The save is tens of kilobytes: 807 statuses, form flags, stars, mode. One document per account is
  therefore cheap (one read to load, one write per change) and needs no schema of ours beyond the
  existing validator.
- Concurrency is the whole difficulty. A device that is offline for a day and then reconnects must
  not clobber another device's recent edits, so a per-record `updatedAt` map travels with the save
  and the client merges field by field before writing. A whole-document last-write-wins is simpler
  and wrong for this use case — the phone would routinely revert the PC.
- Deletes need a tombstone (an explicitly cleared status), or a merge will resurrect a status the
  player deliberately reset. `Reset` and `uncaught` both need a defined meaning once two copies exist.
- Realtime is a bonus, not the load-bearing part: the app is offline-first, so a device that never
  receives a push still converges on the next open.

Chat channel, deliberately dumb:

- A dedicated bot, separate from the agent's own bot, so the checklist's command channel does not
  depend on the agent being up, and the agent's conversations stay out of the player's data path.
- Verbs map onto state that already exists: caught, seen, star, unstar. `trade` is the interesting
  one — it is the transition *out of* caught, and it needs a defined effect on location completion
  and form progress before it is implemented.
- Name resolution is a lookup, not a language model: the app already ships every species name and
  slug and a `normalize()` helper, so `pikachu`, `025` and `Mr. Mime` are all resolvable
  deterministically. An LLM fallback is optional polish, never the mechanism.
- Linking is by one-time code so that a stray Telegram sender cannot write to the owner's checklist.

## Options considered

| Option | What it gives | What it costs | Main risk |
| --- | --- | --- | --- |
| Managed BaaS, client SDK only (Firebase-style) | Google sign-in, realtime, storage, security rules; no server code | Free tier of the provider | Vendor lock-in; the chat webhook still needs a small function |
| Managed Postgres BaaS (Supabase-style) | Google OAuth, realtime, SQL + row-level security | Free tier; you own a schema and policies | More moving parts than the document shape needs |
| Serverless compute + storage (Workers + KV/D1) | Cheapest request pricing, one place for the chat webhook | You write auth and sync yourself | Most code to own |
| Self-hosted (PocketBase-style) on the home NAS | Data never leaves home, no third party, no per-op cost | His hardware, his backups, his uptime; needs remote access for the phone | Reachability: a phone away from home, and a webhook Telegram can call, both need a public path |

The self-hosted row is the one that matches the owner's local-first instincts, and the reachability
problem is solvable (a tunnel, or a remote-access overlay) — but it is the only option where "the
NAS is down" or "the tunnel expired" is a real failure mode for the app.

## Verified facts (checked 2026-09-18)

As published today, which is what the provider decision rests on:

| | Firebase (Spark) | Supabase (Free) | PocketBase self-hosted |
| --- | --- | --- | --- |
| Cost | $0, and no payment method is required | $0; the card requirement is not explicitly documented, so treat it as unverified | $0 for the software, plus his hardware and power |
| Identity | Firebase Auth with Google sign-in from the client SDK, 50,000 MAU free | Supabase Auth with `signInWithOAuth({ provider: 'google' })`, 50,000 MAU free | OAuth2 providers including Google, configured on an auth collection |
| Data | Firestore: 1 GiB, 50,000 reads/day, 20,000 writes/day, 10 GiB/month egress | Postgres: 500 MB, 5 GB/month egress | SQLite under `pb_data`, bounded by the NAS |
| Realtime | Firestore listeners | 200 concurrent connections, 2M messages/month, 256 KB per message | SSE on `/api/realtime` |
| Server code for the chat webhook | **Cloud Functions require Blaze** — billing enabled, though free within 2M invocations/month | **Edge Functions are included on Free** — 500,000 invocations/month | Something must run on the NAS |
| Who owns it | Nobody | Nobody | Patching, TLS, uptime and backups are all his |
| Sharp edge | The webhook cannot be free without enabling billing | Free projects pause after roughly seven days of inactivity, so sync would silently stop until unpaused | Pre-1.0 (v0.40.4) with no compatibility promise across releases, and no official Docker image |

Two consequences worth stating plainly:

- **No option removes server-side code from the chat feature.** Telegram requires an HTTPS webhook,
  so a small function exists in every design. What is optional is *billing* (Supabase Edge Functions
  on the free plan, or a free worker elsewhere) and *ownership*.
- **A hybrid is legitimate**: Firestore plus Firebase Auth on Spark, with the Telegram webhook on a
  free worker outside Firebase, keeps the whole thing at zero cost without enabling billing.

Exposure, if the self-hosted route is chosen: Tailscale Funnel is free on all plans (still labelled
beta) and publishes an HTTPS URL on ports 443, 8443 or 10000, which covers the port Telegram wants.
Cloudflare Tunnel is the alternative and needs a domain. Only the webhook must be public, but the app
needs a reachable URL when the owner is away from home, and a tunnel or access overlay covers both.

Telegram interactivity improves the chat design: bots can attach inline keyboards and edit their own
messages, so the common actions can be taps rather than typed commands, with command text as the
fallback. Guidance is one message per second per chat. A second bot is entirely normal — each token
is independent — and the sender's `User.id` is the stable key that a one-time linking code binds to.

Second batch of answers, same day:

- **The SDK ships inside the artifact, and signing in is what turns sync on.** In signed-in mode the
  app stays offline-first: every change is applied locally and queued, and it syncs when the network
  returns. Nothing may block on the network — no tap gated behind a request.
- **One checklist per person, never shared.** The data belongs to the signed-in account; the same
  account on several devices live-syncs. No cross-account sharing, so there is no membership model,
  no roles, and no shared-record ownership problem.
- **Allowlist by email, and Google sign-in has to be near one-click** in the browser. That is a
  requirement on the provider, not a nicety: a multi-step consent detour is a failure.
- **Records plus a bounded recent log**, which the owner wants to grow into a progression log, undo,
  and possibly a social feed later. The log therefore needs a stable event vocabulary from the first
  release; history added later cannot be retrofitted onto months of unlogged changes.
- **The son may never sign in at all.** If his supervised account cannot complete Google OAuth, his
  tablet just runs the offline app — so offline-only stays a first-class mode, not a degraded one,
  and export/import remains the only backup for that device.

Third batch of answers, same day:

- **The log records progress only** — status, form and star changes, each with actor, device, time and
  before→after — capped at roughly 500 events or 90 days and compacted into the records as it ages.
  Preferences such as the selected mode are not logged. Single-step undo ships in v1 on top of it.
- **Local data is namespaced per account.** A device's existing data is adopted into the account the
  first time one signs in; a different account signing in later gets its own separate space and never
  sees or overwrites the first one's.
- **The backend is Firebase Realtime Database plus Auth on Spark**, with the app owning the durable
  state and the outbox.

### Undo, including undo of a Reset

The owner asked whether undo should store a full pre-reset snapshot locally instead of pushing one to
the database, and whether undo could instead roll back using log entries. Measured sizes for the real
shape (807 species, 412 caught, 180 seen, 25 forms, 5 starred):

```
full save, compact             8,990 B
full save, pretty             12,747 B
a reset's before-image         8,413 B   (the records the reset actually clears)
one ordinary log entry           115 B
500-entry log (the cap)        ~56 KB
Realtime Database Spark: 1 GB stored = 119,437x the full save
```

The snapshot is therefore not "a large amount of data" — but the log-based approach is still the
better design, for reasons of correctness rather than size:

- **A snapshot restore is blunt.** Undoing a reset by restoring the old state would also erase
  anything caught on another device *after* the reset. Applying the inverse per record, under the same
  merge rule, restores only records untouched since the reset and leaves new catches alone.
- **A local-only undo snapshot fails exactly when it is needed.** Clearing site data, switching
  devices or a lost tablet takes the undo data with it. Carried in the log entry, the before-image is
  durable and *any* device can undo, not only the one that pressed Reset.
- **The cost is one larger log entry, not a parallel copy of the state** — about 8 KB once, against
  merging a second full snapshot on every reset.

So: a Reset is logged like any other operation, its entry carries the before-image of what it cleared,
and undo is the inverse of a logged operation. The undo window therefore equals the log retention
window (500 events or 90 days), and an undone record is re-armed by the newer operation that follows.

## Research verdicts (2026-09-18)

**What the community actually uses** (`plans/research/community-sync-2026.md`): Firebase is the
obvious turnkey answer for Google sign-in plus realtime plus offline in one dependency; Supabase is
the strong open/SQL alternative; PocketBase is well liked but is a server to run; Appwrite is
credible with more operational weight; the local-first engines (PowerSync, Electric, InstantDB,
Convex, Jazz, TinyBase) have real interest but less traction and usually another service to run;
Cloudflare's primitives are cheap but not turnkey. Recurring complaints: Firebase billing anxiety and
GCP coupling, Supabase's free-tier pausing, self-hosting burden, and unsolved conflict,
authorization and revocation questions in the sync engines.

**What the numbers say** (`plans/research/backends-free-tiers-2026.md`): Firebase **Realtime Database**
plus Auth on Spark is the only surveyed option that is genuinely zero cost, needs no server code,
requires no card, and — decisively for the ledger idea — **does not bill per document read**.
Firestore on the same plan does bill reads, which is exactly what would penalise replaying a log.
Supabase Free is the strongest SQL alternative but pauses a project after about a week without
activity.

**Three findings that shape the design:**

- **The son's sign-in is a gate, not a detail.** Google does not document a guarantee that an
  under-13 Family Link (supervised) account can complete an arbitrary third-party OAuth flow; it
  documents parental control of third-party access, and user reports exist of supervised accounts
  being refused. This must be tested with the real account, and the design needs a fallback identity
  for him that is not Google. The gate applies to every Google-based option including Drive, so
  Drive is not an escape from it.
- **Google Drive as the database is viable but weak.** A normal shared Drive file (not
  `appDataFolder`, which cannot be shared at all) can back a family checklist, using the file
  revision as a conditional-write precondition. But cross-device notification needs push, push needs
  a webhook, and a static SPA has none — so the app would poll, and Drive revisions must never be
  used as the event log. A fallback, not the recommended path.
- **A full CRDT is not justified.** Versioned records with server-assigned ordering cover a handful
  of users and occasional conflicts; the research advice is explicitly not to adopt Automerge or Yjs
  merely because the app is offline-first.

## Verified Firebase behaviour (2026-09-18)

Checked against official documentation, because the provider recommendation rests on it:

- **Writes queue and replay while the tab lives, but the Realtime Database web cache is memory-only.**
  A write applies locally at once and synchronises on reconnect with no replay code of ours, and
  `/.info/connected` reports connectivity — but Firebase states the web APIs do not persist data
  offline outside the session, so a reload or a crash loses anything not yet accepted. Firestore is
  the opposite: its persistent cache is IndexedDB-backed and survives reloads.
- **Consequence, and it is not optional: the app owns the durable state *and* the outbox.** The
  localStorage save stays the source of truth and gains a pending-operations queue flushed on
  reconnect. This is required with any provider anyway, because the per-record merge is ours, so the
  SDK is a transport and never the storage of record.
- **Signing in stays signed in.** Auth's web default (LOCAL) persists across browser restarts, scoped
  to the origin. Google One Tap provides the near-one-click Chrome path, with a fallback button,
  because FedCM behaviour depends on browser version, privacy settings and account state.
- **The allowlist lives in the security rules, not at sign-in.** Rules can read `auth.token.email`,
  `auth.token.email_verified` and `auth.uid` per path. Blocking authentication itself needs Identity
  Platform with Cloud Functions, which needs Blaze and is out of scope. So an uninvited Google account
  can still authenticate; it must then be told, in the UI, that there is no checklist for it here.
- **Spark is cardless and cannot surprise-bill.** Realtime Database on Spark: 1 GB stored, 10 GB/month
  download (about 360 MB/day), 100 simultaneous connections — a connection is a tab or a device, so a
  family is nowhere near the cap. Over-quota is capped rather than converted into charges, and no
  inactivity pause or deletion is documented. Keep independent exports anyway, because "not
  documented" is not a guarantee.
- **Leaving is possible, not painless.** The database exports as JSON from the console or over REST,
  and Auth accounts export through the CLI with UIDs preserved on re-import; the rules, claims and
  sync behaviour would all have to be rebuilt by hand elsewhere.

## Owner setup checklist (Firebase)

What has to exist before Stage 1 can be built or tested, all inside the free Spark plan. Nothing here
needs a payment method, and billing must stay **off** — enabling Blaze would also enable Cloud
Functions, which this design deliberately does not use.

1. Create a Firebase project. Decline analytics; keep billing off.
2. Create a **Realtime Database** (the region cannot be changed later, so pick it deliberately).
3. Add a **Web app** to the project and copy its config object. This config is public by design — it
   ships inside the artifact either way — so it is not a secret and can live in the repository.
4. Enable **Google** as a sign-in provider. Optionally also email/password, which is how the agent
   would authenticate in Stage 2.
5. Add the authorised domains: the GitHub Pages host and the local dev host, or sign-in fails in both.
6. Paste the security rules (written during Stage 1) containing the email allowlist.
7. Tell me the allowlist emails and the database URL.

Credential handling: the web config is not a secret. The only secret is whatever the agent uses in
Stage 2 — either a dedicated allowlisted user whose refresh token sits in `/opt/data/.env`, or a
service-account key file. Both belong in `.env` or at a path I name, never in chat, and Stage 1 does
not need either one.

## How the client keeps state (built 2026-09-18)

The player's save is untouched, so sync needed no schema bump: per-record ordering is replica
bookkeeping, rebuildable by construction, and it would turn an 8.8 KB backup into 25 KB of uids and
timestamps. Sync gets its own localStorage document (`pokemon-checklist-sync-v1`) holding the device
id, the signed-in account and `base` — the last document the server confirmed.

**There is no operation queue, deliberately.** Pending work is *derived*:
`diff(base, entriesFromState(save))`. Retrying a failed publish is therefore idempotent, a reload
loses nothing, and the server's own echo empties the diff — there is no acknowledgement bookkeeping
to get wrong, and no queue that can drift out of step with the save.

What a device shows is `base` with unpublished local edits layered on top. That layering is not
cosmetic: a local edit waiting to be published will be stamped by the server *later* than anything
already there, so dropping it because a remote change arrived first would discard a change that has
legitimately won.

Undo follows the same shape. A `set` inverts through its own `from` value; a `reset` carries the
before-image of what it cleared, and undo restores only the records the reset still owns — a catch
made on another device after the reset survives the undo instead of being silently deleted.

Built and tested so far (`src/sync/`): the merge layer (`records.ts`, 19 tests) and the store plus
derived pending (`outbox.ts`, 14 tests). Next: the engine that wires them to the database, per-account
save namespacing in `state.ts`, and the sign-in affordance. The Firebase SDK stays unimported until
that lands, so the deployed artifact is still byte-identical to the offline-only build.

## Staged plan

- **Stage 1 — one save, several devices.** Schema v4 with sync metadata, provider choice, Google
  sign-in restricted to the owner, the sync-enabled build alongside the offline one, realtime
  updates, and a defined merge for offline edits.
- **Stage 2 — the chat channel.** Dedicated bot, webhook function, one-time-code linking, the verb
  set, deterministic name matching, confirmation replies that quote progress.
- **Stage 3 — polish.** Form-level commands, undo, a "what changed recently" view, and whatever the
  grilling surfaces that is worth having.

## Open decisions (grilling rounds)

Round 1, asked: artifact shape, conflict model, chat channel identity, trade semantics, sign-in
allowlist. Round 1b, asked alongside it now that the numbers are in: which provider (and therefore
which migration and backup story), and whether the chat is taps, typed commands, or both. Later:
what `Reset` means when the data lives in two places, how the offline artifact advertises the synced
one, and what undo looks like through a bot.

Superseded by the owner's answers: the chat is the agent, not a bot; `trade` is sugar for seen; the
publisher rule is restated rather than a second build added; the provider decision narrowed to
Realtime Database versus Supabase once the son's sign-in path is settled.
All questions raised have been answered. Settled: one artifact with the SDK bundled and sign-in as
the sync switch; per-person checklists with multi-device live sync; allowlist by email with One Tap
plus a fallback; records plus a bounded log; the son offline-only; log-derived undo including undo of
a Reset; Firebase Realtime Database plus Auth on Spark. Next step is the Stage 1 build plan rather
than more questions — the remaining uncertainty is implementation detail (bundle size, merge tests,
the publisher rule wording), not direction.

Superseded history follows, kept so the reasoning is not lost:

