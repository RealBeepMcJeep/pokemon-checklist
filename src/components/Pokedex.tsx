import { computed, type ReadonlySignal } from "@preact/signals";
import { useEffect, useMemo, useRef, useState } from "preact/hooks";
import { memo } from "preact/compat";
import { ENCOUNTERS_BY_MODE, POKEMON, byDex, detailsByDex, formDetails } from "../data";
import { MODE_LABELS, crossModeOccurrences, getOccurrences, normalize, safeId } from "../domain";
import {
  activeEncounters,
  caughtCount,
  drawerOpen,
  formDefinitions,
  formsTracked,
  isStarred,
  mode,
  readOnly,
  searchTerm,
  seenCount,
  selectedDex,
  sidebarHidden,
  starred,
  toggleStar,
} from "../state";
import {
  closeDrawer,
  consumeSelectionFocusIntent,
  isMobile,
  jumpTo,
  openPokemon,
} from "../ui";
import { CatchNext } from "./CatchNext";
import { PokemonFacts, TYPES, TypeMarks } from "./PokemonFacts";
import { PopularMoves } from "./PopularMoves";
import { FormStatusButton, PokemonIcon, StatusButton } from "./StatusControls";

const evolutionIds = new Map(
  POKEMON.flatMap((pokemon) => [
    [normalize(pokemon.name), pokemon.id] as const,
    [normalize(pokemon.slug), pokemon.id] as const,
  ]),
);

// normalize() does an NFD Unicode normalization plus two regex passes; names never
// change at runtime, so do it once per Pokémon instead of on every search keystroke.
const normalizedNames = new Map(
  POKEMON.map((pokemon) => [pokemon.id, normalize(pokemon.name)] as const),
);

// A computed per id so selecting a Pokémon only invalidates the previously and
// newly selected row: @preact/signals only notifies a computed's subscribers when
// its own output changes, so the other ~805 rows' `=== id` stays false on both
// sides of the change and those rows never re-render at all (memo() alone can't
// give this, since it only gates parent-driven updates, not a row's own read of
// the shared selectedDex signal). Created lazily as rows first mount.
const selectedFlags = new Map<number, ReadonlySignal<boolean>>();
function selectedFlag(id: number): ReadonlySignal<boolean> {
  let flag = selectedFlags.get(id);
  if (!flag) {
    flag = computed(() => selectedDex.value === id);
    selectedFlags.set(id, flag);
  }
  return flag;
}

function DexCount({ filtered }: { filtered: number }) {
  return (
    <div class="dex-count" id="dex-count">
      {filtered} of {POKEMON.length} Pokémon · {caughtCount.value} caught ·{" "}
      {seenCount.value} seen
    </div>
  );
}

function Selection() {
  const selected = selectedDex.value;
  if (!selected) {
    return (
      <div class="empty">
        <p>Select a Pokémon to see its status and wild locations.</p>
        <CatchNext />
      </div>
    );
  }
  const pokemon = byDex.get(selected);
  if (!pokemon) return null;
  const occurrences = getOccurrences(activeEncounters.value, selected);
  const otherModeOccurrences = crossModeOccurrences(
    ENCOUNTERS_BY_MODE,
    mode.value,
    selected,
  );
  const details = detailsByDex.get(selected);
  const bulbapediaUrl = `https://bulbapedia.bulbagarden.net/wiki/${encodeURIComponent(`${pokemon.name}_(Pokémon)`).replaceAll("%20", "_")}`;
  const forms = [...formDefinitions.values()].filter(
    (form) => form.speciesId === selected,
  );
  return (
    <>
      <button
        class="deselect-button"
        type="button"
        aria-label="Close these details and show what to catch next"
        onClick={() => {
          selectedDex.value = null;
        }}
      >
        ← Catch next
      </button>
      <div class="selected-title">
        <PokemonIcon id={selected} />
        <span>
          #{String(selected).padStart(3, "0")} {pokemon.name}
        </span>
        <a
          class="bulbapedia-link"
          href={bulbapediaUrl}
          target="_blank"
          rel="noopener noreferrer"
          aria-label={`Open ${pokemon.name} on Bulbapedia in a new tab`}
        >
          Bulbapedia ↗
        </a>
        <StatusButton id={selected} context="selected" />
      </div>
      {details && <PokemonFacts details={details} name={pokemon.name} labels />}
      {formsTracked.value && forms.length > 0 && (
        <div class="form-summary">
          <strong>Tracked forms (separate from location progress)</strong>
          <div class="form-detail-list">
            {forms.map((form) => {
              const details = formDetails.get(form.key);
              return (
                <div class="form-detail" key={form.key}>
                  <FormStatusButton formKey={form.key} />
                  {details && (
                    <PokemonFacts
                      details={details}
                      name={pokemon.name}
                      labels
                    />
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
      <div class="location-links">
        <strong>
          {occurrences.length
            ? `Known places in this mode (${occurrences.length})`
            : "No direct wild location in this mode"}
        </strong>
        {occurrences.length > 0 && (
          <ul>
            {occurrences.map((item, index) => {
              const href = `#encounter-${safeId(item.row.id)}`;
              return (
                <li key={`${href}:${index}`}>
                  <a
                    href={href}
                    onClick={(event) => {
                      event.preventDefault();
                      jumpTo(href, item.location.id);
                    }}
                  >
                    {item.island.name} › {item.location.name} ›{" "}
                    {item.group.name} ·{" "}
                    {item.group.category === "return-later"
                      ? "return later"
                      : "catch now"}{" "}
                    · {item.ally ? "SOS ally" : "wild encounter"}
                  </a>
                </li>
              );
            })}
          </ul>
        )}
        {/* Shown whenever the species evolves, even when it also has a direct wild
            location above: a caught-but-unevolved Pichu or Feebas still needs the
            reminder of how to finish its line. */}
        {details?.evolution && (
          <div class="evolution-path">
            <span>Evolution path</span>
            <ol aria-label={`Evolution path to ${pokemon.name}`}>
              {details.evolution.map((step, index) => {
                const id = evolutionIds.get(normalize(step.name));
                return (
                  <li key={step.name}>
                    {index > 0 && (
                      <span class="evolution-method">{step.method} →</span>
                    )}
                    {id ? (
                      <button
                        class="evolution-link"
                        type="button"
                        onClick={() => openPokemon(id)}
                      >
                        {step.name}
                      </button>
                    ) : (
                      step.name
                    )}
                  </li>
                );
              })}
            </ol>
          </div>
        )}
        {!occurrences.length && !details?.evolution && (
          <p class="muted">
            This Pokémon does not evolve from another Pokémon.
          </p>
        )}
        {otherModeOccurrences.length > 0 && (
          <details class="also-catchable">
            <summary>
              Also catchable in {otherModeOccurrences.length}{" "}
              other mode{otherModeOccurrences.length === 1 ? "" : "s"}
            </summary>
            <ul>
              {otherModeOccurrences.flatMap(({ mode: otherMode, occurrences: rows }) =>
                rows.map((item, index) => (
                  <li key={`${otherMode}:${index}`}>
                    {MODE_LABELS[otherMode]}: {item.location.name}
                    {item.ally ? " · SOS ally" : ""}
                  </li>
                )),
              )}
            </ul>
          </details>
        )}
      </div>
      <PopularMoves id={selected} />
    </>
  );
}

function StarButton({ id, name }: { id: number; name: string }) {
  const pinned = isStarred(id);
  return (
    <button
      type="button"
      class="star-button"
      data-action="star"
      disabled={readOnly.value !== null}
      data-species={id}
      aria-pressed={pinned}
      aria-label={
        pinned
          ? `Unstar ${name} to return it to its National Dex position`
          : `Star ${name} to keep it at the top of the list`
      }
      title={pinned ? "Unstar" : "Star and keep at the top"}
      onClick={() => toggleStar(id)}
    >
      {pinned ? "★" : "☆"}
    </button>
  );
}

// Memoised row contents: a new chunk or a search keystroke then only touches the
// row's own `hidden` attribute. Status, star and selection still update each row
// through its own signals.
const DexRowContent = memo(function DexRowContent({
  id,
  name,
}: {
  id: number;
  name: string;
}) {
  const selected = selectedFlag(id).value;
  const details = detailsByDex.get(id);
  // Render count exposed only for the Playwright test that guards the isolated
  // selectedFlag() above; an integer attribute costs nothing worth measuring.
  const renders = useRef(0);
  renders.current += 1;
  return (
    <>
      <StarButton id={id} name={name} />
      <button
        type="button"
        class="dex-select"
        data-action="select"
        data-species={id}
        data-renders={renders.current}
        aria-current={selected}
        onClick={() => openPokemon(id)}
      >
        <PokemonIcon id={id} />
        <span class="dex-name">
          {String(id).padStart(3, "0")} · {name}
        </span>
        {details && <PokemonFacts details={details} name={name} />}
      </button>
      <StatusButton id={id} context="Pokédex" />
    </>
  );
});

// Rows mounted per animation frame. Creating all 807 in one render blocked a phone
// (4× CPU throttling) for about a second; chunks keep each frame short and put the
// first screen of rows up at once.
const ROW_CHUNK = 30;

export function Pokedex() {
  const query = normalize(searchTerm.value);
  const matches = (pokemon: (typeof POKEMON)[number]) =>
    !query ||
    normalizedNames.get(pokemon.id)!.includes(query) ||
    String(pokemon.id).padStart(3, "0").includes(query) ||
    String(pokemon.id) === query;
  // Starred species are pinned to the top; everything else keeps National Dex
  // order. The sort is stable for equal ranks. Re-sorting all 807 entries is wasted
  // work on renders that only touch search or the sidebar, so it only recomputes
  // when the starred list itself changes.
  const rows = useMemo(() => {
    const pinned = new Set(starred.value);
    return [...POKEMON].sort(
      (a, b) =>
        Number(pinned.has(b.id)) - Number(pinned.has(a.id)) || a.id - b.id,
    );
  }, [starred.value]);
  const matchCount = query ? POKEMON.filter(matches).length : POKEMON.length;
  const open = drawerOpen.value;
  const mobile = isMobile.value;
  const hidden = mobile ? !open : sidebarHidden.value;
  // The Pokédex is a closed drawer on phones, so building rows before anyone has
  // opened it is wasted work. Mount the list in chunks the first time it is shown,
  // then keep every row: a search only hides rows, because rebuilding them when a
  // search is cleared cost as much as the first open.
  const [mountedRows, setMountedRows] = useState(hidden ? 0 : ROW_CHUNK);
  useEffect(() => {
    if ((hidden && !mountedRows) || mountedRows >= POKEMON.length) return;
    const frame = requestAnimationFrame(() =>
      setMountedRows((count) => count + ROW_CHUNK),
    );
    return () => cancelAnimationFrame(frame);
  }, [hidden, mountedRows]);
  useEffect(() => {
    if (!open) return;
    // openPokemon() (opened for a specific Pokémon) already queued focus for the
    // selection panel; only a generic open (the header button, the backdrop) sends
    // focus to search.
    if (consumeSelectionFocusIntent()) return;
    requestAnimationFrame(() =>
      document.querySelector<HTMLInputElement>("#dex-search")?.focus(),
    );
  }, [open]);
  return (
    <>
      <button
        class={`backdrop ${open ? "visible" : ""}`}
        id="backdrop"
        type="button"
        aria-label="Close Pokédex"
        onClick={closeDrawer}
      />
      <aside
        class={`pokedex ${open ? "drawer-open" : ""}`}
        id="pokedex"
        aria-label="National Pokédex"
        aria-hidden={hidden}
        inert={hidden}
        role={mobile && open ? "dialog" : undefined}
        aria-modal={mobile && open ? "true" : undefined}
      >
        <div class="drawer-heading">
          <h2>Pokédex</h2>
          <button
            class="drawer-close"
            id="drawer-close"
            type="button"
            onClick={closeDrawer}
          >
            Close
          </button>
        </div>
        <div class="dex-controls">
          <label for="dex-search">Search Pokémon</label>
          <input
            id="dex-search"
            type="search"
            placeholder="Name or number"
            autocomplete="off"
            value={searchTerm.value}
            onInput={(event) => {
              searchTerm.value = event.currentTarget.value;
            }}
          />
          <DexCount filtered={matchCount} />
          <details class="type-legend">
            <summary>Type colors</summary>
            <div>
              {TYPES.map((type) => (
                <span key={type}>
                  <TypeMarks types={[type]} /> {type}
                </span>
              ))}
            </div>
          </details>
        </div>
        <div class="dex-content">
          <div
            class="dex-selection"
            id="dex-selection"
            tabIndex={-1}
            aria-live="polite"
          >
            <Selection />
          </div>
          <div class="dex-list" id="dex-list">
            {rows.slice(0, mountedRows).map((pokemon) => (
              <div class="dex-row" key={pokemon.id} hidden={!matches(pokemon)}>
                <DexRowContent id={pokemon.id} name={pokemon.name} />
              </div>
            ))}
            {mountedRows > 0 && !matchCount && (
              <div class="empty">No Pokémon match that search.</div>
            )}
          </div>
        </div>
      </aside>
    </>
  );
}
