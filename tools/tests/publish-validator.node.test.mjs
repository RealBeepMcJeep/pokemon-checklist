import assert from "node:assert/strict";
import test from "node:test";
import { standaloneResourceFailures } from "../publish-validator.mjs";

test("rejects standalone external resource tags and CSS references", () => {
  const failures = standaloneResourceFailures(`
    <iframe src="https://example.test/frame"></iframe>
    <object data="/object.svg"></object>
    <embed src="https://example.test/embed">
    <video poster="https://example.test/poster"><source src="/movie.mp4"></video>
    <track src="/captions.vtt">
    <style>@import "theme.css"; .x { background: url('/image.png') }</style>
  `);
  assert.deepEqual(failures, [
    "external iframe",
    "external object",
    "external embed",
    "external video",
    "external source",
    "external track",
    "external CSS url",
    "external CSS import",
  ]);
});

test("rejects an external srcset candidate after a data URL", () => {
  assert.deepEqual(
    standaloneResourceFailures(
      '<img srcset="data:image/png;base64,AAAA 1x, https://example.test/x.png 2x">',
    ),
    ["external img"],
  );
});

test("allows data and fragment-only resources", () => {
  assert.deepEqual(standaloneResourceFailures(`
    <iframe src="#card"></iframe>
    <object data="data:image/svg+xml,<svg/>"></object>
    <img src="data:image/png;base64,AAAA">
    <style>.x { background: url(#sprite) }</style>
    <link rel="stylesheet" href="#embedded">
  `), []);
});
