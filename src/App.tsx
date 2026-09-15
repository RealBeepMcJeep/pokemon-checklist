import { useEffect } from "preact/hooks";
import { Header } from "./components/Header";
import { LocationList } from "./components/Locations";
import { Pokedex } from "./components/Pokedex";
import { drawerOpen, mode, sidebarHidden } from "./state";
import { closeDrawer } from "./ui";

export function App() {
  const currentMode = mode.value;
  const hidden = sidebarHidden.value;
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
  return (
    <>
      <Header />
      <div class="layout">
        <LocationList />
        <Pokedex />
      </div>
    </>
  );
}
