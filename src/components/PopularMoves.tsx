import { MOVES, byDex } from "../data";
import {
  describeRoute,
  moveInfo,
  movesFinals,
  shownRoutes,
  statsTier,
} from "../moves";
import { mode } from "../state";
import { TypeMarks } from "./PokemonFacts";

function FinalMoves({ final, heading }: { final: number; heading: boolean }) {
  const entry = MOVES.finals[final];
  const name = byDex.get(final)?.name ?? `#${final}`;
  const currentMode = mode.value;
  return (
    <section class="final-moves">
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
            return (
              <li key={`${row.move}:${info.name}`}>
                <span class="move-line">
                  <strong>{info.name}</strong>
                  <TypeMarks types={[info.type]} />
                  {info.power !== undefined && (
                    <span class="muted">{info.power} power</span>
                  )}
                  <span class="move-usage">{Math.round(row.usage)}%</span>
                </span>
                <span class={`move-routes ${row.how.length ? "" : "unavailable"}`}>
                  {row.how.length
                    ? shownRoutes(row.how, final)
                        .map((route) =>
                          describeRoute(route, info, final, currentMode),
                        )
                        .join(" · ")
                    : "Not obtainable in Gen 7"}
                </span>
              </li>
            );
          })}
        </ol>
      ) : (
        <p class="muted">
          No competitive usage data lists {name}, so there is nothing to rank.
        </p>
      )}
    </section>
  );
}

/**
 * The moves competitive players ran most, for a species or the final evolutions it
 * grows into. Collapsed by default so the sticky selection stays short; the browser
 * keeps it open across selections once a player opens it.
 */
export function PopularMoves({ id }: { id: number }) {
  const finals = movesFinals(id);
  if (!finals.length) return null;
  const own = finals.length === 1 && finals[0] === id;
  const ownStats = own ? MOVES.finals[id].stats : null;
  const summary = own
    ? `Popular moves${ownStats ? ` (${statsTier(ownStats)})` : ""}`
    : finals.length === 1
      ? `Popular moves of ${byDex.get(finals[0])?.name}`
      : `Popular moves of its ${finals.length} final evolutions`;
  return (
    <details class="popular-moves">
      <summary>{summary}</summary>
      {finals.map((final) => (
        <FinalMoves key={final} final={final} heading={!own} />
      ))}
      <p class="muted moves-source">
        Percent of competitive sets running each move, from Smogon's Gen 7
        statistics for November 2019. Learnsets are standard Gen 7.
      </p>
    </details>
  );
}
