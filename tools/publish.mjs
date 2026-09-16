import { readFileSync, readdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import process from "node:process";

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
const failures = [
  [/<script\b[^>]*\bsrc\s*=/i, "external script"],
  [/<link\b[^>]*\brel\s*=\s*["']?stylesheet/i, "external stylesheet"],
  [
    /<(?:img|source)\b[^>]*\bsrc(?:set)?\s*=\s*["'](?!data:)/i,
    "external image",
  ],
  [/\b(?:fetch|XMLHttpRequest)\s*\(/, "runtime network API"],
  [/sourceMappingURL/i, "source map"],
  [/__(?:VITE|POKEMON|ENCOUNTERS|ASSETS|ATLAS)_/i, "unresolved build token"],
].filter(([pattern]) => pattern.test(html));
if (!/^<!doctype html>/i.test(html)) failures.push([/./, "HTML doctype"]);
if ((html.match(/data:image\//g) || []).length < 72)
  failures.push([/./, "embedded images"]);
if (failures.length) {
  throw new Error(
    `Invalid standalone build: missing or contains ${failures.map(([, label]) => label).join(", ")}`,
  );
}

if (check) {
  if (readFileSync(published, "utf8") !== html) {
    throw new Error("index.html is stale; run npm run build");
  }
  console.log("OK: one-file artifact is complete and index.html is fresh");
} else {
  writeFileSync(published, html, "utf8");
  console.log(
    `Published ${html.length.toLocaleString()} characters to index.html`,
  );
}
