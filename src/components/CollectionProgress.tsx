import { computed, signal } from "@preact/signals";
import { POKEMON } from "../data";
import { formStatus, formsTracked, speciesStatus } from "../state";
import { REGIONAL_DETAILS } from "../regional";
import { countProgress, defaultProgressMetric, isProgressMetric, readProgressPreference, writeProgressPreference, type ProgressMetric } from "../progress";

const preference = signal(readProgressPreference());
const preferenceError = signal("");
export const progressMetric = computed(() => preference.value ?? defaultProgressMetric(formsTracked.value));
export const progressCounts = computed(() => countProgress(POKEMON,
  Object.fromEntries(POKEMON.map(row => [String(row.id), speciesStatus(row.id)])),
  Object.fromEntries(Object.keys(REGIONAL_DETAILS).map(key => [key, formStatus(key)])), formsTracked.value));
const labels: Record<ProgressMetric, string> = { registered: "Registered species", owned: "National Dex owned", living: "Living Dex owned" };

export function selectProgressMetric(value: unknown): void {
  if (!isProgressMetric(value)) return;
  preference.value = value;
  preferenceError.value = writeProgressPreference(value) ? "" : "Display preference could not be remembered on this device. Player progress is unchanged.";
}

export function ProgressHeadline() {
  const metric = progressMetric.value;
  const count = progressCounts.value[metric];
  return <div class="collection-headline" data-progress-metric={metric}>
    <label id="progress-label" for="overall-progress">{labels[metric]}</label>
    <span id="overall-text">{count.value} / {count.max}</span>
    <progress id="overall-progress" aria-label={labels[metric]} max={count.max} value={count.value} />
  </div>;
}

export function ProgressSettings() {
  const counts = progressCounts.value;
  return <section class="progress-settings" aria-labelledby="progress-settings-title">
    <h3 id="progress-settings-title">Collection progress</h3>
    <label for="progress-metric">Headline progress</label>
    <select id="progress-metric" value={progressMetric.value} onChange={event => selectProgressMetric(event.currentTarget.value)} aria-describedby="progress-explanation">
      {(Object.keys(labels) as ProgressMetric[]).map(metric => <option value={metric} key={metric}>{labels[metric]}</option>)}
    </select>
    <p id="progress-explanation">Registered includes Seen or Caught species. Owned means currently owned. Living counts Alolan and Kanto separately with tracking on; with No forms, both Owned totals coincide. This display choice stays on this device, outside backups and account sync.</p>
    <dl>{(Object.keys(labels) as ProgressMetric[]).map(metric => <div key={metric} data-progress-stat={metric}><dt>{labels[metric]}</dt><dd>{counts[metric].value} / {counts[metric].max}</dd></div>)}</dl>
    {preferenceError.value && <p role="status" class="preference-error">{preferenceError.value}</p>}
  </section>;
}
