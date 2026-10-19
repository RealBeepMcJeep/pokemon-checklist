import { byDex } from "../data";
import { encounterName } from "../encounter-names";
import { encounterRegionalForm } from "../regional";
import { firstIncompleteLocation, uncaughtCatchNowRows } from "../domain";
import { activeEncounters,
 activeUnlocks, focusedLocation, speciesStatus, formsTracked, formStatus } from "../state";
import { closeDrawer, isMobile } from "../ui";
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
  const formStatusOf = formsTracked.value ? formStatus : undefined;
  const location = firstIncompleteLocation(activeEncounters.value, speciesStatus, activeUnlocks.value, formStatusOf);
  if (!location) {
    return (
      <p class="catch-next-done">
        Every catch-now Pokémon in this mode is caught. Nice work!
      </p>
    );
  }
  const rows = uncaughtCatchNowRows(location, speciesStatus, activeUnlocks.value, formStatusOf);
  return (
    <details class="catch-next" open={!isMobile.value}>
      <summary><strong>Catch next in {location.name}</strong></summary>
      <ul>
        {rows.map((row) => {
          const name = encounterName(row, byDex.get(row.speciesId!)?.name);
          // Different SOS targets can share their caller's source-row ID.
          return (
            <li key={`${row.id}:${row.speciesId}:${row.form || ""}`}>
              <PokemonIcon id={row.speciesId!} />
              <span class="catch-next-name">{name}</span>
              <StatusButton id={row.speciesId!} form={encounterRegionalForm(row.speciesId!, row.form)} context="catch next" compact />
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
    </details>
  );
}
