import { MOVES, byDex } from "./data";
import type { GameMode, MoveInfo, MoveRoute, MoveTarget, PopularMove } from "./types";
import { isRegional, type RegionalForm } from "./regional";

/** The final evolutions whose popular moves apply to a species: itself, or its evolutions. */
export function movesFinals(id: number, form?: RegionalForm, tracking = false): MoveTarget[] {
  const key = isRegional(id) ? `${id}:${form ?? "alolan"}` : String(id);
  if (MOVES.finals[key]) return [isRegional(id) ? key : id];
  return (MOVES.lines[key] ?? []).flatMap(target => {
    if (typeof target === "number" && isRegional(target)) {
      return tracking ? [`${target}:alolan`, `${target}:kanto`] : [`${target}:alolan`];
    }
    return [target];
  });
}

export function routesForMode(row: PopularMove, mode: GameMode): MoveRoute[] {
  const profile = mode === "photonic-prismatic" ? "prismatic"
    : mode === "sun" || mode === "moon" ? "sm" : "usum";
  return row.profiles?.[profile] ?? [];
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
export function shownRoutes(how: MoveRoute[], final: MoveTarget): MoveRoute[] {
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
  ).sort((a, b) => Number(a.via === "reminder") - Number(b.via === "reminder"));
}

/** "gen7ru-1630" -> "RU", "gen7ubers-1630" -> "Ubers". */
export function statsTier(stats: string): string {
  const tier = /^gen7([a-z]+)-/.exec(stats)?.[1] ?? stats;
  return tier === "ubers" ? "Ubers" : tier.toUpperCase();
}

export function moveTargetName(target: MoveTarget, showForms = true): string {
  const [raw, form] = String(target).split(":");
  const name = byDex.get(Number(raw))?.name ?? `#${raw}`;
  return showForms && (form === "alolan" || form === "kanto")
    ? `${name} (${form === "alolan" ? "Alolan" : "Kanto"})` : name;
}

/**
 * One way of learning a move, in plain words. The data holds facts; the wording is
 * chosen here so a game mode can phrase the same fact its own way.
 */
export function describeRoute(
  route: MoveRoute,
  info: MoveInfo,
  final: MoveTarget,
  mode: GameMode,
  showForms = true,
): string {
  const other = route.form !== undefined && route.form !== final;
  let text: string;
  switch (route.via) {
    case "level":
      text = other
        ? `${moveTargetName(route.form!, showForms)} at level ${route.level}`
        : `Level ${route.level}`;
      break;
    case "reminder":
      text = "Move Reminder";
      break;
    case "TM": {
      const number = route.tm ?? info.tm;
      // Legacy placement is not version-scoped. New native routes show only a
      // documented profile-specific location, rather than borrowing USUM's.
      const at = route.at ?? (route.tm === undefined ? info.tmAt : undefined);
      text = number ? `TM${String(number).padStart(2, "0")}${at ? ` · ${at}` : ""}` : "TM";
      break;
    }
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
      const on = other ? ` on ${moveTargetName(route.form!, showForms)}` : "";
      // Standard's verified levels are separate routes, not inferred from an egg flag.
      text = `Egg move${on} (breed for it)`;
      break;
    }
    case "event":
      text = "Event only";
      break;
    case "evolution":
      text = "On evolution";
      break;
    case "special":
      text = route.note ?? "Special learning method";
      break;
  }
  if (other && route.via !== "level" && route.via !== "egg") {
    text += ` (${moveTargetName(route.form!, showForms)})`;
  }
  if (route.note && route.via !== "special") text += ` · ${route.note}`;
  // Egg routes already name the required breeding stage.
  return route.beforeEvolving && route.via !== "egg"
    ? `Before evolving: ${text}`
    : text;
}
