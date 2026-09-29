import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");

/** Version from package.json — the single source of truth for the release number. */
export function readVersion() {
  const pkg = JSON.parse(readFileSync(resolve(root, "package.json"), "utf8"));
  return pkg.version;
}

/** Short commit the build was produced from. "unknown" when git is unavailable. */
export function readCommit() {
  try {
    const sha = execFileSync("git", ["rev-parse", "--short", "HEAD"], {
      cwd: root,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
    return sha || "unknown";
  } catch {
    return "unknown";
  }
}

/** The stamp rendered in the page header, e.g. "v1.0.0 - 8d7c12". */
export function buildLabel() {
  return `v${readVersion()} - ${readCommit()}`;
}

// The commit baked into a build is necessarily the parent commit (a commit cannot
// contain its own hash), so the committed index.html and a rebuild of it always
// differ by this one token. publish.mjs --check normalizes the stamp before
// comparing, so the freshness gate still catches every other difference.
export const STAMP_SOURCE =
  "v\\d+\\.\\d+\\.\\d+(?:[-+][0-9A-Za-z.]+)? - (?:[0-9a-f]{7,40}|unknown)";
export const STAMP_PLACEHOLDER = "v<version> - <commit>";

export function normalizeStamp(html) {
  return html.replace(new RegExp(STAMP_SOURCE, "g"), STAMP_PLACEHOLDER);
}

export function hasStamp(html) {
  return new RegExp(STAMP_SOURCE).test(html);
}

/**
 * Is the committed root index.html an exact rebuild of dist/index.html (other than
 * the stamp)? Both sides are normalized to LF first: a fresh build is always LF, but
 * the committed file could have been resaved with CRLF line endings by some tool or
 * editor outside git's own `eol=lf` filters, and that must not read as a stale build.
 */
export function isFreshBuild(builtHtml, publishedHtml) {
  const normalize = (text) => normalizeStamp(text.replace(/\r\n?/g, "\n"));
  return normalize(builtHtml) === normalize(publishedHtml);
}
