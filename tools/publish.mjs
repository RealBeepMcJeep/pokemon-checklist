import { readFileSync, readdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import process from "node:process";
import { hasStamp, normalizeStamp } from "./version.mjs";

const root = resolve(import.meta.dirname, "..");
const dist = resolve(root, "dist");
const output = resolve(dist, "index.html");
const published = resolve(root, "index.html");
const check = process.argv.includes("--check");

const files = readdirSync(dist, { recursive: true, withFileTypes: true })
  .filter((entry) => entry.isFile())
  .map((entry) => entry.name);
if (files.length !== 1 || files[0] !== "index.html") {
  throw new Error(
    `Expected only dist/index.html, found: ${files.join(", ") || "nothing"}`,
  );
}

const html = readFileSync(output, "utf8").replace(/\r\n?/g, "\n");
// The offline contract used to be structural: no runtime network API could exist
// in the file at all. Sync changes that. The artifact now bundles a database SDK,
// whose network code is reachable only after a player signs in, so the rule is
// restated as a behavioural one that is enforced where it can actually be checked:
//
//   tests/app.spec.ts — "attempts no network requests while signed out" loads this
//   exact file, records every request the page makes, and fails if anything other
//   than data:/file:/localhost is even attempted.
//
// Everything below still keeps the artifact self-contained: no external scripts,
// stylesheets or images, no source maps, no unresolved build tokens.
const failures = [
  [/<script\b[^>]*\bsrc\s*=/i, "external script"],
  [/<link\b[^>]*\brel\s*=\s*["']?stylesheet/i, "external stylesheet"],
  [
    /<(?:img|source)\b[^>]*\bsrc(?:set)?\s*=\s*["'](?!data:)/i,
    "external image",
  ],
  [/sourceMappingURL/i, "source map"],
  [/__(?:VITE|POKEMON|ENCOUNTERS|ASSETS|ATLAS)_/i, "unresolved build token"],
].filter(([pattern]) => pattern.test(html));
if (!/^<!doctype html>/i.test(html)) failures.push([/./, "HTML doctype"]);
if (!hasStamp(html)) failures.push([/./, "build version stamp"]);
if ((html.match(/data:image\//g) || []).length < 72)
  failures.push([/./, "embedded images"]);
if (failures.length) {
  throw new Error(
    `Invalid standalone build: missing or contains ${failures.map(([, label]) => label).join(", ")}`,
  );
}

if (check) {
  // The stamped commit is necessarily the parent commit, so a rebuild can never
  // reproduce the committed hash exactly. Normalize the stamp (and only the stamp)
  // so the freshness gate still fails on any other difference.
  if (normalizeStamp(readFileSync(published, "utf8")) !== normalizeStamp(html)) {
    throw new Error("index.html is stale; run npm run build");
  }
  console.log("OK: one-file artifact is complete and index.html is fresh");
} else {
  writeFileSync(published, html, "utf8");
  console.log(
    `Published ${html.length.toLocaleString()} characters to index.html`,
  );
}
