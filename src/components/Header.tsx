import { ASSETS, POKEMON } from "../data";
import { DEFAULT_MODE, MODE_LABELS } from "../domain";
import {
  caughtCount,
  drawerOpen,
  formDefinitions,
  formsCaught,
  formsTracked,
  mode,
  notice,
  sidebarHidden,
  toggleForms,
} from "../state";
import { GAME_MODES } from "../types";
import type { GameMode } from "../types";
import { BUILD_LABEL } from "../version";
import {
  DRAWER_BREAKPOINT,
  changeMode,
  exportJSON,
  importFile,
  reset,
  toggleSidebar,
} from "../ui";

export function Header() {
  const caught = caughtCount.value;
  const trackForms = formsTracked.value;
  const currentMode = mode.value;
  const currentNotice = notice.value;
  return (
    <header class="app-header">
      <div class="header-inner">
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
          <div class="actions" aria-label="Checklist actions">
            <button
              class="action-button"
              id="sidebar-toggle"
              type="button"
              aria-controls="pokedex"
              aria-expanded={
                !sidebarHidden.value &&
                (window.innerWidth >= DRAWER_BREAKPOINT || drawerOpen.value)
              }
              onClick={toggleSidebar}
            >
              Pokédex
            </button>
            <label class="visually-hidden" for="mode-select">
              Game mode
            </label>
            <select
              class="action-button"
              id="mode-select"
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
              type="button"
              onClick={reset}
            >
              Reset
            </button>
          </div>
        </div>
        <div class="progress-row">
          <label for="overall-progress">Overall caught</label>
          <progress id="overall-progress" max={POKEMON.length} value={caught}>
            {caught} / {POKEMON.length}
          </progress>
          <strong id="overall-text">
            {caught} / {POKEMON.length} Pokémon
          </strong>
          <span id="form-progress" class="muted" hidden={!trackForms}>
            Forms caught: {formsCaught.value} / {formDefinitions.size}
          </span>
        </div>
        <div
          id="notice"
          class={currentNotice.kind}
          role="status"
          aria-live="polite"
        >
          {currentNotice.message}
        </div>
      </div>
    </header>
  );
}
