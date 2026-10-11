export const BALLS = [
  "Poké Ball",
  "Great Ball",
  "Ultra Ball",
  "Master Ball",
  "Premier Ball",
  "Luxury Ball",
  "Heal Ball",
  "Net Ball",
  "Nest Ball",
  "Dive Ball",
  "Repeat Ball",
  "Timer Ball",
  "Quick Ball",
  "Dusk Ball",
  "Fast Ball",
  "Level Ball",
  "Love Ball",
  "Lure Ball",
  "Heavy Ball",
  "Moon Ball",
  "Friend Ball",
  "Beast Ball",
];
export interface CaptureStats {
  catchRate: number;
  speed: number;
  weight: number;
  types: number[];
  gender: number;
}
export interface BallContext {
  turn: number;
  level: number;
  yourLevel: number;
  night: boolean;
  cave: boolean;
  fishing: boolean;
  surfing: boolean;
  registered: boolean;
  sameSpecies: boolean;
  oppositeGender: boolean;
}
export function ballModifiers(
  ball: string,
  p: CaptureStats & { id: number },
  c: BallContext,
  game: "sm" | "usum",
) {
  if (!BALLS.includes(ball)) throw new Error("Select a valid Gen VII ball.");
  if (!Number.isInteger(p.catchRate) || p.catchRate < 0 || p.catchRate > 255)
    throw new Error("Catch rate must be an integer from 0 to 255.");
  const numbers =
    ball === "Quick Ball" || ball === "Timer Ball"
      ? [c.turn]
      : ball === "Nest Ball"
        ? [c.level]
        : ball === "Level Ball"
          ? [c.level, c.yourLevel]
          : [];
  for (const n of numbers)
    if (!Number.isInteger(n) || n < 1)
      throw new Error("Use positive integer turns and levels.");
  if (
    (ball === "Nest Ball" || ball === "Level Ball") &&
    (c.level > 100 || (ball === "Level Ball" && c.yourLevel > 100))
  )
    throw new Error("Levels must be 1–100.");
  let rate = p.catchRate,
    bonus = 1;
  if (ball === "Heavy Ball")
    rate = Math.min(
      255,
      Math.max(
        game === "usum" ? 1 : 0,
        rate +
          (p.weight >= 3000
            ? 30
            : p.weight >= 2000
              ? 20
              : p.weight < 1000
                ? -20
                : 0),
      ),
    );
  const ub = (p.id >= 793 && p.id <= 799) || (p.id >= 803 && p.id <= 806);
  if (ub && ball !== "Beast Ball" && ball !== "Master Ball") bonus = 410 / 4096;
  else
    switch (ball) {
      case "Great Ball":
        bonus = 1.5;
        break;
      case "Ultra Ball":
        bonus = 2;
        break;
      case "Net Ball":
        bonus = p.types.some((t) => t === 10 || t === 6) ? 3.5 : 1;
        break;
      case "Nest Ball":
        bonus = c.level < 30 ? Math.max(1, (41 - c.level) / 10) : 1;
        break;
      case "Dive Ball":
        bonus = c.surfing || c.fishing ? 3.5 : 1;
        break;
      case "Repeat Ball":
        bonus = c.registered ? 3.5 : 1;
        break;
      case "Timer Ball":
        bonus = Math.min(4, 1 + ((c.turn - 1) * 1229) / 4096);
        break;
      case "Quick Ball":
        bonus = c.turn === 1 ? 5 : 1;
        break;
      case "Dusk Ball":
        bonus = c.night || c.cave ? 3 : 1;
        break;
      case "Fast Ball":
        bonus = p.speed >= 100 ? 4 : 1;
        break;
      case "Level Ball":
        bonus =
          c.yourLevel >= c.level * 4
            ? 8
            : c.yourLevel >= c.level * 2
              ? 4
              : c.yourLevel > c.level
                ? 2
                : 1;
        break;
      case "Love Ball":
        bonus =
          c.sameSpecies &&
          c.oppositeGender &&
          p.gender !== 255 &&
          p.gender !== 0 &&
          p.gender !== 254
            ? 8
            : 1;
        break;
      case "Lure Ball":
        bonus = c.fishing ? 5 : 1;
        break;
      case "Moon Ball":
        bonus = [30, 33, 35, 39, 300, 517].includes(p.id) ? 4 : 1;
        break;
      case "Beast Ball":
        bonus = ub ? 5 : 410 / 4096;
        break;
    }
  return { rate, bonus, master: ball === "Master Ball" };
}
export type Status = "none" | "slp" | "frz" | "par" | "psn" | "brn";
export const STATUS_BONUS: Record<Status, number> = {
  none: 1,
  slp: 2.5,
  frz: 2.5,
  par: 1.5,
  psn: 1.5,
  brn: 1.5,
};
export interface ProbabilityInput {
  catchRate: number;
  ballBonus: number;
  currentHP: number;
  maxHP: number;
  status: string;
  roto: boolean;
  caught: number;
  master?: boolean;
}
const down = (n: number) => Math.floor(n * 4096) / 4096;
const round = (n: number) => Math.floor(n * 4096 + 0.5) / 4096;
export function dexBonus(count: number) {
  return count > 600
    ? 2.5
    : count > 450
      ? 2
      : count > 300
        ? 1.5
        : count > 150
          ? 1
          : count > 30
            ? 0.5
            : 0;
}
export function probability(i: ProbabilityInput) {
  if (
    !Number.isInteger(i.currentHP) ||
    !Number.isInteger(i.maxHP) ||
    i.currentHP < 1 ||
    i.currentHP > i.maxHP ||
    i.maxHP > 65535 ||
    !Number.isInteger(i.catchRate) ||
    i.catchRate < 0 ||
    i.catchRate > 255 ||
    !Number.isInteger(i.caught) ||
    i.caught < 0 ||
    i.caught > 807 ||
    !Number.isFinite(i.ballBonus) ||
    i.ballBonus <= 0 ||
    !Object.hasOwn(STATUS_BONUS, i.status)
  )
    throw new Error("Enter legal HP, rate, status and historical count.");
  const statusBonus = STATUS_BONUS[i.status as Status];
  const x = Math.min(
    255,
    down(
      round(
        down(
          round(
            round(3 * i.maxHP - 2 * i.currentHP) * i.catchRate * i.ballBonus,
          ) /
            (3 * i.maxHP),
        ) * statusBonus,
      ) * (i.roto ? 2.5 : 1),
    ),
  );
  const b =
    x === 0
      ? 0
      : Math.floor(round(65536 / round(Math.pow(round(255 / x), 3 / 16))));
  const q = Math.min(1, b / 65536);
  const critical = Math.floor(round(round(x * dexBonus(i.caught)) / 6)) / 256;
  return {
    x,
    b,
    q,
    critical,
    ordinary: q ** 4,
    statusBonus,
    probability: i.master ? 1 : critical * q + (1 - critical) * q ** 4,
  };
}
