import { render } from "preact";
import { App } from "./App";
import { firstIncompleteLocation } from "./domain";
import {
  activeEncounters,
  focusedLocation,
  initializeState,
  mode,
  speciesStatus,
  watchOtherTabs,
} from "./state";
import "./styles/themes.css";
import "./styles/app.css";
import "./styles/responsive.css";

initializeState();
watchOtherTabs();
document.documentElement.dataset.mode = mode.value;
focusedLocation.value =
  firstIncompleteLocation(activeEncounters.value, speciesStatus)?.id || null;

render(<App />, document.getElementById("app")!);
