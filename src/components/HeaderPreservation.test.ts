import { afterEach, expect, it, vi } from "vitest";
import { signal } from "@preact/signals";
import type { VNode } from "preact";
vi.mock("preact/hooks", () => ({ useEffect: vi.fn(), useRef: (value: unknown) => ({ current: value }), useState: (value: unknown) => [value, vi.fn()] }));
vi.mock("../state", () => ({ formsTracked: signal(false), mode: signal("photonic-prismatic"), notice: signal({message:"",kind:""}), readOnly: signal(null), drawerOpen: signal(false), sidebarHidden: signal(false), toggleForms: vi.fn(), speciesCounts: signal({none:807,seen:0,caught:0}), caughtCount: signal(0), formCounts: signal({none:48,seen:0,caught:0}) }));
vi.mock("../ui", () => ({ isMobile: signal(false), changeMode: vi.fn(), exportJSON: vi.fn(), importFile: vi.fn(), reset: vi.fn(), toggleSidebar: vi.fn() }));
vi.mock("./Tools", () => ({ toolsOpen: signal(false) }));
vi.mock("./SyncPanel", () => ({ HeldClears: function HeldClears(){return null;}, MobileSyncStatus: function MobileSyncStatus(){return null;}, SyncPanel: function SyncPanel(){return null;} }));
import { Header } from "./Header";
afterEach(() => vi.unstubAllGlobals());
it("keeps desktop HeldClears, CollectionProgress and notice in their original order", () => {
  vi.stubGlobal("window", { scrollY: 0 });
  const order: string[] = [];
  function visit(value: unknown): void {
    if (Array.isArray(value)) { value.forEach(visit); return; }
    if (!value || typeof value !== "object") return;
    const node = value as VNode<{children?: unknown; id?: string}>;
    if (typeof node.type === "function" && ["HeldClears", "CollectionProgress"].includes(node.type.name)) order.push(node.type.name);
    if (node.props?.id === "notice") order.push("notice");
    visit(node.props?.children);
  }
  visit(Header({}));
  expect(order).toEqual(["HeldClears", "CollectionProgress", "notice"]);
});
