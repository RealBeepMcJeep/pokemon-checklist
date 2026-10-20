import { useEffect, useRef, useState } from "preact/hooks";
import { UnlockSettings } from "./UnlockSettings";
import { toolsOpen } from "./Tools";
import { ASSETS, POKEMON } from "../data";
import { DEFAULT_MODE, MODE_LABELS } from "../domain";
import {
  speciesCounts,
  caughtCount,
  drawerOpen,
  formCounts,
  formsTracked,
  mode,
  notice,
  readOnly,
  sidebarHidden,
  toggleForms,
} from "../state";
import { GAME_MODES } from "../types";
import type { GameMode } from "../types";
import { BUILD_LABEL } from "../version";
import { HeldClears, MobileSyncStatus, SyncPanel } from "./SyncPanel";
import {
  changeMode,
  exportJSON,
  importFile,
  isMobile,
  reset,
  toggleSidebar,
} from "../ui";

import { StatusCounts } from "./StatusCounts";

// Keep collection subscriptions out of the action/header tree.
function CollectionProgress({ details = false }: { details?: boolean }) {
  const counts = speciesCounts.value;
  return (
    <div class="progress-row">
      <label for="overall-progress">Overall caught</label>
      <progress id="overall-progress" max={POKEMON.length} value={caughtCount.value} />
      {!details && <span id="overall-text">
        <span class="collection-label">Pokémon</span> <StatusCounts counts={counts} label="Overall Pokémon" />
      </span>}
      {formsTracked.value && <span id="form-progress">
        <span class="collection-label">Forms</span> <StatusCounts counts={formCounts.value} label="Active mode forms" />
      </span>}
    </div>
  );
}

function MobileCounts() {
  const counts = speciesCounts.value;
  return <><span id="overall-text"><span class="visually-hidden">Pokémon </span><StatusCounts counts={counts} label="Overall Pokémon" compact /></span>
    <span class="mobile-progress-rail" aria-hidden="true">{(["none", "seen", "caught"] as const).map(status => <span data-status={status} style={{ width: `${counts[status] / POKEMON.length * 100}%` }} />)}</span></>;
}

function HeaderIcon({ name }: { name: "dex" | "tools" | "more" | "game" }) {
  const paths = {
    dex: "M5 3h14v18H5z M9 3v18 M12 7h4 M12 11h4 M12 15h4",
    tools: "M14 4a6 6 0 0 0-7 7L2 16l6 6 5-5a6 6 0 0 0 7-7l-4 4-4-4 4-4z",
    more: "M5 12h.01 M12 12h.01 M19 12h.01",
    game: "M20 15A9 9 0 0 1 9 4a9 9 0 1 0 11 11z",
  };
  return <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width={name === "more" ? 4 : 1.8} stroke-linecap="round" stroke-linejoin="round"><path d={paths[name]} /></svg>;
}

export function Header({ inert = false }: { inert?: boolean }) {
  const trackForms = formsTracked.value;
  const currentMode = mode.value;
  const currentNotice = notice.value;
  const locked = readOnly.value !== null;
  const mobile = isMobile.value;
  const [scrolled, setScrolled] = useState(window.scrollY > 90);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const settingsRef = useRef<HTMLDialogElement>(null);
  const previousMobile = useRef(mobile);
  useEffect(() => {
    if (previousMobile.current !== mobile) {
      previousMobile.current = mobile;
      setSettingsOpen(false);
    }
  }, [mobile]);
  const alertsRef = useRef<HTMLDivElement>(null);
  const [alertsHeight, setAlertsHeight] = useState(0);
  // Reserve only extra alert space, never the shrinking identity row: this avoids
  // scroll/height feedback while keeping notices from covering the first section.
  useEffect(() => {
    const alerts = alertsRef.current;
    if (!mobile || !alerts) return;
    const measure = () => setAlertsHeight(Math.ceil(alerts.getBoundingClientRect().height));
    const observer = new ResizeObserver(measure);
    observer.observe(alerts);
    measure();
    return () => observer.disconnect();
  }, [mobile]);
  // Undo expires after eight seconds. A new action/error must not be left behind
  // a modal backdrop; opening Settings with an older notice does not close it.
  useEffect(() => {
    if (currentNotice.action || currentNotice.kind === "error") setSettingsOpen(false);
  }, [currentNotice]);
  useEffect(() => {
    const update = () => setScrolled(window.scrollY > 90);
    window.addEventListener("scroll", update, { passive: true });
    return () => window.removeEventListener("scroll", update);
  }, []);
  useEffect(() => {
    if (drawerOpen.value || toolsOpen.value) setSettingsOpen(false);
  }, [mobile, drawerOpen.value, toolsOpen.value]);
  useEffect(() => {
    const dialog = settingsRef.current;
    if (!settingsOpen || !dialog) return;
    const previous = document.body.style.overflow;
    dialog.showModal();
    document.body.style.overflow = "hidden";
    return () => {
      dialog.close();
      document.body.style.overflow = previous;
      if (!drawerOpen.value && !toolsOpen.value)
        document.getElementById("header-settings-toggle")?.focus({ preventScroll: true });
    };
  }, [settingsOpen, mobile]);
  const controls = <>
            <label class="visually-hidden" for="mode-select">
              Game mode
            </label>
            <select
              class="action-button"
              id="mode-select"
              disabled={locked}
              aria-label="Game mode"
              value={currentMode}
              onChange={(event) =>
                changeMode(event.currentTarget.value as GameMode)
              }
            >
              {GAME_MODES.map((gameMode) => (
                <option key={gameMode} value={gameMode}>
                  {MODE_LABELS[gameMode]}
                </option>
              ))}
            </select>
            <button
              class="action-button"
              id="forms-toggle"
              disabled={locked}
              type="button"
              aria-pressed={trackForms}
              onClick={toggleForms}
            >
              Track forms: {trackForms ? "On" : "Off"}
            </button>
            <button
              class="action-button"
              id="export-button"
              type="button"
              onClick={exportJSON}
            >
              Backup
            </button>
            <button
              class="action-button"
              id="import-button"
              disabled={locked}
              type="button"
              onClick={() =>
                document
                  .querySelector<HTMLInputElement>("#import-file")
                  ?.click()
              }
            >
              Restore
            </button>
            <input
              class="visually-hidden"
              id="import-file"
              type="file"
              accept="application/json,.json"
              aria-label="Choose a checklist backup to restore"
              onChange={importFile}
            />
            <button
              class="action-button"
              id="reset-button"
              disabled={locked}
              type="button"
              onClick={() => void reset()}
            >
              Reset
            </button>
  </>;
  const dex = <button class="action-button" id="sidebar-toggle" type="button" aria-label="Pokédex" aria-controls="pokedex" aria-expanded={!sidebarHidden.value && (!mobile || drawerOpen.value)} onClick={() => { setSettingsOpen(false); toggleSidebar(); }}>{mobile ? <HeaderIcon name="dex" /> : "Pokédex"}</button>;
  const tools = <button id="tools-toggle" class="action-button" type="button" aria-label="Tools" aria-haspopup="dialog" aria-controls="tools-panel" aria-expanded={toolsOpen.value} onClick={() => { setSettingsOpen(false); toolsOpen.value = true; }}>{mobile ? <HeaderIcon name="tools" /> : "Tools"}</button>;
  return <>
    {mobile && <div class="mobile-header-space" style={{ height: `${112 + alertsHeight}px` }} aria-hidden="true" />}
    <header class={`app-header${mobile ? " mobile-header" : ""}${scrolled ? " is-scrolled" : ""}`} inert={inert}>
      <div class="header-inner">
        {mobile ? <>
          <div class="mobile-identity"><h1>Pokémon Checklist</h1><span>{MODE_LABELS[currentMode]}</span></div>
          <div class="mobile-command-row">
            <button class="action-button mobile-mode" type="button" aria-label={`Game mode: ${MODE_LABELS[currentMode]}`} onClick={() => { setSettingsOpen(true); requestAnimationFrame(() => document.getElementById("mode-select")?.focus()); }}><HeaderIcon name="game" /><small>{({ "photonic-prismatic": "PM", sun: "Sun", moon: "Moon", "ultra-sun": "US", "ultra-moon": "UM" })[currentMode]}</small></button>
            <MobileCounts />{dex}{tools}
            <button class="action-button" id="header-settings-toggle" type="button" aria-label="Settings" aria-haspopup="dialog" aria-controls="header-settings-panel" aria-expanded={settingsOpen} onClick={() => setSettingsOpen(true)}><HeaderIcon name="more" /></button>
          </div>
        </> : <>
          <div class="title-row">
          <div class="brand">
            <img
              class="title-art"
              id="title-art"
              src={ASSETS["assets/locations/title.png"]}
              alt={
                currentMode === DEFAULT_MODE
                  ? "Photonic Sun and Prismatic Moon"
                  : ""
              }
              hidden={currentMode !== DEFAULT_MODE}
            />
            <div class="brand-copy">
              <h1>Wild Pokémon Checklist</h1>
              <div class="subtitle" id="mode-summary">
                {MODE_LABELS[currentMode]} · Alola locations in story order ·
                National Pokédex 001–807
              </div>
              <span
                class="build-stamp"
                id="build-version"
                title="Release version and commit this build came from"
              >
                {BUILD_LABEL}
              </span>
            </div>
          </div>
            <div class="actions" aria-label="Checklist actions">{dex}{controls}{tools}<button class="action-button" id="header-settings-toggle" type="button" aria-haspopup="dialog" aria-controls="header-settings-panel" onClick={() => setSettingsOpen(true)}>Settings</button><SyncPanel /></div>
          </div>
        </>}
        <div class={mobile ? "mobile-alerts" : undefined} ref={alertsRef}>
          {mobile && <MobileSyncStatus />}
          <HeldClears />
          {!mobile && <CollectionProgress />}
          <div id="notice" class={currentNotice.kind} role="status" aria-live="polite">{currentNotice.message}</div>
        </div>
      </div>
    </header>
    {<dialog ref={settingsRef} id="header-settings-panel" aria-labelledby="header-settings-title" onCancel={() => setSettingsOpen(false)}>
      <div class="header-settings-heading"><h2 id="header-settings-title">Settings</h2><button class="action-button" type="button" onClick={() => setSettingsOpen(false)}>Close settings</button></div>
      {mobile && <div class="header-settings-controls actions" aria-label="Checklist actions">{controls}</div>}
      <UnlockSettings />
      {mobile && <><CollectionProgress details /><SyncPanel /></>}
      {mobile && <footer><strong>Wild Pokémon Checklist</strong><p>{MODE_LABELS[currentMode]} · Alola locations in story order · National Pokédex 001–807</p><span class="build-stamp" id="build-version" title="Release version and commit this build came from">{BUILD_LABEL}</span></footer>}
    </dialog>}
  </>;
}
