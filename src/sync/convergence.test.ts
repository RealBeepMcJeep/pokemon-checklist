import { describe, expect, it } from "vitest";
import { cycleStatus } from "../domain";
import type { SavedState, Status } from "../types";
import {
  TOMBSTONE,
  mergeDocument,
  speciesKey,
  stateFromDocument,
  type RecordEntry,
  type RecordKey,
  type SyncDocument,
} from "./records";
import {
  emptyDocument,
  pendingEntries,
  saveFromView,
  viewWithPending,
} from "./outbox";

/**
 * Two devices against one shared server, using the real merge and pending logic.
 *
 * The engine's I/O is thin on purpose, so what actually decides whether offline
 * edits reconcile is the policy in `records.ts` and `outbox.ts`. This harness runs
 * that policy the way the engine does — publish the diff, let the SERVER stamp the
 * time, then merge what comes back — so the awkward interleavings can be asserted
 * here instead of only being tried by hand on two phones.
 */

const POKEMON = new Set([1, 25, 150]);
const FORMS = new Set<string>();

interface Device {
  name: string;
  uid: string;
  save: SavedState;
  base: SyncDocument;
}

interface Server {
  records: Record<RecordKey, RecordEntry>;
  /** Server time, advancing per write so ordering is never in doubt. */
  clock: number;
}

function device(name: string): Device {
  return {
    name,
    uid: `uid-${name}`,
    save: {
      schemaVersion: 3,
      species: {},
      forms: {},
      starred: [],
      settings: { forms: false, mode: "moon" },
    },
    base: emptyDocument(),
  };
}

const server = (): Server => ({ records: {}, clock: 1_000 });

/** A local tap: the save changes first, exactly as the app does it. */
function tap(target: Device, id: number): void {
  const key = String(id);
  const current = target.save.species[key] ?? "none";
  const next = cycleStatus(current as Status);
  const species = { ...target.save.species };
  if (next === "none") delete species[key];
  else species[key] = next;
  target.save = { ...target.save, species };
}

function setStatus(target: Device, id: number, status: Status): void {
  const species = { ...target.save.species };
  if (status === "none") delete species[String(id)];
  else species[String(id)] = status;
  target.save = { ...target.save, species };
}

/** Publish the derived diff; the server stamps the time it received it. */
function publish(target: Device, hub: Server): void {
  const pending = pendingEntries(target.base, target.save, hub.clock, target.uid);
  if (Object.keys(pending).length === 0) return;
  hub.clock += 1;
  for (const [key, entry] of Object.entries(pending)) {
    hub.records[key] = { s: entry.s, at: hub.clock, by: target.uid };
  }
  receive(target, hub);
}

/** What the engine does in its subscription callback. */
function receive(target: Device, hub: Server): void {
  // Mirror the engine exactly: what the device owes is judged against the document
  // it had confirmed BEFORE the message, then filtered against the merged one, so a
  // server-side change is never mistaken for an unpublished local edit.
  const owedBefore = pendingEntries(
    target.base,
    target.save,
    hub.clock,
    target.uid,
  );
  target.base = mergeDocument(target.base, {
    schema: 1,
    records: { ...hub.records },
    updatedAt: hub.clock,
  });
  const owed: Record<RecordKey, RecordEntry> = {};
  for (const [key, entry] of Object.entries(owedBefore)) {
    if (target.base.records[key]?.s !== entry.s) owed[key] = entry;
  }
  target.save = saveFromView(
    viewWithPending(target.base, owed),
    POKEMON,
    FORMS,
  );
}

describe("two devices reconciling", () => {
  it("carries an offline catch across when the device reconnects", () => {
    const phone = device("phone");
    const tablet = device("tablet");
    const hub = server();

    // The phone is offline: the tap lands locally and nothing else happens.
    tap(phone, 25);
    expect(phone.save.species["25"]).toBe("caught");

    // Reconnecting publishes it, and the other device picks it up.
    publish(phone, hub);
    receive(tablet, hub);
    expect(tablet.save.species["25"]).toBe("caught");
  });

  it("keeps unrelated offline edits from both devices", () => {
    const phone = device("phone");
    const tablet = device("tablet");
    const hub = server();

    publish(phone, hub);
    receive(tablet, hub);

    tap(phone, 25); // offline on the phone
    tap(tablet, 150); // offline on the tablet
    publish(phone, hub);
    publish(tablet, hub);
    receive(phone, hub);
    receive(tablet, hub);

    expect(phone.save.species["25"]).toBe("caught");
    expect(phone.save.species["150"]).toBe("caught");
    expect(tablet.save.species["25"]).toBe("caught");
    expect(tablet.save.species["150"]).toBe("caught");
  });

  it("resolves the same record by which write reached the server later", () => {
    const phone = device("phone");
    const tablet = device("tablet");
    const hub = server();

    publish(phone, hub);
    receive(tablet, hub);

    tap(phone, 25); // phone goes offline with "caught"
    setStatus(tablet, 25, "seen"); // tablet edits the same species and syncs first
    publish(tablet, hub);

    publish(phone, hub); // the phone's write lands later, so it wins
    receive(tablet, hub);

    expect(phone.save.species["25"]).toBe("caught");
    expect(tablet.save.species["25"]).toBe("caught");
  });

  it("does not resurrect a species the player cleared after the other device saw it", () => {
    const phone = device("phone");
    const tablet = device("tablet");
    const hub = server();

    tap(phone, 25);
    publish(phone, hub);
    receive(tablet, hub);

    // The phone clears it; the tablet must not hold it any more.
    setStatus(phone, 25, "none");
    publish(phone, hub);
    receive(tablet, hub);

    expect(tablet.save.species["25"]).toBeUndefined();
    // And a later edit on the tablet does not bring the old value back.
    publish(tablet, hub);
    expect(hub.records[speciesKey(25)].s).toBe(TOMBSTONE);
  });
});

describe("convergence holds whatever the interleaving", () => {
  it("ends with both devices holding the same checklist", () => {
    const phone = device("phone");
    const tablet = device("tablet");
    const hub = server();

    // A deliberately awkward script: alternating offline edits, out-of-order
    // publishes, and a receive that lands between two local taps.
    tap(phone, 1);
    tap(tablet, 1);
    publish(tablet, hub);
    tap(phone, 25);
    publish(phone, hub);
    receive(tablet, hub);
    tap(tablet, 150);
    tap(phone, 150);
    publish(phone, hub);
    receive(phone, hub);
    publish(tablet, hub);
    receive(phone, hub);
    receive(tablet, hub);

    // Both devices must now present the same document and the same checklist.
    const view = (target: Device) =>
      mergeDocument(
        target.base,
        viewWithPending(
          target.base,
          pendingEntries(target.base, target.save, hub.clock, target.uid),
        ),
      );
    expect(view(phone).records).toEqual(view(tablet).records);
    expect(stateFromDocument(view(phone), POKEMON, FORMS)).toEqual(
      stateFromDocument(view(tablet), POKEMON, FORMS),
    );
  });
});
