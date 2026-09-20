import assert from "node:assert/strict";
import test from "node:test";
import {
  applyRecords,
  buildApplyPayload,
  keyKind,
  mergeAccountSnapshot,
  validateRecordMap,
  validateUid,
} from "../firebase-admin-rest.mjs";

test("validates Firebase-safe account and record keys", () => {
  assert.equal(validateUid("abc:123"), "abc:123");
  for (const value of ["", "a/b", "a.b", "a#b", "a$b", "a[b", "a]b", "a?b", "a#b", "a%b"]) {
    assert.throws(() => validateUid(value), /uid must be/);
  }
  assert.throws(() => validateUid("x".repeat(129)), /uid must be/);
  assert.equal(keyKind("species:807"), "species");
  assert.equal(keyKind("form:mr-mime"), "form");
  assert.throws(() => keyKind("species:808"), /National Dex/);
  assert.throws(() => keyKind("form:bad?key"), /Firebase/);
  assert.throws(() => validateRecordMap({ "species:808": "caught" }), /National Dex/);
});

test("uses a process-safe log id and preserves full change provenance", () => {
  const payload = buildApplyPayload(
    "abc:123",
    [{ key: "species:25", from: "seen", to: "caught" }],
    { now: 10, idFactory: () => "unique-test-id", note: "chat" },
  );
  const logKey = Object.keys(payload).find((key) => key.startsWith("log/"));
  assert.equal(logKey, "log/chat-10-unique-test-id-000");
  assert.deepEqual(payload[logKey], {
    op: "set", at: { ".sv": "timestamp" }, by: "abc:123", via: "chat",
    key: "species:25", from: "seen", to: "caught", note: "chat",
  });
});

test("merges updates into a cloned account without losing unknown data or logs", () => {
  const snapshot = {
    profile: { nickname: "unknown-but-preserved" },
    state: {
      schema: 1,
      records: { "species:25": { s: "caught", at: 1, by: "device" } },
      extra: ["keep me"],
    },
    log: { existing: { op: "set", key: "species:1" } },
  };
  const before = structuredClone(snapshot);
  const updates = buildApplyPayload(
    "abc:123",
    [{ key: "species:25", from: "caught", to: "seen" }],
    { now: 10, idFactory: () => "new-log" },
  );

  const merged = mergeAccountSnapshot(snapshot, updates);
  assert.deepEqual(snapshot, before);
  assert.notEqual(merged, snapshot);
  assert.deepEqual(merged.profile, snapshot.profile);
  assert.deepEqual(merged.state.extra, ["keep me"]);
  assert.deepEqual(merged.log.existing, snapshot.log.existing);
  assert.equal(merged.state.records["species:25"].s, "seen");
  assert.deepEqual(merged.state.records["species:25"].at, { ".sv": "timestamp" });
  assert.equal(merged.log["chat-10-new-log-000"].to, "seen");
});

test("retries a full conditional PUT from a fresh account snapshot", async () => {
  const calls = [];
  let read = 0;
  const requestFn = async (path, init, options) => {
    calls.push({ path, init, options });
    if (init.method === "PUT") {
      if (read === 1) {
        const error = new Error("precondition failed");
        error.status = 412;
        throw error;
      }
      return null;
    }
    read += 1;
    return read === 1
      ? {
          body: {
            keep: { unknown: true },
            state: { records: { "species:25": { s: "caught" } } },
            log: { existing: { op: "old" } },
          },
          etag: "etag-1",
        }
      : {
          body: {
            keep: { unknown: "changed" },
            state: { records: { "species:25": { s: "caught" } } },
            log: { existing: { op: "old" }, other: { op: "also-old" } },
          },
          etag: "etag-2",
        };
  };

  const result = await applyRecords("abc:123", { "species:25": "seen" }, { requestFn });
  assert.equal(result.changes[0].from, "caught");
  const writes = calls.filter(({ init }) => init.method === "PUT");
  assert.equal(writes.length, 2);
  assert.equal(writes[0].init.headers["if-match"], "etag-1");
  assert.equal(writes[1].init.headers["if-match"], "etag-2");
  assert.match(writes[1].path, /\/users\/abc%3A123$/);

  const finalAccount = JSON.parse(writes[1].init.body);
  assert.deepEqual(finalAccount.keep, { unknown: "changed" });
  assert.deepEqual(finalAccount.log.existing, { op: "old" });
  assert.deepEqual(finalAccount.log.other, { op: "also-old" });
  assert.equal(finalAccount.state.records["species:25"].s, "seen");
  const newLogs = Object.keys(finalAccount.log).filter((key) => key.startsWith("chat-"));
  assert.equal(newLogs.length, 1);
  assert.equal(finalAccount.log[newLogs[0]].from, "caught");
  assert.equal(finalAccount.log[newLogs[0]].to, "seen");
});
