import graphJson from "../data/evolutions.json";
import type { CollectionTarget } from "./collection";
import { isRegional } from "./regional";
import type { RegionalForm } from "./regional";
import type { GameMode } from "./types";

interface Node extends CollectionTarget { name: string }
interface Edge { from: string; to: string; stock: string; prismatic?: string; conditions?: Partial<Record<GameMode, string>> }
const graph = graphJson as { nodes: Record<string, Node>; edges: Edge[] };
export interface EvolutionStage extends CollectionTarget { key: string; name: string; methods: string[] }

/** Project a connected evolution family; stages are collection identities, not writes. */
export function evolutionFamily(target: CollectionTarget, mode: GameMode, tracking: boolean): EvolutionStage[] {
  const preferred: RegionalForm | undefined = tracking ? target.form : "alolan";
  const root = isRegional(target.id) ? `${target.id}:${preferred ?? "alolan"}` : String(target.id);
  if (!graph.nodes[root]) return [];
  const keys = new Set([root]);
  const queue = [root];
  for (const key of queue) {
    for (const edge of graph.edges) {
      const adjacent = edge.from === key ? edge.to : edge.to === key ? edge.from : undefined;
      if (adjacent && (!preferred || !graph.nodes[adjacent].form || graph.nodes[adjacent].form === preferred) && !keys.has(adjacent)) { keys.add(adjacent); queue.push(adjacent); }
    }
  }
  const ordered = new Set<string>();
  const visit = (key: string): void => {
    if (ordered.has(key)) return;
    for (const edge of graph.edges) if (edge.to === key && keys.has(edge.from)) visit(edge.from);
    ordered.add(key);
  };
  [...keys].sort((a, b) => graph.nodes[a].id - graph.nodes[b].id || a.localeCompare(b)).forEach(visit);
  return [...ordered].map(key => ({
    ...graph.nodes[key],
    form: tracking ? graph.nodes[key].form : undefined,
    name: tracking ? graph.nodes[key].name : graph.nodes[key].name.replace(/ \((Alolan|Kanto)\)$/, ""),
    key: tracking ? key : String(graph.nodes[key].id), methods: graph.edges.filter(edge => edge.to === key).map(edge => {
      const method = mode === "photonic-prismatic" ? edge.prismatic ?? edge.stock : edge.stock;
      return edge.conditions?.[mode] ? `${method}. ${edge.conditions[mode]}` : method;
    }),
  }));
}
