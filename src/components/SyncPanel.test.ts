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
    syncHeldKeys: signal(["species:1", "species:4", "form:37:alolan", "star:25"]),
    syncMessage: signal(""),
    syncOnline: signal(true),
    syncPending: signal(0),
    syncPhase: signal("error"),
  };
});

import { HeldClears, heldConfirmText } from "./SyncPanel";
import { resolveHeldClears } from "../sync/engine";
import { readOnly } from "../state";

const HELD = ["species:1", "species:4", "form:37:alolan", "star:25"];

/** The buttons a component renders, in order. */
function buttons(node: unknown): VNode<Record<string, unknown>>[] {
  if (!node || typeof node !== "object") return [];
  if (Array.isArray(node)) return node.flatMap(buttons);
  const vnode = node as VNode<Record<string, unknown>>;
  const own = vnode.type === "button" ? [vnode] : [];
  return [...own, ...buttons(vnode.props?.children)];
}

function text(node: unknown): string {
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (!node || typeof node !== "object") return "";
  if (Array.isArray(node)) return node.map(text).join("");
  return text((node as VNode<{ children?: unknown }>).props?.children);
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

  it("counts Pokémon and favourites apart", () => {
    expect(text(HeldClears())).toContain("Clearing 3 Pokémon and 1 favourite would empty");
    expect(heldConfirmText(HELD)).toBe(
      "Clear 3 Pokémon and 1 favourite on every device? This can't be undone here.",
    );
    expect(heldConfirmText(["star:1", "star:2"])).toBe(
      "Clear 2 favourites on every device? This can't be undone here.",
    );
  });

  it("sends nothing unless confirmed", async () => {
    const asked: string[] = [];
    vi.stubGlobal("confirm", (question: string) => (asked.push(question), false));
    const [, send] = buttons(HeldClears());
    await (send.props.onClick as () => Promise<void>)();
    expect(asked).toEqual([heldConfirmText(HELD)]);
    expect(resolveHeldClears).not.toHaveBeenCalled();

    vi.stubGlobal("confirm", () => true);
    await (send.props.onClick as () => Promise<void>)();
    expect(resolveHeldClears).toHaveBeenCalledWith(true);
  });

  it("sends nothing if editing moved to another tab while the dialog was open", async () => {
    vi.stubGlobal("confirm", () => {
      // The steal happened while the dialog blocked the tab; its news is queued.
      setTimeout(() => (readOnly.value = "elsewhere"), 0);
      return true;
    });
    const [, send] = buttons(HeldClears());
    await (send.props.onClick as () => Promise<void>)();
    expect(resolveHeldClears).not.toHaveBeenCalled();
  });

  it("shows held clears in a view-only tab too, with the choices disabled", () => {
    readOnly.value = "elsewhere";
    const choices = buttons(HeldClears());
    expect(choices).toHaveLength(2);
    expect(choices.every((button) => button.props.disabled === true)).toBe(true);
  });
});
