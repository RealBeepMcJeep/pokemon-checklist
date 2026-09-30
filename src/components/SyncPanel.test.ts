import { afterEach, describe, expect, it, vi } from "vitest";
import type { VNode } from "preact";

vi.mock("../sync/firebase", () => ({
  initFirebase: vi.fn(),
  watchAuth: vi.fn(() => vi.fn()),
  signOutOfSync: vi.fn(async () => {}),
  prepareSignIn: vi.fn(async () => {}),
  signInWithGoogle: vi.fn(async () => null),
}));
vi.mock("../sync/engine", async () => {
  const { signal } = await import("@preact/signals");
  return {
    beginSignIn: vi.fn(),
    cancelSignIn: vi.fn(),
    resolveHeldClears: vi.fn(),
    syncAccount: signal({ uid: "uid-a", email: "x" }),
    syncHeld: signal(3),
    syncMessage: signal(""),
    syncOnline: signal(true),
    syncPending: signal(0),
    syncPhase: signal("error"),
  };
});

import { HeldClears, heldConfirmText } from "./SyncPanel";
import { resolveHeldClears } from "../sync/engine";
import { readOnly } from "../state";

/** The buttons a component renders, in order. */
function buttons(node: unknown): VNode<Record<string, unknown>>[] {
  if (!node || typeof node !== "object") return [];
  if (Array.isArray(node)) return node.flatMap(buttons);
  const vnode = node as VNode<Record<string, unknown>>;
  const own = vnode.type === "button" ? [vnode] : [];
  return [...own, ...buttons(vnode.props?.children)];
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.mocked(resolveHeldClears).mockClear();
  readOnly.value = null;
});

describe("held clears", () => {
  it("offers Put back first, and Send clears as the destructive second choice", () => {
    const [first, second] = buttons(HeldClears());
    expect(first.props.id).toBe("held-put-back");
    expect(String(first.props.class)).not.toContain("danger");
    expect(second.props.id).toBe("held-send");
    expect(String(second.props.class)).toContain("danger");
  });

  it("spells out what sending does, and sends nothing unless confirmed", () => {
    expect(heldConfirmText(3)).toBe(
      "Clear 3 Pokémon on every device? This can't be undone here.",
    );
    const asked: string[] = [];
    vi.stubGlobal("confirm", (text: string) => (asked.push(text), false));
    const [, send] = buttons(HeldClears());
    (send.props.onClick as () => void)();
    expect(asked).toEqual([heldConfirmText(3)]);
    expect(resolveHeldClears).not.toHaveBeenCalled();

    vi.stubGlobal("confirm", () => true);
    (send.props.onClick as () => void)();
    expect(resolveHeldClears).toHaveBeenCalledWith(true);
  });

  it("shows held clears in a view-only tab too, with the choices disabled", () => {
    readOnly.value = "elsewhere";
    const choices = buttons(HeldClears());
    expect(choices).toHaveLength(2);
    expect(choices.every((button) => button.props.disabled === true)).toBe(true);
  });
});
