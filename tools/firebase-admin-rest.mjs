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
import { createSign } from "node:crypto";
import { readFileSync } from "node:fs";
import { dirname, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const REPO = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const DATABASE_URL = "https://pokemon-checklist-8c75f-default-rtdb.firebaseio.com";
const KEY_PATH =
  process.env.FIREBASE_SERVICE_ACCOUNT ?? "/opt/data/firebase/service-account.json";

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

async function request(path, init = {}) {
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
  if (!response.ok) throw new Error(`${response.status} ${body.slice(0, 200)}`);
  return body ? JSON.parse(body) : null;
}

export const readPath = (path) => request(path);

/**
 * Stamp a write with the server's own clock. The REST API spells the sentinel
 * `{".sv":"timestamp"}`, which is how the app's ordering stays authoritative even
 * when the write comes from here rather than from a phone.
 */
export const SERVER_TIME = { ".sv": "timestamp" };

export function applyRecords(uid, records, { note = "" } = {}) {
  const payload = { "state/schema": 1, "state/updatedAt": SERVER_TIME };
  for (const [key, value] of Object.entries(records)) {
    payload[`state/records/${key}`] = { s: value, at: SERVER_TIME, by: `chat:${uid}` };
  }
  payload[`log/chat-${Date.now()}`] = {
    op: "set",
    at: SERVER_TIME,
    by: uid,
    via: "chat",
    note,
    keys: Object.keys(records),
  };
  return request(`/users/${uid}`, { method: "PATCH", body: JSON.stringify(payload) });
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
  if (args.read) {
    console.log(JSON.stringify(await readPath(String(args.read)), null, 2));
    return;
  }
  if (args.delete) {
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
      "  --delete <path>                  delete a database path",
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
