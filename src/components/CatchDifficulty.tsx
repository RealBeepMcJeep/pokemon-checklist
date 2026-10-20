import { mode } from "../state";
import { CATCH_SCALE, resolveCatchDifficulty } from "../catch-difficulty";

type Props = { id: number; form?: string | number; onInspect?: () => void };
export function CatchBadge({ id, form, onInspect }: Props) {
  const value = resolveCatchDifficulty(id, mode.value, form);
  const caption = `Catch ${value.tier ?? "—"}`;
  const accessible = `${caption}; stock base catch rate ${value.rate ?? "unavailable"}. F easiest, S hardest; not a battle probability.`;
  const badge = <span class="catch-badge" role="img" aria-label={accessible} title={accessible} data-catch-rate={value.rate ?? "unknown"} data-catch-profile={value.profile ?? "unknown"}>{caption}</span>;
  return onInspect ? <button class="catch-badge-action" type="button" aria-label={`${accessible} Open catch details.`} onClick={event => { event.stopPropagation(); onInspect(); }}>{badge}</button> : badge;
}

export function CatchInfo({ id, form }: Props) {
  const value = resolveCatchDifficulty(id, mode.value, form);
  return <section class="catch-info" aria-label="Intrinsic catch difficulty">
    <p>{value.rate === null ? "Stock catch rate is unavailable for this exact form/profile; no tier is guessed." : `Stock base catch rate: ${value.rate}.`} {value.profile === "sm" ? "Sun/Moon" : value.profile === "usum" ? "Ultra Sun/Ultra Moon" : "Unknown game"}{value.sourceName ? ` · ${value.sourceName}` : ""}.</p>
    {value.stockFallback && <p class="catch-stock-note">Prismatic Moon: stock USUM fallback, as in the calculator. Hack catch-rate overrides and engine equivalence are unverified.</p>}
    <details class="catch-legend">
      <summary>Catch scale and limitations</summary>
      <p>F easiest → D → C → B → A → S hardest. These app-specific intrinsic tiers use the base constant, not a percentage or actual battle catch chance.</p>
      <ul>{CATCH_SCALE.map(band => <li key={band.tier}>{band.tier}: {band.min}–{band.max}</li>)}</ul>
      <p>Separate from competitive grades, encounter rarity and SOS odds. HP, status, ball and turn modifiers belong in Tools → Catch calculator. Ultra Beasts have special Beast Ball rules. A badge does not establish a wild acquisition route; zero or missing rates receive no tier.</p>
    </details>
  </section>;
}
