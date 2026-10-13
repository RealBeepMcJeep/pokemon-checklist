import { expect, it, vi } from "vitest";
import type { VNode } from "preact";
vi.mock("../sync/engine", async () => {
  const { signal } = await import("@preact/signals");
  return { syncAccount: signal({uid:"test",email:"player@example.test"}), syncHeldKeys: signal([]), syncMessage: signal(""), syncOnline: signal(true), syncPending: signal(2), syncPhase: signal("ready") };
});
import * as panel from "./SyncPanel";
import { syncPhase, syncOnline, syncMessage, syncAccount } from "../sync/engine";
function text(node: unknown): string {
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(text).join("");
  if (!node || typeof node !== "object") return "";
  return text((node as VNode<{children?:unknown}>).props.children);
}
it("keeps every unhealthy sync status outside Settings, compacting only healthy sync", () => {
  expect((panel as unknown as Record<string, unknown>).MobileSyncStatus).toBeTypeOf("function");
  const render = () => (panel as unknown as { MobileSyncStatus: () => unknown }).MobileSyncStatus();
  for (const [phase, online, message, expected] of [
    ["pending", true, "", "2 to send"], ["pending", false, "", "Offline · 2 to send"],
    ["ready", false, "", "Offline"], ["error", true, "Retry needed", "Retry needed"],
    ["elsewhere", true, "", "Editing in another tab"], ["outdated", true, "", "A newer version is open"],
    ["connecting", true, "", "Syncing…"],
  ] as const) {
    syncPhase.value = phase; syncOnline.value = online; syncMessage.value = message;
    expect(text(render())).toBe(expected);
  }
  syncPhase.value = "ready"; syncOnline.value = true;
  const healthy = render() as VNode<{"aria-label": string}>;
  expect(healthy.props["aria-label"]).toBe("Synced");
  expect(text(healthy)).toBe("");
  syncAccount.value = null;
  expect(render()).toBeNull();
});
