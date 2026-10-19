import { MOVES } from "../data";
import { MODE_LABELS } from "../domain";
import {
  describeRoute, moveInfo, movesFinals, moveTargetName,
  routesForMode, shownRoutes, statsTier,
} from "../moves";
import { formsTracked, mode } from "../state";
import type { RegionalForm } from "../regional";
import type { MoveTarget } from "../types";
import { TypeMarks } from "./PokemonFacts";

function FinalMoves({ final, heading }: { final: MoveTarget; heading: boolean }) {
  const entry = MOVES.finals[final];
  const name = moveTargetName(final, formsTracked.value);
  const currentMode = mode.value;
  if (!entry) return <p class="muted">Verified move information is unavailable for {name}.</p>;
  return (
    <section class="final-moves" data-target={final}>
      {heading && (
        <h3>
          {name}
          {entry.stats && <span class="muted"> · {statsTier(entry.stats)}</span>}
        </h3>
      )}
      {entry.moves.length ? (
        <ol>
          {entry.moves.map((row) => {
            const info = moveInfo(row);
            const routes = routesForMode(row, currentMode);
            return (
              <li key={`${row.move}:${info.name}`} data-move={row.move}>
                <span class="move-line">
                  <strong>{info.name}</strong>
                  <TypeMarks types={[info.type]} />
                  {info.power !== undefined && <span class="muted">{info.power} power</span>}
                  <span class="move-usage">{Math.round(row.usage)}%</span>
                </span>
                <span class={`move-routes ${routes.length ? "" : "unavailable"}`}>
                  {routes.length
                    ? shownRoutes(routes, final)
                        .map(route => describeRoute(route, info, final, currentMode, formsTracked.value))
                        .join(" · ")
                    : `No verified native learning route in ${MODE_LABELS[currentMode]}`}
                </span>
              </li>
            );
          })}
        </ol>
      ) : (
        <p class="muted">No competitive usage data lists {name}, so there is nothing to rank.</p>
      )}
    </section>
  );
}

/** Competitive suggestions, not the full learnset browser (which remains deferred). */
export function PopularMoves({ id, form }: { id: number; form?: RegionalForm }) {
  const tracking = formsTracked.value;
  const finals = movesFinals(id, form, tracking);
  if (!finals.length) return null;
  const ownKey = form ? `${id}:${form}` : String(id);
  const own = finals.length === 1 && (
    String(finals[0]) === ownKey || (!tracking && Number(String(finals[0]).split(":")[0]) === id)
  );
  const ownStats = own ? MOVES.finals[finals[0]]?.stats : null;
  const summary = own
    ? `Popular moves${ownStats ? ` (${statsTier(ownStats)})` : ""}`
    : finals.length === 1
      ? `Popular moves of ${moveTargetName(finals[0], tracking)}`
      : `Popular moves of its ${finals.length} final evolutions`;
  return (
    <details class="popular-moves">
      <summary>{summary}</summary>
      {finals.map(final => <FinalMoves key={final} final={final} heading={!own} />)}
      <p class="muted moves-source">
        Competitive usage: Smogon Gen 7, November 2019; percentages are not encounter or catch rates.
        {mode.value === "photonic-prismatic"
          ? " Prismatic Moon Standard: verified creator level-ups and documented specialist-mart locations; other methods use stock USUM. Rebalanced-only TM edits are excluded."
          : ` Learning routes: ${MODE_LABELS[mode.value]}.`}
        {" "}TM locations are shown only when verified for this profile. An unlisted native route does not rule out events or transfers.
      </p>
    </details>
  );
}
