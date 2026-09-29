import { describe, expect, it } from "vitest";
import { isAllowedAccount, isAllowedEmail } from "./config";

describe("sync account allowlist", () => {
  it("matches the exact lowercase spelling enforced by the database rules", () => {
    expect(isAllowedEmail("realbeepmcjeep@gmail.com")).toBe(true);
    expect(isAllowedEmail("REALBEEPMCJEEP@GMAIL.COM")).toBe(false);
  });

  it("requires a verified address, as the database rules do", () => {
    const email = "realbeepmcjeep@gmail.com";
    expect(isAllowedAccount({ email, emailVerified: true })).toBe(true);
    expect(isAllowedAccount({ email, emailVerified: false })).toBe(false);
    expect(isAllowedAccount(null)).toBe(false);
  });
});
