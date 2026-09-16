import { describe, expect, it } from "vitest";
import { buildLabel, readCommit, readVersion } from "../tools/version.mjs";
import { BUILD_LABEL } from "./version";

describe("build stamp", () => {
  it("renders as v<version> - <short sha>", () => {
    expect(BUILD_LABEL).toMatch(
      /^v\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.]+)? - (?:[0-9a-f]{7,40}|unknown)$/,
    );
  });

  it("carries the package version, not a hard-coded one", () => {
    expect(BUILD_LABEL.startsWith(`v${readVersion()} - `)).toBe(true);
  });

  it("carries the commit currently checked out", () => {
    expect(BUILD_LABEL.endsWith(` - ${readCommit()}`)).toBe(true);
  });

  it("is the literal the build injects, not a runtime default", () => {
    expect(BUILD_LABEL).toBe(buildLabel());
    expect(BUILD_LABEL).not.toBe("v0.0.0 - unknown");
  });
});
