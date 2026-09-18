import { render } from "preact";
import { App } from "./App";
import { watchSyncAccount } from "./sync/engine";
import { syncSessionExpected } from "./sync/outbox";
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
// Sign-in is what turns sync on. Auth is initialised on load only when this device
// has signed in before: Firebase Auth fetches its sign-in iframe and GAPI helper on
// mobile user agents even for a signed-out visitor, so watching auth eagerly would
// break the promise that an offline-only player's device never talks to anyone. The
// sign-in control calls watchSyncAccount() when someone actually chooses to sign in.
if (syncSessionExpected(localStorage)) watchSyncAccount();
document.documentElement.dataset.mode = mode.value;
focusedLocation.value =
  firstIncompleteLocation(activeEncounters.value, speciesStatus)?.id || null;

render(<App />, document.getElementById("app")!);
