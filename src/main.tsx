import { render } from "preact";
import { App } from "./App";
import { followSignInFromOtherTabs, watchSyncAccount } from "./sync/engine";
import { claimDeviceEditing } from "./editing";
import { availableStorage, syncSessionExpected } from "./sync/outbox";
import { firstIncompleteLocation } from "./domain";
import {
  activeEncounters,
  announceBuild,
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
// Any older build still open in another tab stops editing when this one arrives.
announceBuild();
// One tab edits this device's checklist; any other open tab only follows it.
claimDeviceEditing();
// Sign-in is what turns sync on. Auth is initialised on load only when this device
// has signed in before: Firebase Auth fetches its sign-in iframe and GAPI helper on
// mobile user agents even for a signed-out visitor, so watching auth eagerly would
// break the promise that an offline-only player's device never talks to anyone. The
// sign-in control calls watchSyncAccount() when someone actually chooses to sign in.
if (syncSessionExpected(availableStorage())) watchSyncAccount();
followSignInFromOtherTabs();
document.documentElement.dataset.mode = mode.value;
focusedLocation.value =
  firstIncompleteLocation(activeEncounters.value, speciesStatus)?.id || null;

render(<App />, document.getElementById("app")!);
