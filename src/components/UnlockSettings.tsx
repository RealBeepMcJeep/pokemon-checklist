import { mode, unlocks, setUnlock, readOnly } from "../state";
import { UNLOCKS } from "../types";
const labels = {tauros:"Tauros Charge",surfing:"Surfing",fishing:"Fishing",sos:"SOS Calls","weather-sos":"Weather SOS"};
export function UnlockSettings() {
  if (mode.value !== "photonic-prismatic") return null;
  return <fieldset class="unlock-settings"><legend>Encounter unlocks</legend>
    <p>Saved with your checklist. Enable the abilities and hunts you can use.</p>
    {UNLOCKS.map(flag => <label key={flag}><input type="checkbox" autocomplete="off" checked={unlocks.value.includes(flag)} disabled={!!readOnly.value}
      onChange={event => setUnlock(flag,event.currentTarget.checked)} />{labels[flag]}</label>)}
    <small>Weather SOS also needs SOS Calls; rain/hail/sand conditions still apply. Other story-only restrictions remain unchanged.</small>
  </fieldset>;
}
