import { MOVES, byDex } from "./data";
import type { GameMode, MoveInfo, MoveRoute, PopularMove } from "./types";

/** The final evolutions whose popular moves apply to a species: itself, or its evolutions. */
export function movesFinals(id: number): number[] {
  return MOVES.finals[id] ? [id] : (MOVES.lines[id] ?? []);
}

export function moveInfo(row: PopularMove): MoveInfo {
  const info = MOVES.moves[row.move];
  // A move missing from the table (a stale/mistyped name from a future data build)
  // degrades to a visibly labeled entry instead of crashing the whole Pokédex panel.
  if (!info) return { name: row.name ?? row.move, type: row.type ?? "?" };
  return {
    ...info,
    name: row.name ?? info.name,
    type: row.type ?? info.type,
  };
}

/**
 * The routes worth showing, easiest first in the data's own order. The final's own
 * level-up hides its pre-evolutions' (else only the earliest one stays), and an event is
 * mentioned only when nothing else teaches the move.
 */
export function shownRoutes(how: MoveRoute[], final: number): MoveRoute[] {
  const levels = how.filter((route) => route.via === "level");
  const keep =
    levels.find((route) => route.form === final) ??
    levels.reduce<MoveRoute | undefined>(
      (best, route) => (!best || route.level! < best.level! ? route : best),
      undefined,
    );
  const others = how.some((route) => route.via !== "event");
  return how.filter((route) =>
    route.via === "level" ? route === keep : route.via !== "event" || !others,
  );
}

/** "gen7ru-1630" -> "RU", "gen7ubers-1630" -> "Ubers". */
export function statsTier(stats: string): string {
  const tier = /^gen7([a-z]+)-/.exec(stats)?.[1] ?? stats;
  return tier === "ubers" ? "Ubers" : tier.toUpperCase();
}

const nameOf = (id: number): string => byDex.get(id)?.name ?? `#${id}`;

/**
 * One way of learning a move, in plain words. The data holds facts; the wording is
 * chosen here so a game mode can phrase the same fact its own way.
 */
export function describeRoute(
  route: MoveRoute,
  info: MoveInfo,
  final: number,
  mode: GameMode,
): string {
  const other = route.form !== undefined && route.form !== final;
  let text: string;
  switch (route.via) {
    case "level":
      text = other
        ? `${nameOf(route.form!)} at level ${route.level}`
        : `Level ${route.level}`;
      break;
    case "reminder":
      text = "Move Reminder";
      break;
    case "TM":
      text = info.tm
        ? `TM${String(info.tm).padStart(2, "0")}${info.tmAt ? ` · ${info.tmAt}` : ""}`
        : "TM";
      break;
    case "tutor":
      text = [
        "Tutor",
        info.tutorAt,
        info.tutorBp === undefined ? "" : `${info.tutorBp} BP`,
      ]
        .filter(Boolean)
        .join(" · ");
      break;
    case "egg": {
      // Photonic Sun / Prismatic Moon teach egg moves by level-up; the source gives no level.
      const on = other ? ` on ${nameOf(route.form!)}` : "";
      text =
        mode === "photonic-prismatic"
          ? `Egg move${on}; this hack teaches it by level-up`
          : `Egg move${on} (breed for it)`;
      break;
    }
    case "event":
      text = "Event only";
      break;
  }
  if (other && route.via !== "level" && route.via !== "egg") {
    text += ` (${nameOf(route.form!)})`;
  }
  // Egg moves are always a pre-evolution's; the prefix would say nothing new.
  return route.beforeEvolving && route.via !== "egg"
    ? `Before evolving: ${text}`
    : text;
}
