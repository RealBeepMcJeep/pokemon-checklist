import { useEffect } from "preact/hooks";
import { POKEMON, byDex } from "../data";
import { getOccurrences, normalize, safeId } from "../domain";
import {
  activeEncounters,
  caughtCount,
  drawerOpen,
  formDefinitions,
  formsTracked,
  searchTerm,
  seenCount,
  selectedDex,
  sidebarHidden,
} from "../state";
import { DRAWER_BREAKPOINT, closeDrawer, jumpTo } from "../ui";
import { FormStatusButton, PokemonIcon, StatusButton } from "./StatusControls";

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
        Select a Pokémon to see its status and wild locations.
      </div>
    );
  }
  const pokemon = byDex.get(selected);
  if (!pokemon) return null;
  const occurrences = getOccurrences(activeEncounters.value, selected);
  const forms = [...formDefinitions.values()].filter(
    (form) => form.speciesId === selected,
  );
  return (
    <>
      <div class="selected-title">
        <PokemonIcon id={selected} />
        <span>
          #{String(selected).padStart(3, "0")} {pokemon.name}
        </span>
        <StatusButton id={selected} context="selected" />
      </div>
      {formsTracked.value && forms.length > 0 && (
        <div class="form-summary">
          <strong>Tracked forms (separate from location progress)</strong>
          <div class="form-list">
            {forms.map((form) => (
              <FormStatusButton key={form.key} formKey={form.key} />
            ))}
          </div>
        </div>
      )}
      <div class="location-links">
        <strong>
          {occurrences.length
            ? `Known places in this mode (${occurrences.length})`
            : "No direct wild location in this mode"}
        </strong>
        {occurrences.length ? (
          <ul>
            {occurrences.map((item, index) => {
              const href = `#encounter-${safeId(item.row.id)}`;
              return (
                <li key={`${href}:${index}`}>
                  <a
                    href={href}
                    onClick={(event) => {
                      event.preventDefault();
                      jumpTo(href);
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
        ) : (
          <p class="muted">The source does not include evolution paths.</p>
        )}
      </div>
    </>
  );
}

function DexRow({ id, name }: { id: number; name: string }) {
  const selected = selectedDex.value === id;
  return (
    <div class="dex-row">
      <button
        type="button"
        class="dex-select"
        data-action="select"
        data-species={id}
        aria-current={selected}
        onClick={() => {
          selectedDex.value = id;
          requestAnimationFrame(() => {
            document.querySelector<HTMLElement>("#dex-selection")?.focus({
              preventScroll: true,
            });
          });
        }}
      >
        <PokemonIcon id={id} />
        <span class="dex-name">
          {String(id).padStart(3, "0")} · {name}
        </span>
      </button>
      <StatusButton id={id} context="Pokédex" />
    </div>
  );
}

export function Pokedex() {
  const query = normalize(searchTerm.value);
  const filtered = POKEMON.filter(
    (pokemon) =>
      !query ||
      normalize(pokemon.name).includes(query) ||
      String(pokemon.id).padStart(3, "0").includes(query) ||
      String(pokemon.id) === query,
  );
  const open = drawerOpen.value;
  const mobile = window.innerWidth < DRAWER_BREAKPOINT;
  const hidden = mobile ? !open : sidebarHidden.value;
  useEffect(() => {
    if (open) {
      requestAnimationFrame(() =>
        document.querySelector<HTMLInputElement>("#dex-search")?.focus(),
      );
    }
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
          <DexCount filtered={filtered.length} />
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
            {filtered.length ? (
              filtered.map((pokemon) => (
                <DexRow key={pokemon.id} id={pokemon.id} name={pokemon.name} />
              ))
            ) : (
              <div class="empty">No Pokémon match that search.</div>
            )}
          </div>
        </div>
      </aside>
    </>
  );
}
