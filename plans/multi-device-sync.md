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
