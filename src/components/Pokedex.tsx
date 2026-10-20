import { computed, type ReadonlySignal } from "@preact/signals";
import { useEffect, useMemo, useRef, useState } from "preact/hooks";
import { memo } from "preact/compat";
import { ENCOUNTERS_BY_MODE, POKEMON, byDex, detailsByDex, formDetails } from "../data";
import { MODE_LABELS, crossModeOccurrences, getOccurrences, normalize, safeId } from "../domain";
import {
  activeEncounters,
  formSignal,
  activeUnlocks,
  collectionCounts,
  drawerOpen,
  formDefinitions,
  formsTracked,
  isStarred,
  mode,
  readOnly,
  speciesStatus,
  searchTerm,
  selectedDex,
  selectedRegionalForm,
  sidebarHidden,
  starred,
  starredForms,
} from "../state";
import {
  closeDrawer,
  changeFavorite,
  resolveLegacyFavorite,
  consumeSelectionFocusIntent,
  isMobile,
  jumpTo,
  openPokemon,
  selectedEncounterContext,
} from "../ui";
import { CatchNext } from "./CatchNext";
import { EvolutionControls } from "./EvolutionControls";
import { collectionTargets, matchesTarget, targetKey, targetName, type CollectionTarget } from "../collection";
import { hasUnresolvedRegionalOwnership, isRegional, type RegionalForm } from "../regional";
import { CollectionFacts } from "./CollectionFacts";
import { StatusCounts } from "./StatusCounts";
import { PokemonFacts, TYPES, TypeMarks } from "./PokemonFacts";
import { PopularMoves } from "./PopularMoves";
import { FormStatusButton, PokemonIcon, StatusButton } from "./StatusControls";

// A computed per id so selecting a Pokémon only invalidates the previously and
// newly selected row: @preact/signals only notifies a computed's subscribers when
// its own output changes, so the other ~805 rows' `=== id` stays false on both
// sides of the change and those rows never re-render at all (memo() alone can't
// give this, since it only gates parent-driven updates, not a row's own read of
// the shared selectedDex signal). Created lazily as rows first mount.
const selectedFlags = new Map<string, ReadonlySignal<boolean>>();
function selectedFlag(id: number, form?: RegionalForm): ReadonlySignal<boolean> {
  const key = targetKey({ id, form });
  let flag = selectedFlags.get(key);
  if (!flag) {
    flag = computed(() => selectedDex.value === id && (!formsTracked.value || selectedRegionalForm.value === form || (!selectedRegionalForm.value && form === "alolan")));
    selectedFlags.set(key, flag);
  }
  return flag;
}

function DexCount({ filtered, total }: { filtered: number; total: number }) {
  return (
    <div class="dex-count" id="dex-count">
      <div>{filtered} of {total} {formsTracked.value ? "collection targets" : "Pokémon"}</div>
      <StatusCounts counts={collectionCounts.value} label="Pokédex collection" />
    </div>
  );
}

// Keep selection subscriptions inside this panel: selecting a species must not
// invalidate the parent that mounts all 807 Pokédex rows.
function SelectionPanel() {
  return (
    <div
      class={`dex-selection ${selectedDex.value === null ? "dex-selection-empty" : ""}`}
      id="dex-selection"
      tabIndex={-1}
      aria-live="polite"
    >
      <Selection />
    </div>
  );
}

function Selection() {
  const selected = selectedDex.value;
  if (!selected) {
    return (
      <div class="empty">
        <p class="selection-hint">Select a Pokémon to see its status and wild locations.</p>
        <CatchNext />
      </div>
    );
  }
  const pokemon = byDex.get(selected);
  if (!pokemon) return null;
  const context = selectedEncounterContext.value?.id === selected ? selectedEncounterContext.value : undefined;
  const form = (formsTracked.value || context) && isRegional(selected) ? selectedRegionalForm.value ?? "alolan" : undefined;
  const name = context?.name ?? targetName(pokemon, form);
  const variantView = !!context && !isRegional(selected);
  // Never substitute base facts for a known alternate form. Explicit Base is
  // the sole safe fallback when no separate form-detail record is stored.
  const exactFacts = context?.detailKey ? formDetails.get(context.detailKey)
    ?? (context.detailKey === `${selected}:base` ? detailsByDex.get(selected) : undefined) : undefined;
  const occurrences = getOccurrences(activeEncounters.value, selected, activeUnlocks.value, form);
  const otherModeOccurrences = crossModeOccurrences(
    ENCOUNTERS_BY_MODE,
    mode.value,
    selected,
    form,
  );
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
          selectedRegionalForm.value = undefined;
          selectedEncounterContext.value = undefined;
        }}
      >
        ← Catch next
      </button>
      <div class="selected-title">
        <PokemonIcon id={selected} />
        <span>
          #{String(selected).padStart(3, "0")} {name}
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
        {variantView && <small>Species status</small>}
        <StatusButton id={selected} form={form} context={variantView ? "selected species" : "selected"} />
      </div>
      {variantView ? <>
        <div class="encounter-facts">
          {exactFacts ? <PokemonFacts details={exactFacts} name={name} labels />
            : <p class="encounter-facts-missing">Verified form-specific facts are unavailable.</p>}
        </div>
        <div class="encounter-context-note form-ownership-warning" role="note">
          This is an encounter view. Status and the locations below are species-wide;
          form-specific moves and evolutions are not verified in this view.{" "}
          <button class="action-button" type="button" onClick={() => openPokemon(selected)}>Show species information</button>
        </div>
      </> : <CollectionFacts id={selected} form={form} labels /> }
      {form && hasUnresolvedRegionalOwnership(speciesStatus(selected), [
        formSignal(`${selected}:alolan`).value, formSignal(`${selected}:kanto`).value,
      ]) && (
        <p class="form-ownership-warning" role="status">
          Existing {speciesStatus(selected) === "caught" ? "Caught" : "Seen"} progress is recorded without a form.
          {" "}Confirm each form's status; neither form is assumed.
        </p>
      )}
      {isRegional(selected) && starred.value.includes(selected) && (
        <div class="form-ownership-warning" role="note">
          An existing favorite has no assigned regional form. Choose its form without changing ownership.
          {" "}<button class="action-button" type="button" disabled={readOnly.value !== null}
            onClick={() => resolveLegacyFavorite(selected)}>Choose form for existing favorite</button>
        </div>
      )}
      {formsTracked.value && !isRegional(selected) && forms.length > 0 && (
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
          {variantView ? `Species locations (all forms) (${occurrences.length})` : occurrences.length
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
                    {(item.eligible === undefined ? item.group.category === "return-later" : !item.eligible)
                      ? "return later"
                      : "catch now"}{" "}
                    · {item.ally ? "SOS ally" : "wild encounter"}
                  </a>
                </li>
              );
            })}
          </ul>
        )}
        {!variantView && <EvolutionControls target={{ id: selected, form }} />}
        {otherModeOccurrences.length > 0 && (
          <details class="also-catchable">
            <summary>
              {variantView ? "Species also catchable in" : "Also catchable in"} {otherModeOccurrences.length}{" "}
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
      {!variantView && <PopularMoves id={selected} form={form} />}
    </>
  );
}

function StarButton({ id, name, form }: { id: number; name: string; form?: RegionalForm }) {
  const pinned = isStarred(id, form);
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
      onClick={() => changeFavorite(id, form)}
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
  form,
}: {
  id: number;
  name: string;
  form?: RegionalForm;
}) {
  const selected = selectedFlag(id, form).value;
  // Render count exposed only for the Playwright test that guards the isolated
  // selectedFlag() above; an integer attribute costs nothing worth measuring.
  const renders = useRef(0);
  renders.current += 1;
  return (
    <>
      <StarButton id={id} name={name} form={form} />
      <button
        type="button"
        class="dex-select"
        data-action="select"
        data-species={id}
        data-renders={renders.current}
        aria-current={selected}
        onClick={() => openPokemon(id, form)}
      >
        <PokemonIcon id={id} />
        <span class="dex-name">
          {String(id).padStart(3, "0")} · {name}
        </span>
        <CollectionFacts id={id} form={form} />
      </button>
      <StatusButton id={id} form={form} context="Pokédex" />
    </>
  );
});

// Rows mounted per animation frame. Creating all 807 in one render blocked a phone
// (4× CPU throttling) for about a second; chunks keep each frame short and put the
// first screen of rows up at once.
const ROW_CHUNK = 30;

export function Pokedex() {
  const query = normalize(searchTerm.value);
  const matches = (target: CollectionTarget) => matchesTarget(byDex.get(target.id)!, target, query);
  // Starred species are pinned to the top; everything else keeps National Dex
  // order. The sort is stable for equal ranks. Re-sorting all 807 entries is wasted
  // work on renders that only touch search or the sidebar, so it only recomputes
  // when the starred list itself changes.
  const rows = useMemo(() => collectionTargets(POKEMON, formsTracked.value).sort(
    (a, b) => Number(isStarred(b.id, b.form)) - Number(isStarred(a.id, a.form)) || a.id - b.id,
  ), [formsTracked.value, starred.value, starredForms.value]);
  const matchCount = query ? rows.filter(matches).length : rows.length;
  const open = drawerOpen.value;
  const mobile = isMobile.value;
  const hidden = mobile ? !open : sidebarHidden.value;
  // The Pokédex is a closed drawer on phones, so building rows before anyone has
  // opened it is wasted work. Mount the list in chunks the first time it is shown,
  // then keep every row: a search only hides rows, because rebuilding them when a
  // search is cleared cost as much as the first open.
  const [mountedRows, setMountedRows] = useState(hidden ? 0 : ROW_CHUNK);
  useEffect(() => {
    if ((hidden && !mountedRows) || mountedRows >= rows.length) return;
    const frame = requestAnimationFrame(() =>
      setMountedRows((count) => count + ROW_CHUNK),
    );
    return () => cancelAnimationFrame(frame);
  }, [hidden, mountedRows, rows.length]);
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
          <DexCount filtered={matchCount} total={rows.length} />
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
          <SelectionPanel />
          <div class="dex-list" id="dex-list">
            {rows.slice(0, mountedRows).map((target) => (
              <div class="dex-row" key={targetKey(target)} data-target={targetKey(target)} hidden={!matches(target)}>
                <DexRowContent id={target.id} form={target.form} name={targetName(byDex.get(target.id)!, target.form)} />
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
