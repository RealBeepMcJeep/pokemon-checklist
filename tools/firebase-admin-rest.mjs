#!/usr/bin/env node
/**
 * Realtime Database access for the chat channel, using a service account.
 *
 * The service account is a PROJECT credential, separate from any person's Google
 * account, and it bypasses the database rules the way a server credential should.
 * It must live OUTSIDE this repository, which is public: the default location is
 * the retained Hermes dataset, and this tool refuses to run if the key is inside
 * the repo tree at all.
 *
 * No dependencies: the RS256 JWT is signed with node's own crypto.
 *
 *   node tools/firebase-admin-rest.mjs --accounts
 *   node tools/firebase-admin-rest.mjs --read /users
 *   node tools/firebase-admin-rest.mjs --apply --uid <uid> --record '{"species:25":"caught"}'
 */
import { createSign, randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import { dirname, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const REPO = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const DATABASE_URL = "https://pokemon-checklist-8c75f-default-rtdb.firebaseio.com";
const KEY_PATH =
  process.env.FIREBASE_SERVICE_ACCOUNT ?? "/opt/data/firebase/service-account.json";
const STATUS_VALUES = new Set(["none", "seen", "caught"]);
const STAR_VALUES = new Set(["on", "off"]);
const MODE_VALUES = new Set(["photonic-prismatic", "sun", "moon", "ultra-sun", "ultra-moon"]);
const NATIONAL_DEX_MAX = 807;
const MAX_UID_LENGTH = 128;
const MAX_APPLY_RETRIES = 3;
const KEY_RE = /^(species|star):([1-9][0-9]*)$/;
const FIREBASE_INVALID_PATH_CHARACTER = /[.#$\/\[\]\?#%]/;

function loadKey() {
  const path = resolve(KEY_PATH);
  if (path === REPO || path.startsWith(REPO + sep)) {
    throw new Error(
      `Refusing to read a service-account key from inside the repository (${path}). ` +
        "Keep it in /opt/data/firebase/ or set FIREBASE_SERVICE_ACCOUNT.",
    );
  }
  const key = JSON.parse(readFileSync(path, "utf8"));
  for (const field of ["client_email", "private_key", "token_uri"]) {
    if (!key[field]) throw new Error(`Service account is missing ${field}`);
  }
  return key;
}

const base64url = (input) =>
  Buffer.from(input).toString("base64").replace(/=+$/, "").replace(/\+/g, "-").replace(/\//g, "_");

let cached = null;

/** Mint a bearer token from the service account, cached for its lifetime. */
export async function accessToken() {
  if (cached && cached.expires > Date.now() + 60_000) return cached.token;
  const key = loadKey();
  const issued = Math.floor(Date.now() / 1000);
  const claims = {
    iss: key.client_email,
    scope:
      "https://www.googleapis.com/auth/firebase.database https://www.googleapis.com/auth/userinfo.email",
    aud: key.token_uri,
    iat: issued,
    exp: issued + 3600,
  };
  const signing = `${base64url(JSON.stringify({ alg: "RS256", typ: "JWT" }))}.${base64url(
    JSON.stringify(claims),
  )}`;
  const signature = createSign("RSA-SHA256").update(signing).sign(key.private_key);
  const assertion = `${signing}.${base64url(signature)}`;

  const response = await fetch(key.token_uri, {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "urn:ietf:params:oauth:grant-type:jwt-bearer",
      assertion,
    }),
  });
  const payload = await response.json();
  if (!payload.access_token) {
    throw new Error(`Token exchange failed: ${payload.error_description ?? payload.error}`);
  }
  cached = { token: payload.access_token, expires: Date.now() + payload.expires_in * 1000 };
  return cached.token;
}

export class FirebaseHttpError extends Error {
  constructor(status, body) {
    super(`${status} ${body.slice(0, 200)}`);
    this.name = "FirebaseHttpError";
    this.status = status;
  }
}

async function request(path, init = {}, { includeResponse = false } = {}) {
  const token = await accessToken();
  const response = await fetch(`${DATABASE_URL}${path}.json`, {
    ...init,
    headers: {
      authorization: `Bearer ${token}`,
      "content-type": "application/json",
      ...(init.headers ?? {}),
    },
  });
  const body = await response.text();
  if (!response.ok) throw new FirebaseHttpError(response.status, body);
  const parsed = body ? JSON.parse(body) : null;
  return includeResponse
    ? { body: parsed, etag: response.headers.get("etag") }
    : parsed;
}

export const readPath = (path) => request(path);
export const readUserRecords = (uid) =>
  request(`/users/${encodedUid(uid)}/state/records`);

/**
 * Stamp a write with the server's own clock. The REST API spells the sentinel
 * `{".sv":"timestamp"}`, which is how the app's ordering stays authoritative even
 * when the write comes from here rather than from a phone.
 */
export const SERVER_TIME = { ".sv": "timestamp" };

export function keyKind(key) {
  if (typeof key !== "string") throw new Error("record keys must be strings");
  if (FIREBASE_INVALID_PATH_CHARACTER.test(key)) {
    throw new Error(`invalid Firebase record key: ${key}`);
  }
  const match = KEY_RE.exec(key);
  if (match) {
    const speciesId = Number(match[2]);
    if (speciesId > NATIONAL_DEX_MAX) {
      throw new Error(`record key is outside National Dex 1..${NATIONAL_DEX_MAX}: ${key}`);
    }
    return match[1];
  }
  if (/^form:[^/]+$/.test(key)) return "form";
  if (key === "setting:mode") return "setting:mode";
  if (key === "setting:forms") return "setting:forms";
  throw new Error(`invalid record key: ${key}`);
}

function allowedValues(kind) {
  if (kind === "species" || kind === "form") return STATUS_VALUES;
  if (kind === "star" || kind === "setting:forms") return STAR_VALUES;
  if (kind === "setting:mode") return MODE_VALUES;
  throw new Error(`invalid record kind: ${kind}`);
}

export function validateRecordMap(records, { entries = false } = {}) {
  if (records === null || records === undefined) return {};
  if (typeof records !== "object" || Array.isArray(records)) {
    throw new Error("records must be an object or null");
  }
  const checked = {};
  for (const [key, raw] of Object.entries(records)) {
    const kind = keyKind(key);
    if (entries) {
      if (typeof raw !== "object" || raw === null || Array.isArray(raw)) {
        throw new Error(`record ${key} must be an object`);
      }
      const fields = Object.keys(raw);
      if (fields.some((field) => !["s", "at", "by"].includes(field))) {
        throw new Error(`record ${key} has unknown fields`);
      }
      if (typeof raw.s !== "string" || !allowedValues(kind).has(raw.s)) {
        throw new Error(`record ${key} has invalid value`);
      }
      if ("at" in raw && typeof raw.at !== "number" &&
          !(raw.at && raw.at[".sv"] === "timestamp")) {
        throw new Error(`record ${key} has invalid at`);
      }
      if ("by" in raw && typeof raw.by !== "string") {
        throw new Error(`record ${key} has invalid by`);
      }
      checked[key] = raw;
    } else {
      if (typeof raw !== "string" || !allowedValues(kind).has(raw)) {
        throw new Error(`record ${key} has invalid value`);
      }
      checked[key] = raw;
    }
  }
  return checked;
}

function emptyValue(key) {
  return key.startsWith("star:") || key === "setting:forms" ? "off" : "none";
}

export function validateUid(uid) {
  if (
    typeof uid !== "string" ||
    uid.length < 1 ||
    uid.length > MAX_UID_LENGTH ||
    FIREBASE_INVALID_PATH_CHARACTER.test(uid)
  ) {
    throw new Error(
      `uid must be 1..${MAX_UID_LENGTH} characters and contain no Firebase path/query delimiters`,
    );
  }
  return uid;
}

function encodedUid(uid) {
  validateUid(uid);
  return encodeURIComponent(uid);
}

export function recordChanges(current, requested) {
  const changes = [];
  for (const [key, to] of Object.entries(requested)) {
    const from = current[key]?.s ?? emptyValue(key);
    if (from !== to) changes.push({ key, from, to });
  }
  return changes;
}

export function buildApplyPayload(uid, changes, { note = "", now = Date.now(), idFactory = randomUUID } = {}) {
  validateUid(uid);
  const payload = { "state/schema": 1, "state/updatedAt": SERVER_TIME };
  const logPrefix = `chat-${now}-${idFactory()}`;
  for (const [index, change] of changes.entries()) {
    payload[`state/records/${change.key}`] = {
      s: change.to,
      at: SERVER_TIME,
      by: `chat:${uid}`,
    };
    payload[`log/${logPrefix}-${String(index).padStart(3, "0")}`] = {
      op: "set",
      at: SERVER_TIME,
      by: uid,
      via: "chat",
      key: change.key,
      from: change.from,
      to: change.to,
      note,
    };
  }
  return payload;
}

function setNestedValue(target, path, value) {
  const parts = path.split("/");
  if (parts.some((part) => !part)) throw new Error(`invalid update path: ${path}`);
  let cursor = target;
  for (const part of parts.slice(0, -1)) {
    const existing = cursor[part];
    if (existing === undefined || existing === null) {
      cursor[part] = {};
    } else if (typeof existing !== "object" || Array.isArray(existing)) {
      throw new Error(`cannot merge update through non-object path: ${path}`);
    }
    cursor = cursor[part];
  }
  cursor[parts.at(-1)] = structuredClone(value);
}

/** Apply a Firebase multi-location update to a cloned full account snapshot. */
export function mergeAccountSnapshot(snapshot, updates) {
  const account = snapshot === null || snapshot === undefined ? {} : structuredClone(snapshot);
  if (typeof account !== "object" || Array.isArray(account)) {
    throw new Error("Firebase account snapshot must be an object or null");
  }
  for (const [path, value] of Object.entries(updates)) {
    setNestedValue(account, path, value);
  }
  return account;
}

function accountRecords(snapshot) {
  if (snapshot === null || snapshot === undefined) return {};
  if (typeof snapshot !== "object" || Array.isArray(snapshot)) {
    throw new Error("Firebase account snapshot must be an object or null");
  }
  const state = snapshot.state;
  if (state !== undefined && (state === null || typeof state !== "object" || Array.isArray(state))) {
    throw new Error("Firebase account state must be an object or null");
  }
  return validateRecordMap(state?.records, { entries: true });
}

/**
 * Apply one validated record patch against one current account snapshot.
 * Firebase's ETag precondition protects a complete account-subtree PUT, so the
 * `from` values and state/log update stay tied to the same snapshot while all
 * unrelated account data is preserved. `requestFn` is an injectable test seam.
 */
export async function applyRecords(
  uid,
  records,
  { note = "", maxRetries = MAX_APPLY_RETRIES, requestFn = request } = {},
) {
  validateUid(uid);
  const requested = validateRecordMap(records);
  if (!Number.isInteger(maxRetries) || maxRetries < 1) {
    throw new Error("maxRetries must be a positive integer");
  }
  const path = `/users/${encodedUid(uid)}`;

  for (let attempt = 1; attempt <= maxRetries; attempt += 1) {
    const snapshot = await requestFn(
      path,
      { headers: { "X-Firebase-ETag": "true" } },
      { includeResponse: true },
    );
    const current = accountRecords(snapshot?.body);
    const changes = recordChanges(current, requested);
    if (!changes.length) return { ok: true, changed: false, changes: [] };
    if (!snapshot?.etag) throw new Error("Firebase account read did not return an ETag");

    const payload = buildApplyPayload(uid, changes, { note });
    const merged = mergeAccountSnapshot(snapshot.body, payload);
    try {
      await requestFn(
        path,
        {
          method: "PUT",
          headers: { "if-match": snapshot.etag },
          body: JSON.stringify(merged),
        },
        { includeResponse: false },
      );
      return { ok: true, changed: true, changes };
    } catch (error) {
      if (error?.status !== 412) throw error;
      if (attempt === maxRetries) {
        throw new Error(`Firebase account changed during apply; exhausted ${maxRetries} retries`);
      }
    }
  }
  throw new Error("Firebase apply retry loop terminated unexpectedly");
}

export const accounts = async () => Object.keys((await readPath("/users")) ?? {});

function parseArgs(argv) {
  const args = { _: [] };
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (token.startsWith("--")) {
      const name = token.slice(2);
      const next = argv[index + 1];
      if (next && !next.startsWith("--")) {
        args[name] = next;
        index += 1;
      } else {
        args[name] = true;
      }
    } else {
      args._.push(token);
    }
  }
  return args;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.accounts) {
    console.log(JSON.stringify(await accounts(), null, 2));
    return;
  }
  if (args["read-records"]) {
    if (!args.uid) throw new Error("--read-records needs --uid");
    console.log(JSON.stringify(await readUserRecords(String(args.uid)), null, 2));
    return;
  }
  if (args.read) {
    console.log(JSON.stringify(await readPath(String(args.read)), null, 2));
    return;
  }
  // Kept only as a gated compatibility escape hatch for an existing operator;
  // it is not advertised by normal help and cannot be reached accidentally.
  if (args.delete) {
    if (!args.verified || args["confirm-delete"] !== String(args.delete)) {
      throw new Error("delete requires --verified and --confirm-delete <same-path>");
    }
    await request(String(args.delete), { method: "DELETE" });
    console.log(JSON.stringify({ deleted: String(args.delete) }));
    return;
  }
  if (args.apply) {
    if (!args.uid || !args.record) {
      throw new Error("--apply needs --uid and --record '{\"species:25\":\"caught\"}'");
    }
    const result = await applyRecords(String(args.uid), JSON.parse(String(args.record)), {
      note: String(args.note ?? ""),
    });
    console.log(JSON.stringify(result ?? { ok: true }));
    return;
  }
  console.log(
    [
      "usage:",
      "  --accounts                       list account uids holding a checklist",
      "  --read <path>                    read a database path",
      "  --read-records --uid <uid>       read one account's records",
      "  --apply --uid <uid> --record <json> [--note <text>]",
      "",
      `key: ${KEY_PATH} (must stay outside the repository)`,
    ].join("\n"),
  );
}

if (process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url))) {
  main().catch((error) => {
    console.error(String(error.message ?? error));
    process.exit(1);
  });
}
