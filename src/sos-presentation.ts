import type { GuideSosNode } from "./unlocks";

/** Presentation only: group sibling weather rules at ONE actual caller anchor.
 * Keep every rule object; differing identity/access and descendant chains stay separate. */
export function groupWeatherNodes(nodes: readonly GuideSosNode[]): GuideSosNode[][] {
  const groups: GuideSosNode[][] = [], weather = new Map<string, GuideSosNode[]>();
  for (const node of nodes) {
    if (node.call.kind !== "weather-sos" || node.children.length) { groups.push([node]); continue; }
    const r = node.call.row;
    const key = JSON.stringify([r.speciesId, r.speciesName, r.species, r.form, r.ability, node.eligible]);
    const existing = weather.get(key);
    if (existing) existing.push(node);
    else { const group = [node]; weather.set(key, group); groups.push(group); }
  }
  return groups;
}

/** Only known duplicate classification prose is hidden; source data is untouched. */
export function sosConditions(node: GuideSosNode): string[] {
  const values = [...new Set([...(node.call.group.conditions || []), ...(node.call.sourceRow.conditions || [])])];
  if (node.call.kind !== "weather-sos") return values;
  const explicitRain = values.some(value => /^(During rain|Rain)$/i.test(value));
  return values.filter(value => value !== "Appears as an SOS ally; the caller depends on the encounter."
    && value !== "Weather-dependent SOS encounter."
    && !(explicitRain && value === "SOS encounter while it is raining."));
}
