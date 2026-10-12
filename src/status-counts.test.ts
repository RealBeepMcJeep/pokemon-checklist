import { beforeEach, expect, it } from "vitest";
import * as state from "./state";
import { catchNowRows, firstIncompleteLocation, locationProgress } from "./domain";
import { ENCOUNTERS_BY_MODE } from "./data";
import type { Location } from "./types";

beforeEach(() => state.applyState(state.defaultState()));
it("derives forms only for the active mode and reacts to restore and settings", () => {
  expect(state).toHaveProperty("formCounts");
  state.mode.value = "sun";
  const keys = [...state.activeFormDefinitions.value.keys()];
  const excluded = [...state.formDefinitions.keys()].find(key => !keys.includes(key))!;
  state.formSignal(keys[0]).value = "caught";
  state.formSignal(keys[1]).value = "seen";
  state.formSignal(excluded).value = "caught";
  expect(state.formCounts.value).toEqual({none:keys.length-2,seen:1,caught:1});
  state.formsTracked.value = true;
  const saved = state.exportState();
  state.applyState(state.defaultState());
  expect(state.formCounts.value).toEqual({none:48,seen:0,caught:0});
  state.applyState(saved);
  expect(state.formCounts.value).toEqual({none:keys.length-2,seen:1,caught:1});
  state.formsTracked.value = false;
  expect(state.formCounts.value).toEqual({none:keys.length-2,seen:1,caught:1});
  state.mode.value = "photonic-prismatic";
  expect(state.formCounts.value.none+state.formCounts.value.seen+state.formCounts.value.caught).toBe(state.activeFormDefinitions.value.size);
});
it("derives exclusive global species counts without changing the save", () => {
  const save = state.exportState();
  expect(state).toHaveProperty("speciesCounts");
  expect(state.speciesCounts.value).toEqual({none:807,seen:0,caught:0});
  for (const [status,counts] of [["caught",{none:806,seen:0,caught:1}],["seen",{none:806,seen:1,caught:0}],["none",{none:807,seen:0,caught:0}]] as const) {
    state.speciesSignal(731).value = status;
    expect(state.speciesCounts.value).toEqual(counts);
  }
  expect(state.exportState()).toEqual(save);
});
it("partitions duplicate regular rows but excludes return-later and SOS allies", () => {
  const original = ENCOUNTERS_BY_MODE.sun.islands[0].locations[0];
  const row = catchNowRows(original)[0];
  const location: Location = {...original, groups:[{...original.groups[0], category:"regular", encounters:[row,row]},{...original.groups[0], category:"return-later", encounters:[{...row,speciesId:807}]}]};
  expect(locationProgress(location,()=>"seen")).toEqual({none:0,seen:1,caught:0,total:1});
  expect(firstIncompleteLocation({...ENCOUNTERS_BY_MODE.sun,islands:[{...ENCOUNTERS_BY_MODE.sun.islands[0],locations:[location]}]},()=>"seen")).toBe(location);
  expect(locationProgress({...location,groups:[]},()=>"none")).toEqual({none:0,seen:0,caught:0,total:0});
});
