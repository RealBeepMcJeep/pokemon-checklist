import { describe, expect, it } from "vitest";
import { isAllowedEmail } from "./config";

describe("sync account allowlist", () => {
  it("matches the exact lowercase spelling enforced by the database rules", () => {
    expect(isAllowedEmail("realbeepmcjeep@gmail.com")).toBe(true);
    expect(isAllowedEmail("REALBEEPMCJEEP@GMAIL.COM")).toBe(false);
  });
});
