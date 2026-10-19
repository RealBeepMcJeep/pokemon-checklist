import { evolutionFamily } from "../evolutions";
import { encounterViewContext } from "../encounter-names";
import { formsTracked, mode } from "../state";
import { openPokemon } from "../ui";
import type { CollectionTarget } from "../collection";
import { StatusButton } from "./StatusControls";

export function EvolutionControls({ target }: { target: CollectionTarget }) {
  // Explicit encounter/stage identity wins over collapsed collection browsing.
  const tracking = formsTracked.value || !!target.form;
  const activeMode = mode.value;
  const stages = evolutionFamily(target, activeMode, tracking);
  if (stages.length < 2) return null;
  const rows = <>
    <p class="muted evolution-source">{activeMode === "photonic-prismatic"
      ? "Prismatic Moon Standard changes where documented; otherwise stock Gen VII rules."
      : "Stock Gen VII evolution rules for this game."}</p>
    <ol class="evolution-stages" aria-label="Evolution stages with independent ownership">
      {stages.map(stage => <li class="evolution-stage" data-target={stage.key} key={stage.key}>
        <button type="button" class="evolution-name" aria-current={stage.id === target.id && (!tracking || stage.form === target.form || (!target.form && stage.form === "alolan")) ? "true" : "false"}
          onClick={() => openPokemon(stage.id, stage.form, encounterViewContext({ speciesId: stage.id, speciesName: stage.name, form: stage.form }, stage.name))}>{stage.name}</button>
        <StatusButton id={stage.id} form={stage.form} context="evolution stage" />
        {stage.methods.map(method => <span class="evolution-method" key={method}>{method}</span>)}
      </li>)}
    </ol>
  </>;
  return <section class="evolution-controls" aria-label="Evolution family">
    {stages.length > 4 ? <details><summary>Evolution family ({stages.length} stages)</summary>{rows}</details>
      : <><h3>Evolution family</h3>{rows}</>}
  </section>;
}
