import assert from "node:assert/strict";
import test from "node:test";
import { isFreshBuild } from "../version.mjs";

test("isFreshBuild ignores line-ending differences on either side", () => {
  const built = "<!doctype html>\n<title>v1.0.0 - abc1234</title>\n";
  // The committed file resaved with CRLF endings by some tool outside git's own
  // filters must not read as stale: publish.mjs used to normalize only the freshly
  // built side, leaving the committed side's CRLF unnormalized.
  const publishedCrlf = built.replace(/\n/g, "\r\n");
  assert.ok(isFreshBuild(built, publishedCrlf));
});

test("isFreshBuild still ignores only the version/commit stamp", () => {
  const built = "<!doctype html>\n<title>v1.0.0 - abc1234</title>\n<p>content</p>\n";
  const published = "<!doctype html>\n<title>v1.0.0 - def5678</title>\n<p>content</p>\n";
  assert.ok(isFreshBuild(built, published));
});

test("isFreshBuild still catches a real content difference", () => {
  const built = "<!doctype html>\n<title>v1.0.0 - abc1234</title>\n<p>content</p>\n";
  const published = "<!doctype html>\n<title>v1.0.0 - abc1234</title>\n<p>stale</p>\n";
  assert.ok(!isFreshBuild(built, published));
});
