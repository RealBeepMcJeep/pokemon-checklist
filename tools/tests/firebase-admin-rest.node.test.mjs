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

test("writes a regional favorite with an off before-image and preserves ownership", async () => {
  const records = { "species:52": { s: "caught", at: 1, by: "fixture" } };
  let written;
  const requestFn = async (_path, init) => {
    if (init.method === "PUT") { written = JSON.parse(init.body); return null; }
    return { body: { state: { records } }, etag: "fixture-etag" };
  };
  let result = null;
  try { result = await applyRecords("fixture-account", { "starform:52:alolan": "on" }, { requestFn }); }
  catch (error) { assert.match(error.message, /invalid record key/); }
  assert.notEqual(result, null, "regional favorite key must be accepted");
  assert.deepEqual(result.changes, [{ key: "starform:52:alolan", from: "off", to: "on" }]);
  assert.deepEqual(written.state.records["species:52"], records["species:52"]);
});

test("unresolved favorite flags are strict regional on/off records with off before-images", async () => {
  let written; let result = null;
  const records = { "species:52": { s: "caught", at: 1, by: "fixture" } };
  const requestFn = async (_path, init) => {
    if (init.method === "PUT") { written = JSON.parse(init.body); return null; }
    return { body: { state: { records } }, etag: "fixture-etag" };
  };
  try { result = await applyRecords("fixture-account", { "starlegacy:52": "on" }, { requestFn }); }
  catch (error) { assert.match(error.message, /invalid record key/); }
  assert.notEqual(result, null, "explicit unresolved-intent flag must be admitted");
  assert.deepEqual(result.changes, [{ key: "starlegacy:52", from: "off", to: "on" }]);
  assert.deepEqual(written.state.records["species:52"], records["species:52"]);
  for (const key of ["starlegacy:0", "starlegacy:052", "starlegacy:25", "starlegacy:808", "starlegacy:52/extra", "starlegacy:52?query"])
    assert.throws(() => validateRecordMap({ [key]: "on" }));
  assert.throws(() => validateRecordMap({ "starlegacy:52": "caught" }));
});

test("regional favorite keys and values fail closed", () => {
  for (const key of ["starform:25:kanto", "starform:0:alolan", "starform:052:alolan", "starform:808:alolan", "starform:52:future", "starform:52:alolan/extra", "starform:52:alolan?query"]) {
    assert.throws(() => validateRecordMap({ [key]: "on" }));
  }
  assert.throws(() => validateRecordMap({ "starform:52:alolan": "caught" }));
});

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

test("rejects an unresolved server-value sentinel as a record's at", () => {
  // A real Firebase GET always resolves {".sv": "timestamp"} to a number before
  // returning it, so a record still carrying the raw sentinel is never valid.
  assert.throws(
    () => validateRecordMap(
      { "species:25": { s: "caught", at: { ".sv": "timestamp" } } },
      { entries: true },
    ),
    /invalid at/,
  );
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
  // The record entry's `by` must match every other writer (the log entry
  // above, and the browser's own engine.ts): a bare uid, no "chat:" prefix.
  const recordKey = Object.keys(payload).find((key) => key.startsWith("state/records/"));
  assert.equal(payload[recordKey].by, "abc:123");
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

test("rejects an expected-old mismatch from the ETag snapshot without writing", async () => {
  const calls = [];
  const requestFn = async (path, init, options) => {
    calls.push({ path, init, options });
    return {
      body: { state: { records: { "species:25": { s: "seen" } } } },
      etag: "etag-1",
    };
  };

  await assert.rejects(
    applyRecords("abc:123", { "species:25": "caught" }, {
      expected: { "species:25": "none" }, requestFn,
    }),
    /status precondition failed.*species:25/,
  );
  assert.equal(calls.filter(({ init }) => init.method === "PUT").length, 0);
});

test("rechecks the expected-old status after an ETag conflict", async () => {
  const calls = [];
  let reads = 0;
  const requestFn = async (path, init, options) => {
    calls.push({ path, init, options });
    if (init.method === "PUT") {
      const error = new Error("precondition failed");
      error.status = 412;
      throw error;
    }
    reads += 1;
    return reads === 1
      ? { body: { state: { records: { "species:25": { s: "caught" } } } }, etag: "etag-1" }
      : { body: { state: { records: { "species:25": { s: "seen" } } } }, etag: "etag-2" };
  };

  await assert.rejects(
    applyRecords("abc:123", { "species:25": "seen" }, {
      expected: { "species:25": "caught" }, requestFn,
    }),
    /status precondition failed.*species:25/,
  );
  assert.equal(reads, 2);
  assert.equal(calls.filter(({ init }) => init.method === "PUT").length, 1);
});

test("a concurrent opposite-form catch aborts a stale aggregate downgrade after ETag conflict", async () => {
  let reads = 0, writes = 0;
  const requestFn = async (_path, init) => {
    if (init.method === "PUT") {
      writes += 1;
      const conflict = new Error("precondition failed");
      conflict.status = 412;
      throw conflict;
    }
    reads += 1;
    const records = { "species:26": { s: "caught" }, "form:26:alolan": { s: "caught" } };
    if (reads > 1) records["form:26:kanto"] = { s: "caught" };
    return { body: { state: { records } }, etag: `fixture-${reads}` };
  };
  const desired = { "species:26": "seen", "form:26:alolan": "seen", "form:26:kanto": "none", "setting:forms": "off" };
  const expected = { "species:26": "caught", "form:26:alolan": "caught", "form:26:kanto": "none", "setting:forms": "off" };
  await assert.rejects(applyRecords("fixture-account", desired, { expected, requestFn }), /status precondition failed.*form:26:kanto/);
  assert.equal(reads, 2);
  assert.equal(writes, 1, "stale aggregate must never be retried over the opposite-form catch");
});
