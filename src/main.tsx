import { render } from "preact";
import { App } from "./App";
import { ATLAS } from "./data";
import { firstIncompleteLocation } from "./domain";
import {
  activeEncounters,
  focusedLocation,
  initializeState,
  mode,
  speciesStatus,
} from "./state";
import "./styles/themes.css";
import "./styles/app.css";
import "./styles/responsive.css";

initializeState();
document.documentElement.dataset.mode = mode.value;
document.documentElement.style.setProperty("--atlas", `url("${ATLAS.url}")`);
focusedLocation.value =
  firstIncompleteLocation(activeEncounters.value, speciesStatus)?.id || null;

render(<App />, document.getElementById("app")!);
