import { byDex } from "../data";
import { firstIncompleteLocation, uncaughtCatchNowRows } from "../domain";
import { activeEncounters, focusedLocation, speciesStatus } from "../state";
import { closeDrawer } from "../ui";
import { PokemonIcon, StatusButton } from "./StatusControls";

/**
 * The single question a checklist app exists to answer: what do I catch next?
 * Composed entirely from firstIncompleteLocation + catchNowRows (src/domain.ts),
 * which already drive the auto-open behaviour, so this adds no new data or state.
 * Shown as the Pokédex's default (no-selection) panel, since that is what a player
 * sees before picking anything — the header has no room to spare on phone, and the
 * location list already shows this same location open, just scrolled past.
 */
export function CatchNext() {
  const location = firstIncompleteLocation(activeEncounters.value, speciesStatus);
  if (!location) {
    return (
      <p class="catch-next-done">
        Every catch-now Pokémon in this mode is caught. Nice work!
      </p>
    );
  }
  const rows = uncaughtCatchNowRows(location, speciesStatus);
  return (
    <div class="catch-next">
      <strong>Catch next in {location.name}</strong>
      <ul>
        {rows.map((row) => {
          const name =
            row.speciesName || row.species || byDex.get(row.speciesId!)?.name || "Pokémon";
          return (
            <li key={row.id}>
              <PokemonIcon id={row.speciesId!} />
              <span class="catch-next-name">{name}</span>
              <StatusButton id={row.speciesId!} context="catch next" compact />
            </li>
          );
        })}
      </ul>
      <button
        type="button"
        class="catch-next-jump"
        onClick={() => {
          focusedLocation.value = location.id;
          closeDrawer();
        }}
      >
        Go to {location.name}
      </button>
    </div>
  );
}
