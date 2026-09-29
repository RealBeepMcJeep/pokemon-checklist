import { useEffect } from "preact/hooks";
import { Header } from "./components/Header";
import { LocationList } from "./components/Locations";
import { Pokedex } from "./components/Pokedex";
import { drawerOpen, mode, sidebarHidden } from "./state";
import { closeDrawer } from "./ui";

export function App() {
  const currentMode = mode.value;
  const hidden = sidebarHidden.value;
  // The drawer behaves as a modal on a phone: everything behind it (header, location
  // list) is made inert, which both blocks background clicks and keeps Tab from
  // ever leaving the drawer while it's open — a native focus trap, no keyboard
  // handling of our own required.
  const modalOpen = drawerOpen.value;
  useEffect(() => {
    document.documentElement.dataset.mode = currentMode;
  }, [currentMode]);
  useEffect(() => {
    document.body.classList.toggle("sidebar-hidden", hidden);
  }, [hidden]);
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && drawerOpen.value) closeDrawer();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);
  useEffect(() => {
    // The header wraps to extra lines once its action row runs out of space
    // (many buttons, a select, the sync panel), so the sticky Pokédex's offset
    // (app.css) reads this instead of assuming a fixed number of header lines.
    const header = document.querySelector<HTMLElement>(".app-header");
    if (!header || typeof ResizeObserver === "undefined") return;
    const setHeaderHeight = () => {
      document.documentElement.style.setProperty(
        "--header-h",
        `${header.offsetHeight}px`,
      );
    };
    setHeaderHeight();
    const observer = new ResizeObserver(setHeaderHeight);
    observer.observe(header);
    return () => observer.disconnect();
  }, []);
  return (
    <>
      <Header inert={modalOpen} />
      <div class="layout">
        <LocationList inert={modalOpen} />
        <Pokedex />
      </div>
    </>
  );
}
