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

**Facts still being verified** (dispatch in flight, not assumptions): current free-tier limits and
Google sign-in support for each managed option, whether the free tiers need a credit card, PocketBase's
current OAuth and realtime support, the rules for exposing a home service as a public webhook, and the
Telegram Bot API's webhook, rate-limit and identity behaviour. The provider decision stays open until
those come back.

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
allowlist. Round 2 (blocked on the verification above): which provider, and therefore which
migration and backup story. Later: what `Reset` means when data is in two places, and how the
offline artifact advertises the synced one.
